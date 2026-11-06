// memSharing Paseo plugin — RPC contracts shared by client and server.
// The client never sends trust-relevant inputs: plan digests are verified
// against server-held pending plans, and the release identity is a
// server-side compile-time constant that no RPC may override.

import { defineRpc } from "@getpaseo/plugin";
import { z } from "zod";

const jsonObject = z.object({}).passthrough();

const interpreterStatus = z.object({
  status: z.enum(["ready", "missing", "blocked", "unknown"]),
  selectedPath: z.string().optional(),
  pythonVersion: z.string().optional(),
  detail: z.string().optional(),
  evidence: z.string().optional(),
});

const gitStatus = z.object({
  status: z.enum(["ready", "missing", "blocked", "unknown"]),
  version: z.string().optional(),
  path: z.string().optional(),
  detail: z.string(),
});

export const envStatusRpc = defineRpc({
  name: "memsharing.env.status",
  input: z.object({}).strict(),
  output: z.object({
    python: interpreterStatus,
    git: gitStatus,
    payload: z.object({
      status: z.enum(["ready", "missing"]),
      installerPath: z.string().optional(),
      searched: z.array(z.string()),
    }),
    releaseIdentity: z.object({
      manifestSha256: z.string().regex(/^[a-f0-9]{64}$/).optional(),
      status: z.enum(["ready", "missing"]),
      detail: z.string(),
    }),
    durableSource: z.object({
      status: z.enum(["ready", "missing"]),
      sourceManifestPath: z.string().optional(),
      installerPath: z.string().optional(),
      detail: z.string(),
    }),
  }),
});

// A preview ends in one of: dependency/identity gates, an approval plan to
// confirm, an already-prepared state, or a terminal CLI envelope.
const previewStatus = z.discriminatedUnion("status", [
  z.object({ status: z.literal("missing_dependency"), dependency: z.enum(["python", "git"]), detail: z.string() }),
  z.object({ status: z.literal("identity_missing"), detail: z.string() }),
  z.object({ status: z.literal("payload_missing"), detail: z.string(), searched: z.array(z.string()) }),
  z.object({ status: z.literal("already_prepared"), sourceManifestPath: z.string() }),
  z.object({
    status: z.literal("approval_required"),
    planKind: z.string(),
    digest: z.string(),
    confirmationToken: z.string(),
    summary: z.array(z.object({ label: z.string(), value: z.string() })),
    plan: jsonObject,
  }),
  z.object({ status: z.literal("completed"), envelope: jsonObject }),
  z.object({
    status: z.literal("failed"),
    code: z.string(),
    message: z.string(),
    envelope: jsonObject.optional(),
  }),
]);

export const bootstrapPreviewRpc = defineRpc({
  name: "memsharing.bootstrap.preview",
  input: z.object({}).strict(),
  output: previewStatus,
});

export const confirmAction = z.object({
  action: z.enum(["confirm", "reject"]),
  confirmationToken: z.string().optional(),
});

const confirmStatus = z.discriminatedUnion("status", [
  z.object({ status: z.literal("rejected") }),
  z.object({ status: z.literal("stale_plan"), detail: z.string() }),
  z.object({ status: z.literal("no_pending_plan"), detail: z.string() }),
  z.object({
    status: z.literal("acquired"),
    sourceManifestPath: z.string(),
    installerPath: z.string(),
    envelope: jsonObject,
  }),
  z.object({ status: z.literal("completed"), envelope: jsonObject }),
  z.object({
    status: z.literal("failed"),
    code: z.string(),
    message: z.string(),
    envelope: jsonObject.optional(),
  }),
]);

export const bootstrapConfirmRpc = defineRpc({
  name: "memsharing.bootstrap.confirm",
  input: confirmAction.strict(),
  output: confirmStatus,
});

export const dependencyPreviewRpc = defineRpc({
  name: "memsharing.dependency.preview", input: z.object({}).strict(), output: previewStatus,
});
export const dependencyConfirmRpc = defineRpc({
  name: "memsharing.dependency.confirm", input: confirmAction.strict(), output: confirmStatus,
});

export const machinePreviewRpc = defineRpc({
  name: "memsharing.machine.preview",
  input: z
    .object({
      agents: z.array(z.enum(["codex", "claude", "workbuddy", "dsh", "zcode", "opencode"])).min(1),
    })
    .strict(),
  output: previewStatus,
});

