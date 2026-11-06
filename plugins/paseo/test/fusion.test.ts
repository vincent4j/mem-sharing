import assert from "node:assert/strict";
import { test } from "node:test";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { Orchestrator, type Runner } from "../server/orchestrator";
import { fusionGroups, contextKeeperResult } from "../client/fusion";

function fixture(scope: "user" | "project" = "user", projectRoot?: string) {
  const home = fs.realpathSync(fs.mkdtempSync(path.join(os.tmpdir(), "ms-fusion-")));
  const scripts = path.join(home, ".local/share/mem-sharing/scripts"); fs.mkdirSync(scripts, { recursive: true });
  for (const name of ["agm.py", "install.py"]) fs.writeFileSync(path.join(scripts, name), "# fixture");
  const calls: string[][] = []; let drift = false; let fail = false;
  const plan = { command: scope === "project" ? "organize-project-rules" : "organize-user-rules", request: { home, scope, ...(projectRoot ? { project: projectRoot } : {}) }, scope, project: projectRoot ?? null,
    layout: { home }, agents: ["codex"], observations: { source: "stable" },
    groups: [{ number: 1, sources: [{ source: "one", text: "- 完整原文\n" }] }] };
  const runner: Runner = { async run(argv) {
    calls.push([...argv]);
    const selected = argv.indexOf("--selection-plan-file");
    if (selected >= 0) {
      const file = argv[selected + 1];
      assert.deepEqual(JSON.parse(fs.readFileSync(file, "utf8")), plan);
      assert.equal(fs.statSync(file).mode & 0o777, 0o600);
      assert.equal(fs.statSync(path.dirname(file)).mode & 0o777, 0o700);
      assert.ok(argv.includes("--selection-reference")); assert.ok(!argv.includes("--approval-file"));
      return { kind: "completed", exitCode: drift || fail ? 2 : 0, stdout: JSON.stringify(drift ? { status: "failed", errors: [{ code: "drift" }] } : fail ? { status: "recovery_required", manifest: "/backup/manifest.json" } : { status: "completed", fusion_status: "completed", context_keeper: { status: "pending_selection" } }) };
    }
    const viewed = argv.includes("查看 1"), declined = argv.includes("--decline");
    return { kind: "completed", exitCode: viewed || declined ? 0 : 5, stdout: JSON.stringify({ status: viewed ? "viewed" : declined ? "completed" : "approval_required", fusion_status: declined ? "declined" : "pending_selection", approval_plan: { ...plan, ...(viewed ? { view: 1 } : {}) } }) };
  } };
  const orch = new Orchestrator({ home, pluginDir: null, searchedPluginDirs: [], runner,
    pythonProbe: async () => ({ status: "ready", selected: { origin: "system", path: "/usr/bin/python3", status: "ready", probe: { pythonVersion: "3.13.0", executable: "/usr/bin/python3", machine: "arm64", platform: "Darwin", stdlibOk: true } }, candidates: [], evidence: "fixture" }) });
  return { home, scripts, orch, calls, runner, drift: () => { drift = true; }, fail: () => { fail = true; }, cleanup: () => fs.rmSync(home, { recursive: true, force: true }) };
}

test("fusion: preview/view read only; one selection executes complete displayed scene", async () => {
  const f = fixture(); try {
    const initial = await f.orch.fusionPreview({ scope: "user" });
    const viewed = await f.orch.fusionSelect({ scope: "user", contextToken: initial.contextToken, selection: "查看 1" });
    assert.equal(viewed.status, "completed"); assert.equal(fusionGroups(viewed.envelope)[0].original, "one\n- 完整原文\n");
    assert.ok(!f.calls.at(-1)!.includes("--selection-reference"));
    const done = await f.orch.fusionSelect({ scope: "user", contextToken: initial.contextToken, selection: "按默认方案" });
    assert.equal(done.envelope.fusion_status, "completed"); assert.equal(done.approval, undefined);
    const file = f.calls.at(-1)![f.calls.at(-1)!.indexOf("--selection-plan-file") + 1]; assert.ok(!fs.existsSync(file));
    assert.equal((await f.orch.fusionSelect({ scope: "user", contextToken: initial.contextToken, selection: "1" })).status, "failed");
  } finally { f.cleanup(); }
});

