import assert from "node:assert/strict";
import { test } from "node:test";
import fs from "node:fs";
import { createHash } from "node:crypto";
import os from "node:os";
import path from "node:path";
import { Orchestrator, recordJournalForOperation, type CliRunOutcome, type Runner } from "../server/orchestrator";
import { planDigest as digestOf } from "../server/shared/common/digest";
import { isSha256Hex } from "../server/shared/common/digest";

// ---- fixtures -------------------------------------------------------------

function tempHome(): { home: string; cleanup: () => void } {
  const home = fs.realpathSync(fs.mkdtempSync(path.join(os.tmpdir(), "ms-orch-")));
  return { home, cleanup: () => fs.rmSync(home, { recursive: true, force: true }) };
}

const PYTHON = process.execPath.includes("node") ? "/usr/bin/python3" : "python3";

function readyPython() {
  return async () => ({
    status: "ready" as const,
    selected: {
      origin: "system" as const,
      path: PYTHON,
      status: "ready" as const,
      probe: { pythonVersion: "3.13.0", executable: PYTHON, machine: "arm64", platform: "Darwin", stdlibOk: true },
    },
    candidates: [],
    evidence: "fixture",
  });
}

function readyGit() {
  return async () => ({
    status: "ready" as const,
    version: "git version 9.9.9 (fixture)",
    path: "/usr/local/bin/git",
    detail: "fixture",
  });
}

interface ScriptedRunner extends Runner {
  calls: string[][];
}

// Runner that answers from a script and records every argv.
function scriptedRunner(responses: (() => CliRunOutcome)[]): ScriptedRunner {
  const calls: string[][] = [];
  let index = 0;
  return {
    calls,
    async run(argv) {
      calls.push([...argv]);
      const respond = responses[Math.min(index, responses.length - 1)];
      index += 1;
      return respond();
    },
  };
}

function completed(exitCode: number, payload: unknown): () => CliRunOutcome {
  return () => ({ kind: "completed", exitCode, stdout: JSON.stringify(payload), stderr: "" });
}

function pluginPayloadFixture(dir: string): string {
  const pluginDir = path.join(dir, "plugin");
  fs.mkdirSync(path.join(pluginDir, "payload", "core", "scripts"), { recursive: true });
  fs.writeFileSync(path.join(pluginDir, "payload", "core", "scripts", "install.py"), "# fixture\n");
  fs.writeFileSync(path.join(pluginDir, "payload", "release.json"), "{}\n");
  fs.writeFileSync(path.join(pluginDir, "paseo-plugin.json"), "{}\n");
  return pluginDir;
}

function durableSourceFixture(home: string): { sourceManifest: string; installer: string; tree: string } {
  const root = path.join(home, ".local", "share", "mem-sharing-sources", "0.1.3", "a".repeat(64), "core");
  fs.mkdirSync(path.join(root, "scripts"), { recursive: true });
  fs.writeFileSync(path.join(root, "..", "source-manifest.json"), "{}\n");
  fs.writeFileSync(path.join(root, "scripts", "install.py"), "# durable\n");
  fs.writeFileSync(path.join(root, "scripts", "agm.py"), "# agm\n");
  return { sourceManifest: path.join(root, "..", "source-manifest.json"), installer: path.join(root, "scripts", "install.py"), tree: root };
}

function activeKernelFixture(home: string): string {
  const root = path.join(home, ".local", "share", "mem-sharing");
  fs.mkdirSync(path.join(root, "scripts"), { recursive: true });
  fs.writeFileSync(path.join(root, "scripts", "agm.py"), "# active agm\n");
  fs.writeFileSync(path.join(root, "scripts", "install.py"), "# active installer\n");
  return path.join(root, "scripts", "agm.py");
}

const RELEASE_DIGEST = "c".repeat(64);

function makeOrchestrator(home: string, pluginDir: string | null, runner: Runner) {
  return new Orchestrator({
    runner,
    home,
    pluginDir,
    searchedPluginDirs: [],
    pythonProbe: readyPython(),
    gitProbe: readyGit(),
    releaseManifestSha256: RELEASE_DIGEST,
    now: () => new Date("2026-10-31T12:00:00Z"),
    newOperationId: () => "op-fixture",
  });
}

// ---- tests ----------------------------------------------------------------

