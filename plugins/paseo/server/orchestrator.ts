// memSharing Paseo plugin — server-side orchestration over the real Python
// CLIs. This layer owns NO business policy: every write goes through
// scripts/install.py / scripts/agm.py with their exact-plan approvals, and
// every read goes through the same kernels. The plugin only prepares
// inputs, surfaces exact plans for host-side confirmation, and binds the
// user's confirm action to the plan digest it displayed.

import fs from "node:fs";
import { randomUUID, createHash } from "node:crypto";
import { hostname } from "node:os";
import path from "node:path";
import { CORE_RELEASE_MANIFEST_SHA256 } from "./shared/release-identity";
import { ensureRealDirectory } from "./owned-paths";
import { ckAcquisitionPlan, ckDestination, acquireCkSource } from "./ck-source";
import { runProcess } from "./shared/common/process";
import { parseCliJson, classifyExitCode } from "./shared/common/json";
import { planDigest, buildEvidence, buildApproval, isSha256Hex } from "./shared/common/digest";
import { productPaths } from "./shared/common/paths";
import type { PythonEnvironment } from "./shared/common/python";
import type { GitEnvironment } from "./shared/common/git";
import { probePythonEnvironment } from "./shared/common/python";
import { probeGitEnvironment } from "./shared/common/git";

export type FlowKind = "bootstrap" | "machine" | "enable" | "remove" | "ck" | "recover";

export interface CliRunOutcome {
  kind: "completed" | "timeout" | "canceled" | "spawn_error";
  exitCode?: number;
  stdout?: string;
  stderr?: string;
  message?: string;
}

export interface Runner {
  run(argv: readonly string[], options: { timeoutMs: number; signal?: AbortSignal }): Promise<CliRunOutcome>;
}

export const DEFAULT_TIMEOUT_MS = 10 * 60 * 1000;

export function realRunner(home: string): Runner {
  return {
    async run(argv, options) {
      const result = await runProcess({
        argv,
        env: { ...process.env, HOME: home },
        timeoutMs: options.timeoutMs,
        signal: options.signal,
      });
      switch (result.kind) {
        case "completed":
          return { kind: "completed", exitCode: result.exitCode, stdout: result.stdout, stderr: result.stderr };
        default:
          return { kind: result.kind, message: "subprocess did not complete" };
      }
    },
  };
}

interface PendingPlan {
  flow: FlowKind;
  binding: string;
  confirmationToken: string;
  digest: string;
  // Exact plan object exactly as the CLI produced it.
  plan: Record<string, unknown>;
  // How to rebuild the approval file for this plan.
  approvalShape: "plan-plus-evidence" | "next-action-template";
  // Extra argv appended (in order) for the confirm execution.
  confirmArgv: readonly string[];
  createdAt: number;
}

const PENDING_TTL_MS = 10 * 60 * 1000;

export interface OrchestratorDeps {
  readonly runner: Runner;
  readonly home: string;
  readonly pluginDir: string | null;
  readonly searchedPluginDirs: readonly string[];
  readonly now?: () => Date;
  readonly newOperationId?: () => string;
  /** Test seam: override the Python environment probe. */
  readonly pythonProbe?: () => Promise<PythonEnvironment>;
  /** Test seam: override the Git environment probe. */
  readonly gitProbe?: () => Promise<GitEnvironment>;
  /**
   * Test seam: override the in-package release identity. Production leaves
   * this unset so the compile-time CORE_RELEASE_MANIFEST_SHA256 constant
   * is the only source; no RPC can ever influence it.
   */
  readonly releaseManifestSha256?: string;
}

export type PreviewOutcome =
  | { status: "missing_dependency"; dependency: "python" | "git"; detail: string }
  | { status: "identity_missing"; detail: string }
  | { status: "payload_missing"; detail: string; searched: string[] }
  | { status: "already_prepared"; sourceManifestPath: string }
  | { status: "approval_required"; planKind: string; digest: string; confirmationToken: string; summary: { label: string; value: string }[]; plan: Record<string, unknown>; envelope?: Record<string, unknown> }
  | { status: "completed"; envelope: Record<string, unknown> }
  | { status: "failed"; code: string; message: string; envelope?: Record<string, unknown> };

export type ConfirmOutcome =
  | { status: "rejected" }
  | { status: "stale_plan"; detail: string }
  | { status: "no_pending_plan"; detail: string }
  | { status: "acquired"; sourceManifestPath: string; installerPath: string; envelope: Record<string, unknown> }
  | { status: "completed"; envelope: Record<string, unknown> }
  | { status: "failed"; code: string; message: string; envelope?: Record<string, unknown> };

// Enable/remove/CK/recovery confirmations never produce the bootstrap-only
// "acquired" variant; this narrower type is what their RPC contracts accept.
export type PlanConfirmOutcome = Exclude<ConfirmOutcome, { status: "acquired" }>;

function jsonRecord(value: unknown): Record<string, unknown> | null {
  return value !== null && typeof value === "object" && !Array.isArray(value) ? (value as Record<string, unknown>) : null;
}

// Human-facing summary rows derived from a CLI plan. Only known-safe
// scalar fields; everything else stays available in the full plan view.
export function summarizePlan(plan: Record<string, unknown>): { label: string; value: string }[] {
  const rows: { label: string; value: string }[] = [];
  const push = (label: string, value: unknown): void => {
    if (value === undefined || value === null) return;
    if (typeof value === "string" || typeof value === "number" || typeof value === "boolean") {
      rows.push({ label, value: String(value) });
    }
  };
  push("command", plan.command);
  push("home", plan.home);
  push("version", (plan.manifest as Record<string, unknown> | undefined)?.source ?? undefined);
  const source = plan.source as Record<string, unknown> | undefined;
  if (source) {
    push("source url", source.url);
    push("source commit", source.commit);
    push("source version", source.version);
  }
  push("operation_id", plan.operation_id);
  const delivery = plan.delivery as Record<string, unknown> | undefined;
  if (delivery) {
    push("payload", delivery.payload);
    push("payload manifest sha256", delivery.manifest_sha256);
  }
  const changes = plan.changes as unknown[] | undefined;
  if (Array.isArray(changes)) {
    rows.push({ label: "changes", value: `${changes.length} 项` });
  }
  push("memory policy after", plan.memory_policy);
  const transition = jsonRecord(plan.memory_transition);
  if (transition) { push("memory policy before", transition.before); push("memory policy after transition", transition.after); }
  else if (plan.memory_policy !== undefined) rows.push({ label: "memory policy before", value: "原计划未报告变更前值（完整计划为准）" });
  const agents = (plan as Record<string, unknown>).agents;
  if (Array.isArray(agents)) rows.push({ label: "agents", value: agents.join(", ") });
  const projects = (plan as Record<string, unknown>).projects;
  if (Array.isArray(projects)) rows.push({ label: "projects", value: String(projects.length) });
  return rows;
}