export const machineConfirmRpc = defineRpc({
  name: "memsharing.machine.confirm",
  input: confirmAction.strict(),
  output: confirmStatus,
});

export const projectCheckRpc = defineRpc({
  name: "memsharing.project.check",
  input: z.object({ projectRoot: z.string().min(1) }).strict(),
  output: z.object({
    status: z.enum(["completed", "gaps", "failed"]),
    envelope: jsonObject,
  }),
});

export const projectEnablePreviewRpc = defineRpc({
  name: "memsharing.project.enable.preview",
  input: z
    .object({
      projectRoot: z.string().min(1),
      agents: z.array(z.enum(["codex", "claude", "workbuddy", "dsh", "zcode", "opencode"])).min(1),
    })
    .strict(),
  output: previewStatus,
});

export const projectEnableConfirmRpc = defineRpc({
  name: "memsharing.project.enable.confirm",
  input: confirmAction.strict(),
  output: z.discriminatedUnion("status", [
    z.object({ status: z.literal("rejected") }),
    z.object({ status: z.literal("stale_plan"), detail: z.string() }),
    z.object({ status: z.literal("no_pending_plan"), detail: z.string() }),
    z.object({ status: z.literal("completed"), envelope: jsonObject }),
    z.object({
      status: z.literal("failed"),
      code: z.string(),
      message: z.string(),
      envelope: jsonObject.optional(),
    }),
  ]),
});

export const ckPreviewRpc = defineRpc({
  name: "memsharing.ck.preview",
  input: z.object({}).strict(),
  output: previewStatus,
});

export const ckConfirmRpc = defineRpc({
  name: "memsharing.ck.confirm",
  input: confirmAction.strict(),
  output: confirmStatus,
});

export const recoverPreviewRpc = defineRpc({
  name: "memsharing.recover.preview",
  input: z
    .object({
      journalPath: z.string().min(1),
      action: z.enum(["continue", "rollback"]).optional(),
    })
    .strict(),
  output: previewStatus,
});

export const recoverConfirmRpc = defineRpc({
  name: "memsharing.recover.confirm",
  input: confirmAction.strict(),
  output: confirmStatus,
});

export const cancelPendingRpc = defineRpc({
  name: "memsharing.pending.cancel",
  input: z.object({ flow: z.enum(["dependency", "bootstrap", "machine", "enable", "uninstall", "ck", "recover", "ckUninstall", "stagingCleanup", "fusion"]) }).strict(),
  output: z.object({ status: z.enum(["cancel_requested", "cleared", "none"]) }),
});

export const operationStatusRpc = defineRpc({
  name: "memsharing.operation.status", input: z.object({}).strict(),
  output: z.array(jsonObject),
});

// ---- full-machine uninstall (2026-11-01 retirement) ----------------------
// The retired project "remove" flow is replaced by the core-routed
// uninstall-machine / recover-uninstall commands. Exit-code contract for the
// new flows: approval_required=5, failed=2, completed/restored/retained=0;
// the envelope's structured status is validated alongside the exit code and
// rc alone never classifies the outcome.

export const uninstallPreviewRpc = defineRpc({
  name: "memsharing.uninstall.preview",
  input: z.object({ backupDir: z.string().min(1) }).strict(),
  output: previewStatus,
});

export const uninstallConfirmRpc = defineRpc({
  name: "memsharing.uninstall.confirm",
  input: confirmAction.strict(),
  output: confirmStatus,
});

export const uninstallRecoverPreviewRpc = defineRpc({
  name: "memsharing.uninstall.recover.preview",
  input: z
    .object({
      manifest: z.string().min(1),
      action: z.enum(["restore", "resume"]).optional(),
    })
    .strict(),
  output: previewStatus,
});

export const uninstallRecoverConfirmRpc = defineRpc({
  name: "memsharing.uninstall.recover.confirm",
  input: confirmAction.strict(),
  output: confirmStatus,
});