test("bootstrap preview writes a server-owned delivery JSON and stores the export plan", async () => {
  const { home, cleanup } = tempHome();
  const pluginDir = pluginPayloadFixture(home);
  const runner = scriptedRunner([
    completed(5, { status: "approval_required", approval_plan: { command: "prepare-release-source", plan_sha256: "x" }, installation_complete: false, source_trust: "caller-trusted-package-required" }),
  ]);
  try {
    const orch = makeOrchestrator(home, pluginDir, runner);
    const outcome = await orch.bootstrapPreview();
    assert.equal(outcome.status, "approval_required");
    if (outcome.status !== "approval_required") return;
    assert.equal(outcome.planKind, "prepare-release-source");
    assert.match(outcome.digest, /^[0-9a-f]{64}$/);

    const argv = runner.calls[0];
    assert.equal(argv[0], PYTHON);
    assert.equal(argv[1], "-B");
    assert.equal(argv[2], path.join(pluginDir, "payload", "core", "scripts", "install.py"));
    assert.equal(argv[3], "--release-request");
    assert.ok(fs.existsSync(argv[4]));
    assert.equal(argv[5], "--operation-id");
    assert.equal(argv[6], "op-fixture");

    // The delivery JSON binds the release identity constant, not any input.
    const delivery = JSON.parse(fs.readFileSync(argv[4], "utf8"));
    assert.deepEqual(delivery, {
      kind: "plugin-package",
      payload: path.join(pluginDir, "payload"),
      manifest_sha256: RELEASE_DIGEST,
    });
  } finally {
    cleanup();
  }
});

test("bootstrap confirm executes alone with --approval-file and maps acquired", async () => {
  const { home, cleanup } = tempHome();
  const pluginDir = pluginPayloadFixture(home);
  const runner = scriptedRunner([
    completed(5, { status: "approval_required", approval_plan: { command: "prepare-release-source" } }),
    completed(0, { status: "acquired", installation_complete: false, source_manifest: path.join(home, "sm.json") }),
  ]);
  try {
    const orch = makeOrchestrator(home, pluginDir, runner);
    const preview = await orch.bootstrapPreview();
    if (preview.status !== "approval_required") throw new Error("preview must be approval_required");
    const confirmed = await orch.bootstrapConfirm({ action: "confirm", confirmationToken: preview.confirmationToken });
    assert.equal(confirmed.status, "acquired");
    if (confirmed.status !== "acquired") return;

    const argv = runner.calls[1];
    // Export approval is applied independently: exactly [python, -B, installer, --approval-file, file].
    assert.deepEqual(argv.slice(0, 4), [PYTHON, "-B", path.join(pluginDir, "payload", "core", "scripts", "install.py"), "--approval-file"]);
    const approval = JSON.parse(fs.readFileSync(argv[4], "utf8"));
    assert.deepEqual(approval, {
      command: "prepare-release-source",
      confirmed_at: "2026-10-31T12:00:00Z",
      reference: "paseo-plugin memsharing bootstrap confirm-screen user press",
    });
  } finally {
    cleanup();
  }
});

test("wrong digest never executes the plan", async () => {
  const { home, cleanup } = tempHome();
  const pluginDir = pluginPayloadFixture(home);
  const runner = scriptedRunner([
    completed(5, { status: "approval_required", approval_plan: { command: "prepare-release-source" } }),
  ]);
  try {
    const orch = makeOrchestrator(home, pluginDir, runner);
    await orch.bootstrapPreview();
    const outcome = await orch.bootstrapConfirm({ action: "confirm", confirmationToken: "0".repeat(64) });
    assert.equal(outcome.status, "stale_plan");
    assert.equal(runner.calls.length, 1);
  } finally {
    cleanup();
  }
});

test("reject clears the pending plan", async () => {
  const { home, cleanup } = tempHome();
  const pluginDir = pluginPayloadFixture(home);
  const runner = scriptedRunner([
    completed(5, { status: "approval_required", approval_plan: { command: "prepare-release-source" } }),
  ]);
  try {
    const orch = makeOrchestrator(home, pluginDir, runner);
    const preview = await orch.bootstrapPreview();
    if (preview.status !== "approval_required") throw new Error("unexpected");
    assert.equal((await orch.bootstrapConfirm({ action: "reject" })).status, "rejected");
    const after = await orch.bootstrapConfirm({ action: "confirm", confirmationToken: preview.confirmationToken });
    assert.equal(after.status, "no_pending_plan");
    assert.equal(runner.calls.length, 1);
  } finally {
    cleanup();
  }
});