export class Orchestrator {
  private readonly pending = new Map<FlowKind, PendingPlan>();
  private readonly running = new Map<FlowKind, { controller: AbortController; record: string }>();

  operationStatus(): Record<string, unknown>[] {
    const root = path.join(this.paths.pluginStagingRoot, "pending");
    if (!fs.existsSync(root)) return [];
    const records: Record<string, unknown>[] = [];
    if (!fs.lstatSync(root).isDirectory() || fs.lstatSync(root).isSymbolicLink()) return [];
    for (const dir of fs.readdirSync(root)) {
      if (!/^op-[A-Za-z0-9]+$/.test(dir)) continue;
      try {
        const directory = path.join(root, dir);
        if (!fs.lstatSync(directory).isDirectory() || fs.lstatSync(directory).isSymbolicLink()) continue;
        const file = path.join(directory, "operation.json");
        if (!fs.lstatSync(file).isFile() || fs.lstatSync(file).isSymbolicLink()) continue;
        const value = JSON.parse(fs.readFileSync(file, "utf8"));
        if (value.home !== this.deps.home || value.host !== hostname() || typeof value.id !== "string") continue;
        if (value.state === "running" && ![...this.running.values()].some(r => r.record === file)) value.state = "unknown";
        // Resolve advisory unknown state only from the ORIGINAL kernel journal.
        // Never infer a committed transaction from host RPC completion alone.
        if (value.state === "unknown" && typeof value.journal === "string") {
          try {
            if (fs.realpathSync(value.journal) === value.journal && fs.lstatSync(value.journal).isFile()) {
              const journal = JSON.parse(fs.readFileSync(value.journal, "utf8"));
              if (journal.plan?.layout?.root === path.join(this.deps.home, ".mem-sharing") && ["committed", "rolled_back"].includes(journal.status)) value.state = "recovered";
            }
          } catch { /* original journal remains authoritative and unresolved */ }
        }
        records.push({ id: value.id, flow: value.flow, phase: value.phase, state: value.state, started_at: value.started_at, journal: value.journal });
      } catch { /* an evidence-only directory has no operation record */ }
    }
    return records;
  }

  private async operate<T>(flow: FlowKind, phase: "preview" | "execute", signal: AbortSignal | undefined, work: (signal: AbortSignal) => Promise<T>): Promise<T> {
    if (this.running.has(flow)) return { status: "failed", code: "operation_busy", message: "An operation is already running for this flow" } as T;
    if (phase === "preview") this.pending.delete(flow);
    const controller = new AbortController();
    const abort = () => controller.abort();
    if (signal?.aborted) controller.abort();
    signal?.addEventListener("abort", abort, { once: true });
    let record: string;
    let recordFd: number;
    try {
      record = this.stagingFile("operation.json");
      recordFd = fs.openSync(record, "wx", 0o600);
    } catch (error) {
      signal?.removeEventListener("abort", abort);
      return { status: "failed", code: "operation_prepare_failed", message: String(error) } as T;
    }
    const entry = { id: randomUUID(), flow, phase, journal: this.pending.get(flow)?.plan.journal ?? (this.pending.get(flow)?.plan.plan as Record<string, unknown> | undefined)?.journal, home: this.deps.home, host: hostname(), state: "running", started_at: this.now().toISOString() };
    const save = () => { fs.ftruncateSync(recordFd); fs.writeSync(recordFd, JSON.stringify(entry), 0, "utf8"); fs.fsyncSync(recordFd); };
    this.running.set(flow, { controller, record });
    try {
      save();
      const result = await work(controller.signal);
      const out = result as Record<string, unknown>;
      entry.state = phase === "execute" && (controller.signal.aborted || String(out.code).match(/cli_(timeout|canceled|spawn_error|stdout_invalid)/)) ? "unknown" : String(out.status);
      save();
      return result;
    } catch (error) {
      entry.state = phase === "execute" ? "unknown" : "failed";
      save();
      return { status: "failed", code: "operation_error", message: String(error) } as T;
    } finally {
      fs.closeSync(recordFd);
      this.running.delete(flow);
      signal?.removeEventListener("abort", abort);
    }
  }

  private kernelBinding(argv: readonly string[]): string {
    const script = argv[2];
    const hash = createHash("sha256");
    hash.update(JSON.stringify({ home: this.deps.home, host: hostname(), argv, release: this.releaseDigest() }));
    const walk = (file: string): void => {
      const st = fs.lstatSync(file);
      hash.update(JSON.stringify([file, st.dev, st.ino, st.mode]));
      if (st.isSymbolicLink()) throw new Error("kernel symlink refused: " + file);
      if (st.isDirectory()) for (const name of fs.readdirSync(file).sort()) { if (name !== "__pycache__") walk(path.join(file, name)); }
      else if (st.isFile()) hash.update(fs.readFileSync(file));
      else throw new Error("unsafe kernel node");
    };
    walk(path.dirname(script));
    return hash.digest("hex");
  }

  private cachedPython: PythonEnvironment | null = null;
  private cachedGit: GitEnvironment | null = null;
  private readonly deps: OrchestratorDeps;

  constructor(deps: OrchestratorDeps) {
    this.deps = deps;
  }

  private get paths() {
    return productPaths(this.deps.home);
  }

  private now(): Date {
    return this.deps.now ? this.deps.now() : new Date();
  }

