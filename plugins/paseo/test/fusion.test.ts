import assert from "node:assert/strict";
import { test } from "node:test";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { Orchestrator, type Runner } from "../server/orchestrator";
import { fusionGroups, fusionResult } from "../client/fusion";

function fixture() {
  const home = fs.realpathSync(fs.mkdtempSync(path.join(os.tmpdir(), "ms-fusion-")));
  const scripts = path.join(home, ".local/share/mem-sharing/scripts"); fs.mkdirSync(scripts, { recursive: true });
  fs.writeFileSync(path.join(scripts, "agm.py"), "# fixture"); fs.writeFileSync(path.join(scripts, "install.py"), "# fixture");
  const calls: string[][] = []; let drift = false; let fail = false;
  const plan = { command: "organize-user-rules", request: { home, scope: "user" }, scope: "user", project: null,
    observations: { source: "stable" }, groups: [{ number: 1, summary: "共同项", sources: [{ source: "one", text: "- 完整原文\n" }] }], selected_numbers: [1], changes: [{ path: "one" }] };
  const runner: Runner = { async run(argv) {
    calls.push([...argv]);
    const approvalAt = argv.indexOf("--approval-file");
    if (approvalAt >= 0) {
      const approval = JSON.parse(fs.readFileSync(argv[approvalAt + 1], "utf8"));
      assert.deepEqual(approval, { ...plan, confirmed_at: approval.confirmed_at, reference: approval.reference });
      assert.match(approval.confirmed_at, /Z$/); assert.match(approval.reference, /fusion.*user press/);
      assert.ok(!argv.includes("--selection")); assert.ok(!argv.includes("--retention-file"));
      return { kind: "completed", exitCode: fail ? 2 : 0, stdout: JSON.stringify(fail ? { status: "recovery_required", manifest: "/backup/manifest.json", errors: [] } : { status: "completed", fusion_status: "completed" }) };
    }
    const viewed = argv.includes("查看 1"); const declined = argv.includes("--decline");
    return { kind: "completed", exitCode: viewed || declined ? 0 : 5, stdout: JSON.stringify({
      status: viewed ? "viewed" : declined ? "completed" : "approval_required", prompt: "默认共享\n1. 共同项\n由你选择是否共享", fusion_status: declined ? "declined" : "pending_confirmation",
      approval_plan: { ...plan, observations: { source: drift ? "changed" : "stable" }, ...(viewed ? { view: 1, changes: [] } : declined ? { declined: true, changes: [] } : {}) },
    }) };
  } };
  const orch = new Orchestrator({ home, pluginDir: null, searchedPluginDirs: [], runner,
    pythonProbe: async () => ({ status: "ready", selected: { origin: "system", path: "/usr/bin/python3", status: "ready", probe: { pythonVersion: "3.13.0", executable: "/usr/bin/python3", machine: "arm64", platform: "Darwin", stdlibOk: true } }, candidates: [], evidence: "fixture" }) });
  return { home, scripts, orch, calls, runner, drift: () => { drift = true; }, fail: () => { fail = true; }, cleanup: () => fs.rmSync(home, { recursive: true, force: true }) };
}

test("fusion: initial/read original never grant approval; select then exact one-use confirmation", async () => {
  const f = fixture(); try {
    const initial = await f.orch.fusionPreview({ scope: "user" }); assert.equal(initial.status, "completed"); assert.equal(initial.approval, undefined);
    const viewed = await f.orch.fusionPreview({ scope: "user", contextToken: initial.contextToken, selection: "查看 1" });
    assert.equal(viewed.approval, undefined); assert.equal(fusionGroups(viewed.envelope)[0].original, "one\n- 完整原文\n");
    assert.match(fusionResult(viewed.envelope), /只读/);
    const chosen = await f.orch.fusionPreview({ scope: "user", contextToken: initial.contextToken, selection: "按默认方案" });
    assert.equal(chosen.approval?.status, "approval_required"); if (chosen.approval?.status !== "approval_required") return;
    const bad = await f.orch.fusionConfirm({ action: "confirm", confirmationToken: "other" }); assert.equal(bad.status, "stale_plan");
    // Wrong tokens invalidate the old plan; a new preview is required.
    const again = await f.orch.fusionPreview({ scope: "user", contextToken: initial.contextToken, selection: "按默认方案" });
    if (again.approval?.status !== "approval_required") assert.fail(JSON.stringify(again));
    const done = await f.orch.fusionConfirm({ action: "confirm", confirmationToken: again.approval.confirmationToken }); assert.equal(done.status, "completed");
    assert.equal((await f.orch.fusionConfirm({ action: "confirm", confirmationToken: again.approval.confirmationToken })).status, "no_pending_plan");
  } finally { f.cleanup(); }
});