test("dev sentinel release identity blocks bootstrap (fail-closed, no fake hash)", async () => {
  const { home, cleanup } = tempHome();
  const pluginDir = pluginPayloadFixture(home);
  const runner = scriptedRunner([]);
  try {
    const orch = new Orchestrator({
      runner,
      home,
      pluginDir,
      searchedPluginDirs: [],
      pythonProbe: readyPython(),
      gitProbe: readyGit(),
      // Explicitly exercise the sentinel independent of the checked-in release identity.
      releaseManifestSha256: "",
      now: () => new Date(),
    });
    const identity = orch.releaseIdentity();
    assert.equal(identity.status, "missing");
    const outcome = await orch.bootstrapPreview();
    assert.equal(outcome.status, "identity_missing");
    assert.equal(runner.calls.length, 0);
  } finally {
    cleanup();
  }
});

test("machine preview uses the durable export with repeated --agent flags", async () => {
  const { home, cleanup } = tempHome();
  durableSourceFixture(home);
  const source = durableSourceFixture(home);
  const plan = { command: "install-machine-cli", version: "0.1.3", source: { root: source.tree, commit: "a".repeat(40) } };
  const runner = scriptedRunner([
    completed(5, { status: "approval_required", approval_plan: plan }),
    completed(0, { status: "completed", product: {} }),
  ]);
  try {
    const orch = makeOrchestrator(home, pluginPayloadFixture(home), runner);
    const outcome = await orch.machinePreview(["codex", "zcode"]);
    assert.equal(outcome.status, "approval_required");
    const previewArgv = runner.calls[0];
    assert.equal(previewArgv.indexOf("--release-request") > 0, true);
    const confirm = await orch.machineConfirm({ action: "confirm", confirmationToken: outcome.status === "approval_required" ? outcome.confirmationToken : "" });
    assert.equal(confirm.status, "completed");
    const confirmArgv = runner.calls[1];
    // install.py uses repeated single --agent flags.
    const agentPositions = confirmArgv.filter((token) => token === "--agent").length;
    assert.equal(agentPositions, 2);
    assert.equal(confirmArgv[confirmArgv.length - 2], "--approval-file");
  } finally {
    cleanup();
  }
});

test("enable preview passes --preview last and confirm drops it for --approval-file", async () => {
  const { home, cleanup } = tempHome();
  activeKernelFixture(home);
  const template = JSON.stringify({
    schema_version: 1,
    command: "enable-memory",
    main_checkout: "/proj",
    memory_policy: "default",
    agents: ["codex"],
    confirmed_at: "<UTC timestamp>",
    reference: "<user confirmation reference>",
  });
  const runner = scriptedRunner([
    completed(5, { status: "approval_required", next_action: template }),
    completed(0, { status: "completed" }),
  ]);
  try {
    const orch = makeOrchestrator(home, null, runner);
    const preview = await orch.projectEnablePreview({ projectRoot: "/proj", agents: ["codex", "dsh"] });
    assert.equal(preview.status, "approval_required");
    const previewArgv = runner.calls[0];
    assert.equal(previewArgv[previewArgv.length - 1], "--preview");
    assert.equal(previewArgv.includes("--approval-file"), false);
    // enable-memory uses ONE multi-value --agent flag.
    assert.equal(previewArgv.filter((token) => token === "--agent").length, 1);
    assert.deepEqual(previewArgv.slice(previewArgv.indexOf("--agent") + 1, previewArgv.indexOf("--agent") + 3), ["codex", "dsh"]);

    if (preview.status !== "approval_required") return;
    const confirm = await orch.projectEnableConfirm({ action: "confirm", confirmationToken: preview.confirmationToken });
    assert.equal(confirm.status, "completed");
    const confirmArgv = runner.calls[1];
    assert.equal(confirmArgv.includes("--preview"), false);
    assert.equal(confirmArgv[confirmArgv.length - 2], "--approval-file");
    const approval = JSON.parse(fs.readFileSync(confirmArgv[confirmArgv.length - 1], "utf8"));
    // Approval = template minus the two evidence placeholders plus real evidence.
    assert.deepEqual(Object.keys(approval).sort(), ["agents", "command", "confirmed_at", "main_checkout", "memory_policy", "reference", "schema_version"]);
    assert.equal(approval.confirmed_at, "2026-10-31T12:00:00Z");
    assert.equal(typeof approval.reference, "string");
  } finally {
    cleanup();
  }
});