  private operationId(): string {
    if (this.deps.newOperationId) return this.deps.newOperationId();
    return `paseo-${this.now().toISOString().replace(/[-:T]/g, "").slice(0, 14)}Z-${Math.random().toString(16).slice(2, 10)}`;
  }

  private reference(flow: FlowKind): string {
    return `paseo-plugin memsharing ${flow} confirm-screen user press`;
  }

  async python(): Promise<PythonEnvironment> {
    if (this.deps.pythonProbe) return this.deps.pythonProbe();
    this.cachedPython ??= await probePythonEnvironment({ runtimeRoot: this.paths.runtimeRoot });
    return this.cachedPython;
  }

  async git(): Promise<GitEnvironment> {
    if (this.deps.gitProbe) return this.deps.gitProbe();
    this.cachedGit ??= await probeGitEnvironment();
    return this.cachedGit;
  }

  payload(): { status: "ready" | "missing"; installerPath?: string; searched: string[] } {
    const searched: string[] = [];
    if (this.deps.pluginDir) {
      const payloadDir = path.join(this.deps.pluginDir, "payload");
      searched.push(payloadDir);
      const installer = path.join(payloadDir, "core", "scripts", "install.py");
      const releaseJson = path.join(payloadDir, "release.json");
      try {
        if (fs.statSync(installer).isFile() && fs.statSync(releaseJson).isFile()) {
          return { status: "ready", installerPath: installer, searched };
        }
      } catch {
        // fall through to missing
      }
    }
    return { status: "missing", searched: [...searched, ...this.deps.searchedPluginDirs] };
  }

  private releaseDigest(): string {
    return this.deps.releaseManifestSha256 ?? CORE_RELEASE_MANIFEST_SHA256;
  }

  releaseIdentity(): { status: "ready" | "missing"; detail: string } {
    if (isSha256Hex(this.releaseDigest())) {
      return { status: "ready", detail: "in-package compile-time release identity present" };
    }
    return {
      status: "missing",
      detail: "release identity is unset in this development source; a release-generated build is required for bootstrap delivery",
    };
  }

  // Discovery for status only. Normal onboarding always invokes the bundled
  // release resolver; a directory name or receipt is never source authority.
  durableSource(): { status: "ready" | "missing"; sourceManifestPath?: string; installerPath?: string; detail: string } {
    try {
      if (!this.deps.pluginDir || !isSha256Hex(this.releaseDigest())) throw new Error("current package unavailable");
      const raw = fs.readFileSync(path.join(this.deps.pluginDir, "payload", "release.json"));
      if (createHash("sha256").update(raw).digest("hex") !== this.releaseDigest()) throw new Error("package manifest digest differs");
      const manifest = JSON.parse(raw.toString("utf8"));
      const { version, tree_sha256: tree } = manifest.source;
      if (!/^\d+\.\d+\.\d+$/.test(version) || !isSha256Hex(tree)) throw new Error("invalid release descriptor");
      const destination = path.join(this.paths.durableSourceRoot, version, tree);
      const sourceManifestPath = path.join(destination, "source-manifest.json");
      const installerPath = path.join(destination, "core", "scripts", "install.py");
      if (!fs.statSync(sourceManifestPath).isFile() || !fs.statSync(installerPath).isFile()) throw new Error("current export absent");
      return { status: "ready", sourceManifestPath, installerPath, detail: "current package export candidate; original release resolver verifies it before use" };
    } catch { return { status: "missing", detail: "current package export unavailable; old exports are recovery sources only" }; }
  }

  private async resolveCurrent(agents: readonly string[] | undefined, signal?: AbortSignal): Promise<PreviewOutcome> {
    const python = await this.requirePython();
    if (!python.ok) return { status: "missing_dependency", dependency: "python", detail: python.detail };
    const git = await this.git();
    if (git.status !== "ready") return { status: "missing_dependency", dependency: "git", detail: git.detail };
    const identity = this.releaseIdentity();
    if (identity.status !== "ready") return { status: "identity_missing", detail: identity.detail };
    const payload = this.payload();
    if (payload.status !== "ready") return { status: "payload_missing", detail: "current package payload missing", searched: payload.searched };
    const requestFile = this.stagingFile("release-request.json");
    fs.writeFileSync(requestFile, JSON.stringify({ kind: "plugin-package", payload: path.join(this.deps.pluginDir as string, "payload"), manifest_sha256: this.releaseDigest() }), { mode: 0o600, flag: "wx" });
    const argv = [python.pythonPath, "-B", payload.installerPath as string, "--release-request", requestFile, "--operation-id", this.operationId()];
    for (const agent of agents ?? []) argv.push("--agent", agent);
    const result = await this.runJson<PreviewOutcome>(argv, { signal });
    if ("failure" in result) return result.failure;
    const { parsed, exitKind } = result;
    const plan = jsonRecord(parsed.approval_plan);
    if (exitKind !== "approval_required" || !plan) return { status: "failed", code: "release_resolution_failed", message: JSON.stringify(parsed.errors ?? parsed.status), envelope: parsed };
    if (plan.command === "prepare-release-source") {
      const stored = this.storePending("bootstrap", plan, "plan-plus-evidence", [python.pythonPath, "-B", payload.installerPath as string]);
      return { status: "approval_required", planKind: "prepare-release-source", ...stored, plan };
    }
    if (plan.command !== "install-machine-cli") return { status: "failed", code: "unexpected_release_plan", message: "original resolver returned an unsupported plan", envelope: parsed };
    // These paths come only from the original resolver after package-digest,
    // closed payload and durable acquisition-receipt verification.
    const source = jsonRecord(plan.source);
    if (!source || typeof source.root !== "string" || !path.isAbsolute(source.root)) return { status: "failed", code: "source_identity_missing", message: "verified source missing from machine plan" };
    const sourceManifestPath = path.join(path.dirname(source.root), "source-manifest.json");
    if (agents === undefined) return { status: "already_prepared", sourceManifestPath };
    const confirmArgv = [python.pythonPath, "-B", path.join(source.root, "scripts", "install.py"), "--source-manifest", sourceManifestPath];
    for (const agent of agents) confirmArgv.push("--agent", agent);
    const stored = this.storePending("machine", plan, "plan-plus-evidence", confirmArgv);
    return { status: "approval_required", planKind: "install-machine", ...stored, plan, envelope: parsed };
  }

