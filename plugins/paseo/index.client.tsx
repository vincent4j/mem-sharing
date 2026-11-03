// memSharing Paseo plugin — client entry.
// Thin command entries only: Command Center items open the one-time flow or
// status screens. No persistent sidebar item, no management page. Workspace
// commands bind the workspace's absolute directory; agent context is not
// required for v1.

import type { PluginClientContext } from "@getpaseo/plugin/client";
import { FlowScreen } from "./client/flow";
import { StatusScreen } from "./client/status";

export default function contribute(client: PluginClientContext) {
  client.addScreen({ id: "ms-status", title: "memSharing 状态", Component: StatusScreen });
  client.addScreen({ id: "ms-flow", title: "memSharing", Component: FlowScreen });

  client.addCommandCenterItem({
    id: "ms-status",
    title: "memSharing：查看共享状态",
    icon: "BookOpen",
    context: "global",
    onSelect({ openScreen }) {
      openScreen({ screenId: "ms-status" });
    },
  });

  client.addCommandCenterItem({
    id: "ms-onboard",
    title: "memSharing：设置记忆共享",
    icon: "Rocket",
    context: "global",
    keywords: ["install", "setup", "memory"],
    onSelect({ openScreen }) {
      openScreen({ screenId: "ms-flow", params: { flow: "onboard" } });
    },
  });

  client.addCommandCenterItem({
    id: "ms-project-check",
    title: "memSharing：检查当前项目记忆",
    icon: "Stethoscope",
    context: "workspace",
    keywords: ["check", "memory"],
    onSelect({ openScreen, workspace }) {
      openScreen({ screenId: "ms-flow", params: { flow: "check", projectRoot: workspace.directory } });
    },
  });

  client.addCommandCenterItem({
    id: "ms-project-enable",
    title: "memSharing：为当前项目启用共享",
    icon: "BookOpenCheck",
    context: "workspace",
    keywords: ["enable", "memory"],
    onSelect({ openScreen, workspace }) {
      openScreen({ screenId: "ms-flow", params: { flow: "enable", projectRoot: workspace.directory } });
    },
  });

  client.addCommandCenterItem({
    id: "ms-uninstall",
    title: "memSharing：卸载记忆共享",
    icon: "BookX",
    context: "global",
    keywords: ["uninstall", "memory"],
    onSelect({ openScreen }) {
      openScreen({ screenId: "ms-flow", params: { flow: "uninstall" } });
    },
  });

  client.addCommandCenterItem({
    id: "ms-ck",
    title: "memSharing：安装 Context Keeper（可选）",
    icon: "NotebookPen",
    context: "global",
    keywords: ["context-keeper", "ck", "optional"],
    onSelect({ openScreen }) {
      openScreen({ screenId: "ms-flow", params: { flow: "ck" } });
    },
  });

  client.addCommandCenterItem({
    id: "ms-recover",
    title: "memSharing：高级：处理未完成的操作",
    icon: "Undo2",
    context: "global",
    keywords: ["recover", "journal", "rollback"],
    onSelect({ openScreen }) {
      openScreen({ screenId: "ms-flow", params: { flow: "recover" } });
    },
  });

  for (const item of [
    { id: "ms-staging-cleanup", title: "memSharing：高级：清理安装暂存文件", flow: "stagingCleanup" },
    { id: "ms-uninstall-recover", title: "memSharing：高级：处理未完成的卸载", flow: "uninstallRecover" },
  ]) client.addCommandCenterItem({ id: item.id, title: item.title, icon: "Undo2", context: "global", keywords: ["memsharing", "recover"], onSelect({ openScreen }) { openScreen({ screenId: "ms-flow", params: { flow: item.flow } }); } });
  return () => {};
}
