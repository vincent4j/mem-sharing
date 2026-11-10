// Thin adapter to the existing eight-file Windows preview kernel. Plans stay
// server-owned in memory. The kernel regenerates them before every write.
import { randomUUID, createHash } from "node:crypto";
import { hostname } from "node:os";
import { runProcess, type RunProcessOptions, type ProcessResult } from "./shared/common/process";
import { probePythonEnvironment, type PythonEnvironment } from "./shared/common/python";

export const PREVIEW_BRIDGE = String.raw`
import sys,json,platform
try:
 if sys.platform != 'win32' or platform.machine().lower() not in ('amd64','x86_64') or sys.getwindowsversion().build < 22000:
  raise ValueError('仅限 Windows 11 x64 双端预览')
 sys.path.insert(0,sys.argv[1])
 from agm_core import windows_preview as p
 request=json.load(sys.stdin)
 home=p.absolute(request['home'])
 p.guard(home);p.guard(sys.argv[1])
 source=p.absolute(request['source'])
 source_files=p.source_manifest(source)
 if (home/p.RECEIPT).exists():
  current,_=p.load_receipt(home)
  if current['source_files']!=source_files:
   raise ValueError('已安装预览与当前包源码不同；不自动升级或接管')
 action=request['action']
 if action=='status':
  if not (home/p.RECEIPT).exists():
   if any((home/n).exists() for n in ('.mem-sharing',p.CODE,'.agents-group')):
    raise ValueError('存在既有安装或未知内容；不自动接管')
   result={'status':'not_installed'}
  else:
   r,_=p.load_receipt(home)
   # exit_plan validates all native entries and the export path, zero writes.
   p.exit_plan(home)
   public=p.snap(home/p.PUBLIC)
   result={'status':'installed','public_text':public.data.decode('utf-8'),
           'public_sha256':public.fingerprint,'externally_edited':public.fingerprint!=r['public_sha256']}
 elif action=='preview':
  operation=request['operation']
  if operation=='install': plan=p.install_plan(home,request['source'])
  elif operation=='add': plan=p.add_plan(home,request['text'])
  elif operation=='exit': plan=p.exit_plan(home)
  else: raise ValueError('不支持此预览操作')
  result={'status':'approval_required','plan':plan,'digest':p.digest(p.encoded(plan))}
 elif action=='confirm':
  plan=request['plan']
  if plan['home']!=str(home): raise ValueError('HOME与批准计划不符')
  result=p.execute(plan,request['digest'])
 else: raise ValueError('不支持此操作')
 print(json.dumps(result,ensure_ascii=False))
except (ValueError,OSError,KeyError,TypeError) as exc:
 print(json.dumps({'status':'failed','message':str(exc),'manifest':getattr(exc,'manifest',None)},ensure_ascii=False))
 sys.exit(2)
`;

export interface WindowsPreviewDeps {
  home: string;
  source: () => string;
  /** Constructor-only test seams, never supplied by an RPC. */
  platform?: NodeJS.Platform;
  python?: () => Promise<PythonEnvironment>;
  run?: (options: RunProcessOptions) => Promise<ProcessResult>;
  now?: () => number;
}
export type PreviewOperation = "install" | "add" | "exit";
export type PreviewReply = Record<string, unknown> & { status: string };