  private async requirePython(): Promise<{ ok: true; pythonPath: string } | { ok: false; detail: string }> {
    const env = await this.python();
    if (env.status === "ready" && env.selected) return { ok: true, pythonPath: env.selected.path };
    return { ok: false, detail: `python ${env.status}: ${env.candidates.map((c) => `${c.path}:${c.status}`).join("; ") || env.evidence}` };
  }

  private async runCli(argv: readonly string[], options?: { timeoutMs?: number; signal?: AbortSignal }): Promise<CliRunOutcome> {
    return this.deps.runner.run(argv, { timeoutMs: options?.timeoutMs ?? DEFAULT_TIMEOUT_MS, signal: options?.signal });
  }

  // Runs a CLI expecting a JSON envelope; maps exit codes per kernel contract.
  private async runJson<Failure extends PreviewOutcome | ConfirmOutcome>(argv: readonly string[], options?: { signal?: AbortSignal }): Promise<{ parsed: Record<string, unknown>; exitKind: "approval_required" | "completed" | "failed"; stderr: string } | { failure: Failure }> {
    const outcome = await this.runCli(argv, options);
    if (outcome.kind !== "completed") {
      return {
        failure: { status: "failed", code: `cli_${outcome.kind}`, message: outcome.message ?? outcome.kind } as Failure,
      };
    }
    const parsed = parseCliJson(outcome.stdout ?? "");
    if (!parsed.ok || !jsonRecord(parsed.value)) {
      return {
        failure: {
          status: "failed",
          code: "cli_stdout_invalid",
          message: parsed.error ?? "cli stdout was not a JSON object",
        } as Failure,
      };
    }
    const exitKind = classifyExitCode(outcome.exitCode ?? -1);
    return { parsed: jsonRecord(parsed.value) as Record<string, unknown>, exitKind, stderr: outcome.stderr ?? "" };
  }

  private stagingFile(name: string): string {
    const dir = path.join(this.paths.pluginStagingRoot, "pending");
    ensureRealDirectory(dir);
    // Every request/approval/operation gets an OS-exclusive directory;
    // worker IDs and user-controlled operation IDs are never file names.
    const owned = fs.mkdtempSync(path.join(dir, "op-"));
    fs.chmodSync(owned, 0o700);
    return path.join(owned, name);
  }

  cancel(flow: FlowKind): { status: "cancel_requested" | "cleared" | "none" } {
    const active = this.running.get(flow);
    if (active) { active.controller.abort(); return { status: "cancel_requested" }; }
    return this.pending.delete(flow) ? { status: "cleared" } : { status: "none" };
  }

  private storePending(flow: FlowKind, plan: Record<string, unknown>, approvalShape: PendingPlan["approvalShape"], confirmArgv: readonly string[]): { digest: string; confirmationToken: string; summary: { label: string; value: string }[] } {
    const binding = this.kernelBinding(confirmArgv);
    const digest = planDigest(plan);
    const confirmationToken = planDigest({ digest, binding, nonce: randomUUID() });
    this.pending.set(flow, {
      flow,
      binding,
      confirmationToken,
      digest,
      plan,
      approvalShape,
      confirmArgv,
      createdAt: this.now().getTime(),
    });
    return { digest, confirmationToken, summary: [...summarizePlan(plan), { label: "host", value: hostname() }, { label: "HOME", value: this.deps.home }, { label: "kernel binding", value: binding }] };
  }

  private popPending(flow: FlowKind, confirmationToken: string | undefined): { ok: true; pending: PendingPlan } | { ok: false; outcome: ConfirmOutcome } {
    const pending = this.pending.get(flow);
    if (!pending) {
      return { ok: false, outcome: { status: "no_pending_plan", detail: `no pending ${flow} plan; run the preview again` } };
    }
    if (this.now().getTime() - pending.createdAt > PENDING_TTL_MS) {
      this.pending.delete(flow);
      return { ok: false, outcome: { status: "stale_plan", detail: "pending plan expired; preview again" } };
    }
    if (confirmationToken !== pending.confirmationToken) {
      return { ok: false, outcome: { status: "stale_plan", detail: "confirmation token does not match the pending plan; preview again" } };
    }
    let currentBinding: string;
    try { currentBinding = this.kernelBinding(pending.confirmArgv); }
    catch { currentBinding = "unavailable"; }
    if (pending.binding !== currentBinding) {
      this.pending.delete(flow);
      return { ok: false, outcome: { status: "stale_plan", detail: "host/HOME/kernel binding changed; preview again" } };
    }
    this.pending.delete(flow);
    return { ok: true, pending };
  }

  private buildApprovalFile(pending: PendingPlan): string {
    const evidence = buildEvidence(this.reference(pending.flow), this.now());
    let approval: Record<string, unknown>;
    if (pending.approvalShape === "next-action-template") {
      // enable/remove templates carry placeholder evidence values; replace
      // only those two with real evidence while keeping every plan key
      // verbatim. rebuild_confirmation needs a SEPARATE user confirmation
      // and is never auto-filled from one click — such plans are blocked
      // before confirm ever runs (see projectEnablePreview).
      const { confirmed_at: _c, reference: _r, ...planKeys } = pending.plan;
      approval = buildApproval(planKeys as Record<string, unknown>, evidence);
    } else {
      approval = buildApproval(pending.plan, evidence);
    }
    const file = this.stagingFile(`${pending.flow}-approval.json`);
    fs.writeFileSync(file, JSON.stringify(approval, null, 2), { encoding: "utf8", mode: 0o600, flag: "wx" });
    return file;
  }

  // Execution argv for a confirmed plan: the stored base argv plus the
  // staging approval file as the final input.
  private confirmArgv(pending: PendingPlan, approvalFile: string): string[] {
    return [...pending.confirmArgv, "--approval-file", approvalFile];
  }

  // ---- bootstrap: plugin payload -> durable source export ----

