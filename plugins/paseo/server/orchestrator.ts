// memSharing Paseo plugin — server-side orchestration over the real Python
// CLIs. This layer owns NO business policy: every write goes through
// scripts/install.py / scripts/agm.py with their exact-plan approvals, and
// every read goes through the same kernels. The plugin only prepares
// inputs, surfaces exact plans for host-side confirmation, and binds the
// user's confirm action to the plan digest it displayed.

import fs from "node:fs";
import { randomUUID, createHash } from "node:crypto";
import { hostname, release, tmpdir } from "node:os";
import path from "node:path";
import { CORE_RELEASE_MANIFEST_SHA256 } from "./shared/release-identity";
import { ensureRealDirectory } from "./owned-paths";
import { ckAcquisitionPlan, acquireCkSource } from "./ck-source";
import { runProcess } from "./shared/common/process";
import { parseCliJson, classifyExitCode } from "./shared/common/json";
import { planDigest, buildEvidence, buildApproval, isSha256Hex } from "./shared/common/digest";
import { productPaths } from "./shared/common/paths";
import type { PythonEnvironment } from "./shared/common/python";
import type { GitEnvironment } from "./shared/common/git";
import { probePythonEnvironment } from "./shared/common/python";
import { probeGitEnvironment } from "./shared/common/git";
import { PRODUCTION_TOOL_ASSETS } from "./shared/common/production-assets";
import { assetScene, assetDestination, prepareToolAsset, toolEnvironment, toolTreeDigest, type ToolAsset } from "./shared/common/tool-assets";

export type FusionInput = { scope: "user" | "project"; projectRoot?: string; selection?: string; decline?: boolean;
  contextToken?: string; retentions?: Record<string, string>; equivalentSources?: Record<string, unknown>[]; publicReuse?: Record<string, unknown>[] };

export type FlowKind = "dependency" | "bootstrap" | "machine" | "enable" | "uninstall" | "stagingCleanup" | "ck" | "recover" | "ckUninstall" | "fusion";

export interface CliRunOutcome {
  kind: "completed" | "timeout" | "canceled" | "spawn_error";
  exitCode?: number;
  stdout?: string;
  stderr?: string;
  message?: string;
}

export interface Runner {
  run(argv: readonly string[], options: { timeoutMs: number; signal?: AbortSignal; env?: NodeJS.ProcessEnv }): Promise<CliRunOutcome>;
}

export const DEFAULT_TIMEOUT_MS = 10 * 60 * 1000;

