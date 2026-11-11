import fs from "node:fs";
import path from "node:path";
import { createHash, randomUUID } from "node:crypto";
import { hostname } from "node:os";
import { acquireCkSource, ckAcquisitionPlan, ckDestination } from "./ck-source";
import { runProcess, type ProcessResult, type RunProcessOptions } from "./shared/common/process";
import { probePythonEnvironment, type PythonEnvironment } from "./shared/common/python";
import { probeGitEnvironment, type GitEnvironment } from "./shared/common/git";
import { WINDOWS_CK_BRIDGE } from "./windows-ck-bridge";
import type { PreviewReply } from "./windows-preview";

interface Deps {
  home: string; previewSource: () => string;
  platform?: NodeJS.Platform; now?: () => number;
  python?: () => Promise<PythonEnvironment>; git?: () => Promise<GitEnvironment>;
  run?: (options: RunProcessOptions) => Promise<ProcessResult>;
  acquire?: typeof acquireCkSource;
}
const digest = (value: unknown) => createHash("sha256").update(JSON.stringify(value)).digest("hex");
// Include raw bytes and the complete working tree (except Git's own metadata).
// The acquisition helper first independently validates every tracked Git blob.
export function ckWorkingTree(source: string): string {
  const entries: [string, string][] = [];
  function walk(dir: string) {
    if (fs.realpathSync(dir) !== dir || fs.lstatSync(dir).isSymbolicLink()) throw new Error("Context Keeper source alias refused");
    for (const name of fs.readdirSync(dir).sort()) {
      if (dir === source && name === ".git") continue;
      const file = path.join(dir, name), st = fs.lstatSync(file);
      if (st.isSymbolicLink()) throw new Error("Context Keeper source link refused");
      if (st.isDirectory()) walk(file);
      else if (st.isFile() && st.nlink === 1) entries.push([path.relative(source, file), createHash("sha256").update(fs.readFileSync(file)).digest("hex")]);
      else throw new Error("Context Keeper source node refused");
    }
  }
  walk(source);
  if (!entries.some(([n]) => n === path.join("scripts", "install.py")) || !entries.some(([n]) => n === "SKILL.md")) throw new Error("Context Keeper installer missing");
  return digest(entries);
}
export class WindowsCkHost {
  private busy = false;
  private unknown = false;
  private last?: PreviewReply;
  status(): PreviewReply { return this.busy ? { status: "running" } : this.last ?? { status: "idle" }; }
  private prepared?: { source: string; tree: string; environment: string };
  private pending?: { token: string; operation: "prepare" | "install"; plan: Record<string, unknown>; binding: string; at: number };
  private readonly deps: Deps;
  constructor(deps: Deps) { this.deps = deps; }
  cancel(): PreviewReply {
    if (this.busy) return { status: "busy", message: "操作进行中，请等待；不能保证中断后的事务结果。" };
    this.pending = undefined; this.prepared = undefined;
    return this.last = { status: "rejected" };
  }
  private async context() {
    if ((this.deps.platform ?? process.platform) !== "win32" || this.unknown) throw new Error("Windows Context Keeper operation unavailable; inspect any incomplete operation before reload");
    const previewSource = this.deps.previewSource();
    const python = await (this.deps.python?.() ?? probePythonEnvironment({ runtimeRoot: "" }));
    const git = await (this.deps.git?.() ?? probeGitEnvironment());
    if (python.status !== "ready" || !python.selected || git.status !== "ready" || !git.path) throw new Error("需要 Host 上可用的 Python 3.9+ 和 Git；不会自动下载 Windows 运行时。");
    const env = { ...process.env, HOME: this.deps.home, USERPROFILE: this.deps.home };
    const binding = digest({ env, home: this.deps.home, host: hostname(), previewSource, python: python.selected.path, git: git.path });
    if (this.deps.previewSource() !== previewSource) throw new Error("Preview source changed");
    return { env, binding, previewSource, python: python.selected.path, git: git.path };
  }
  private async exclusive(work: () => Promise<PreviewReply>): Promise<PreviewReply> {
    if (this.busy) return { status: "busy", message: "已有 Context Keeper 操作进行中。" };
    this.busy = true;
    try { return await work(); }
    catch (error) { this.pending = undefined; return { status: "failed", message: String(error) }; }
    finally { this.busy = false; }
  }
  private async call(c: Awaited<ReturnType<WindowsCkHost["context"]>>, request: Record<string, unknown>, writes = false): Promise<PreviewReply> {
    const outcome = await (this.deps.run ?? runProcess)({ argv: [c.python, "-I", "-S", "-B", "-X", "utf8", "-c", WINDOWS_CK_BRIDGE, path.join(c.previewSource, "scripts")],
      stdin: JSON.stringify({ ...request, home: this.deps.home, ck_source: this.prepared?.source }), env: c.env, timeoutMs: 60_000, maxStdoutBytes: 8 * 1024 * 1024 });
    try {
      if (outcome.kind !== "completed" || outcome.stdoutTruncated) throw new Error();
      const reply = JSON.parse(outcome.stdout);
      if (!reply || typeof reply.status !== "string" || (outcome.exitCode !== 0 && reply.status !== "failed")) throw new Error();
      return reply;
    } catch {
      if (writes) this.unknown = true;
      return { status: writes ? "unknown" : "failed", message: "未取得完整结果；保留 Context Keeper 操作备份与日志，核对后再继续。" };
    }
  }
  preview(operation: "prepare" | "install") {
    return this.exclusive(async () => {
      this.pending = undefined;
      const c = await this.context();
      let plan: Record<string, unknown>;
      if (operation === "prepare") { this.prepared = undefined; plan = ckAcquisitionPlan(this.deps.home); }
      else {
        if (!this.prepared || this.prepared.environment !== c.binding || ckWorkingTree(this.prepared.source) !== this.prepared.tree) throw new Error("请先重新获取并核对官方 main 源码。");
        const reply = await this.call(c, { action: "plan", run_id: randomUUID() });
        if (reply.status !== "approval_required" || !reply.plan || typeof reply.plan !== "object") return reply;
        plan = reply.plan as Record<string, unknown>;
      }
      const token = randomUUID();
      this.pending = { token, operation, plan, binding: digest({ context: c.binding, prepared: this.prepared }), at: this.deps.now?.() ?? Date.now() };
      return { status: "approval_required", operation, confirmationToken: token, digest: digest(plan), source: operation === "prepare" ? ckDestination(this.deps.home) : this.prepared?.source,
        agents: plan.agents ?? ["zcode", "workbuddy"], skipped: plan.skipped ?? [], backup_root: plan.backup_root,
        changes: Object.entries((plan.files ?? {}) as Record<string, { before: { sha256: string }; after: { sha256: string } }>).map(([file, item]) => ({ path: file, before: item.before.sha256, after: item.after.sha256 })),
        skill_entries: Object.keys((plan.links ?? {}) as object), acquisition: operation === "prepare" ? plan : undefined };
    });
  }
  confirm(token: string): PreviewReply {
    if (this.busy) return { status: "busy", message: "已有 Context Keeper 操作进行中。" };
    this.last = { status: "running" };
    void this.confirmAndWait(token).then(result => { this.last = result; });
    return { status: "running" };
  }
  private confirmAndWait(token: string) {
    return this.exclusive(async () => {
      const pending = this.pending; this.pending = undefined;
      if (!pending || token !== pending.token) throw new Error("无有效待确认计划，请重新预览。");
      const c = await this.context();
      if ((this.deps.now?.() ?? Date.now()) - pending.at > 600_000 || pending.binding !== digest({ context: c.binding, prepared: this.prepared })) throw new Error("计划过期或 Host 环境变化，请重新预览。");
      if (pending.operation === "prepare") {
        try {
          const source = await (this.deps.acquire ?? acquireCkSource)(this.deps.home, c.git, { run: (argv, options) => (this.deps.run ?? runProcess)({ ...options, argv, env: c.env }) });
          this.prepared = { source, tree: ckWorkingTree(source), environment: c.binding };
          return { status: "source_prepared", source, installation_complete: false };
        } catch (error) { this.unknown = true; throw error; }
      }
      if (!this.prepared || ckWorkingTree(this.prepared.source) !== this.prepared.tree) throw new Error("Context Keeper 源码漂移，请重新获取。");
      const result = await this.call(c, { action: "confirm", plan: pending.plan }, true);
      this.prepared = undefined;
      // A failed upstream operation can require manual recovery; do not replay.
      if (result.status !== "committed") this.unknown = true;
      return result;
    });
  }
}