  private async bootstrapPreviewImpl(signal?: AbortSignal): Promise<PreviewOutcome> {
    return this.resolveCurrent(undefined, signal);
  }

  private async bootstrapConfirmImpl(input: { action: "confirm" | "reject"; confirmationToken?: string }, signal?: AbortSignal): Promise<ConfirmOutcome> {
    if (input.action === "reject") {
      this.pending.delete("bootstrap");
      return { status: "rejected" };
    }
    const popped = this.popPending("bootstrap", input.confirmationToken);
    if (!popped.ok) return popped.outcome;
    const approvalFile = this.buildApprovalFile(popped.pending);
    // Export approval is applied alone: --approval-file is the only input,
    // matching the previewed HOME.
    const argv = this.confirmArgv(popped.pending, approvalFile);
    const result = await this.runJson<ConfirmOutcome>(argv, { signal });
    if ("failure" in result) return result.failure;
    const { parsed, exitKind } = result;
    if (exitKind === "completed" && parsed.status === "acquired") {
      return {
        status: "acquired",
        sourceManifestPath: String(parsed.source_manifest),
        installerPath: path.join(path.dirname(String(parsed.source_manifest)), "core", "scripts", "install.py"),
        envelope: parsed,
      };
    }
    return {
      status: "failed",
      code: exitKind === "completed" ? String(parsed.status) : `exit_${exitKind}`,
      message: `bootstrap confirm failed: ${JSON.stringify(parsed.errors ?? parsed.status)}`,
      envelope: parsed,
    };
  }

  // ---- machine installation via durable source export ----

  private async machinePreviewImpl(agents: readonly string[], signal?: AbortSignal): Promise<PreviewOutcome> {
    return this.resolveCurrent(agents, signal);
  }

  private async machineConfirmImpl(input: { action: "confirm" | "reject"; confirmationToken?: string }, signal?: AbortSignal): Promise<ConfirmOutcome> {
    if (input.action === "reject") {
      this.pending.delete("machine");
      return { status: "rejected" };
    }
    const popped = this.popPending("machine", input.confirmationToken);
    if (!popped.ok) return popped.outcome;
    const approvalFile = this.buildApprovalFile(popped.pending);
    const argv = this.confirmArgv(popped.pending, approvalFile);
    const result = await this.runJson<ConfirmOutcome>(argv, { signal });
    if ("failure" in result) return result.failure;
    const { parsed, exitKind } = result;
    if (exitKind === "completed") return { status: "completed", envelope: parsed };
    return {
      status: "failed",
      code: `exit_${exitKind}`,
      message: `machine confirm failed: ${JSON.stringify(parsed.errors ?? parsed.status)}`,
      envelope: parsed,
    };
  }

  // ---- project commands via the active kernel ----

  // The machine installer lays active code out flat under the product code
  // root: <codeRoot>/scripts/{agm,install}.py plus the managed documents
  // (verified against a real temp-HOME install; layout.py owns the shape).
  private activeKernel(): { agm: string; installer: string; root: string } | null {
    const root = this.paths.codeRoot;
    const agm = path.join(root, "scripts", "agm.py");
    const installer = path.join(root, "scripts", "install.py");
    try {
      if (fs.statSync(agm).isFile() && fs.statSync(installer).isFile()) {
        return { agm, installer, root };
      }
    } catch {
      // not installed
    }
    return null;
  }

  private activeKernelAgm(): string | null {
    return this.activeKernel()?.agm ?? null;
  }

  async projectCheck(projectRoot: string, signal?: AbortSignal): Promise<{ status: "completed" | "gaps" | "failed"; envelope: Record<string, unknown> }> {
    const python = await this.requirePython();
    if (!python.ok) {
      return { status: "failed", envelope: { status: "failed", errors: [{ code: "python_missing", message: python.detail }] } };
    }
    const agm = this.activeKernelAgm();
    if (!agm) {
      return { status: "failed", envelope: { status: "failed", errors: [{ code: "kernel_missing", message: "memSharing machine install not found; run onboarding first" }] } };
    }
    const outcome = await this.runCli([python.pythonPath, "-B", agm, "check-memory", "--project", projectRoot], { signal });
    if (outcome.kind !== "completed") {
      return { status: "failed", envelope: { status: "failed", errors: [{ code: `cli_${outcome.kind}`, message: outcome.message ?? outcome.kind }] } };
    }
    const parsed = parseCliJson(outcome.stdout ?? "");
    if (!parsed.ok || !jsonRecord(parsed.value)) {
      return { status: "failed", envelope: { status: "failed", errors: [{ code: "cli_stdout_invalid", message: parsed.error ?? "invalid stdout" }] } };
    }
    const envelope = jsonRecord(parsed.value) as Record<string, unknown>;
    const status = envelope.status === "completed" ? "completed" : envelope.status === "gaps" ? "gaps" : "failed";
    return { status, envelope };
  }