test("fusion: decline never selects; kernel drift/recovery are preserved", async () => {
  const f = fixture(); try {
    let initial = await f.orch.fusionPreview({ scope: "user" });
    const no = await f.orch.fusionSelect({ scope: "user", contextToken: initial.contextToken, decline: true });
    assert.equal(no.envelope.fusion_status, "declined"); assert.ok(!f.calls.at(-1)!.includes("--selection-reference"));
    initial = await f.orch.fusionPreview({ scope: "user" }); f.drift();
    assert.equal((await f.orch.fusionSelect({ scope: "user", contextToken: initial.contextToken, selection: "1" })).status, "failed");
  } finally { f.cleanup(); }
  const g = fixture(); try {
    const initial = await g.orch.fusionPreview({ scope: "user" }); g.fail();
    assert.equal((await g.orch.fusionSelect({ scope: "user", contextToken: initial.contextToken, selection: "1" })).status, "failed");
    assert.ok(g.orch.operationStatus().some(r => r.state === "unknown" && r.journal === "/backup/manifest.json"));
  } finally { g.cleanup(); }
});

test("fusion: kernel binding, cross-scope and preview writes rejected", async () => {
  const f = fixture(); try {
    const initial = await f.orch.fusionPreview({ scope: "user" });
    assert.equal((await f.orch.fusionPreview({ scope: "user", selection: "1" })).status, "failed");
    assert.equal((await f.orch.fusionSelect({ scope: "project", projectRoot: "/fixture", contextToken: initial.contextToken, selection: "1" })).status, "failed");
    fs.appendFileSync(path.join(f.scripts, "agm.py"), "# drift");
    assert.equal((await f.orch.fusionSelect({ scope: "user", contextToken: initial.contextToken, selection: "1" })).status, "failed");
    assert.ok(f.calls.every(argv => !argv.includes("--selection-reference")));
  } finally { f.cleanup(); }
});

test("fusion: Agent proposal uses private ephemeral files and is reused with selection", async () => {
  const f = fixture(); try {
    const initial = await f.orch.fusionPreview({ scope: "user" });
    const equivalentSources = [{ sources: [{ source: "one", start: 0, end: 8, context: [], text_sha256: "untrusted", basis: {} }], canonical_context: [], reason: "Agent actual reading" }];
    const publicReuse = [{ source: "one", source_context: [], public_context: [], start: 0, end: 8, public_start: 0, public_end: 8, text_sha256: "untrusted", source_basis: {}, public_basis: {}, equivalent: true, reason: "Agent actual reading" }];
    const original = f.runner.run; const files: string[] = [];
    f.runner.run = async (argv, options) => {
      for (const [flag, value] of [["--equivalent-sources-file", equivalentSources], ["--public-reuse-file", publicReuse]] as const) {
        const at = argv.indexOf(flag); if (at < 0) continue;
        const file = argv[at + 1]; files.push(file);
        assert.deepEqual(JSON.parse(fs.readFileSync(file, "utf8")), value);
        assert.equal(fs.statSync(file).mode & 0o777, 0o600);
        assert.equal(fs.statSync(path.dirname(file)).mode & 0o777, 0o700);
      }
      return original(argv, options);
    };
    const proposed = await f.orch.fusionPropose({ scope: "user", contextToken: initial.contextToken, equivalentSources, publicReuse });
    assert.equal(proposed.status, "completed"); assert.ok(proposed.contextToken);
    assert.equal(files.length, 2); assert.ok(files.every(file => !fs.existsSync(file)));
    const selected = await f.orch.fusionSelect({ scope: "user", contextToken: proposed.contextToken, selection: "1" });
    assert.equal(selected.status, "completed"); assert.equal(files.length, 4);
    assert.ok(files.every(file => !fs.existsSync(file)));
  } finally { f.cleanup(); }
});

test("CK terminal wording distinguishes configured and unsupported/skipped", () => {
  assert.match(contextKeeperResult({ status: "configured" }), /配置完成.*\/context-keeper/);
  assert.match(contextKeeperResult({ status: "skipped" }), /未安装/);
  assert.doesNotMatch(contextKeeperResult({ status: "skipped" }), /配置完成/);
});


