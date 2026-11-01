// memSharing Paseo plugin — daemon-side entry.
// Registers the RPC handlers that bridge the real Python CLIs. All writes
// go through the kernel's exact-plan approvals; the client can only
// confirm or reject the digest of a server-held plan.

import type { PluginHandlerContext, PluginServerContext } from "@getpaseo/plugin/server";
import { homedir } from "node:os";
import { Orchestrator, realRunner } from "./server/orchestrator";
import { HostPayloadBinding } from "./server/payload";
import { CORE_RELEASE_MANIFEST_SHA256 } from "./server/shared/release-identity";
import type { PluginRpcContract } from "@getpaseo/plugin";
import type { ZodType, input as ZodInput, output as ZodOutput } from "zod";
import {
  dependencyPreviewRpc,
  dependencyConfirmRpc,
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
  let active: Orchestrator | undefined;
  const cancelAll = () => {
    for (const flow of ["dependency", "bootstrap", "machine", "enable", "remove", "ck", "recover"] as const) active?.cancel(flow);
  };
  const binding = new HostPayloadBinding(CORE_RELEASE_MANIFEST_SHA256, (resolution) => {
    active = new Orchestrator({ runner: realRunner(homedir()), home: homedir(),
      pluginDir: resolution.dir, searchedPluginDirs: resolution.searched });
    return active;
  });
  function handle<I extends ZodType, O extends ZodType>(contract: PluginRpcContract<I, O>,
    run: (orchestrator: Orchestrator, input: ZodOutput<I>) => ZodInput<O> | Promise<ZodInput<O>>) {
    server.handle(contract, async (input, context: PluginHandlerContext) => {
      let sources;
      try {
        // Consume only host-owned plugin sources. Never log/return/persist the
        // full SDK configuration, provider values or a raw SDK failure.
        sources = (await context.paseo.config.get()).config.plugins;
      } catch {
        binding.invalidate();
        cancelAll();
        throw new Error("plugin_source_unavailable: daemon plugin sources could not be read");
      }
      let orchestrator: Orchestrator;
      try { orchestrator = binding.get(sources); }
      catch (error) { cancelAll(); throw error; }
      return run(orchestrator, input);
    });
  }

  handle(envStatusRpc, async (orchestrator) => {
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
      releaseIdentity: { ...orchestrator.releaseIdentity(), manifestSha256: CORE_RELEASE_MANIFEST_SHA256 || undefined },
      durableSource: orchestrator.durableSource(),
    };
  });

  handle(bootstrapPreviewRpc, async (orchestrator) => orchestrator.bootstrapPreview());
  handle(dependencyPreviewRpc, async (orchestrator) => orchestrator.dependencyPreview());
  handle(dependencyConfirmRpc, async (orchestrator, input) => orchestrator.dependencyConfirm(input));
  handle(bootstrapConfirmRpc, async (orchestrator, input) => orchestrator.bootstrapConfirm(input));

  handle(machinePreviewRpc, async (orchestrator, input) => orchestrator.machinePreview(input.agents));
  handle(machineConfirmRpc, async (orchestrator, input) => orchestrator.machineConfirm(input));

  handle(projectCheckRpc, async (orchestrator, input) => orchestrator.projectCheck(input.projectRoot));
  handle(projectEnablePreviewRpc, async (orchestrator, input) =>
    orchestrator.projectEnablePreview({ projectRoot: input.projectRoot, agents: input.agents, memory: input.memory }),
  );
  handle(projectEnableConfirmRpc, async (orchestrator, input) => orchestrator.projectEnableConfirm(input));

  handle(projectRemovePreviewRpc, async (orchestrator, input) => orchestrator.projectRemovePreview(input.projectRoot));
  handle(projectRemoveConfirmRpc, async (orchestrator, input) => orchestrator.projectRemoveConfirm(input));

  handle(ckPreviewRpc, async (orchestrator, input) => orchestrator.ckPreview());
  handle(ckConfirmRpc, async (orchestrator, input) => orchestrator.ckConfirm(input));

  handle(recoverPreviewRpc, async (orchestrator, input) => orchestrator.recoverPreview(input));
  handle(recoverConfirmRpc, async (orchestrator, input) => orchestrator.recoverConfirm(input));

  handle(cancelPendingRpc, async (orchestrator, input) => orchestrator.cancel(input.flow));

  handle(operationStatusRpc, async (orchestrator) => orchestrator.operationStatus());
  return cancelAll;
}