export function realRunner(home: string): Runner {
  return {
    async run(argv, options) {
      const result = await runProcess({
        argv,
        env: { ...process.env, ...options.env, HOME: home, PYTHONPATH: "", PYTHONHOME: "", PYTHONDONTWRITEBYTECODE: "1", PYTHONNOUSERSITE: "1" },
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
  approvalShape: "plan-plus-evidence" | "next-action-template" | "core-envelope";
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
  /** config 派生的本插件真实安装 alias 记录(非 RPC 输入);同目录多别名须阻断。 */
  readonly pluginRecords?: readonly { id: string; source: string; path: string; enabled?: boolean }[];
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
  /** Constructor-only fixture seams; never provided by RPC or plugin entry. */
  readonly toolAssets?: readonly ToolAsset[];
  readonly allowInsecureAssetTransportForTests?: boolean;
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

// Enable/remove/Context Keeper/recovery confirmations never produce the bootstrap-only
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
  push("plan sha256", plan.plan_sha256);
  push("backup dir", plan.backup_dir);
  push("manifest", plan.manifest);
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
    const stages: Record<string, number> = {};
    for (const change of changes) {
      if (change && typeof change === "object" && "stage" in change) {
        const stage = String((change as Record<string, unknown>).stage);
        stages[stage] = (stages[stage] ?? 0) + 1;
      }
    }
    for (const [stage, count] of Object.entries(stages)) {
      rows.push({ label: `stage ${stage}`, value: `${count} 项` });
    }
  }
  // 统一验收口径:用户摘要仅 paths/hash/stage/证据;经历开关退役后不再展示
  // memory policy 转置行,内部 hex 正文一律不出摘要。
  const runtime = jsonRecord(plan.recovery_runtime);
  if (runtime) {
    push("recovery interpreter", runtime.interpreter);
    push("recovery interpreter sha256", runtime.executable_sha256);
  }
  const validation = jsonRecord(plan.validation);
  if (validation) {
    for (const [key, value] of Object.entries(validation)) rows.push({ label: `validation ${key}`, value: String(value) });
  }
  const retained = plan.retained_evidence as unknown[] | undefined;
  if (Array.isArray(retained)) rows.push({ label: "retained evidence", value: `${retained.length} 项(逐项见计划)` });
  const agents = (plan as Record<string, unknown>).agents;
  if (Array.isArray(agents)) rows.push({ label: "agents", value: agents.join(", ") });
  const projects = (plan as Record<string, unknown>).projects;
  if (Array.isArray(projects)) rows.push({ label: "projects", value: String(projects.length) });
  return rows;
}

// Context Keeper 执行计划携带的 journal 是本 HOME var/ck-install-*.json 的非事务审计件
// (无 layout.root,宿主与内核认领规则均永不可归结);照抄进操作记录会把已完成
// 的 Context Keeper 安装永久留成 staging 阻断。仅这一已知来源不写入记录——Context Keeper 审计原件与
// 计划批准材料原样保留。其余任何 journal(非 ck 流程、路径不符、他 HOME、
// 未知形态)一律原样写入,交由 staging 认领规则拒绝,不静默清洗。
export function recordJournalForOperation(flow: FlowKind, journal: unknown, home: string): unknown {
  if (flow !== "ck" || typeof journal !== "string" || !journal) return journal;
  const audit = path.join(home, ".mem-sharing", "var");
  return journal.startsWith(audit + path.sep)
    && /^ck-install-[A-Za-z0-9][A-Za-z0-9._-]*\.json$/.test(journal.slice(audit.length + 1))
    ? undefined
    : journal;
}

export class Orchestrator {
  private preparedContextKeeperSource?: string;
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
    const planJournal = this.pending.get(flow)?.plan.journal ?? (this.pending.get(flow)?.plan.plan as Record<string, unknown> | undefined)?.journal;
    const entry = { id: randomUUID(), flow, phase, journal: recordJournalForOperation(flow, planJournal, this.deps.home), home: this.deps.home, host: hostname(), state: "running", started_at: this.now().toISOString() };
    const save = () => { fs.ftruncateSync(recordFd); fs.writeSync(recordFd, JSON.stringify(entry), 0, "utf8"); fs.fsyncSync(recordFd); };
    this.running.set(flow, { controller, record });
    try {
      save();
      const result = await work(controller.signal);
      const out = result as Record<string, unknown>;
      if (flow === "fusion" && jsonRecord(out.envelope)?.status === "recovery_required" && typeof jsonRecord(out.envelope)?.manifest === "string") entry.journal = jsonRecord(out.envelope)!.manifest;
      entry.state = phase === "execute" && (controller.signal.aborted || (flow === "fusion" && jsonRecord(out.envelope)?.status === "recovery_required") || String(out.code).match(/cli_(timeout|canceled|spawn_error|stdout_invalid)/)) ? "unknown" : String(out.status);
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
    hash.update(JSON.stringify({ home: this.deps.home, host: hostname(), argv, release: this.releaseDigest(), toolAssets: this.assetBinding() }));
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

  private assets(): readonly ToolAsset[] {
    if (this.deps.toolAssets) return this.deps.toolAssets;
    if (process.platform !== "darwin") return [];
    if (Number.parseInt(release(), 10) < (process.arch === "arm64" ? 20 : 19)) return [];
    return PRODUCTION_TOOL_ASSETS.filter(a => a.arch === (process.arch === "x64" ? "x86_64" : process.arch));
  }

  private assetBinding(): string {
    return planDigest({ home: this.deps.home, host: hostname(), assets: this.assets(), scenes: this.assets().map(a => assetScene(this.paths.runtimeRoot, a)) });
  }

  private async dependencyPreviewImpl(): Promise<PreviewOutcome> {
    const [python, git] = await Promise.all([this.python(), this.git()]);
    const needed = ([...(python.status === "ready" ? [] : ["python"]), ...(git.status === "ready" ? [] : ["git"])]);
    if (!needed.length) return { status: "completed", envelope: { status: "tool_assets_ready", installation_complete: false } };
    const assets = this.assets().filter(a => needed.includes(a.tool));
    if (assets.length !== needed.length) return { status: "failed", code: "unsupported_runtime_supply", message: "No fixed supplier for this daemon OS/architecture" };
    const blocked = assets.filter(a => a.blockedReason);
    if (blocked.length) return { status: "failed", code: "supply_evidence_incomplete", message: blocked.map(a => `${a.tool}: ${a.blockedReason}`).join("; "), envelope: { assets } };
    const scenes = assets.map(a => assetScene(this.paths.runtimeRoot, a));
    if (scenes.some(s => s.state === "conflict")) return { status: "failed", code: "foreign_runtime_conflict", message: "Existing runtime differs from fixed archive; preserved without replacement", envelope: { scenes } };
    if (scenes.some(s => (s.lease as Record<string, unknown> | undefined)?.active)) return { status: "failed", code: "asset_busy", message: "Another dependency preparation owns a live lease" };
    const plan = { command: "prepare-tool-assets", home: this.deps.home, host: hostname(), assets, scenes,
      writes: assets.map((a, i) => ({ destination: scenes[i].destination, marker: "asset.json", exclusive_lease: "lease.json", download: "download-<exclusive-uuid>.tar.gz", extraction: "payload (exclusive; sibling .extract-<random> staging)", source: a.url, reuse: scenes[i].state === "ready", recovery: "interrupted owned downloads retained; retry requires a new preview/token", cleanup: "only this operation's inode-matching lease and download/extractor-owned partial staging; verified archives retained for audit", uninstall: "persists outside plugin directory" })), installation_complete: false };
    const stored = this.storePending("dependency", plan, "plan-plus-evidence", []);
    stored.summary.push(...assets.flatMap((a, i) => [
      { label: `${a.tool} version`, value: `${a.version} (${a.arch})` },
      { label: `${a.tool} source`, value: a.url },
      { label: `${a.tool} bytes / sha256`, value: `${a.bytes} / ${a.sha256}` },
      { label: `${a.tool} license`, value: `${a.license}; ${a.licenseUrls.join("; ")}` },
      { label: `${a.tool} notices`, value: `${a.noticeFile ?? "fixture"}; ${a.disclosure ?? "synthetic fixture"}` },
      { label: `${a.tool} minimum macOS`, value: a.minimumMacos ?? "fixture" },
      { label: `${a.tool} corresponding source`, value: a.sourceUrls.join("; ") },
      { label: `${a.tool} destination`, value: String(scenes[i].destination) },
    ]));
    return { status: "approval_required", planKind: "prepare-tool-assets", ...stored, plan };
  }

  private async dependencyConfirmImpl(input: { action: "confirm" | "reject"; confirmationToken?: string }, signal?: AbortSignal): Promise<PlanConfirmOutcome> {
    if (input.action === "reject") { this.pending.delete("dependency"); return { status: "rejected" }; }
    const popped = this.popPending("dependency", input.confirmationToken);
    if (!popped.ok) return popped.outcome as PlanConfirmOutcome;
    const assets = popped.pending.plan.assets as ToolAsset[];
    const scenes = popped.pending.plan.scenes as Record<string, unknown>[];
    for (let i = 0; i < assets.length; i++) {
      await prepareToolAsset({ runtimeRoot: this.paths.runtimeRoot, home: this.deps.home, asset: assets[i], scene: scenes[i], signal, allowInsecureTransportForTests: this.deps.allowInsecureAssetTransportForTests });
    }
    this.cachedPython = null; this.cachedGit = null;
    return { status: "completed", envelope: { status: "tool_assets_ready", installation_complete: false, next_action: "Resume original preview for a separate machine/source approval" } };
  }

  private reference(flow: FlowKind): string {
    return `paseo-plugin memsharing ${flow} confirm-screen user press`;
  }

  async python(): Promise<PythonEnvironment> {
    const privateAsset = this.assets().find(a => a.tool === "python" && assetScene(this.paths.runtimeRoot, a).state === "ready");
    if (privateAsset) return probePythonEnvironment({ runtimeRoot: "", systemCandidates: [path.join(assetDestination(this.paths.runtimeRoot, privateAsset), "payload", privateAsset.entry)] });
    if (this.deps.pythonProbe) return this.deps.pythonProbe();
    this.cachedPython ??= await probePythonEnvironment({ runtimeRoot: "" });
    return this.cachedPython;
  }

  async git(): Promise<GitEnvironment> {
    const privateAsset = this.assets().find(a => a.tool === "git" && assetScene(this.paths.runtimeRoot, a).state === "ready");
    if (privateAsset) return probeGitEnvironment({ candidateDirs: [path.join(assetDestination(this.paths.runtimeRoot, privateAsset), "payload", "bin")] });
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
    if (!python.ok) return this.dependencyPreviewImpl();
    const git = await this.git();
    if (git.status !== "ready") return this.dependencyPreviewImpl();
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
    if (exitKind === "completed" && parsed.status === "completed" && parsed.approval_plan === null && Array.isArray(parsed.changes) && parsed.changes.length === 0) {
      return { status: "completed", envelope: parsed };
    }
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

  // One detector: import the bundled/active kernel, without launching an Agent.
  async detectAgents(): Promise<{ status: "completed" | "failed"; envelope: Record<string, unknown> }> {
    const python = await this.requirePython();
    const installer = this.activeKernel()?.installer ?? this.payload().installerPath;
    if (!python.ok || !installer) return { status: "failed", envelope: { errors: [{ code: "kernel_or_python_missing" }] } };
    const script = "import sys,json;sys.path.insert(0,sys.argv[1]);from agm_core import detect,paths;config=paths.select_platform(paths.load_agents_table(),sys.platform);print(json.dumps(dict(status='completed',facts=detect.detect_agents(config,home=sys.argv[2]))))";
    const result = await this.runJson<PreviewOutcome>([python.pythonPath, "-B", "-c", script, path.dirname(installer), this.deps.home]);
    if ("failure" in result) return { status: "failed", envelope: { errors: [result.failure] } };
    return { status: result.exitKind === "completed" && result.parsed.status === "completed" ? "completed" : "failed", envelope: result.parsed };
  }

  private async requirePython(): Promise<{ ok: true; pythonPath: string } | { ok: false; detail: string }> {
    const env = await this.python();
    if (env.status === "ready" && env.selected) return { ok: true, pythonPath: env.selected.path };
    return { ok: false, detail: `python ${env.status}: ${env.candidates.map((c) => `${c.path}:${c.status}`).join("; ") || env.evidence}` };
  }

  private async runCli(argv: readonly string[], options?: { timeoutMs?: number; signal?: AbortSignal }): Promise<CliRunOutcome> {
    return this.deps.runner.run(argv, { timeoutMs: options?.timeoutMs ?? DEFAULT_TIMEOUT_MS, signal: options?.signal, env: toolEnvironment(this.paths.runtimeRoot, this.assets().find(a => a.tool === "git")) });
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
    if (this.productRemoved) {
      // 主产品已删除:宿主此后零写任何 mem-sharing-* 路径(含 staging 重建)。
      throw new Error("product removed: host must not recreate product staging paths");
    }
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
    // P1-A: stagingCleanup 是宿主自有实现,无 Python argv;kernelBinding 会以
    // argv[2] 走 path.dirname 而崩。改用独立 host 绑定,不伪造内核 argv。
    const binding = flow === "dependency" ? this.assetBinding()
      : flow === "stagingCleanup" ? createHash("sha256").update(JSON.stringify({ kind: "host-staging-cleanup", home: this.deps.home, host: hostname(), evidence_dir: plan.evidence_dir })).digest("hex")
      : this.kernelBinding(confirmArgv);
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
    try {
      currentBinding = flow === "dependency" ? this.assetBinding()
        : flow === "stagingCleanup" ? createHash("sha256").update(JSON.stringify({ kind: "host-staging-cleanup", home: this.deps.home, host: hostname(), evidence_dir: (pending.plan as Record<string, unknown>).evidence_dir })).digest("hex")
        : this.kernelBinding(pending.confirmArgv);
    }
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
      // enable templates carry placeholder evidence values; replace
      // only those two with real evidence while keeping every plan key
      // verbatim. rebuild_confirmation needs a SEPARATE user confirmation
      // and is never auto-filled from one click — such plans are blocked
      // before confirm ever runs (see projectEnablePreview).
      const { confirmed_at: _c, reference: _r, ...planKeys } = pending.plan;
      approval = buildApproval(planKeys as Record<string, unknown>, evidence);
    } else if (pending.approvalShape === "core-envelope") {
      // Uninstall/recovery/Context Keeper cores use a nested {plan, reference,
      // confirmed_at} envelope that must byte-match the previewed summary.
      approval = { plan: pending.plan, reference: evidence.reference, confirmed_at: evidence.confirmed_at };
    } else {
      approval = buildApproval(pending.plan, evidence);
    }
    const file = this.stagingFile(`${pending.flow}-approval.json`);
    fs.writeFileSync(file, JSON.stringify(approval, null, 2), { encoding: "utf8", mode: 0o600, flag: "wx" });
    return file;
  }

  // Approval writer for product-root-free flows (uninstall family): the
  // to-be-deleted tree must never gain new staging entries from the uninstall
  // itself. The approval lives in a 0600 tempfile OUTSIDE every product root
  // and is removed after the core subprocess returns; the core's manifest
  // durably records the approval, so nothing durable is lost.
  private buildExternalApprovalFile(pending: PendingPlan): string {
    const evidence = buildEvidence(this.reference(pending.flow), this.now());
    if (pending.approvalShape !== "core-envelope") {
      throw new Error("external approval writer only supports the core envelope shape");
    }
    const approval = { plan: pending.plan, reference: evidence.reference, confirmed_at: evidence.confirmed_at };
    const directory = fs.mkdtempSync(path.join(tmpdir(), "memsharing-uninstall-"));
    fs.chmodSync(directory, 0o700);
    const file = path.join(directory, "approval.json");
    fs.writeFileSync(file, JSON.stringify(approval, null, 2), { encoding: "utf8", mode: 0o600 });
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
  }, signal?: AbortSignal): Promise<PreviewOutcome> {
    const python = await this.requirePython();
    if (!python.ok) return this.dependencyPreviewImpl();
    const git = await this.git();
    if (git.status !== "ready") return this.dependencyPreviewImpl();
    const agm = this.activeKernelAgm();
    if (!agm) {
      return { status: "failed", code: "kernel_missing", message: "memSharing machine install not found; run onboarding first" };
    }
    // A plain enable call can legally WRITE without a new approval when a
    // consistent registered repair exists, so project previews must pass
    // the kernel's read-only --preview flag (mutually exclusive with
    // --approval-file, placed last per the frozen kernel contract). The
    // confirm argv never carries --preview. The retired --memory/--no-memory
    // switches are never passed; historical disabled projects surface as a
    // read-only gap (历史停用登记) in the kernel's own envelope.
    const previewArgv: string[] = [python.pythonPath, "-B", agm, "enable-memory", "--project", input.projectRoot];
    if (input.agents.length > 0) previewArgv.push("--agent", ...input.agents);
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
      const stored = this.storePending("enable", plan, "next-action-template", confirmArgv);
      return { status: "approval_required", planKind: "enable-memory", ...stored, plan, envelope: parsed };
    }
    if (parsed.status === "gaps") {
      // 历史停用登记等项目:内核只读预览返回 gaps,附明确 next_action;不作为
      // 可执行计划,交界面按提示展示,不猜测任何重建路径。
      return {
        status: "failed",
        code: "project_skipped",
        message: String(parsed.next_action ?? "项目预览未产生可执行计划（可能为历史停用登记项目）"),
        envelope: parsed,
      };
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

  // ---- whole-machine uninstall family (2026-11-01 retirement) ------------
  // Unified exit-code contract for the core flows: 5 approval_required,
  // 2 failed/recovery_required, 0 completed/restored/retained. The exit code
  // is validated TOGETHER with the structured envelope status; rc alone never
  // classifies an outcome.

  private productRemoved = false;

  private coreEnvelopeStatusValid(exitKind: string, parsed: Record<string, unknown>): boolean {
    const status = String(parsed.status ?? "");
    if (exitKind === "completed") return status === "completed" || status === "restored" || status === "retained";
    if (exitKind === "approval_required") return status === "approval_required";
    return status === "failed" || status === "recovery_required";
  }

  private corePlanFromEnvelope(parsed: Record<string, unknown>): Record<string, unknown> | null {
    const plan = jsonRecord(parsed.plan);
    return plan;
  }

  private async uninstallPreviewImpl(backupDir: string, signal?: AbortSignal): Promise<PreviewOutcome> {
    const staging = this.stagingInventory();
    const blockers = staging.entries.filter(e => e.disposition === "block");
    if (blockers.length || staging.entries.some(e => e.disposition === "preserve_external_then_clean")) {
      return {
        status: "failed",
        code: "staging_cleanup_required",
        message: "宿主 staging 存在待清理/阻断条目：先完成独立批准的 staging 清理（外置→删→host-receipt），再运行整机卸载预览。逐项原因见 staging inventory。",
        envelope: { entries: staging.entries.map(e => ({ path: e.path, activity: e.activity, disposition: e.disposition, reason: e.reason })) },
      };
    }
    const python = await this.requirePython();
    if (!python.ok) return this.dependencyPreviewImpl();
    const agm = this.activeKernelAgm();
    if (!agm) return { status: "failed", code: "kernel_missing", message: "memSharing machine install not found; nothing to uninstall" };
    // 材料外置:本流程不写产品 staging(无 operate()/stagingFile()),批准文件在
    // 确认时写 0600 系统 tmpdir 并于子进程返回后删除;核心 manifest 持久化批准。
    // host obligation(与呱唧定稿):声明 paseo 义务并绑定真实安装 ID+来源目录
    // +编译期 manifest 摘要(不硬编码 plugin_id);machine 完成=
    // machine_assets:completed/host_plugin:pending/overall:partial;removed 仅由
    // 外置 recover --check-host-plugin 同 daemon full-list 实查且 ID 不存在证
    // 明;disabled 永不解锁;本批无 manual fallback,不删 plugin 目录。
    const records = this.deps.pluginRecords ?? [];
    if (records.length > 1) {
      return {
        status: "failed",
        code: "host_plugin_ambiguous",
        message: "同一物理目录存在多个 config 安装别名(含 disabled 残留)，无法唯一定位本插件；请先在 Paseo 清理重复别名后重试："
          + records.map(r => `${r.id}(${r.source}:${r.path}${r.enabled === false ? ",disabled" : ""})`).join("; "),
      };
    }
    if (records.length === 0) return { status: "failed", code: "host_plugin_unknown", message: "缺少与当前加载来源匹配的唯一安装记录，不能声明宿主义务；请核对插件安装来源。" };
    const record = records[0];
    const previewArgv = [python.pythonPath, "-B", agm, "uninstall-machine", "--backup-dir", backupDir,
      "--host-obligation", "paseo",
      "--host-plugin-id", record.id, "--host-plugin-source", record.path,
      "--host-plugin-record-json", JSON.stringify({ id: record.id, source: record.source, path: record.path, enabled: record.enabled !== false }),
      ...(isSha256Hex(this.releaseDigest()) ? ["--host-plugin-manifest-sha256", this.releaseDigest()] : [])];
    const result = await this.runJson<PreviewOutcome>(previewArgv, { signal });
    if ("failure" in result) return result.failure;
    const { parsed, exitKind } = result;
    if (!this.coreEnvelopeStatusValid(exitKind, parsed)) {
      return { status: "failed", code: "cli_status_mismatch", message: `退出码与结构化状态不一致: rc=${exitKind} status=${String(parsed.status)}`, envelope: parsed };
    }
    if (exitKind === "approval_required") {
      const plan = this.corePlanFromEnvelope(parsed);
      if (!plan) return { status: "failed", code: "plan_unavailable", message: "uninstall preview did not expose a summary plan", envelope: parsed };
      const stored = this.storePending("uninstall", plan, "core-envelope", previewArgv);
      return { status: "approval_required", planKind: "uninstall-machine", ...stored, plan };
    }
    if (exitKind === "completed") return { status: "completed", envelope: parsed };
    return { status: "failed", code: String(parsed.errors && Array.isArray(parsed.errors) && parsed.errors[0]?.code ? parsed.errors[0].code : "uninstall_failed"), message: `uninstall preview failed: ${JSON.stringify(parsed.errors ?? parsed.status)}`, envelope: parsed };
  }

  private async uninstallConfirmImpl(input: { action: "confirm" | "reject"; confirmationToken?: string }, signal?: AbortSignal): Promise<ConfirmOutcome> {
    if (input.action === "reject") { this.pending.delete("uninstall"); return { status: "rejected" }; }
    const popped = this.popPending("uninstall", input.confirmationToken);
    if (!popped.ok) return popped.outcome;
    const approvalFile = this.buildExternalApprovalFile(popped.pending);
    try {
      const argv = [...popped.pending.confirmArgv, "--approval-file", approvalFile];
      const result = await this.runJson<ConfirmOutcome>(argv, { signal });
      if ("failure" in result) return result.failure;
      const { parsed, exitKind } = result;
      if (!this.coreEnvelopeStatusValid(exitKind, parsed)) {
        return { status: "failed", code: "cli_status_mismatch", message: `退出码与结构化状态不一致: rc=${exitKind} status=${String(parsed.status)}`, envelope: parsed };
      }
      if (exitKind === "completed") {
        // 主产品已删除:宿主此后零写任何 mem-sharing-* 路径(含 staging 重建)。
        this.productRemoved = true;
        return { status: "completed", envelope: parsed };
      }
      return { status: "failed", code: `exit_${exitKind}`, message: `uninstall confirm failed: ${JSON.stringify(parsed.errors ?? parsed.status)}`, envelope: parsed };
    } finally {
      try { fs.rmSync(path.dirname(approvalFile), { recursive: true, force: true }); } catch { /* tempfile cleanup is best-effort */ }
    }
  }

  // Read-only staging inventory; no path inputs, entries keyed by id. This
  // RPC never grants deletion rights — cleanup happens only inside the
  // separately approved host cleanup flow.
  stagingInventory() {
    const root = this.paths.pluginStagingRoot;
    const entries: {
      id: string; kind: "plugin_staging_op"; path: string;
      ownership: "proven" | "unverified"; activity: "running" | "terminal" | "unknown";
      activity_evidence: Record<string, unknown>;
      disposition: "preserve_external_then_clean" | "block" | "retain"; reason: string;
    }[] = [];
    const notes: string[] = ["内存确认令牌不是文件；运行中操作以 in-memory running 表为准"];
    let pendingDir: string | null = null;
    try {
      const dir = path.join(root, "pending");
      if (fs.lstatSync(dir).isDirectory() && !fs.lstatSync(dir).isSymbolicLink()) pendingDir = dir;
    } catch { /* absent staging root is fine */ }
    if (pendingDir !== null) {
      const knownArtifacts = /^([a-z]+-approval\.json|release-request\.json)$/;
      for (const name of fs.readdirSync(pendingDir)) {
        if (!/^op-[A-Za-z0-9]+$/.test(name)) continue;
        const dirPath = path.join(pendingDir, name);
        const id = createHash("sha256").update(`plugin_staging_op:${name}`).digest("hex");
        let activity: "running" | "terminal" | "unknown" = "unknown";
        let recordState: string | null = null;
        let journalStatus: string | null = null;
        let recordPhase: string | null = null;
        let recordFlow: string | null = null;
        let ownership: "proven" | "unverified" = "proven";
        let reason = "";
        const artifactHashes: { name: string; sha256: string; mode: number }[] = [];
        try {
          const st = fs.lstatSync(dirPath);
          if (!st.isDirectory() || st.isSymbolicLink()) throw new Error("not a real directory");
          const runningRecord = [...this.running.values()].some(r => path.dirname(r.record) === dirPath);
          for (const file of fs.readdirSync(dirPath).sort()) {
            const filePath = path.join(dirPath, file);
            if (fs.lstatSync(filePath).isSymbolicLink() || !fs.lstatSync(filePath).isFile()) throw new Error("unknown artifact node: " + file);
            if (file === "operation.json") {
              const record = JSON.parse(fs.readFileSync(filePath, "utf8"));
              const keys = new Set(Object.keys(record));
              // 历史记录 journal=undefined 时 JSON.stringify 省略该键(7 键);
              // 兼容已知 7/8 键,其余未知键拒绝(与核心口径一致)。
              const expected = new Set(["id", "flow", "phase", "journal", "home", "host", "state", "started_at"]);
              if (!((keys.size === 8) || (keys.size === 7 && !keys.has("journal"))) || [...keys].some(k => !expected.has(k))) throw new Error("operation record schema invalid");
              if (record.home !== this.deps.home || record.host !== hostname()) throw new Error("operation record home/host mismatch");
              // flow 白名单=会写 staging 的七个 operate() 流程;核心按固定列表校验,
              // 新流程(stagingCleanup/ckUninstall)从不写产品 staging。
              if (!["dependency", "bootstrap", "machine", "enable", "remove", "ck", "recover"].includes(String(record.flow))) throw new Error("operation record flow not recognized: " + String(record.flow));
              recordState = String(record.state);
              recordPhase = String(record.phase); recordFlow = String(record.flow);
              if (!["preview","execute"].includes(recordPhase)) throw new Error("operation phase unknown");
              // journal 非 null(旧 machine/recover execute 正常可达):宿主按
              // operationStatus() 同规则实读原 journal 归结——绝对真实路径、
              // plan.layout.root 匹配本机 R、status∈{committed,rolled_back} 才算
              // 终态 recovered 并写准确 journal_status;否则 unknown 阻断不删。
              if (typeof record.journal === "string" && record.journal) {
                // journal 归属:仅认核心既有固定根 home/.mem-sharing-install-*/journal.json
                // 或 R/backups/<op>/(journal|manifest).json;任意路径不可认领(与核心一致)。
                const relJournal = path.relative(this.deps.home, record.journal);
                const legalJournal = new RegExp("^(\\.mem-sharing-install-[^/]+/journal\\.json|\\.mem-sharing/backups/[^/]+/(journal|manifest)\\.json)$").test(relJournal);
                let resolved: string | null = null;
                try {
                  if (!legalJournal) throw new Error("journal path outside known roots");
                  if (fs.realpathSync(record.journal) === record.journal && fs.lstatSync(record.journal).isFile()) {
                    const journal = JSON.parse(fs.readFileSync(record.journal, "utf8")) as { status?: unknown; plan?: { layout?: { root?: unknown } } };
                    if (journal?.plan?.layout?.root === path.join(this.deps.home, ".mem-sharing")
                        && (journal.status === "committed" || journal.status === "rolled_back")) resolved = journal.status;
                  }
                } catch { /* 原始 journal 仍是唯一权威;不可读即不可归结 */ }
                if (resolved) { journalStatus = resolved; recordState = "recovered"; }
                else throw new Error("record journal 不可归结(缺失/非终态/布局不符): " + record.journal);
              }
            } else if (!knownArtifacts.test(file)) {
              throw new Error("unknown artifact: " + file);
            }
            artifactHashes.push({ name: file, sha256: createHash("sha256").update(fs.readFileSync(filePath)).digest("hex"), mode: fs.lstatSync(filePath).mode & 0o777 });
          }
          if (runningRecord) { activity = "running"; reason = "in-memory operation still running"; }
          else if (recordState !== null && recordState === "running") { activity = "unknown"; reason = "record says running without in-memory owner; only the original kernel journal can resolve"; }
          else if (recordState !== null && (["completed", "failed", "rejected", "approval_required", "gaps", "recovered"].includes(recordState) || (recordPhase === "preview" && ["already_prepared","identity_missing","payload_missing"].includes(recordState)) || (recordPhase === "execute" && ["stale_plan","no_pending_plan"].includes(recordState)) || (recordPhase === "execute" && recordFlow === "bootstrap" && recordState === "acquired"))) { activity = "terminal"; reason = "record terminal state: " + recordState; }
          else if (recordState === null) {
            const oldest = Math.max(...artifactHashes.map(a => fs.lstatSync(path.join(dirPath, a.name)).mtimeMs));
            if (this.now().getTime() - oldest > 10 * 60 * 1000) { activity = "terminal"; reason = "no operation record; known artifacts older than pending TTL"; }
            else { activity = "unknown"; reason = "no operation record and artifacts younger than TTL"; }
          } else { activity = "unknown"; reason = "unrecognized record state: " + recordState; }
        } catch (error) {
          ownership = "unverified";
          activity = "unknown";
          reason = String(error);
        }
        entries.push({
          id, kind: "plugin_staging_op", path: dirPath, ownership, activity,
          activity_evidence: { record_state: recordState ?? "no_operation_record", in_memory_running: activity === "running", journal_status: journalStatus, artifacts: artifactHashes },
          disposition: ownership === "proven" && activity === "terminal" ? "preserve_external_then_clean" : "block",
          reason: ownership === "proven" && activity === "terminal" ? reason : `拒绝认领: ${reason}`,
        });
      }
    }
    return {
      schema_version: 1 as const,
      home: this.deps.home,
      host: hostname(),
      roots: { plugin_staging: root, durable_sources: this.paths.durableSourceRoot, private_runtimes: this.paths.runtimeRoot },
      entries,
      notes,
    };
  }

  // ---- separately approved host staging cleanup (writes host-receipt) -----
  // 独立交互,不隐藏:只读预览 → 单独精确用户批准 → 逐字节外置(保留 mtime)并
  // 校验 → 删前复核无新文件 → 删除 op 目录 → staging 根仅余 host-receipt.json。
  // uninstallPreview 绝不自动清目录或写 receipt(巴克 2026-11-01 裁定)。

  private productRoots(): string[] {
    const p = this.paths;
    return [path.join(this.deps.home, ".mem-sharing"), p.codeRoot, p.durableSourceRoot, p.runtimeRoot,
            p.pluginStagingRoot, path.join(this.deps.home, ".local", "share", "mem-sharing-versions")];
  }

  private validateExternalEvidenceDir(evidenceDir: string): { ok: true; backupRoot: string } | { ok: false; message: string } {
    // P1 修复:预览必须零写——只读校验,不 mkdir;evidenceDir 须已存在且整条
    // 祖先链为真实目录(无符号链接),backupRoot 须尚不存在。
    if (!path.isAbsolute(evidenceDir) || path.resolve(evidenceDir) !== evidenceDir) return { ok: false, message: "外置证据目录必须是规范绝对路径" };
    const backupRoot = path.join(evidenceDir, "memsharing-host-staging");
    for (const root of this.productRoots()) {
      if (backupRoot === root || backupRoot.startsWith(root + path.sep) || root.startsWith(backupRoot + path.sep)) {
        return { ok: false, message: "外置证据目录不得与任何产品根重叠: " + root };
      }
    }
    const chain: string[] = [];
    let current = evidenceDir;
    for (;;) {
      chain.push(current);
      const parent = path.dirname(current);
      if (parent === current) break;
      current = parent;
    }
    for (const dir of chain.reverse()) {
      let st: fs.Stats;
      try { st = fs.lstatSync(dir); } catch { return { ok: false, message: "外置证据目录或其祖先不存在(预览零写,不创建): " + dir }; }
      if (!st.isDirectory() || st.isSymbolicLink()) return { ok: false, message: "外置证据目录祖先不是真实目录: " + dir };
      if (dir === evidenceDir && fs.existsSync(backupRoot)) return { ok: false, message: "外置证据树已存在，须使用新目录: " + backupRoot };
    }
    return { ok: true, backupRoot };
  }

  private stagingCleanupPreviewImpl(evidenceDir: string): PreviewOutcome {
    const validated = this.validateExternalEvidenceDir(evidenceDir);
    if (!validated.ok) return { status: "failed", code: "evidence_dir_invalid", message: validated.message };
    const inventory = this.stagingInventory();
    const blockers = inventory.entries.filter(e => e.disposition === "block");
    if (blockers.length) {
      return {
        status: "failed",
        code: "staging_blocked",
        message: "存在活跃/未知 staging 条目，清理中止（逐项原因见 envelope）；解决或显式保留后再试。",
        envelope: { entries: blockers.map(b => ({ path: b.path, activity: b.activity, reason: b.reason })) },
      };
    }
    const claimable = inventory.entries.filter(e => e.disposition === "preserve_external_then_clean");
    const plan = {
      command: "host-staging-cleanup",
      home: this.deps.home,
      host: hostname(),
      evidence_dir: evidenceDir,
      backup_root: validated.backupRoot,
      entries: claimable.map(e => ({ dir: path.basename(e.path), path: e.path, activity_evidence: e.activity_evidence })),
      receipt_path: path.join(this.paths.pluginStagingRoot, "host-receipt.json"),
    };
    const stored = this.storePending("stagingCleanup", plan, "plan-plus-evidence", []);
    return { status: "approval_required", planKind: "host-staging-cleanup", ...stored, plan };
  }

  private stagingCleanupConfirmImpl(input: { action: "confirm" | "reject"; confirmationToken?: string }): PlanConfirmOutcome {
    if (input.action === "reject") { this.pending.delete("stagingCleanup"); return { status: "rejected" }; }
    const popped = this.popPending("stagingCleanup", input.confirmationToken);
    if (!popped.ok) return popped.outcome as PlanConfirmOutcome;
    type Artifact = { name: string; sha256: string; mode: number };
    type PlanEntry = { dir: string; path: string; activity_evidence: { record_state?: string; in_memory_running?: boolean; journal_status?: string | null; artifacts?: Artifact[] } };
    const plan = popped.pending.plan as unknown as { evidence_dir: string; backup_root: string; entries: PlanEntry[]; receipt_path: string };
    const digest = planDigest(popped.pending.plan);
    // P1-B:重建计划仅作比较,必须与获批计划深度相等(目录/工件 name+sha256+mode/
    // 状态任何变化、新增目录或阻断条目)——比较失败零外置零删除。
    const rebuilt = this.stagingCleanupPreviewImpl(plan.evidence_dir);
    if (rebuilt.status !== "approval_required"
        || planDigest((rebuilt as { plan?: Record<string, unknown> }).plan as Record<string, unknown>) !== digest) {
      return { status: "stale_plan", detail: "staging 现场与清理计划不符（文件字节/模式/状态变化或新增），请重新预览" };
    }
    const fsyncDir = (directory: string): void => {
      const fd = fs.openSync(directory, "r");
      try { fs.fsyncSync(fd); } finally { fs.closeSync(fd); }
    };
    let backupRootCreated = false;
    try {
      fs.mkdirSync(plan.backup_root, { mode: 0o700, recursive: false });
      backupRootCreated = true;
      // 外置:严格迭代获批 entries/artifacts(绝不采纳现场新内容);copy 保留 mode
      // 与 mtime(供核心核 TTL),逐文件字节校验+fsync。
      for (const entry of plan.entries) {
        const target = path.join(plan.backup_root, entry.dir);
        fs.mkdirSync(target, { mode: 0o700 });
        for (const artifact of entry.activity_evidence.artifacts ?? []) {
          const sourceFile = path.join(entry.path, artifact.name);
          const stat = fs.lstatSync(sourceFile);
          if (stat.isSymbolicLink() || !stat.isFile() || (stat.mode & 0o777) !== artifact.mode
              || createHash("sha256").update(fs.readFileSync(sourceFile)).digest("hex") !== artifact.sha256) {
            throw Object.assign(new Error("外置前复核失败(字节/模式变化): " + sourceFile), { code: "staging_changed_before_externalize" });
          }
          const targetFile = path.join(target, artifact.name);
          fs.copyFileSync(sourceFile, targetFile);
          fs.chmodSync(targetFile, stat.mode & 0o777);
          fs.utimesSync(targetFile, stat.atime, stat.mtime);
          if (createHash("sha256").update(fs.readFileSync(targetFile)).digest("hex") !== artifact.sha256) {
            throw Object.assign(new Error("外置拷贝字节校验失败: " + targetFile), { code: "externalize_verify_failed" });
          }
          const fd = fs.openSync(targetFile, "r+");
          try { fs.fsyncSync(fd); } finally { fs.closeSync(fd); }
        }
        fsyncDir(target);
      }
      // P1-C:外置目录层级全部持久化(backup_root 与 evidence_dir),任一 fsync
      // 失败零源删除;保留外置证据,重试使用新证据目录。
      fsyncDir(plan.backup_root);
      fsyncDir(plan.evidence_dir);
    } catch (error) {
      // External evidence may now contain unapproved additions. Preserve it
      // on failure; never recursively reclaim a root after exposing it.
      const code = (error as { code?: string }).code ?? "externalize_failed";
      return { status: "failed", code, message: String((error as Error).message ?? error) + (backupRootCreated ? "；外置失败证据已保留，重试须选新证据目录：" + plan.backup_root : ""),
        envelope: { backup_root: plan.backup_root, partial_evidence_retained: backupRootCreated, source_deletion_started: false } };
    }
    // P1-C:删第一源之前核全树 digest(双算一致)。
    const treeFirst = toolTreeDigest(plan.backup_root);
    if (treeFirst !== toolTreeDigest(plan.backup_root)) {
      return { status: "failed", code: "external_tree_unstable", message: "外置树 digest 不稳定，零删除" };
    }
    // 删除:逐获批工件先复核 hash+mode 再 unlink;目录 rmdir 收尾,未知新文件令
    // rmdir 失败并保留现场(已核验工件已外置),绝不递归吞删。
    for (const entry of plan.entries) {
      for (const artifact of entry.activity_evidence.artifacts ?? []) {
        const sourceFile = path.join(entry.path, artifact.name);
        const stat = fs.lstatSync(sourceFile);
        if (stat.isSymbolicLink() || !stat.isFile()
            || (stat.mode & 0o777) !== artifact.mode
            || createHash("sha256").update(fs.readFileSync(sourceFile)).digest("hex") !== artifact.sha256) {
          return { status: "failed", code: "staging_changed_before_delete", message: "删除前复核失败(字节/模式变化): " + sourceFile };
        }
        fs.unlinkSync(sourceFile);
      }
      try { fs.rmdirSync(entry.path); } catch (error) {
        return { status: "failed", code: "staging_dir_not_empty", message: "目录存在未核验新文件，已保留现场: " + entry.path + " (" + String(error) + ")" };
      }
    }
    const pendingRoot = path.join(this.paths.pluginStagingRoot, "pending");
    if (fs.existsSync(pendingRoot) && fs.readdirSync(pendingRoot).length === 0) fs.rmdirSync(pendingRoot);
    // 单一时刻供 generated_at 与 confirmed_at 共用:真实时钟下两次 now() 会令
    // confirmed_at > generated_at,核心按"receipt 不得早于批准"拒绝(呱唧实读发现)。
    const confirmedAt = this.now().toISOString();
    const receipt = {
      schema_version: 1, product_id: "mem-sharing", kind: "host-staging-retired",
      home: this.deps.home, host: hostname(), staging_root: this.paths.pluginStagingRoot,
      backup_root: plan.backup_root, backup_tree_sha256: treeFirst,
      generated_at: confirmedAt, status: "completed",
      approval: { digest, confirmed_at: confirmedAt, reference: "paseo-plugin memsharing stagingCleanup confirm-screen user press" },
      terminal_evidence: plan.entries.map((entry) => ({
        dir: entry.dir,
        record_state: entry.activity_evidence.record_state ?? "no_operation_record",
        in_memory_running: false,
        journal_status: (entry.activity_evidence as { journal_status?: string | null }).journal_status ?? null,
        artifacts: (entry.activity_evidence.artifacts ?? []).map(({ name, sha256 }: Artifact) => ({ name, sha256 })),
      })),
    };
    fs.mkdirSync(this.paths.pluginStagingRoot, { mode: 0o700, recursive: true });
    fs.writeFileSync(plan.receipt_path, JSON.stringify(receipt, null, 2), { encoding: "utf8", mode: 0o600 });
    const receiptFd = fs.openSync(plan.receipt_path, "r+");
    try { fs.fsyncSync(receiptFd); } finally { fs.closeSync(receiptFd); }
    fsyncDir(this.paths.pluginStagingRoot);
    return {
      status: "completed",
      envelope: { status: "completed", command: "host-staging-cleanup", receipt: plan.receipt_path, backup_root: plan.backup_root, backup_tree_sha256: treeFirst, externalized: plan.entries.length },
    };
  }

  private ckFollowUpInputs(manifest: string): { interpreter: string; recoverPy: string } | { error: string } {
    try {
      if (!path.isAbsolute(manifest) || fs.realpathSync(manifest) !== manifest) return { error: "manifest 必须是绝对真实路径" };
      const data = JSON.parse(fs.readFileSync(manifest, "utf8"));
      if (data.status !== "completed") return { error: "主 manifest 必须 completed" };
      const interpreter = data?.plan?.recovery_runtime?.interpreter;
      if (typeof interpreter !== "string" || !interpreter) return { error: "主结果未绑定独立解释器" };
      const recoverPy = path.join(path.dirname(manifest), "recover.py");
      if (!fs.lstatSync(recoverPy).isFile()) return { error: "外置 recover.py 缺失" };
      return { interpreter, recoverPy };
    } catch (error) {
      return { error: String(error) };
    }
  }

  private async runRecoverPy(argv: readonly string[], signal?: AbortSignal): Promise<{ parsed: Record<string, unknown> | null; exitKind: string; raw: CliRunOutcome }> {
    const outcome = await this.runCli(argv, { signal });
    if (outcome.kind !== "completed") return { parsed: null, exitKind: `cli_${outcome.kind}`, raw: outcome };
    const parsed = parseCliJson(outcome.stdout ?? "");
    const value = parsed.ok ? jsonRecord(parsed.value) : null;
    const exitKind = classifyExitCode(outcome.exitCode ?? -1);
    return { parsed: value, exitKind, raw: outcome };
  }

  async ckChoiceRetain(manifest: string): Promise<{ status: "completed" | "failed"; envelope?: Record<string, unknown>; code?: string; message?: string }> {
    const inputs = this.ckFollowUpInputs(manifest);
    if ("error" in inputs) return { status: "failed", code: "ck_followup_binding_missing", message: inputs.error };
    const { parsed, exitKind } = await this.runRecoverPy([inputs.interpreter, "-I", "-S", "-B", inputs.recoverPy, "--manifest", manifest, "--ck-choice", "retain"]);
    if (parsed && this.coreEnvelopeStatusValid(exitKind, parsed) && exitKind === "completed") return { status: "completed", envelope: parsed };
    return { status: "failed", code: "ck_retain_failed", message: `retain: rc=${exitKind} status=${String(parsed?.status ?? "unparseable")}` };
  }

  private async ckUninstallPreviewImpl(input: { manifest: string; ckSource: string; ckAgents: readonly string[]; ckProject?: string }, signal?: AbortSignal): Promise<PreviewOutcome> {
    const inputs = this.ckFollowUpInputs(input.manifest);
    if ("error" in inputs) return { status: "failed", code: "ck_followup_binding_missing", message: inputs.error };
    // source 必须用户显式选择;不自动定位、不自动执行。
    if (!path.isAbsolute(input.ckSource) || fs.realpathSync(input.ckSource) !== input.ckSource) {
      return { status: "failed", code: "ck_source_invalid", message: "Context Keeper source 必须是用户显式选择的绝对真实路径" };
    }
    const argv = [inputs.interpreter, "-I", "-S", "-B", inputs.recoverPy, "--manifest", input.manifest, "--ck-choice", "uninstall", "--ck-source", input.ckSource];
    for (const agent of input.ckAgents) argv.push("--ck-agent", agent);
    if (input.ckProject) argv.push("--ck-project", input.ckProject);
    const { parsed, exitKind } = await this.runRecoverPy(argv, signal);
    if (!parsed || !this.coreEnvelopeStatusValid(exitKind, parsed)) {
      return { status: "failed", code: "cli_status_mismatch", message: `Context Keeper 预览: rc=${exitKind} status=${String(parsed?.status ?? "unparseable")}` };
    }
    if (exitKind === "approval_required") {
      const plan = this.corePlanFromEnvelope(parsed);
      if (!plan) return { status: "failed", code: "plan_unavailable", message: "Context Keeper preview did not expose a plan" };
      const stored = this.storePending("ckUninstall", plan, "core-envelope", argv);
      return { status: "approval_required", planKind: "uninstall-context-keeper", ...stored, plan };
    }
    return { status: "failed", code: String(parsed.status ?? "ck_unavailable"), message: `Context Keeper preview: ${JSON.stringify(parsed.errors ?? parsed.status)}`, envelope: parsed };
  }

  private async ckUninstallConfirmImpl(input: { action: "confirm" | "reject"; confirmationToken?: string }, signal?: AbortSignal): Promise<PlanConfirmOutcome> {
    if (input.action === "reject") { this.pending.delete("ckUninstall"); return { status: "rejected" }; }
    const popped = this.popPending("ckUninstall", input.confirmationToken);
    if (!popped.ok) return popped.outcome as PlanConfirmOutcome;
    // 独立 Context Keeper 批准,绝不复用主 uninstall 批准;批准文件仍走外置临时文件。
    const approvalFile = this.buildExternalApprovalFile(popped.pending);
    try {
      const argv = [...popped.pending.confirmArgv, "--ck-approval-file", approvalFile];
      const { parsed, exitKind } = await this.runRecoverPy(argv, signal);
      if (!parsed || !this.coreEnvelopeStatusValid(exitKind, parsed)) {
        return { status: "failed", code: "cli_status_mismatch", message: `Context Keeper 执行: rc=${exitKind} status=${String(parsed?.status ?? "unparseable")}`, envelope: parsed ?? undefined };
      }
      if (exitKind === "completed") return { status: "completed", envelope: parsed };
      return { status: "failed", code: `exit_${exitKind}`, message: `Context Keeper confirm failed: ${JSON.stringify(parsed.errors ?? parsed.status)}`, envelope: parsed };
    } finally {
      try { fs.rmSync(path.dirname(approvalFile), { recursive: true, force: true }); } catch { /* best-effort */ }
    }
  }

  // ---- optional Context Keeper user install (independent approval) ----

  private async ckPreviewImpl(ckSource?: string, signal?: AbortSignal): Promise<PreviewOutcome> {
    const python = await this.requirePython();
    if (!python.ok) return this.dependencyPreviewImpl();
    const git = await this.git();
    if (git.status !== "ready") return this.dependencyPreviewImpl();
    const kernel = this.activeKernel();
    if (!kernel) {
      return { status: "failed", code: "kernel_missing", message: "memSharing machine install not found; Context Keeper is a separate optional step after it" };
    }
    // Every new install intent first fetches current main after source approval.
    ckSource = ckSource ?? this.preparedContextKeeperSource;
    this.preparedContextKeeperSource = undefined;
    if (!ckSource) {
      const plan = ckAcquisitionPlan(this.deps.home);
      const stored = this.storePending("ck", plan, "plan-plus-evidence", [python.pythonPath, "-B", kernel.installer]);
      return { status: "approval_required", planKind: "prepare-context-keeper-source", ...stored, plan };
    }
    const previewArgv = [python.pythonPath, "-B", kernel.installer, "--context-keeper", "--ck-preview-only"];
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
    return {
      status: "failed",
      code: String((parsed.errors as Record<string, unknown>[] | undefined)?.[0]?.code ?? "ck_unavailable"),
      message: `Context Keeper preview: ${JSON.stringify(parsed.errors ?? parsed.status)}`,
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
      if (planDigest(popped.pending.plan) !== planDigest(ckAcquisitionPlan(this.deps.home))) return { status: "stale_plan", detail: "Context Keeper acquisition target changed" };
      const git = await this.git();
      if (git.status !== "ready" || !git.path) return { status: "failed", code: "git_missing", message: git.detail };
      const source = await acquireCkSource(this.deps.home, git.path, { run: (argv, options) => this.runCli(argv, options) }, signal);
      this.preparedContextKeeperSource = source;
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
      message: `Context Keeper confirm failed: ${JSON.stringify(parsed.errors ?? parsed.status)}`,
      envelope: parsed,
    };
  }

  // ---- recovery of an interrupted machine operation ----

  private async recoverPreviewImpl(input: { journalPath: string; action?: "continue" | "rollback" }, signal?: AbortSignal): Promise<PreviewOutcome> {
    const python = await this.requirePython();
    if (!python.ok) return this.dependencyPreviewImpl();
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

  private fusionContext?: { token: string; binding: string; plan: Record<string, unknown>; scope: string; project?: string; proposals?: Pick<FusionInput, "equivalentSources" | "publicReuse"> };

  async fusionPreview(input: { scope: "user" | "project"; projectRoot?: string; selection?: string;
    decline?: boolean; contextToken?: string; retentions?: Record<string, string> }, signal?: AbortSignal) {
    if (input.selection || input.decline || input.retentions) return { status: "failed" as const, envelope: { errors: [{ code: "use_fusion_select" }] } };
    return this.fusionRun(input, false, signal);
  }

  async fusionPropose(input: FusionInput, signal?: AbortSignal) {
    const context = this.fusionContext;
    if (!input.contextToken || context?.token !== input.contextToken || context.scope !== input.scope || context.project !== input.projectRoot) return { status: "failed" as const, envelope: { errors: [{ code: "stale_fusion_context" }] } };
    // Revalidate the displayed scene first; proposals are judgments, never authority.
    const fresh = await this.fusionRun({ scope: input.scope, projectRoot: input.projectRoot }, false, signal);
    const current = this.fusionContext;
    if (fresh.status !== "completed" || !current || context.binding !== current.binding || ["layout", "observations", "groups", "agents", "scope", "project"].some(key => planDigest({ value: context.plan[key] }) !== planDigest({ value: current.plan[key] }))) {
      this.fusionContext = undefined;
      return { status: "failed" as const, envelope: { errors: [{ code: "fusion_scene_changed_preview_again" }] } };
    }
    const proposed = await this.fusionRun({ ...input, contextToken: undefined }, false, signal);
    const proposedScene = this.fusionContext;
    if (proposed.status !== "completed" || !proposedScene || ["layout", "observations", "agents", "scope", "project"].some(key => planDigest({ value: context.plan[key] }) !== planDigest({ value: proposedScene.plan[key] }))) {
      this.fusionContext = undefined;
      return { status: "failed" as const, envelope: { errors: [{ code: "fusion_scene_changed_preview_again" }] } };
    }
    return proposed;
  }

  async fusionSelect(input: FusionInput, signal?: AbortSignal) {
    return this.fusionRun(input, true, signal);
  }

  private async fusionRun(input: FusionInput, execute: boolean, signal?: AbortSignal): Promise<{
    status: "completed" | "failed"; envelope: Record<string, unknown>; contextToken?: string; approval?: PreviewOutcome }> {
    return this.operate("fusion", execute ? "execute" : "preview", signal, async owned => {
      const fail = (code: string, envelope: Record<string, unknown> = {}) => ({ status: "failed" as const, envelope: { ...envelope, errors: [{ code, message: code }] } });
      if (input.scope === "project" && (!input.projectRoot || !path.isAbsolute(input.projectRoot))) return fail("project_required");
      const context = this.fusionContext;
      if (execute && (!input.contextToken || context?.token !== input.contextToken || context.scope !== input.scope || context.project !== input.projectRoot)) return fail("stale_fusion_context");
      if (execute && !input.selection && !input.decline) return fail("selection_required");
      const python = await this.requirePython(); const agm = this.activeKernelAgm();
      if (!python.ok || !agm) return fail("kernel_or_python_missing");
      const base = [python.pythonPath, "-B", agm, input.scope === "project" ? "organize-project-memory" : "organize-user-memory"];
      if (input.scope === "project") base.push("--project", input.projectRoot!);
      const binding = this.kernelBinding(base);
      if (execute && context!.binding !== binding) return fail("fusion_kernel_changed_preview_again");
      const argv = [...base];
      const directory = fs.mkdtempSync(path.join(tmpdir(), "memsharing-fusion-input-"));
      fs.chmodSync(directory, 0o700);
      const write = (name: string, value: unknown) => {
        const file = path.join(directory, name);
        fs.writeFileSync(file, JSON.stringify(value), { mode: 0o600, flag: "wx" }); return file;
      };
      try {
        if (input.decline) argv.push("--decline");
        else if (input.selection) {
          argv.push("--selection", input.selection);
          // The kernel compares the complete displayed scene before any write.
          if (!input.selection.trim().startsWith("查看")) argv.push("--selection-plan-file", write("shown.json", context!.plan), "--selection-reference", `Paseo user selection: ${input.selection}`);
        }
        const proposals = execute ? context!.proposals : input;
        if (proposals?.equivalentSources) argv.push("--equivalent-sources-file", write("equivalent.json", proposals.equivalentSources));
        if (proposals?.publicReuse) argv.push("--public-reuse-file", write("reuse.json", proposals.publicReuse));
        // Retentions affect a project selection only; 查看/decline must stay
        // independent of any supplied retention map, even for direct RPC callers.
        if (input.scope === "project" && input.retentions && input.selection && !input.decline && !input.selection.trim().startsWith("查看")) {
          argv.push("--retention-file", write("retentions.json", input.retentions));
        }
        const result = await this.runJson<PreviewOutcome>(argv, { signal: owned });
        if ("failure" in result) return fail(result.failure.status === "failed" ? result.failure.code : "cli_failed");
        const { parsed, exitKind } = result;
        if (exitKind === "failed" || !["approval_required", "viewed", "completed"].includes(String(parsed.status))) return { status: "failed", envelope: parsed };
        const terminal = ["completed", "declined", "unchanged"].includes(String(parsed.fusion_status));
        if (terminal) { this.fusionContext = undefined; return { status: "completed", envelope: parsed }; }
        const plan = jsonRecord(parsed.approval_plan);
        if (!plan) return fail("fusion_plan_missing", parsed);
        const token = execute ? context!.token : randomUUID();
        // 查看 must not replace the scene the user originally saw.
        if (!execute) this.fusionContext = { token, binding, plan, scope: input.scope, project: input.projectRoot, proposals: { equivalentSources: input.equivalentSources, publicReuse: input.publicReuse } };
        return { status: "completed", envelope: parsed, contextToken: token };
      } finally { fs.rmSync(directory, { recursive: true, force: true }); }
    });
  }

  async fusionConfirm(input: { action: "confirm" | "reject"; confirmationToken?: string }, signal?: AbortSignal): Promise<PlanConfirmOutcome> {
    return this.operate("fusion", "execute", signal, async owned => {
      if (input.action === "reject") { this.pending.delete("fusion"); return { status: "rejected" }; }
      const popped = this.popPending("fusion", input.confirmationToken);
      if (!popped.ok) return popped.outcome as PlanConfirmOutcome;
      const file = this.buildApprovalFile(popped.pending);
      const result = await this.runJson<PlanConfirmOutcome>(this.confirmArgv(popped.pending, file), { signal: owned });
      if ("failure" in result) return result.failure;
      this.fusionContext = undefined;
      if (result.exitKind === "completed" && result.parsed.status === "completed" && result.parsed.fusion_status === "completed") return { status: "completed", envelope: result.parsed };
      return { status: "failed", code: "fusion_not_completed", message: "融合未完成；保留现场，按错误与 manifest 恢复。", envelope: result.parsed };
    });
  }

  async bootstrapPreview(signal?: AbortSignal): Promise<PreviewOutcome> {
    return this.operate("bootstrap", "preview", signal, owned => this.bootstrapPreviewImpl(owned));
  }

  async dependencyPreview(signal?: AbortSignal): Promise<PreviewOutcome> {
    return this.operate("dependency", "preview", signal, () => this.dependencyPreviewImpl());
  }

  async dependencyConfirm(input: { action: "confirm" | "reject"; confirmationToken?: string }, signal?: AbortSignal): Promise<PlanConfirmOutcome> {
    return this.operate("dependency", "execute", signal, owned => this.dependencyConfirmImpl(input, owned));
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

  async projectEnablePreview(input: { projectRoot: string; agents: readonly string[] }, signal?: AbortSignal): Promise<PreviewOutcome> {
    return this.operate("enable", "preview", signal, owned => this.projectEnablePreviewImpl(input, owned));
  }

  async projectEnableConfirm(input: { action: "confirm" | "reject"; confirmationToken?: string }, signal?: AbortSignal): Promise<PlanConfirmOutcome> {
    return this.operate("enable", "execute", signal, owned => this.projectEnableConfirmImpl(input, owned));
  }

  // Uninstall family: deliberately NOT wrapped in operate() — the flow must
  // never create its own operation/approval entries inside the to-be-deleted
  // staging root (host materials stay external; core manifest persists them).
  async uninstallPreview(backupDir: string, signal?: AbortSignal): Promise<PreviewOutcome> {
    return this.uninstallPreviewImpl(backupDir, signal);
  }

  async uninstallConfirm(input: { action: "confirm" | "reject"; confirmationToken?: string }, signal?: AbortSignal): Promise<ConfirmOutcome> {
    return this.uninstallConfirmImpl(input, signal);
  }

  async stagingCleanupPreview(evidenceDir: string): Promise<PreviewOutcome> {
    return this.stagingCleanupPreviewImpl(evidenceDir);
  }

  async stagingCleanupConfirm(input: { action: "confirm" | "reject"; confirmationToken?: string }): Promise<PlanConfirmOutcome> {
    return this.stagingCleanupConfirmImpl(input);
  }

  async ckUninstallPreview(input: { manifest: string; ckSource: string; ckAgents: readonly string[]; ckProject?: string }, signal?: AbortSignal): Promise<PreviewOutcome> {
    return this.ckUninstallPreviewImpl(input, signal);
  }

  async ckUninstallConfirm(input: { action: "confirm" | "reject"; confirmationToken?: string }, signal?: AbortSignal): Promise<PlanConfirmOutcome> {
    return this.ckUninstallConfirmImpl(input, signal);
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