test("enable plan containing rebuild is blocked structurally", async () => {
  const { home, cleanup } = tempHome();
  activeKernelFixture(home);
  const template = JSON.stringify({
    command: "enable-memory",
    rebuild: { registry_sha256: "d".repeat(64) },
    confirmed_at: "<UTC timestamp>",
    reference: "<user confirmation reference>",
  });
  const runner = scriptedRunner([completed(5, { status: "approval_required", next_action: template })]);
  try {
    const orch = makeOrchestrator(home, null, runner);
    const preview = await orch.projectEnablePreview({ projectRoot: "/proj", agents: ["codex"] });
    assert.equal(preview.status, "failed");
    if (preview.status === "failed") assert.equal(preview.code, "rebuild_confirmation_required");
    // A second preview+confirm must not find any pending plan.
    const confirm = await orch.projectEnableConfirm({ action: "confirm", confirmationToken: "x" });
    assert.equal(confirm.status, "no_pending_plan");
  } finally {
    cleanup();
  }
});

test("uninstall uses core envelope and preserves partial host status, without rebuilding staging", async () => {
  const { home, cleanup } = tempHome(); activeKernelFixture(home);
  const plan = { command: "uninstall-machine", plan_sha256: "a".repeat(64), changes: [], agents: ["codex"], host_obligation: { plugin_id: "custom-id" } };
  const runner = scriptedRunner([completed(5, { status: "approval_required", plan }), completed(0, { status: "completed", machine_assets: "completed", host_plugin: "pending", overall: "partial" })]);
  try {
    const dir=pluginPayloadFixture(home);
    const orch = new Orchestrator({runner,home,pluginDir:dir,searchedPluginDirs:[],pluginRecords:[{id:"custom-id",source:"directory",path:dir,enabled:true}],pythonProbe:readyPython(),gitProbe:readyGit()});
    const preview = await orch.uninstallPreview(path.join(home, "external-backup"));
    assert.equal(preview.status, "approval_required", JSON.stringify(preview));
    assert.ok(runner.calls[0].includes("uninstall-machine"));assert.ok(runner.calls[0].includes("--host-obligation"));
    assert.equal(runner.calls[0][runner.calls[0].indexOf("--host-plugin-id")+1],"custom-id");
    assert.equal(runner.calls[0][runner.calls[0].indexOf("--host-plugin-source")+1],dir);
    assert.equal(fs.existsSync(path.join(home,".local/share/mem-sharing-plugin-staging")),false);
    if (preview.status !== "approval_required") return;
    const result = await orch.uninstallConfirm({ action: "confirm", confirmationToken: preview.confirmationToken });
    assert.equal(result.status,"completed");
    if(result.status === "completed") assert.equal(result.envelope.overall,"partial");
    assert.equal(fs.existsSync(path.join(home,".local/share/mem-sharing-plugin-staging")),false);
    assert.equal((await orch.bootstrapPreview()).status,"failed");
  } finally { cleanup(); }
});

test("ck preview/confirm keeps the independent CK approval shape", async () => {
  const { home, cleanup } = tempHome();
  activeKernelFixture(home);
  const plan = { command: "install-context-keeper", source: { root: "/durable/ck" } };
  const runner = scriptedRunner([completed(5, { status: "approval_required", approval_plan: plan }), completed(0, { status: "completed" })]);
  try {
    const orch = makeOrchestrator(home, null, runner);
    const preview = await orch.ckPreview("/durable/ck");
    assert.equal(preview.status, "approval_required");
    const previewArgv = runner.calls[0];
    assert.deepEqual(previewArgv.slice(3, 5), ["--context-keeper", "--ck-source"]);
    assert.equal(previewArgv[5], "/durable/ck");
    if (preview.status !== "approval_required") return;
    const confirm = await orch.ckConfirm({ action: "confirm", confirmationToken: preview.confirmationToken });
    assert.equal(confirm.status, "completed");
  } finally {
    cleanup();
  }
});

