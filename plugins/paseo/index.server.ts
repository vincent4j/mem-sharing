// memSharing Paseo plugin — daemon-side entry.
// Registers the RPC handlers that bridge the real Python CLIs. All writes
// go through the kernel's exact-plan approvals; the client can only
// confirm or reject the digest of a server-held plan.

import type { PluginHandlerContext, PluginServerContext } from "@getpaseo/plugin/server";
import { homedir } from "node:os";
import { Orchestrator, realRunner } from "./server/orchestrator";
import { HostPayloadBinding } from "./server/payload";
import { CORE_RELEASE_MANIFEST_SHA256 } from "./server/shared/release-identity";
import { WINDOWS_PREVIEW_MANIFEST_SHA256 } from "./server/shared/windows-preview-identity";
import { WindowsPreviewBinding, verifyPreviewSource } from "./server/windows-preview-source";
import path from "node:path";
import { WindowsPreviewHost } from "./server/windows-preview";
import type { PluginRpcContract } from "@getpaseo/plugin";
import type { ZodType, input as ZodInput, output as ZodOutput } from "zod";
import {
  hostPlatformRpc, windowsPreviewStatusRpc, windowsPreviewPlanRpc, windowsPreviewConfirmRpc, windowsPreviewCancelRpc,
  fusionPreviewRpc, fusionProposeRpc, fusionSelectRpc, fusionConfirmRpc,
  dependencyPreviewRpc,
  dependencyConfirmRpc,
  operationStatusRpc,
  envStatusRpc, detectAgentsRpc,
  bootstrapPreviewRpc,
  bootstrapConfirmRpc,
  machinePreviewRpc,
  machineConfirmRpc,
  projectCheckRpc,
  projectEnablePreviewRpc,
  projectEnableConfirmRpc,
  uninstallPreviewRpc,
  uninstallConfirmRpc,
  stagingInventoryRpc,
  stagingCleanupPreviewRpc,
  stagingCleanupConfirmRpc,
  ckPreviewRpc,
  ckConfirmRpc,
  recoverPreviewRpc,
  recoverConfirmRpc,
  ckChoiceRetainRpc,
  ckUninstallPreviewRpc,
  ckUninstallConfirmRpc,
  cancelPendingRpc,
} from "./shared/contracts";