test("project retention: selection binds displayed scene; input is private and cleaned; view/decline ignore retention", async () => {
  const projectRoot = "/fixture/project";
  const f = fixture("project", projectRoot); try {
    const retentions = { "1": "CLAUDE.md" };
    const input = { scope: "project" as const, projectRoot };
    const initial = await f.orch.fusionPreview(input);
    const shown = initial.envelope.approval_plan;
    const viewed = await f.orch.fusionSelect({ ...input, contextToken: initial.contextToken, selection: "查看 1", retentions });
    assert.equal(viewed.status, "completed");
    assert.ok(!f.calls.at(-1)!.includes("--retention-file"));
    assert.ok(!f.calls.at(-1)!.includes("--selection-plan-file"));
    const declined = await f.orch.fusionSelect({ ...input, contextToken: initial.contextToken, decline: true, retentions });
    assert.equal(declined.envelope.fusion_status, "declined");
    assert.ok(!f.calls.at(-1)!.includes("--retention-file"));
    assert.ok(!f.calls.at(-1)!.includes("--selection-reference"));
    const next = await f.orch.fusionPreview(input);
    let retentionFile = ""; let shownFile = "";
    const original = f.runner.run;
    f.runner.run = async (argv, options) => {
      const at = argv.indexOf("--retention-file");
      if (at >= 0) {
        retentionFile = argv[at + 1];
        shownFile = argv[argv.indexOf("--selection-plan-file") + 1];
        assert.deepEqual(JSON.parse(fs.readFileSync(retentionFile, "utf8")), retentions);
        assert.equal(fs.statSync(retentionFile).mode & 0o777, 0o600);
        assert.equal(fs.statSync(path.dirname(retentionFile)).mode & 0o777, 0o700);
        assert.deepEqual(JSON.parse(fs.readFileSync(shownFile, "utf8")), shown);
        assert.deepEqual(JSON.parse(fs.readFileSync(shownFile, "utf8")), next.envelope.approval_plan);
        assert.equal(argv[argv.indexOf("--project") + 1], projectRoot);
        assert.equal(argv[argv.indexOf("--selection") + 1], "不共享 1");
        assert.equal(argv.filter(value => value === "--project").length, 1);
        assert.ok(!argv.includes("--agent"));
      }
      return original(argv, options);
    };
    const callsBeforeWrongScene = f.calls.length;
    const wrong = await f.orch.fusionSelect({ ...input, projectRoot: "/fixture/other", contextToken: next.contextToken, selection: "不共享 1", retentions });
    assert.equal(wrong.status, "failed"); assert.equal(f.calls.length, callsBeforeWrongScene);
    const selected = await f.orch.fusionSelect({ ...input, contextToken: next.contextToken, selection: "不共享 1", retentions });
    assert.equal(selected.status, "completed"); assert.ok(retentionFile); assert.ok(shownFile);
    for (const file of [retentionFile, shownFile]) assert.ok(!fs.existsSync(file));
    assert.ok(!fs.existsSync(path.dirname(retentionFile)));
    assert.ok(!fs.existsSync(path.join(f.home, "CLAUDE.md")));
  } finally { f.cleanup(); }
});

test("project retention: private inputs are cleaned on CLI failure", async () => {
  const projectRoot = "/fixture/project";
  const f = fixture("project", projectRoot); try {
    const initial = await f.orch.fusionPreview({ scope: "project", projectRoot });
    let file = "";
    f.runner.run = async argv => {
      file = argv[argv.indexOf("--retention-file") + 1];
      assert.deepEqual(JSON.parse(fs.readFileSync(file, "utf8")), { "1": "CLAUDE.md" });
      throw new Error("fixture interrupted retention selection");
    };
    const failed = await f.orch.fusionSelect({ scope: "project", projectRoot, contextToken: initial.contextToken, selection: "不共享 1", retentions: { "1": "CLAUDE.md" } });
    assert.equal(failed.status, "failed"); assert.ok(file);
    assert.ok(!fs.existsSync(file)); assert.ok(!fs.existsSync(path.dirname(file)));
    assert.ok(f.orch.operationStatus().some(row => row.state === "unknown"));
  } finally { f.cleanup(); }
});
