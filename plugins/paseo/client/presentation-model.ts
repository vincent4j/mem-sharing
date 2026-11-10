export function flowCopy(flow: string): { title: string; description: string } {
  const titles: Record<string, string> = {
    onboard: "设置记忆共享", check: "memSharing 检查当前项目", enable: "memSharing 启用当前项目",
    ck: "memSharing 可选安装 Context Keeper", recover: "memSharing 恢复未完成操作",
    uninstall: "memSharing 整机卸载", stagingCleanup: "memSharing 宿主暂存清理", uninstallRecover: "memSharing 外置卸载恢复",
  };
  return { title: titles[flow] ?? "memSharing", description: flow === "onboard" ? "选择要共享记忆的 Agent，预览改动，再按你的决定执行。"
    : flow === "check" ? "只读检查当前项目的记忆入口与接入情况。"
    : flow === "uninstall" ? "先核对归还与备份计划，再决定是否卸载。"
    : flow === "recover" || flow === "uninstallRecover" ? "保留现场，核对记录后选择继续或恢复。"
    : "先查看当前方案，所有变更按你的明确选择执行。" };
}
export function flowStage(kind: string, ok = false): string {
  return kind === "form" ? "填写与选择" : kind === "fusion" ? "记忆融合 · 选择即执行"
    : kind === "preview" ? "核对变更计划" : kind === "ckChoice" ? "独立可选 · 项目经历"
    : kind === "busy" || kind === "loading" ? "正在处理" : kind === "gate" ? "预览受阻" : ok ? "操作结果" : "核对与重试";
}