  private async projectEnablePreviewImpl(input: {
    projectRoot: string;
    agents: readonly string[];
    memory?: "enable" | "disable";
  }, signal?: AbortSignal): Promise<PreviewOutcome> {
    const python = await this.requirePython();
    if (!python.ok) return { status: "missing_dependency", dependency: "python", detail: python.detail };
    const git = await this.git();
    if (git.status !== "ready") return { status: "missing_dependency", dependency: "git", detail: git.detail };
    const agm = this.activeKernelAgm();
    if (!agm) {
      return { status: "failed", code: "kernel_missing", message: "memSharing machine install not found; run onboarding first" };
    }
    // A plain enable call can legally WRITE without a new approval when a
    // consistent registered repair exists, so project previews must pass
    // the kernel's read-only --preview flag (mutually exclusive with
    // --approval-file, placed last per the frozen kernel contract). The
    // confirm argv never carries --preview.
    const previewArgv: string[] = [python.pythonPath, "-B", agm, "enable-memory", "--project", input.projectRoot];
    if (input.agents.length > 0) previewArgv.push("--agent", ...input.agents);
    if (input.memory === "enable") previewArgv.push("--memory");
    if (input.memory === "disable") previewArgv.push("--no-memory");
    previewArgv.push("--preview");
    const result = await this.runJson<PreviewOutcome>(previewArgv, { signal });
    if ("failure" in result) return result.failure;
    const { parsed, exitKind } = result;
    if (exitKind === "approval_required" || parsed.status === "approval_required") {
      // The kernel's --preview exposes the exact plan as the next_action
      // JSON template; only the two evidence placeholders are replaced at
      // confirm time. Plans are never assembled on this side.
      const template = parsed.next_action;
      if (typeof template !== "string") {
        return { status: "failed", code: "plan_unavailable", message: "enable preview did not expose an exact plan", envelope: parsed };
      }
      let plan: Record<string, unknown>;
      try {
        plan = JSON.parse(template) as Record<string, unknown>;
      } catch {
        return { status: "failed", code: "plan_unparseable", message: "next_action is not JSON", envelope: parsed };
      }
      if (plan.rebuild !== undefined) {
        return {
          status: "failed",
          code: "rebuild_confirmation_required",
          message: "该计划包含全局注册表重建，需要独立的第二份用户确认；本版插件未实现该二次确认，已结构化阻断",
          envelope: parsed,
        };
      }
      const confirmArgv: string[] = [python.pythonPath, "-B", agm, "enable-memory", "--project", input.projectRoot];
      if (input.agents.length > 0) confirmArgv.push("--agent", ...input.agents);
      if (input.memory === "enable") confirmArgv.push("--memory");
      if (input.memory === "disable") confirmArgv.push("--no-memory");
      const stored = this.storePending("enable", plan, "next-action-template", confirmArgv);
      if (!jsonRecord(plan.memory_transition)) {
        // No transition is emitted for unchanged policy or an unregistered
        // project. Read only the matching original ledger entry for display;
        // the kernel's exact approval remains the sole write authority.
        let before = "未登记";
        try {
          const ledger = JSON.parse(fs.readFileSync(this.paths.registryFile, "utf8"));
          const previous = ledger.projects?.[String(plan.main_checkout)];
          if (typeof previous?.memory_policy === "string") before = previous.memory_policy;
        } catch { before = "原台账不可读（完整计划为准）"; }
        stored.summary = stored.summary.filter(row => row.label !== "memory policy before");
        stored.summary.push({ label: "memory policy before", value: before });
      }
      return { status: "approval_required", planKind: "enable-memory", ...stored, plan, envelope: parsed };
    }
    if (exitKind === "completed") return { status: "completed", envelope: parsed };
    return {
      status: "failed",
      code: "cli_failed",
      message: `enable preview failed: ${JSON.stringify(parsed.errors ?? parsed.status)}`,
      envelope: parsed,
    };
  }

  private async projectEnableConfirmImpl(input: { action: "confirm" | "reject"; confirmationToken?: string }, signal?: AbortSignal): Promise<PlanConfirmOutcome> {
    if (input.action === "reject") {
      this.pending.delete("enable");
      return { status: "rejected" };
    }
    const popped = this.popPending("enable", input.confirmationToken);
    if (!popped.ok) return popped.outcome as PlanConfirmOutcome;
    const approvalFile = this.buildApprovalFile(popped.pending);
    const argv = this.confirmArgv(popped.pending, approvalFile);
    const result = await this.runJson<PlanConfirmOutcome>(argv, { signal });
    if ("failure" in result) return result.failure;
    const { parsed, exitKind } = result;
    if (exitKind === "completed") return { status: "completed", envelope: parsed };
    return {
      status: "failed",
      code: `exit_${exitKind}`,
      message: `enable confirm failed: ${JSON.stringify(parsed.errors ?? parsed.status)}`,
      envelope: parsed,
    };
  }

  // ---- project removal via the kernel's read-only --preview ----

  private async projectRemovePreviewImpl(projectRoot: string, signal?: AbortSignal): Promise<PreviewOutcome> {
    const python = await this.requirePython();
    if (!python.ok) return { status: "missing_dependency", dependency: "python", detail: python.detail };
    const agm = this.activeKernelAgm();
    if (!agm) {
      return { status: "failed", code: "kernel_missing", message: "memSharing machine install not found; nothing to remove" };
    }
    // Frozen kernel contract: remove-memory --project ABS --preview, no
    // --agent/--memory; the exact 11-key template (including
    // registry_sha256 and memory_policy=disabled) arrives in next_action.
    const previewArgv = [python.pythonPath, "-B", agm, "remove-memory", "--project", projectRoot, "--preview"];
    const result = await this.runJson<PreviewOutcome>(previewArgv, { signal });
    if ("failure" in result) return result.failure;
    const { parsed, exitKind } = result;
    if (exitKind === "approval_required" || parsed.status === "approval_required") {
      const template = parsed.next_action;
      if (typeof template !== "string") {
        return { status: "failed", code: "plan_unavailable", message: "remove preview did not expose an exact plan", envelope: parsed };
      }
      let plan: Record<string, unknown>;
      try {
        plan = JSON.parse(template) as Record<string, unknown>;
      } catch {
        return { status: "failed", code: "plan_unparseable", message: "next_action is not JSON", envelope: parsed };
      }
      if (typeof plan.registry_sha256 !== "string" || plan.memory_policy !== "disabled") {
        return { status: "failed", code: "plan_shape_invalid", message: "remove template missing registry_sha256 / memory_policy=disabled", envelope: parsed };
      }
      const confirmArgv = [python.pythonPath, "-B", agm, "remove-memory", "--project", projectRoot];
      const stored = this.storePending("remove", plan, "next-action-template", confirmArgv);
      return { status: "approval_required", planKind: "remove-memory", ...stored, plan, envelope: parsed };
    }
    if (exitKind === "completed") return { status: "completed", envelope: parsed };
    return {
      status: "failed",
      code: "cli_failed",
      message: `remove preview failed: ${JSON.stringify(parsed.errors ?? parsed.status)}`,
      envelope: parsed,
    };
  }