// Host-side staging inventory: no path inputs; entries are derived from
// product-owned constants and reference cleanup candidates by id only. The
// RPC never grants deletion rights — cleanup happens inside the core's exact
// approved plan, never by an RPC-supplied path.
export const stagingInventoryRpc = defineRpc({
  name: "memsharing.staging.inventory",
  input: z.object({}).strict(),
  output: z.object({
    schema_version: z.literal(1),
    home: z.string(),
    host: z.string(),
    roots: z.object({
      plugin_staging: z.string(),
      durable_sources: z.string(),
      private_runtimes: z.string(),
    }),
    entries: z.array(
      z.object({
        id: z.string(),
        kind: z.enum(["plugin_staging_op", "durable_source_export", "private_runtime"]),
        path: z.string(),
        ownership: z.enum(["proven", "unverified"]),
        activity: z.enum(["running", "terminal", "unknown"]),
        activity_evidence: jsonObject,
        disposition: z.enum(["preserve_external_then_clean", "block", "retain"]),
        reason: z.string(),
      }),
    ),
    notes: z.array(z.string()),
  }),
});

// Host-side staging cleanup: an EXPLICIT separate interaction (read-only
// preview → separate exact approval → byte-preserving externalization →
// verified per-artifact delete → host-receipt.json as the only remaining
// staging content). The uninstall preview never cleans or writes receipts.
export const stagingCleanupPreviewRpc = defineRpc({
  name: "memsharing.staging.cleanup.preview",
  input: z.object({ evidenceDir: z.string().min(1) }).strict(),
  output: previewStatus,
});

export const stagingCleanupConfirmRpc = defineRpc({
  name: "memsharing.staging.cleanup.confirm",
  input: confirmAction.strict(),
  output: confirmStatus,
});

// ---- post-uninstall Context Keeper follow-up ------------------------------
// Independent path, never reusing the uninstall approval. Default is retain;
// uninstall requires an explicit user-selected CK source and hosts. The
// external recover.py wrapper converts the upstream CK installer exit codes
// to the unified contract (5 approval / 2 failed / 0 completed|retained).

export const CK_FOLLOWUP_HOSTS = ["codex", "claude", "cursor", "workbuddy", "hermes", "opencode", "openclaw"] as const;

export const ckChoiceRetainRpc = defineRpc({
  name: "memsharing.ck.choice.retain",
  input: z.object({ manifest: z.string().min(1) }).strict(),
  output: z.object({
    status: z.enum(["completed", "failed"]),
    envelope: jsonObject.optional(),
    code: z.string().optional(),
    message: z.string().optional(),
  }),
});

export const ckUninstallPreviewRpc = defineRpc({
  name: "memsharing.ck.uninstall.preview",
  input: z
    .object({
      manifest: z.string().min(1),
      ckSource: z.string().min(1),
      ckAgents: z.array(z.enum(CK_FOLLOWUP_HOSTS)).min(1),
      ckProject: z.string().optional(),
    })
    .strict(),
  output: previewStatus,
});

export const ckUninstallConfirmRpc = defineRpc({
  name: "memsharing.ck.uninstall.confirm",
  input: confirmAction.strict(),
  output: confirmStatus,
});

// Preview is read-only; numbered selection executes the displayed kernel plan.
const fusionOutput = z.object({ status: z.enum(["completed", "failed"]), envelope: jsonObject,
  contextToken: z.string().optional() });
export const fusionPreviewRpc = defineRpc({ name: "memsharing.fusion.preview",
  input: z.object({ scope: z.enum(["user", "project"]), projectRoot: z.string().optional() }).strict(), output: fusionOutput });
export const fusionSelectRpc = defineRpc({ name: "memsharing.fusion.select",
  input: z.object({ scope: z.enum(["user", "project"]), projectRoot: z.string().optional(),
    selection: z.string().optional(), decline: z.boolean().optional(), contextToken: z.string(),
    retentions: z.record(z.string(), z.string()).optional() }).strict(), output: fusionOutput });
export const fusionConfirmRpc = defineRpc({ name: "memsharing.fusion.confirm", input: confirmAction.strict(), output: confirmStatus });

export const detectAgentsRpc = defineRpc({ name: "memsharing.agents.detect", input: z.object({}).strict(),
  output: z.object({ status: z.enum(["completed", "failed"]), envelope: jsonObject }) });

// Agent-authored exact proposals; all bases/contexts/spans remain untrusted
// input and are validated by the original kernel against actual bytes.
export const fusionProposeRpc = defineRpc({ name: "memsharing.fusion.propose",
  input: z.object({ scope: z.enum(["user", "project"]), projectRoot: z.string().optional(), contextToken: z.string(),
    equivalentSources: z.array(jsonObject).optional(), publicReuse: z.array(jsonObject).optional() }).strict(), output: fusionOutput });
