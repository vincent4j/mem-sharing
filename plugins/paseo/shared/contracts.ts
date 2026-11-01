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
      agents: z.array(z.enum(["codex", "claude", "workbuddy", "dsh", "zcode"])).min(1),
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
      agents: z.array(z.enum(["codex", "claude", "workbuddy", "dsh", "zcode"])).min(1),
      memory: z.enum(["enable", "disable"]).optional(),
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

export const projectRemovePreviewRpc = defineRpc({
  name: "memsharing.project.remove.preview",
  input: z.object({ projectRoot: z.string().min(1) }).strict(),
  output: previewStatus,
});

export const projectRemoveConfirmRpc = defineRpc({
  name: "memsharing.project.remove.confirm",
  input: confirmAction.strict(),
  output: confirmStatus,
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
  input: z.object({ flow: z.enum(["dependency", "bootstrap", "machine", "enable", "remove", "ck", "recover"]) }).strict(),
  output: z.object({ status: z.enum(["cancel_requested", "cleared", "none"]) }),
});

export const operationStatusRpc = defineRpc({
  name: "memsharing.operation.status", input: z.object({}).strict(),
  output: z.array(jsonObject),
});