  private async projectRemoveConfirmImpl(input: { action: "confirm" | "reject"; confirmationToken?: string }, signal?: AbortSignal): Promise<PlanConfirmOutcome> {
    if (input.action === "reject") {
      this.pending.delete("remove");
      return { status: "rejected" };
    }
    const popped = this.popPending("remove", input.confirmationToken);
    if (!popped.ok) return popped.outcome as PlanConfirmOutcome;
    const approvalFile = this.buildApprovalFile(popped.pending);
    const argv = this.confirmArgv(popped.pending, approvalFile);
    const result = await this.runJson<PlanConfirmOutcome>(argv, { signal });
    if ("failure" in result) return result.failure;
    const { parsed, exitKind } = result;
    if (exitKind === "completed") return { status: "completed", envelope: parsed };
    return {
      status: "failed",
      code: `exit_${exitKind}`,
      message: `remove confirm failed: ${JSON.stringify(parsed.errors ?? parsed.status)}`,
      envelope: parsed,
    };
  }

  // ---- optional Context Keeper user install (independent approval) ----

  private async ckPreviewImpl(ckSource?: string, signal?: AbortSignal): Promise<PreviewOutcome> {
    const python = await this.requirePython();
    if (!python.ok) return { status: "missing_dependency", dependency: "python", detail: python.detail };
    const git = await this.git();
    if (git.status !== "ready") return { status: "missing_dependency", dependency: "git", detail: git.detail };
    const kernel = this.activeKernel();
    if (!kernel) {
      return { status: "failed", code: "kernel_missing", message: "memSharing machine install not found; CK is a separate optional step after it" };
    }
    // Existing installations are discovered by the original CLI first. Only
    // its explicit source-unavailable result offers a separately approved fetch.
    const automaticSource = ckDestination(this.deps.home);
    if (!ckSource && fs.existsSync(automaticSource)) ckSource = automaticSource;
    const previewArgv = [python.pythonPath, "-B", kernel.installer, "--context-keeper"];
    if (ckSource && ckSource.trim().length > 0) previewArgv.push("--ck-source", ckSource.trim());
    const result = await this.runJson<PreviewOutcome>(previewArgv, { signal });
    if ("failure" in result) return result.failure;
    const { parsed, exitKind } = result;
    if (exitKind === "approval_required") {
      const plan = (parsed.approval_plan ?? parsed) as Record<string, unknown>;
      const confirmArgv = [python.pythonPath, "-B", kernel.installer, "--context-keeper"];
      if (ckSource && ckSource.trim().length > 0) confirmArgv.push("--ck-source", ckSource.trim());
      const stored = this.storePending("ck", plan, "plan-plus-evidence", confirmArgv);
      return { status: "approval_required", planKind: "install-context-keeper", ...stored, plan };
    }
    if (exitKind === "completed") return { status: "completed", envelope: parsed };
    if (!ckSource && (parsed.errors as Record<string, unknown>[] | undefined)?.some(e => e.code === "ck_source_unavailable")) {
      const plan = ckAcquisitionPlan(this.deps.home);
      const stored = this.storePending("ck", plan, "plan-plus-evidence", [python.pythonPath, "-B", kernel.installer]);
      return { status: "approval_required", planKind: "prepare-context-keeper-source", ...stored, plan };
    }
    return {
      status: "failed",
      code: String((parsed.errors as Record<string, unknown>[] | undefined)?.[0]?.code ?? "ck_unavailable"),
      message: `CK preview: ${JSON.stringify(parsed.errors ?? parsed.status)}`,
      envelope: parsed,
    };
  }

  private async ckConfirmImpl(input: { action: "confirm" | "reject"; confirmationToken?: string }, signal?: AbortSignal): Promise<PlanConfirmOutcome> {
    if (input.action === "reject") {
      this.pending.delete("ck");
      return { status: "rejected" };
    }
    const popped = this.popPending("ck", input.confirmationToken);
    if (!popped.ok) return popped.outcome as PlanConfirmOutcome;
    if (popped.pending.plan.command === "prepare-context-keeper-source") {
      if (planDigest(popped.pending.plan) !== planDigest(ckAcquisitionPlan(this.deps.home))) return { status: "stale_plan", detail: "CK acquisition target changed" };
      const git = await this.git();
      if (git.status !== "ready" || !git.path) return { status: "failed", code: "git_missing", message: git.detail };
      const source = await acquireCkSource(this.deps.home, git.path, this.deps.runner, signal);
      return { status: "completed", envelope: { status: "source_prepared", source, installation_complete: false, next_action: "Preview Context Keeper installation for separate approval" } };
    }
    const approvalFile = this.buildApprovalFile(popped.pending);
    const argv = this.confirmArgv(popped.pending, approvalFile);
    const result = await this.runJson<PlanConfirmOutcome>(argv, { signal });
    if ("failure" in result) return result.failure;
    const { parsed, exitKind } = result;
    if (exitKind === "completed") return { status: "completed", envelope: parsed };
    return {
      status: "failed",
      code: `exit_${exitKind}`,
      message: `CK confirm failed: ${JSON.stringify(parsed.errors ?? parsed.status)}`,
      envelope: parsed,
    };
  }

  // ---- recovery of an interrupted machine operation ----

