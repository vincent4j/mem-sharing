// Adapt capability-specific replies to the same presentation used on macOS.
export type PreviewReply = Record<string, unknown>;
export const WINDOWS_SCOPE = "Windows 目前仅支持此 DELL 上 ZCode 与 WorkBuddy 的双端预览：只共享明确新增的内容，保留原有私有记忆；可独立选择安装 Context Keeper。暂不支持旧记忆融合、升级或项目接入。";
export const WINDOWS_SETUP = "DELL Windows 11 x64、本地 NTFS、ZCode 3.17.2.9661 和 WorkBuddy 5.9.3.0，均使用默认用户配置。";
export function previewOperation(flow: string, installed: boolean): "install" | "add" | "exit" {
  return flow === "uninstall" ? "exit" : installed ? "add" : "install";
}
export const OPERATION_LABELS = { install: "接入 ZCode 与 WorkBuddy", add: "新增公共记忆", exit: "导出公共记忆并退出接入" };
export function publicPreview(reply: PreviewReply, text: string) {
  // Neither confirmation capability nor old private file snapshots belong in
  // rendered plan details. Retain the exact text and paths under review.
  const operation = reply.operation as keyof typeof OPERATION_LABELS;
  return {
    operation, home: reply.home, backup_root: reply.backup_root, export: reply.export,
    changes: reply.changes, digest: reply.digest,
    ...(operation === "add" ? { text } : {}),
  };
}
export function previewRows(reply: PreviewReply, text: string) {
  const operation = reply.operation as keyof typeof OPERATION_LABELS;
  const rows = [{ label: "操作", value: OPERATION_LABELS[operation] ?? "核对计划" },
    { label: "参与 Agent", value: "ZCode、WorkBuddy" }];
  if (operation === "add") rows.push({ label: "新增正文", value: text });
  if (reply.export && typeof reply.export === "object") rows.push({ label: "导出位置", value: String((reply.export as PreviewReply).path) });
  if (reply.backup_root) rows.push({ label: "备份位置", value: String(reply.backup_root) });
  return rows;
}

// Only the two completed status replies can establish readiness. A busy
// worker is retryable, while unknown replies must remain explicitly unverified.
export function previewStatus(reply: PreviewReply | undefined) {
  const installed = reply?.status === "installed";
  const available = installed || reply?.status === "not_installed";
  const waiting = reply?.status === "busy";
  return {
    installed, available, waiting,
    headline: installed ? "✓ 记忆接入已核对" : available ? "✓ 环境检查完成" : waiting ? "◌ 已有操作进行中" : "! 状态待核对",
    notice: waiting ? String(reply?.message ?? "已有操作进行中，请等待后刷新状态。") : undefined,
    error: available || waiting ? undefined : String(reply?.message ?? "未取得可确认的状态，请刷新后核对。"),
  };
}