test("recover preview/confirm forwards the journal and action", async () => {
  const { home, cleanup } = tempHome();
  const agm = activeKernelFixture(home);
  const kernel = path.dirname(agm);
  fs.mkdirSync(path.join(kernel, "agm_core"));
  fs.writeFileSync(path.join(kernel, "agm_core", "__init__.py"), "# fixed");
  const sha = (p: string) => createHash("sha256").update(fs.readFileSync(p)).digest("hex");
  const journal = path.join(home, "journal.json");
  fs.writeFileSync(journal, JSON.stringify({ plan: { layout: { root: path.join(home, ".mem-sharing") }, source: { root: path.dirname(kernel), files: { "scripts/install.py": sha(path.join(kernel, "install.py")) } }, tools: [{ path: "__init__.py", sha256: sha(path.join(kernel, "agm_core", "__init__.py")) }] } }));
  const plan = { command: "machine-recover", action: "continue" };
  const runner = scriptedRunner([completed(5, { status: "approval_required", approval_plan: plan }), completed(0, { status: "completed" })]);
  try {
    const orch = makeOrchestrator(home, null, runner);
    const preview = await orch.recoverPreview({ journalPath: journal, action: "continue" });
    assert.equal(preview.status, "approval_required");
    const previewArgv = runner.calls[0];
    assert.deepEqual(previewArgv.slice(3), ["--recover", journal, "--action", "continue"]);
    if (preview.status !== "approval_required") return;
    const confirm = await orch.recoverConfirm({ action: "confirm", confirmationToken: preview.confirmationToken });
    assert.equal(confirm.status, "completed");
    const confirmArgv = runner.calls[1];
    assert.deepEqual(confirmArgv.slice(3, 7), ["--recover", journal, "--action", "continue"]);
    assert.equal(confirmArgv[confirmArgv.length - 2], "--approval-file");
  } finally {
    cleanup();
  }
});

test("digest helper sanity for this suite", () => {
  assert.equal(isSha256Hex(RELEASE_DIGEST), true);
});

test("same-plan previews have equal plan digests and distinct single-use confirmation tokens", async () => {
  const { home, cleanup } = tempHome();
  try {
    const runner = scriptedRunner([completed(5, { status: "approval_required", approval_plan: { command: "prepare-release-source" } }), completed(5, { status: "approval_required", approval_plan: { command: "prepare-release-source" } }), completed(0, { status: "acquired", source_manifest: path.join(home, "sm.json") })]);
    const orch = makeOrchestrator(home, pluginPayloadFixture(home), runner);
    const first = await orch.bootstrapPreview();
    const second = await orch.bootstrapPreview();
    assert.equal(first.status, "approval_required"); assert.equal(second.status, "approval_required");
    if (first.status !== "approval_required" || second.status !== "approval_required") return;
    assert.equal(first.digest, second.digest);
    assert.notEqual(first.confirmationToken, second.confirmationToken);
    assert.equal((await orch.bootstrapConfirm({ action: "confirm", confirmationToken: first.confirmationToken })).status, "stale_plan");
    assert.equal((await orch.bootstrapConfirm({ action: "confirm", confirmationToken: second.confirmationToken })).status, "acquired");
    assert.equal((await orch.bootstrapConfirm({ action: "confirm", confirmationToken: second.confirmationToken })).status, "no_pending_plan");
    assert.equal(runner.calls.length, 3);
  } finally { cleanup(); }
});

test("two workers never share request/approval files; kernel drift invalidates the confirmation envelope", async () => {
  const { home, cleanup } = tempHome();
  try {
    const plugin = pluginPayloadFixture(home);
    const runner = scriptedRunner([completed(5, { status: "approval_required", approval_plan: { command: "prepare-release-source" } })]);
    const a = makeOrchestrator(home, plugin, runner), b = makeOrchestrator(home, plugin, runner);
    const pa = await a.bootstrapPreview(), pb = await b.bootstrapPreview();
    assert.equal(pa.status, "approval_required"); assert.equal(pb.status, "approval_required");
    if (pa.status !== "approval_required" || pb.status !== "approval_required") return;
    assert.notEqual(runner.calls[0][4], runner.calls[1][4]);
    for (const call of runner.calls) assert.equal(fs.statSync(call[4]).mode & 0o777, 0o600);
    assert.equal((await b.bootstrapConfirm({ action: "confirm", confirmationToken: pa.confirmationToken })).status, "stale_plan");
    const installer = path.join(plugin, "payload/core/scripts/install.py");
    fs.writeFileSync(installer, "# drifted kernel\n");
    assert.equal((await a.bootstrapConfirm({ action: "confirm", confirmationToken: pa.confirmationToken })).status, "stale_plan");
    assert.equal(fs.readFileSync(installer, "utf8"), "# drifted kernel\n");
    assert.equal(runner.calls.length, 2);
  } finally { cleanup(); }
});