test("fusion: decline is read only; stale scene blocks numbered choices", async () => {
  const f = fixture(); try {
    const initial = await f.orch.fusionPreview({ scope: "project", projectRoot: "/fixture/project" });
    const no = await f.orch.fusionPreview({ scope: "project", projectRoot: "/fixture/project", contextToken: initial.contextToken, decline: true });
    assert.equal(no.envelope.fusion_status, "declined"); assert.equal(no.approval, undefined); assert.ok(f.calls.at(-1)?.includes("--decline"));
    f.drift(); const stale = await f.orch.fusionPreview({ scope: "project", projectRoot: "/fixture/project", contextToken: initial.contextToken, selection: "1" });
    assert.equal(stale.status, "failed"); assert.equal(stale.approval, undefined);
    assert.ok(f.calls.every(argv => !argv.includes("--approval-file")));
  } finally { f.cleanup(); }
});

test("fusion: kernel drift rejects confirm; recovery_required remains unknown operation", async () => {
  const f = fixture(); try {
    const initial = await f.orch.fusionPreview({ scope: "user" });
    let chosen = await f.orch.fusionPreview({ scope: "user", contextToken: initial.contextToken, selection: "1" });
    if (chosen.approval?.status !== "approval_required") assert.fail();
    fs.appendFileSync(path.join(f.scripts, "agm.py"), "# changed");
    assert.equal((await f.orch.fusionConfirm({ action: "confirm", confirmationToken: chosen.approval.confirmationToken })).status, "stale_plan");
    chosen = await f.orch.fusionPreview({ scope: "user", contextToken: initial.contextToken, selection: "1" });
    if (chosen.approval?.status !== "approval_required") assert.fail();
    f.fail(); assert.equal((await f.orch.fusionConfirm({ action: "confirm", confirmationToken: chosen.approval.confirmationToken })).status, "failed");
    assert.ok(f.orch.operationStatus().some(record => record.state === "unknown" && record.journal === "/backup/manifest.json"));
  } finally { f.cleanup(); }
});


test("fusion: retention input is private, ephemeral and never becomes an approval argv", async () => {
  const f = fixture(); try {
    const initial = await f.orch.fusionPreview({ scope: "project", projectRoot: "/fixture/project" });
    let retainedPath = ""; const original = f.runner.run;
    f.runner.run = async (argv, options) => {
      const index = argv.indexOf("--retention-file");
      if (index >= 0) {
        retainedPath = argv[index + 1];
        assert.deepEqual(JSON.parse(fs.readFileSync(retainedPath, "utf8")), { "1": "CLAUDE.md" });
        assert.equal(fs.statSync(retainedPath).mode & 0o777, 0o600);
        assert.equal(fs.statSync(path.dirname(retainedPath)).mode & 0o777, 0o700);
        assert.ok(!retainedPath.startsWith(path.join(f.home, ".mem-sharing")));
      }
      return original(argv, options);
    };
    const selected = await f.orch.fusionPreview({ scope: "project", projectRoot: "/fixture/project", contextToken: initial.contextToken, selection: "不共享 1", retentions: { "1": "CLAUDE.md" } });
    assert.equal(selected.status, "completed"); assert.ok(retainedPath); assert.ok(!fs.existsSync(retainedPath)); assert.ok(!fs.existsSync(path.dirname(retainedPath)));
  } finally { f.cleanup(); }
});