export default function contribute(server: PluginServerContext) {
  const previewBinding = new WindowsPreviewBinding(WINDOWS_PREVIEW_MANIFEST_SHA256);
  let previewSource: string | undefined;
  const preview = new WindowsPreviewHost({ home: homedir(), source: () => {
    if (!previewSource) throw new Error("windows_preview_source_missing");
    return verifyPreviewSource(path.dirname(previewSource), WINDOWS_PREVIEW_MANIFEST_SHA256);
  } });
  server.handle(hostPlatformRpc, () => ({ platform: process.platform,
    mode: process.platform === "darwin" ? "macos" as const : process.platform === "win32" ? "windows-preview" as const : "unsupported" as const }));
  function previewHandle<I extends ZodType, O extends ZodType>(contract: PluginRpcContract<I, O>,
    run: (input: ZodOutput<I>) => ZodInput<O> | Promise<ZodInput<O>>) {
    server.handle(contract, async (input, context: PluginHandlerContext) => {
      if (process.platform !== "win32") throw new Error("windows_preview_host_required");
      try { previewSource = previewBinding.get((await context.paseo.config.get()).config.plugins); }
      catch { previewBinding.invalidate(); preview.invalidate(); throw new Error("windows_preview_source_unavailable_reload_required"); }
      return run(input);
    });
  }
  previewHandle(windowsPreviewStatusRpc, () => preview.status());
  previewHandle(windowsPreviewPlanRpc, input => {
    if (input.operation === "install" && input.verifiedSetup !== true) throw new Error("请先核实并选择此 DELL 双端限定版本与默认配置范围。");
    return preview.preview(input.operation, input.text);
  });
  previewHandle(windowsPreviewConfirmRpc, input => preview.confirm(input.confirmationToken));
  previewHandle(windowsPreviewCancelRpc, () => preview.cancel());
  let active: Orchestrator | undefined;
  const cancelAll = () => {
    for (const flow of ["dependency", "bootstrap", "machine", "enable", "uninstall", "stagingCleanup", "ck", "recover", "ckUninstall", "fusion"] as const) active?.cancel(flow);
  };
  const binding = new HostPayloadBinding(CORE_RELEASE_MANIFEST_SHA256, (resolution) => {
    active = new Orchestrator({ runner: realRunner(homedir()), home: homedir(),
      pluginDir: resolution.dir, searchedPluginDirs: resolution.searched,
      pluginRecords: resolution.records });
    return active;
  });
  function handle<I extends ZodType, O extends ZodType>(contract: PluginRpcContract<I, O>,
    run: (orchestrator: Orchestrator, input: ZodOutput<I>) => ZodInput<O> | Promise<ZodInput<O>>) {
    server.handle(contract, async (input, context: PluginHandlerContext) => {
      // Every production RPC is closed on Windows, even when called directly
      // without going through the platform-routed client screen.
      if (process.platform !== "darwin") throw new Error("production_host_unsupported_use_windows_preview");
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

  handle(detectAgentsRpc, orchestrator => orchestrator.detectAgents());
  handle(bootstrapPreviewRpc, async (orchestrator) => orchestrator.bootstrapPreview());
  handle(dependencyPreviewRpc, async (orchestrator) => orchestrator.dependencyPreview());
  handle(dependencyConfirmRpc, async (orchestrator, input) => orchestrator.dependencyConfirm(input));
  handle(bootstrapConfirmRpc, async (orchestrator, input) => orchestrator.bootstrapConfirm(input));

  handle(fusionPreviewRpc, (orchestrator, input) => orchestrator.fusionPreview(input));
  handle(fusionProposeRpc, (orchestrator, input) => orchestrator.fusionPropose(input));
  handle(fusionSelectRpc, (orchestrator, input) => orchestrator.fusionSelect(input));
  handle(fusionConfirmRpc, (orchestrator, input) => orchestrator.fusionConfirm(input));

  handle(machinePreviewRpc, async (orchestrator, input) => orchestrator.machinePreview(input.agents));
  handle(machineConfirmRpc, async (orchestrator, input) => orchestrator.machineConfirm(input));

  handle(projectCheckRpc, async (orchestrator, input) => orchestrator.projectCheck(input.projectRoot));
  handle(projectEnablePreviewRpc, async (orchestrator, input) =>
    orchestrator.projectEnablePreview({ projectRoot: input.projectRoot, agents: input.agents }),
  );
  handle(projectEnableConfirmRpc, async (orchestrator, input) => orchestrator.projectEnableConfirm(input));

  handle(uninstallPreviewRpc, async (orchestrator, input) => orchestrator.uninstallPreview(input.backupDir));
  handle(uninstallConfirmRpc, async (orchestrator, input) => orchestrator.uninstallConfirm(input));
  handle(stagingInventoryRpc, async (orchestrator) => orchestrator.stagingInventory());

  handle(stagingCleanupPreviewRpc, async (orchestrator, input) => orchestrator.stagingCleanupPreview(input.evidenceDir));
  handle(stagingCleanupConfirmRpc, async (orchestrator, input) => orchestrator.stagingCleanupConfirm(input));

  handle(ckChoiceRetainRpc, async (orchestrator, input) => orchestrator.ckChoiceRetain(input.manifest));
  handle(ckUninstallPreviewRpc, async (orchestrator, input) =>
    orchestrator.ckUninstallPreview({ manifest: input.manifest, ckSource: input.ckSource, ckAgents: input.ckAgents, ckProject: input.ckProject }),
  );
  handle(ckUninstallConfirmRpc, async (orchestrator, input) => orchestrator.ckUninstallConfirm(input));

  handle(ckPreviewRpc, async (orchestrator, input) => orchestrator.ckPreview());
  handle(ckConfirmRpc, async (orchestrator, input) => orchestrator.ckConfirm(input));

  handle(recoverPreviewRpc, async (orchestrator, input) => orchestrator.recoverPreview(input));
  handle(recoverConfirmRpc, async (orchestrator, input) => orchestrator.recoverConfirm(input));

  handle(cancelPendingRpc, async (orchestrator, input) => orchestrator.cancel(input.flow));

  handle(operationStatusRpc, async (orchestrator) => orchestrator.operationStatus());
  return () => { preview.invalidate(); cancelAll(); };
}