test("running cancel reaches the owned AbortSignal; concurrent flow calls are refused and restart reports unknown", async () => {
  const { home, cleanup } = tempHome();
  try {
    let calls = 0;
    let started!: () => void;
    const ready = new Promise<void>(resolve => { started = resolve; });
    const runner: Runner = { async run(_argv, options) {
      calls++;
      if (calls === 1) return { kind: "completed", exitCode: 5, stdout: JSON.stringify({ approval_plan: { command: "prepare-release-source" } }) };
      started();
      return new Promise(resolve => options.signal!.addEventListener("abort", () => resolve({ kind: "canceled" }), { once: true }));
    } };
    const plugin = pluginPayloadFixture(home);
    const orch = makeOrchestrator(home, plugin, runner);
    const plan = await orch.bootstrapPreview();
    if (plan.status !== "approval_required") throw new Error(JSON.stringify(plan));
    const execution = orch.bootstrapConfirm({ action: "confirm", confirmationToken: plan.confirmationToken });
    await ready;
    const busy = await orch.bootstrapPreview();
    assert.equal(busy.status, "failed"); if (busy.status === "failed") assert.equal(busy.code, "operation_busy");
    const restart = makeOrchestrator(home, plugin, runner);
    assert.ok(restart.operationStatus().some(r => r.state === "unknown"));
    assert.equal(orch.cancel("bootstrap").status, "cancel_requested");
    const canceled = await execution;
    assert.equal(canceled.status, "failed"); if (canceled.status === "failed") assert.equal(canceled.code, "cli_canceled");
    assert.ok(orch.operationStatus().some(r => r.state === "unknown"));
    assert.equal(calls, 2);
  } finally { cleanup(); }
});

test("CK acquisition is separately approved; rejection starts no Git fetch and RPC inputs cannot supply source trust", async () => {
  const { home, cleanup } = tempHome();
  try {
    activeKernelFixture(home);
    const runner = scriptedRunner([completed(1, { status: "failed", errors: [{ code: "ck_source_unavailable" }] })]);
    const orch = makeOrchestrator(home, null, runner);
    const plan = await orch.ckPreview();
    assert.equal(plan.status, "approval_required");
    if (plan.status !== "approval_required") return;
    assert.equal(plan.planKind, "prepare-context-keeper-source");
    assert.equal(plan.plan.commit, "86af15073c1da7fedddc34342eb10bba64062b73");
    assert.deepEqual(plan.plan.agents, ["codex", "claude", "workbuddy", "zcode", "dsh", "opencode"]);
    assert.equal((await orch.ckConfirm({ action: "reject" })).status, "rejected");
    assert.equal(runner.calls.length, 1);
    const contracts = fs.readFileSync(new URL("../shared/contracts.ts", import.meta.url), "utf8");
    const acquisition=contracts.slice(contracts.indexOf("export const ckPreviewRpc"),contracts.indexOf("export const ckConfirmRpc"));
    assert.equal(acquisition.includes("ckSource:"), false);
  } finally { cleanup(); }
});

