import assert from "node:assert/strict";
import { test } from "node:test";
import fs from "node:fs";
import path from "node:path";
import { assetFixture } from "../../shared/test/tool-fixture.ts";
import { Orchestrator } from "../server/orchestrator";

test("missing Python uses Node plan and independent single-use token, then resumes normal preview", async () => {
  const f = await assetFixture();
  try {
    let kernelCalls = 0;
    const orch = new Orchestrator({ home: f.home, pluginDir: null, searchedPluginDirs: [], toolAssets: [f.asset], allowInsecureAssetTransportForTests: true,
      pythonProbe: async () => ({ status: "missing", candidates: [], evidence: "no fixture interpreter" }),
      gitProbe: async () => ({ status: "ready", path: "/fixture/git", detail: "synthetic preexisting Git" }),
      runner: { async run() { kernelCalls++; throw new Error("must not invoke Python for asset preview"); } },
    });
    const before = fs.readdirSync(f.home);
    const preview = await orch.bootstrapPreview();
    assert.equal(preview.status, "approval_required");
    assert.equal(kernelCalls, 0); assert.equal(f.requests(), 0);
    if (preview.status !== "approval_required") throw new Error(JSON.stringify(preview));
    assert.equal(preview.planKind, "prepare-tool-assets");
    assert.equal((preview.plan.assets as any[])[0].sha256, f.asset.sha256);
    assert.equal((await orch.dependencyConfirm({ action: "confirm", confirmationToken: "wrong" })).status, "stale_plan");
    assert.equal(f.requests(), 0);
    assert.equal((await orch.dependencyConfirm({ action: "confirm", confirmationToken: preview.confirmationToken })).status, "completed");
    assert.equal((await orch.dependencyConfirm({ action: "confirm", confirmationToken: preview.confirmationToken })).status, "no_pending_plan");
    assert.equal(f.requests(), 1); assert.equal(kernelCalls, 0);
    assert.equal((await orch.bootstrapPreview()).status, "identity_missing");
    assert.deepEqual(before, []);
  } finally { await f.cleanup(); }
});

test("asset approval rejects changed destination and rejection performs no download", async () => {
  const f = await assetFixture();
  try {
    const orch = new Orchestrator({ home: f.home, pluginDir: null, searchedPluginDirs: [], toolAssets: [f.asset], allowInsecureAssetTransportForTests: true,
      pythonProbe: async () => ({ status: "missing", candidates: [], evidence: "missing" }),
      gitProbe: async () => ({ status: "ready", detail: "fixture" }), runner: { async run() { throw new Error("no kernel"); } },
    });
    const first = await orch.dependencyPreview();
    assert.equal((await orch.dependencyConfirm({ action: "reject" })).status, "rejected"); assert.equal(f.requests(), 0);
    const preview = await orch.dependencyPreview(); if (preview.status !== "approval_required") throw new Error(JSON.stringify(preview));
    const destination = String((preview.plan.scenes as any[])[0].destination);
    fs.mkdirSync(destination, { recursive: true }); fs.writeFileSync(path.join(destination, "foreign.txt"), "keep");
    assert.equal((await orch.dependencyConfirm({ action: "confirm", confirmationToken: preview.confirmationToken })).status, "stale_plan");
    assert.equal(f.requests(), 0); assert.equal(fs.readFileSync(path.join(destination, "foreign.txt"), "utf8"), "keep");
    assert.equal(first.status, "approval_required");
  } finally { await f.cleanup(); }
});

test("unsupported or specifically blocked official supply cannot be RPC-overridden", async () => {
  const f = await assetFixture();
  try {
    const orch = new Orchestrator({ home: f.home, pluginDir: null, searchedPluginDirs: [], toolAssets: [{ ...f.asset, blockedReason: "fixed upstream notice missing" }],
      pythonProbe: async () => ({ status: "missing", candidates: [], evidence: "missing" }), gitProbe: async () => ({ status: "ready", detail: "fixture" }), runner: { async run() { throw new Error("no kernel"); } },
    });
    const result = await orch.dependencyPreview(); assert.equal(result.status === "failed" && result.code, "supply_evidence_incomplete");
    assert.equal(f.requests(), 0);
  } finally { await f.cleanup(); }
});
