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
    title: "memSharing：接入状态",
    icon: "BookOpen",
    context: "global",
    onSelect({ openScreen }) {
      openScreen({ screenId: "ms-status" });
    },
  });

  client.addCommandCenterItem({
    id: "ms-onboard",
    title: "memSharing：接入本机（首次或继续）",
    icon: "Rocket",
    context: "global",
    keywords: ["install", "setup", "memory"],
    onSelect({ openScreen }) {
      openScreen({ screenId: "ms-flow", params: { flow: "onboard" } });
    },
  });

  client.addCommandCenterItem({
    id: "ms-project-check",
    title: "memSharing：检查当前项目",
    icon: "Stethoscope",
    context: "workspace",
    keywords: ["check", "memory"],
    onSelect({ openScreen, workspace }) {
      openScreen({ screenId: "ms-flow", params: { flow: "check", projectRoot: workspace.directory } });
    },
  });

  client.addCommandCenterItem({
    id: "ms-project-enable",
    title: "memSharing：启用当前项目",
    icon: "BookOpenCheck",
    context: "workspace",
    keywords: ["enable", "memory"],
    onSelect({ openScreen, workspace }) {
      openScreen({ screenId: "ms-flow", params: { flow: "enable", projectRoot: workspace.directory } });
    },
  });

  client.addCommandCenterItem({
    id: "ms-project-remove",
    title: "memSharing：停用当前项目",
    icon: "BookX",
    context: "workspace",
    keywords: ["remove", "disable", "memory"],
    onSelect({ openScreen, workspace }) {
      openScreen({ screenId: "ms-flow", params: { flow: "remove", projectRoot: workspace.directory } });
    },
  });

  client.addCommandCenterItem({
    id: "ms-ck",
    title: "memSharing：可选安装 Context Keeper",
    icon: "NotebookPen",
    context: "global",
    keywords: ["context-keeper", "ck", "optional"],
    onSelect({ openScreen }) {
      openScreen({ screenId: "ms-flow", params: { flow: "ck" } });
    },
  });

  client.addCommandCenterItem({
    id: "ms-recover",
    title: "memSharing：恢复未完成操作",
    icon: "Undo2",
    context: "global",
    keywords: ["recover", "journal", "rollback"],
    onSelect({ openScreen }) {
      openScreen({ screenId: "ms-flow", params: { flow: "recover" } });
    },
  });

  return () => {};
}
