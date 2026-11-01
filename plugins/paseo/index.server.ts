// memSharing Paseo plugin — daemon-side entry.
// Registers the RPC handlers that bridge the real Python CLIs. All writes
// go through the kernel's exact-plan approvals; the client can only
// confirm or reject the digest of a server-held plan.

import type { PluginServerContext } from "@getpaseo/plugin/server";
import { homedir } from "node:os";
import { Orchestrator, realRunner } from "./server/orchestrator";
import { resolvePluginDir } from "./server/payload";
import {
  operationStatusRpc,
  envStatusRpc,
  bootstrapPreviewRpc,
  bootstrapConfirmRpc,
  machinePreviewRpc,
  machineConfirmRpc,
  projectCheckRpc,
  projectEnablePreviewRpc,
  projectEnableConfirmRpc,
  projectRemovePreviewRpc,
  projectRemoveConfirmRpc,
  ckPreviewRpc,
  ckConfirmRpc,
  recoverPreviewRpc,
  recoverConfirmRpc,
  cancelPendingRpc,
} from "./shared/contracts";

export default function contribute(server: PluginServerContext) {
  const resolution = resolvePluginDir();
  const orchestrator = new Orchestrator({
    runner: realRunner(homedir()),
    home: homedir(),
    pluginDir: resolution.dir,
    searchedPluginDirs: resolution.searched,
  });

  server.handle(envStatusRpc, async () => {
    const [python, git] = await Promise.all([orchestrator.python(), orchestrator.git()]);
    const payload = orchestrator.payload();
    return {
      python: {
        status: python.status,
        selectedPath: python.selected?.path,
        pythonVersion: python.selected?.probe?.pythonVersion,
        detail: python.selected?.detail ?? (python.status === "ready" ? undefined : "no ready interpreter"),
        evidence: python.evidence,
      },
      git: {
        status: git.status,
        version: git.version,
        path: git.path,
        detail: git.detail,
      },
      payload:
        payload.status === "ready"
          ? { status: "ready" as const, installerPath: payload.installerPath, searched: payload.searched }
          : { status: "missing" as const, searched: payload.searched },
      releaseIdentity: orchestrator.releaseIdentity(),
      durableSource: orchestrator.durableSource(),
    };
  });

  server.handle(bootstrapPreviewRpc, async () => orchestrator.bootstrapPreview());
  server.handle(bootstrapConfirmRpc, async (input) => orchestrator.bootstrapConfirm(input));

  server.handle(machinePreviewRpc, async (input) => orchestrator.machinePreview(input.agents));
  server.handle(machineConfirmRpc, async (input) => orchestrator.machineConfirm(input));

  server.handle(projectCheckRpc, async (input) => orchestrator.projectCheck(input.projectRoot));
  server.handle(projectEnablePreviewRpc, async (input) =>
    orchestrator.projectEnablePreview({ projectRoot: input.projectRoot, agents: input.agents, memory: input.memory }),
  );
  server.handle(projectEnableConfirmRpc, async (input) => orchestrator.projectEnableConfirm(input));

  server.handle(projectRemovePreviewRpc, async (input) => orchestrator.projectRemovePreview(input.projectRoot));
  server.handle(projectRemoveConfirmRpc, async (input) => orchestrator.projectRemoveConfirm(input));

  server.handle(ckPreviewRpc, async (input) => orchestrator.ckPreview());
  server.handle(ckConfirmRpc, async (input) => orchestrator.ckConfirm(input));

  server.handle(recoverPreviewRpc, async (input) => orchestrator.recoverPreview(input));
  server.handle(recoverConfirmRpc, async (input) => orchestrator.recoverConfirm(input));

  server.handle(cancelPendingRpc, async (input) => orchestrator.cancel(input.flow));

  server.handle(operationStatusRpc, async () => orchestrator.operationStatus());
  return () => { for (const flow of ["bootstrap", "machine", "enable", "remove", "ck", "recover"] as const) orchestrator.cancel(flow); };
}