test("every staging ancestor symlink fails structurally before any foreign write", async () => {
  for (const relative of [".local", ".local/share", ".local/share/mem-sharing-plugin-staging", ".local/share/mem-sharing-plugin-staging/pending"]) {
    const { home, cleanup } = tempHome();
    try {
      const foreign = path.join(home, "foreign");
      fs.mkdirSync(foreign);
      fs.mkdirSync(path.join(foreign, "existing"), { mode: 0o750 });
      fs.writeFileSync(path.join(foreign, "existing", "private"), "private bytes", { mode: 0o640 });
      const link = path.join(home, relative);
      fs.mkdirSync(path.dirname(link), { recursive: true });
      fs.symlinkSync(foreign, link);
      const snapshot = (): unknown => {
        const nodes: unknown[] = [];
        const walk = (file: string): void => {
          const st = fs.lstatSync(file);
          nodes.push([path.relative(foreign, file), st.mode, st.mtimeMs, st.isFile() ? fs.readFileSync(file).toString("hex") : null]);
          if (st.isDirectory()) for (const name of fs.readdirSync(file).sort()) walk(path.join(file, name));
        };
        walk(foreign); return nodes;
      };
      const before = snapshot();
      const runner = scriptedRunner([]);
      const orch = makeOrchestrator(home, pluginPayloadFixture(home), runner);
      const outcome = await orch.bootstrapPreview();
      assert.equal(outcome.status, "failed", JSON.stringify(outcome));
      if (outcome.status === "failed") assert.equal(outcome.code, "operation_prepare_failed");
      assert.deepEqual(snapshot(), before, `foreign changed through ${relative}`);
      assert.equal(runner.calls.length, 0);
    } finally { cleanup(); }
  }
});

test("project rules forward no retired experience options", async () => {
  const { home, cleanup } = tempHome(); activeKernelFixture(home);
  try {
    const runner = scriptedRunner([completed(5,{next_action:JSON.stringify({command:"enable-memory",memory_policy:"follow_ck"})}),completed(0,{status:"completed"})]);
    const orch = makeOrchestrator(home,null,runner);
    const preview=await orch.projectEnablePreview({projectRoot:"/project",agents:["codex"]});
    assert.equal(preview.status,"approval_required");
    if(preview.status!=="approval_required")return;
    await orch.projectEnableConfirm({action:"confirm",confirmationToken:preview.confirmationToken});
    for(const argv of runner.calls){assert.equal(argv.includes("--memory"),false);assert.equal(argv.includes("--no-memory"),false);}
  } finally { cleanup(); }
});

test("operation record journal rule drops only this HOME's CK audit journal, keeps every other journal verbatim", () => {
  const home = "/fixtures/home";
  const varDir = path.join(home, ".mem-sharing", "var");
  const ckAudit = path.join(varDir, "ck-install-paseo-20261102045403Z-1c107197.json");
  // 仅 flow==ck 且精确命中本 HOME var/ck-install-*.json(受限字符集)才不写入。
  assert.equal(recordJournalForOperation("ck", ckAudit, home), undefined);
  // 同形但越出受限字符集/前缀不符 → 原样保留,交由 staging 认领规则拒绝。
  assert.equal(recordJournalForOperation("ck", path.join(varDir, "ck-install-../escape.json"), home), path.join(varDir, "ck-install-../escape.json"));
  assert.equal(recordJournalForOperation("ck", path.join(varDir, "ck-installnotes.json"), home), path.join(varDir, "ck-installnotes.json"));
  assert.equal(recordJournalForOperation("ck", path.join(varDir, "ck-install-.hidden.json"), home), path.join(varDir, "ck-install-.hidden.json"));
  // 他 HOME 的同形路径、OS 临时区、任意未知路径 → 原样保留。
  const foreignHome = path.join(varDir, "ck-install-paseo-20261102045403Z-1c107197.json").replace(home, "/other/home");
  assert.equal(recordJournalForOperation("ck", foreignHome, home), foreignHome);
  assert.equal(recordJournalForOperation("ck", "/tmp/ck-install-x.json", home), "/tmp/ck-install-x.json");
  // 非 ck 流程永不丢弃:可归结 install journal 与 ck 审计路径本身都原样保留。
  assert.equal(recordJournalForOperation("machine", ckAudit, home), ckAudit);
  assert.equal(recordJournalForOperation("machine", path.join(home, ".mem-sharing-install-op1", "journal.json"), home), path.join(home, ".mem-sharing-install-op1", "journal.json"));
  // 未知形态(null/undefined/空串/对象)行为与旧写入语义一致,原样返回。
  assert.equal(recordJournalForOperation("ck", undefined, home), undefined);
  assert.equal(recordJournalForOperation("ck", null, home), null);
  assert.equal(recordJournalForOperation("ck", "", home), "");
  const odd = { stray: true };
  assert.equal(recordJournalForOperation("machine", odd, home), odd);
});