export class WindowsPreviewHost {
  private pending?: { token: string; plan: Record<string, unknown>; digest: string; binding: string; at: number };
  private busy = false;
  private unknown = false;
  private readonly deps: WindowsPreviewDeps;
  constructor(deps: WindowsPreviewDeps) { this.deps = deps; }
  invalidate() { this.pending = undefined; this.unknown = true; }
  cancel(): PreviewReply {
    if (this.busy) return { status: "busy", message: "操作进行中，请等待；不能保证中断后的事务结果。" };
    this.pending = undefined;
    return { status: "rejected" };
  }
  private async context() {
    if ((this.deps.platform ?? process.platform) !== "win32") throw new Error("windows_preview_host_required");
    if (this.unknown) throw new Error("preview_result_unknown_reload_and_check_required");
    const source = this.deps.source();
    // The preview has no Git/network/subprocess-tree dependency. Missing
    // Python is reported; macOS private assets are never offered on Windows.
    const python = await (this.deps.python?.() ?? probePythonEnvironment({ runtimeRoot: "" }));
    if (python.status !== "ready" || !python.selected) throw new Error("需要 Host PATH 中可用的 Python 3.9+；本预览不自动下载运行时。");
    const executable = python.selected.path;
    if (this.deps.source() !== source) throw new Error("preview_source_changed");
    const environment = { ...process.env, HOME: this.deps.home, USERPROFILE: this.deps.home };
    const binding = createHash("sha256").update(JSON.stringify({ source, executable, home: this.deps.home,
      host: hostname(), environment })).digest("hex");
    return { source, executable, binding, environment };
  }
  private async call(context: Awaited<ReturnType<WindowsPreviewHost["context"]>>, request: Record<string, unknown>, execute = false): Promise<PreviewReply> {
    const result = await (this.deps.run ?? runProcess)({
      argv: [context.executable, "-I", "-S", "-B", "-X", "utf8", "-c", PREVIEW_BRIDGE, context.source + "/scripts"],
      stdin: JSON.stringify({ ...request, home: this.deps.home, source: context.source }), env: context.environment,
      timeoutMs: 60_000, maxStdoutBytes: 8 * 1024 * 1024,
    });
    if (result.kind !== "completed" || result.stdoutTruncated) {
      if (execute) this.unknown = true;
      return { status: execute ? "unknown" : "failed", message: "操作未取得完整结果。保留备份、锁和事务记录，先核对再继续。" };
    }
    try {
      const reply = JSON.parse(result.stdout);
      if (!reply || typeof reply !== "object" || typeof reply.status !== "string") throw new Error();
      if (result.exitCode !== 0 && reply.status !== "failed") throw new Error();
      return reply;
    } catch {
      if (execute) this.unknown = true;
      return { status: execute ? "unknown" : "failed", message: "内核返回无法解析，保留现场核对。" };
    }
  }
  private async exclusive(work: () => Promise<PreviewReply>): Promise<PreviewReply> {
    if (this.busy) return { status: "busy", message: "已有操作进行中，请等待。" };
    this.busy = true;
    try { return await work(); }
    catch (error) { this.pending = undefined; return { status: "failed", message: String(error) }; }
    finally { this.busy = false; }
  }
  status() { return this.exclusive(async () => this.call(await this.context(), { action: "status" })); }
  preview(operation: PreviewOperation, text?: string) {
    return this.exclusive(async () => {
      this.pending = undefined;
      if (!["install", "add", "exit"].includes(operation)) throw new Error("preview_operation_invalid");
      const context = await this.context();
      const reply = await this.call(context, { action: "preview", operation, text, source: context.source });
      if (reply.status !== "approval_required") return reply;
      if (!reply.plan || typeof reply.plan !== "object" || typeof reply.digest !== "string" || !/^[a-f0-9]{64}$/.test(reply.digest)) throw new Error("invalid_kernel_plan");
      const token = randomUUID();
      this.pending = { token, plan: reply.plan as Record<string, unknown>, digest: reply.digest, binding: context.binding, at: this.deps.now?.() ?? Date.now() };
      // Byte snapshots are held only on the server; the user sees the exact
      // target list, hashes, typed add text and exit export, not old private text.
      const plan = this.pending.plan;
      return { status: "approval_required", confirmationToken: token, digest: reply.digest,
        operation, home: plan.home, backup_root: plan.backup_root, export: plan.export,
        changes: (plan.operations as Record<string, unknown>[]).map(op => ({ path: op.relative,
          before: (op.before as Record<string, unknown>).sha256, after: (op.after as Record<string, unknown>).sha256 })) };
    });
  }
  confirm(token: string) {
    return this.exclusive(async () => {
      const pending = this.pending;
      this.pending = undefined; // Single-use, including drift and failed execution.
      if (!pending || pending.token !== token) return { status: "failed", message: "无有效待确认计划，请重新预览。" };
      const context = await this.context();
      if (context.binding !== pending.binding || (this.deps.now?.() ?? Date.now()) - pending.at > 10 * 60_000) return { status: "failed", message: "环境已变化或计划已过期，请重新预览。" };
      return this.call(context, { action: "confirm", plan: pending.plan, digest: pending.digest }, true);
    });
  }
}