  private async recoverPreviewImpl(input: { journalPath: string; action?: "continue" | "rollback" }, signal?: AbortSignal): Promise<PreviewOutcome> {
    const python = await this.requirePython();
    if (!python.ok) return { status: "missing_dependency", dependency: "python", detail: python.detail };
    // Candidate discovery is not trust: bind the chosen toolkit's bytes to
    // the original journal BEFORE running it. The original CLI then checks
    // the journal, source, locks and recovery scene with its existing rules.
    let toolkit: string | undefined;
    try {
      if (!path.isAbsolute(input.journalPath) || fs.realpathSync(input.journalPath) !== input.journalPath || !fs.lstatSync(input.journalPath).isFile()) throw new Error("journal must be an absolute real file");
      const journal = JSON.parse(fs.readFileSync(input.journalPath, "utf8"));
      const original = journal.plan;
      if (original.layout?.root !== this.paths.registryFile.replace(/\/var\/registry\.json$/, "")) throw new Error("journal HOME differs");
      const source = original.source as { root: string; files: Record<string, string> };
      const expected = source?.files?.["scripts/install.py"];
      if (!isSha256Hex(expected) || !Array.isArray(original.tools) || original.tools.length === 0) throw new Error("journal lacks a fixed CLI/toolkit identity");
      const candidates = [path.join(source.root, "scripts", "install.py"), this.activeKernel()?.installer, this.durableSource().installerPath, this.payload().installerPath];
      for (const candidate of candidates) {
        if (!candidate) continue;
        try {
          const exact = (file: string, hash: string) => fs.realpathSync(file) === file && fs.lstatSync(file).isFile() && createHash("sha256").update(fs.readFileSync(file)).digest("hex") === hash;
          if (!exact(candidate, expected)) continue;
          if (!original.tools.every((item: { path: string; sha256: string }) => path.basename(item.path) === item.path && exact(path.join(path.dirname(candidate), "agm_core", item.path), item.sha256))) continue;
          toolkit = candidate;
          break;
        } catch { /* try another journal-matching source */ }
      }
      if (!toolkit) throw new Error("no available toolkit matches the journal's fixed identity");
    } catch (error) {
      return { status: "failed", code: "recovery_identity_mismatch", message: String(error) };
    }
    // The kernel requires an explicit action alongside --recover.
    const action = input.action ?? "continue";
    const previewArgv = [python.pythonPath, "-B", toolkit, "--recover", input.journalPath, "--action", action];
    const result = await this.runJson<PreviewOutcome>(previewArgv, { signal });
    if ("failure" in result) return result.failure;
    const { parsed, exitKind } = result;
    if (exitKind === "approval_required") {
      const plan = (parsed.approval_plan ?? parsed) as Record<string, unknown>;
      const confirmArgv = [python.pythonPath, "-B", toolkit, "--recover", input.journalPath, "--action", action];
      const stored = this.storePending("recover", plan, "plan-plus-evidence", confirmArgv);
      return { status: "approval_required", planKind: "machine-recovery", ...stored, plan };
    }
    if (exitKind === "completed") return { status: "completed", envelope: parsed };
    return {
      status: "failed",
      code: "cli_failed",
      message: `recover preview failed: ${JSON.stringify(parsed.errors ?? parsed.status)}`,
      envelope: parsed,
    };
  }

  private async recoverConfirmImpl(input: { action: "confirm" | "reject"; confirmationToken?: string }, signal?: AbortSignal): Promise<PlanConfirmOutcome> {
    if (input.action === "reject") {
      this.pending.delete("recover");
      return { status: "rejected" };
    }
    const popped = this.popPending("recover", input.confirmationToken);
    if (!popped.ok) return popped.outcome as PlanConfirmOutcome;
    const approvalFile = this.buildApprovalFile(popped.pending);
    const argv = this.confirmArgv(popped.pending, approvalFile);
    const result = await this.runJson<PlanConfirmOutcome>(argv, { signal });
    if ("failure" in result) return result.failure;
    const { parsed, exitKind } = result;
    if (exitKind === "completed") return { status: "completed", envelope: parsed };
    return {
      status: "failed",
      code: `exit_${exitKind}`,
      message: `recover confirm failed: ${JSON.stringify(parsed.errors ?? parsed.status)}`,
      envelope: parsed,
    };
  }

  async bootstrapPreview(signal?: AbortSignal): Promise<PreviewOutcome> {
    return this.operate("bootstrap", "preview", signal, owned => this.bootstrapPreviewImpl(owned));
  }

  async bootstrapConfirm(input: { action: "confirm" | "reject"; confirmationToken?: string }, signal?: AbortSignal): Promise<ConfirmOutcome> {
    return this.operate("bootstrap", "execute", signal, owned => this.bootstrapConfirmImpl(input, owned));
  }

  async machinePreview(agents: readonly string[], signal?: AbortSignal): Promise<PreviewOutcome> {
    return this.operate("machine", "preview", signal, owned => this.machinePreviewImpl(agents, owned));
  }

  async machineConfirm(input: { action: "confirm" | "reject"; confirmationToken?: string }, signal?: AbortSignal): Promise<ConfirmOutcome> {
    return this.operate("machine", "execute", signal, owned => this.machineConfirmImpl(input, owned));
  }

  async projectEnablePreview(input: { projectRoot: string; agents: readonly string[]; memory?: "enable" | "disable" }, signal?: AbortSignal): Promise<PreviewOutcome> {
    return this.operate("enable", "preview", signal, owned => this.projectEnablePreviewImpl(input, owned));
  }

  async projectEnableConfirm(input: { action: "confirm" | "reject"; confirmationToken?: string }, signal?: AbortSignal): Promise<PlanConfirmOutcome> {
    return this.operate("enable", "execute", signal, owned => this.projectEnableConfirmImpl(input, owned));
  }

  async projectRemovePreview(projectRoot: string, signal?: AbortSignal): Promise<PreviewOutcome> {
    return this.operate("remove", "preview", signal, owned => this.projectRemovePreviewImpl(projectRoot, owned));
  }

  async projectRemoveConfirm(input: { action: "confirm" | "reject"; confirmationToken?: string }, signal?: AbortSignal): Promise<PlanConfirmOutcome> {
    return this.operate("remove", "execute", signal, owned => this.projectRemoveConfirmImpl(input, owned));
  }

  async ckPreview(ckSource?: string, signal?: AbortSignal): Promise<PreviewOutcome> {
    return this.operate("ck", "preview", signal, owned => this.ckPreviewImpl(ckSource, owned));
  }

  async ckConfirm(input: { action: "confirm" | "reject"; confirmationToken?: string }, signal?: AbortSignal): Promise<PlanConfirmOutcome> {
    return this.operate("ck", "execute", signal, owned => this.ckConfirmImpl(input, owned));
  }

  async recoverPreview(input: { journalPath: string; action?: "continue" | "rollback" }, signal?: AbortSignal): Promise<PreviewOutcome> {
    return this.operate("recover", "preview", signal, owned => this.recoverPreviewImpl(input, owned));
  }

  async recoverConfirm(input: { action: "confirm" | "reject"; confirmationToken?: string }, signal?: AbortSignal): Promise<PlanConfirmOutcome> {
    return this.operate("recover", "execute", signal, owned => this.recoverConfirmImpl(input, owned));
  }
}
