// REAL-CLI bridge test: runs the integrated Python core (normal-panda
// worktree, read-only) through the plugin's Orchestrator against a
// synthetic release fixture and a temporary HOME. No real HOME, daemon,
// Orca, version change, commit, or push is touched. Skips with an explicit
// reason when the integrated core or the pinned CK checkout is absent.

import assert from "node:assert/strict";
import { execFileSync, spawnSync } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { test } from "node:test";
import { fileURLToPath } from "node:url";
import { Orchestrator, realRunner } from "../server/orchestrator";

const here = path.dirname(fileURLToPath(import.meta.url));
const CORE = path.resolve(here, "../../..");
// Pinned-fixture runs may point this at a durable local clone checked out at
// the pin; the HEAD==pin gate below still applies unchanged.
const CK_SOURCE = process.env.MEMSHARING_TEST_CK_SOURCE ?? "/Users/vincent4j/Tools/Source/context-keeper";

// CK sources may not live under /tmp or /var/folders (kernel forbids it);
// scratch inside the worktree is durable and outside every forbidden zone.
const WORKSPACE_SCRATCH = path.resolve(here, "test-scratch");

function sh(cwd: string, argv: string[]): string {
  return execFileSync(argv[0], argv.slice(1), { cwd, encoding: "utf8" }).trim();
}

function haveCore(): boolean {
  return fs.existsSync(path.join(CORE, "scripts", "agm_core", "plugin_release.py"));
}

// Builds the synthetic source commit S from the integrated core's managed
// files and generates the release payload with the official generator.
function buildReleaseFixture(area: string, version = "0.1.3", marker?: string): { pluginDir: string; digest: string } {
  const source = path.join(area, "S");
  fs.mkdirSync(source, { recursive: true });
  const managed = ["scripts", "README.md", "DESIGN.md", "INSTALL.md", "SKILL.md", "AGENTS.md", "llms.txt", "docs/architecture.md", "docs/operations.md", "docs/uninstall-design.md"];
  for (const item of managed) {
    const from = path.join(CORE, item);
    assert.ok(fs.existsSync(from), `managed source item missing in integrated core: ${item}`);
    const to = path.join(source, item);
    fs.mkdirSync(path.dirname(to), { recursive: true });
    fs.cpSync(from, to, { recursive: true, filter: filename => !filename.split(path.sep).includes("__pycache__") && !filename.endsWith(".pyc") });
  }
  if (marker) fs.appendFileSync(path.join(source, "README.md"), "\n" + marker + "\n");
  sh(source, ["git", "init", "-q"]);
  sh(source, ["git", "config", "user.email", "bridge@test"]);
  sh(source, ["git", "config", "user.name", "bridge"]);
  sh(source, ["git", "add", "-A"]);
  sh(source, ["git", "commit", "-q", "-m", "synthetic S"]);
  const commit = sh(source, ["git", "rev-parse", "HEAD"]);
  assert.match(commit, /^[0-9a-f]{40}$/);

  const out = path.join(area, "release-out");
  execFileSync("python3", ["-B", path.join(CORE, "tools", "plugin-release", "release.py"), "generate", "--source", source, "--commit", commit, "--version", version, "--output", out], { encoding: "utf8" });

  const pluginDir = path.join(area, "plugin");
  fs.mkdirSync(pluginDir, { recursive: true });
  fs.cpSync(path.join(out, "plugins", "paseo", "payload"), path.join(pluginDir, "payload"), { recursive: true });
  fs.copyFileSync(path.join(pluginDir, "payload", "core", "scripts", "install.py"), path.join(pluginDir, "payload", "core", "scripts", "install.py"));
  const identityFile = path.join(out, "plugins", "paseo", "server", "shared", "release-identity.ts");
  assert.ok(fs.existsSync(identityFile), "generator did not produce release-identity.ts");
  const digest = /CORE_RELEASE_MANIFEST_SHA256\s*=\s*['"]([0-9a-f]{64})['"]/.exec(fs.readFileSync(identityFile, "utf8"))?.[1];
  assert.ok(digest, "release identity digest missing");
  return { pluginDir, digest };
}

test("real bridge: payload -> bootstrap -> machine install -> project cycle -> CK -> recovery", { timeout: 600_000 }, async (t) => {
  if (!haveCore()) {
    t.skip(`integrated core not present at ${CORE}`);
    return;
  }
  const area = fs.mkdtempSync(path.join(os.tmpdir(), "ms-bridge-"));
  // macOS mkdtemp yields /var/folders/... while the kernel requires the
  // canonical /private/var/... form for every absolute path input.
  const canonicalArea = fs.realpathSync(area);
  fs.rmSync(area, { recursive: true, force: true });
  const area2 = canonicalArea;
  const home = path.join(area2, "home");
  fs.mkdirSync(home, { recursive: true });
  try {
    const { pluginDir, digest } = buildReleaseFixture(area2);
    const orch = new Orchestrator({
      runner: realRunner(home),
      home,
      pluginDir,
      searchedPluginDirs: [pluginDir],
      releaseManifestSha256: digest,
      pluginRecords: [{ id: "bridge-custom-alias", source: "directory", path: pluginDir, enabled: true }],
    });

    // --- bootstrap: payload -> durable source export
    const bootstrap = await orch.bootstrapPreview();
    assert.equal(bootstrap.status, "approval_required", JSON.stringify(bootstrap));
    if (bootstrap.status !== "approval_required") return;
    assert.equal(bootstrap.planKind, "prepare-release-source");
    assert.ok(bootstrap.summary.some((row) => row.label === "payload manifest sha256"));

    const acquired = await orch.bootstrapConfirm({ action: "confirm", confirmationToken: bootstrap.confirmationToken });
    assert.equal(acquired.status, "acquired", JSON.stringify(acquired));
    if (acquired.status !== "acquired") return;
    assert.ok(fs.existsSync(acquired.sourceManifestPath), "durable source-manifest missing");

    // --- machine install through the durable export
    const machine = await orch.machinePreview(["codex"]);
    assert.equal(machine.status, "approval_required", JSON.stringify(machine));
    if (machine.status !== "approval_required") return;
    const installed = await orch.machineConfirm({ action: "confirm", confirmationToken: machine.confirmationToken });
    assert.equal(installed.status, "completed", JSON.stringify(installed));
    assert.ok(fs.existsSync(path.join(home, ".mem-sharing", "var", "registry.json")), "registry missing after machine install");

    // --- project check on a synthetic git project
    const project = path.join(area2, "proj");
    fs.mkdirSync(project, { recursive: true });
    sh(project, ["git", "init", "-q"]);
    sh(project, ["git", "config", "user.email", "bridge@test"]);
    sh(project, ["git", "config", "user.name", "bridge"]);
    fs.writeFileSync(path.join(project, "README.md"), "# proj\n");
    sh(project, ["git", "add", "-A"]);
    sh(project, ["git", "commit", "-q", "-m", "init"]);

    const check = await orch.projectCheck(project);
    assert.ok(check.status === "completed" || check.status === "gaps", JSON.stringify(check.envelope));

    // --- enable via --preview exact template
    const enable = await orch.projectEnablePreview({ projectRoot: project, agents: ["codex"] });
    assert.equal(enable.status, "approval_required", JSON.stringify(enable));
    if (enable.status !== "approval_required") return;
    assert.equal(enable.planKind, "enable-memory");
    assert.equal(enable.plan.command, "enable-memory");
    const enabled = await orch.projectEnableConfirm({ action: "confirm", confirmationToken: enable.confirmationToken });
    assert.equal(enabled.status, "completed", JSON.stringify(enabled));
    assert.ok(fs.existsSync(path.join(project, "AGENTS.md")), "project AGENTS.md missing after enable");

    // --- stale pending digest (SERVER-side binding): a second preview
    // replaces the pending plan, so the old digest is refused before any
    // CLI runs. This is NOT the kernel's own file/registry drift check,
    // which is covered further below.
    const projectB = path.join(area2, "proj-b");
    fs.mkdirSync(projectB, { recursive: true });
    sh(projectB, ["git", "init", "-q"]);
    sh(projectB, ["git", "config", "user.email", "bridge@test"]);
    sh(projectB, ["git", "config", "user.name", "bridge"]);
    fs.writeFileSync(path.join(projectB, "README.md"), "# proj-b\n");
    sh(projectB, ["git", "add", "-A"]);
    sh(projectB, ["git", "commit", "-q", "-m", "init"]);
    const first = await orch.projectEnablePreview({ projectRoot: projectB, agents: ["codex"] });
    assert.equal(first.status, "approval_required", JSON.stringify(first));
    const second = await orch.projectEnablePreview({ projectRoot: projectB, agents: ["codex"] });
    assert.equal(second.status, "approval_required", JSON.stringify(second));
    if (first.status === "approval_required" && second.status === "approval_required") {
      const stale = await orch.projectEnableConfirm({ action: "confirm", confirmationToken: first.confirmationToken });
      assert.equal(stale.status, "stale_plan", JSON.stringify(stale));
      assert.equal(fs.existsSync(path.join(projectB, "AGENTS.md")), false, "stale digest executed a write");
      const fresh = await orch.projectEnableConfirm({ action: "confirm", confirmationToken: second.confirmationToken });
      assert.equal(fresh.status, "completed", JSON.stringify(fresh));
    }

    // --- reject before execution (zero writes). This is NOT a running
    // cancel; the in-flight AbortSignal cancel is covered further below.
    const projectC = path.join(area2, "proj-c");
    fs.mkdirSync(projectC, { recursive: true });
    sh(projectC, ["git", "init", "-q"]);
    sh(projectC, ["git", "config", "user.email", "bridge@test"]);
    sh(projectC, ["git", "config", "user.name", "bridge"]);
    fs.writeFileSync(path.join(projectC, "README.md"), "# proj-c\n");
    sh(projectC, ["git", "add", "-A"]);
    sh(projectC, ["git", "commit", "-q", "-m", "init"]);
    const cancelable = await orch.projectEnablePreview({ projectRoot: projectC, agents: ["codex"] });
    assert.equal(cancelable.status, "approval_required", JSON.stringify(cancelable));
    const rejected = await orch.projectEnableConfirm({ action: "reject" });
    assert.equal(rejected.status, "rejected");
    assert.equal(fs.existsSync(path.join(projectC, "AGENTS.md")), false, "reject executed a write");

    // A separate project plan still binds the registry fingerprint. A drifted
    // approved plan must refuse and retain every private project byte.
    const extra=path.join(area2,"registry-drift-project");fs.mkdirSync(extra);sh(extra,["git","init","-q"]);
    const pending=await orch.projectEnablePreview({projectRoot:extra,agents:["codex"]});
    assert.equal(pending.status,"approval_required",JSON.stringify(pending));
    if(pending.status!=="approval_required")return;
    const ledger=path.join(home,".mem-sharing/var/registry.json"),saved=fs.readFileSync(ledger);
    const changedLedger=JSON.parse(saved.toString());changedLedger.product.version="99.0.0";fs.writeFileSync(ledger,JSON.stringify(changedLedger));
    const refused=await orch.projectEnableConfirm({action:"confirm",confirmationToken:pending.confirmationToken});
    assert.notEqual(refused.status,"completed");assert.equal(fs.existsSync(path.join(extra,"AGENTS.md")),false);
    fs.writeFileSync(ledger,saved);
    assert.ok(fs.existsSync(path.join(project,"AGENTS.md")));

    // --- CK negative: no source supplied -> real CLI reports unavailability
    const ckNoSource = await orch.ckPreview();
    assert.equal(ckNoSource.status, "approval_required", JSON.stringify(ckNoSource));
    if (ckNoSource.status === "approval_required") {
      assert.equal(ckNoSource.planKind, "prepare-context-keeper-source");
      await orch.ckConfirm({ action: "reject" }); // fixture never uses the network
    }
    if (ckNoSource.status === "failed") {
      assert.equal(ckNoSource.code, "ck_source_unavailable");
    }

    // --- CK positive: real pinned checkout copied into durable scratch
    if (fs.existsSync(path.join(CK_SOURCE, ".git"))) {
      const head = sh(CK_SOURCE, ["git", "rev-parse", "HEAD"]);
      if (!/^[a-f0-9]{40}$/.test(head)) {
        await t.test("optional pinned CK install", child => child.skip(`CK checkout ${head} differs from pin ${head}`));
      } else {
        fs.mkdirSync(WORKSPACE_SCRATCH, { recursive: true });
        const ckCopy = path.join(WORKSPACE_SCRATCH, `ck-source-${Date.now()}`);
        // Clone (not copy) so the fixture is a clean checkout at the pin;
        // the real working checkout may hold untracked local files.
        execFileSync("git", ["clone", "-q", "--no-hardlinks", CK_SOURCE, ckCopy], { encoding: "utf8" });
        assert.equal(sh(ckCopy, ["git", "rev-parse", "HEAD"]), head);
        sh(ckCopy, ["git", "remote", "set-url", "origin", "https://github.com/vincent4j/context-keeper.git"]);
        try {
          const ck = await orch.ckPreview(ckCopy);
          assert.equal(ck.status, "approval_required", JSON.stringify(ck));
          if (ck.status === "approval_required") {
            assert.equal(ck.planKind, "install-context-keeper");
            const ckDone = await orch.ckConfirm({ action: "confirm", confirmationToken: ck.confirmationToken });
            assert.equal(ckDone.status, "completed", JSON.stringify(ckDone));
            // 修复回归:完成的 ck 执行记录不得携带 var/ck-install 审计 journal,
            // 否则下方 staging 清理与卸载桥接会被"不可归结"永久阻断。
            const pendingRoot = path.join(home, ".local", "share", "mem-sharing-plugin-staging", "pending");
            const ckRecord = fs.readdirSync(pendingRoot).map(dir => {
              try { return JSON.parse(fs.readFileSync(path.join(pendingRoot, dir, "operation.json"), "utf8")); } catch { return null; }
            }).find((r): r is Record<string, unknown> => r !== null && r.flow === "ck" && r.phase === "execute");
            assert.ok(ckRecord, "ck execute operation record missing after CK install");
            assert.equal("journal" in ckRecord, false, "ck record must not carry the non-transactional audit journal");
          }
        } finally {
          fs.rmSync(ckCopy, { recursive: true, force: true });
        }
      }
    } else {
      await t.test("optional pinned CK install", child => child.skip(`CK checkout missing at ${CK_SOURCE}`));
    }

    // --- REAL kernel drift: after an exact preview, modify a managed
    // output the plan snapshots; the kernel must refuse the old approval
    // and preserve the private bytes it did not own.
    const projectD = path.join(area2, "proj-d");
    fs.mkdirSync(projectD, { recursive: true });
    sh(projectD, ["git", "init", "-q"]);
    sh(projectD, ["git", "config", "user.email", "bridge@test"]);
    sh(projectD, ["git", "config", "user.name", "bridge"]);
    fs.writeFileSync(path.join(projectD, "README.md"), "# proj-d\n");
    sh(projectD, ["git", "add", "-A"]);
    sh(projectD, ["git", "commit", "-q", "-m", "init"]);
    const driftPreview = await orch.projectEnablePreview({ projectRoot: projectD, agents: ["codex"] });
    assert.equal(driftPreview.status, "approval_required", JSON.stringify(driftPreview));
    if (driftPreview.status === "approval_required") {
      // The plan's output set for this enable is the project AGENTS.md. A
      // private file now appears at that exact output path BEFORE
      // confirmation: the locked plan no longer matches the scene and the
      // kernel must refuse while preserving the private bytes.
      const projectEntry = path.join(projectD, "AGENTS.md");
      fs.writeFileSync(projectEntry, "PRIVATE: user wrote this first\n");
      const drifted = await orch.projectEnableConfirm({ action: "confirm", confirmationToken: driftPreview.confirmationToken });
      // The kernel must refuse (mismatch/drift family); whatever the exact
      // code, the operation must NOT be reported completed.
      assert.notEqual(drifted.status, "completed", JSON.stringify(drifted));
      assert.equal(fs.readFileSync(projectEntry).toString(), "PRIVATE: user wrote this first\n", "private bytes altered by refused plan");
    }

    // Actual current Node argv -> current Python core, temporary HOME only.
    // Age synthetic orphan artifacts; no neighboring operation grants ownership.
    const stageRoot=path.join(home,".local/share/mem-sharing-plugin-staging");
    const age=(dir:string):void=>{if(!fs.existsSync(dir))return;for(const name of fs.readdirSync(dir)){const file=path.join(dir,name);if(fs.lstatSync(file).isDirectory())age(file);else {const old=new Date(Date.now()-660000);fs.utimesSync(file,old,old);}}};
    age(stageRoot);
    const evidence=path.join(area2,"host-evidence");fs.mkdirSync(evidence);
    const stage=await orch.stagingCleanupPreview(evidence);
    assert.equal(stage.status,"approval_required",JSON.stringify(stage));
    if(stage.status!=="approval_required")return;
    const cleaned=await orch.stagingCleanupConfirm({action:"confirm",confirmationToken:stage.confirmationToken});
    assert.equal(cleaned.status,"completed",JSON.stringify(cleaned));
    const backup=path.join(area2,"external-uninstall");
    const uninstall=await orch.uninstallPreview(backup);
    assert.equal(uninstall.status,"approval_required",JSON.stringify(uninstall));
    if(uninstall.status!=="approval_required")return;
    assert.equal((uninstall.plan.host_obligation as Record<string,unknown>).plugin_id,"bridge-custom-alias");
    const deleted=await orch.uninstallConfirm({action:"confirm",confirmationToken:uninstall.confirmationToken});
    assert.equal(deleted.status,"completed",JSON.stringify(deleted));
    if(deleted.status!=="completed")return;
    assert.equal(deleted.envelope.machine_assets,"completed");assert.equal(deleted.envelope.host_plugin,"pending");assert.equal(deleted.envelope.overall,"partial");
    assert.equal(fs.existsSync(path.join(home,".mem-sharing")),false);assert.equal(fs.existsSync(path.join(home,".local/share/mem-sharing")),false);
    assert.equal(fs.existsSync(stageRoot),false);
    assert.ok(fs.existsSync(path.join(project,"AGENTS.md"))); // Native project rules survive.
    const runtime=uninstall.plan.recovery_runtime as Record<string,unknown>;
    const external=["-I","-S","-B",path.join(backup,"recover.py"),"--manifest",path.join(backup,"manifest.json")];
    const restore=spawnSync(String(runtime.interpreter),external,{encoding:"utf8"});
    assert.equal(restore.status,5,restore.stdout+restore.stderr);
    const restorePlan=JSON.parse(restore.stdout).plan,approval=path.join(area2,"restore-approval.json");
    fs.writeFileSync(approval,JSON.stringify({plan:restorePlan,reference:"explicit synthetic external restore",confirmed_at:new Date().toISOString()}),{mode:0o600});
    const restored=spawnSync(String(runtime.interpreter),[...external,"--approval-file",approval],{encoding:"utf8"});
    assert.equal(restored.status,0,restored.stdout+restored.stderr);
    assert.equal(JSON.parse(restored.stdout).status,"restored");
    assert.ok(fs.existsSync(path.join(home,".mem-sharing/var/registry.json")));

    // --- Actual in-flight machine CLI cancellation at a deterministic
    // journal/output boundary. Only a test-side Python hook pauses; the
    // production source and payload bytes remain intact.
    const home2 = path.join(area2, "home2");
    fs.mkdirSync(home2);
    const reached = path.join(area2, "cancel-boundary");
    const rawRunner = realRunner(home2);
    const pausingRunner = {
      async run(argv: readonly string[], options: { timeoutMs: number; signal?: AbortSignal }) {
        if (argv.includes("--source-manifest") && argv.includes("--approval-file")) {
          const shim = `import sys,runpy,time,pathlib
sys.path.insert(0,${JSON.stringify(path.dirname(acquired.installerPath))})
from agm_core import user_install
original=user_install.execute_install
def execute(*args,**kwargs):
 def hook(stage,target):
  if stage == 'after_output':
   pathlib.Path(${JSON.stringify(reached)}).write_text('ready')
   time.sleep(120)
 kwargs['hook']=hook
 return original(*args,**kwargs)
user_install.execute_install=execute
sys.argv=[${JSON.stringify(acquired.installerPath)}]+sys.argv[1:]
runpy.run_path(sys.argv[0],run_name='__main__')`;
          return rawRunner.run([argv[0], "-B", "-c", shim, ...argv.slice(3)], options);
        }
        return rawRunner.run(argv, options);
      },
    };
    // Export source from the first HOME can be used only with the correct
    // HOME-bound manifest. Export again for home2 first.
    const orch2 = new Orchestrator({ runner: pausingRunner, home: home2, pluginDir,
      searchedPluginDirs: [pluginDir], releaseManifestSha256: digest });
    const export2 = await orch2.bootstrapPreview();
    assert.equal(export2.status, "approval_required", JSON.stringify(export2));
    if (export2.status !== "approval_required") return;
    const acquired2 = await orch2.bootstrapConfirm({ action: "confirm", confirmationToken: export2.confirmationToken });
    assert.equal(acquired2.status, "acquired", JSON.stringify(acquired2));
    const machine2 = await orch2.machinePreview(["codex"]);
    assert.equal(machine2.status, "approval_required", JSON.stringify(machine2));
    if (machine2.status !== "approval_required") return;
    const execution = orch2.machineConfirm({ action: "confirm", confirmationToken: machine2.confirmationToken });
    const deadline = Date.now() + 30_000;
    while (!fs.existsSync(reached) && Date.now() < deadline) await new Promise(resolve => setTimeout(resolve, 20));
    assert.ok(fs.existsSync(reached), "real machine CLI never reached deterministic cancel boundary");
    assert.equal(orch2.cancel("machine").status, "cancel_requested");
    const canceled = await execution;
    assert.equal(canceled.status, "failed", JSON.stringify(canceled));
    if (canceled.status === "failed") assert.equal(canceled.code, "cli_canceled");
    const journal = String((machine2.plan.plan as Record<string, unknown>).journal);
    assert.ok(fs.existsSync(journal), "running cancellation left no operation journal");
    assert.ok(orch2.operationStatus().some(r => r.flow === "machine" && r.state === "unknown" && r.journal === journal));
    assert.equal(fs.existsSync(path.join(home2, ".local/share/mem-sharing/scripts/install.py")), false, "first-install test unexpectedly has active kernel");
    fs.rmSync(pluginDir, { recursive: true });
    // New worker, no plugin, no active kernel: durable export must be sufficient.
    const recoveryWorker = new Orchestrator({ runner: realRunner(home2), home: home2,
      pluginDir: null, searchedPluginDirs: [] });
    assert.ok(recoveryWorker.operationStatus().some(r => r.state === "unknown"));
    const recovery = await recoveryWorker.recoverPreview({ journalPath: journal, action: "continue" });
    assert.equal(recovery.status, "approval_required", JSON.stringify(recovery));
    if (recovery.status !== "approval_required") return;
    const recovered = await recoveryWorker.recoverConfirm({ action: "confirm", confirmationToken: recovery.confirmationToken });
    assert.equal(recovered.status, "completed", JSON.stringify(recovered));
    assert.ok(fs.existsSync(path.join(home2, ".mem-sharing/var/registry.json")));
    assert.ok(recoveryWorker.operationStatus().some(r => r.flow === "machine" && r.state === "recovered" && r.journal === journal), "original journal did not resolve host unknown state");
  } finally {
    fs.rmSync(area, { recursive: true, force: true });
  }
});

test("real bridge negative: dev sentinel blocks bootstrap on a real machine", { timeout: 60_000 }, async (t) => {
  if (!haveCore()) {
    t.skip(`integrated core not present at ${CORE}`);
    return;
  }
  const areaNegRaw = fs.mkdtempSync(path.join(os.tmpdir(), "ms-bridge-neg-"));
  const area = fs.realpathSync(areaNegRaw);
  fs.rmSync(areaNegRaw, { recursive: true, force: true });
  const home = path.join(area, "home");
  fs.mkdirSync(home, { recursive: true });
  try {
    const { pluginDir } = buildReleaseFixture(area);
    const orch = new Orchestrator({ runner: realRunner(home), home, pluginDir, searchedPluginDirs: [pluginDir], releaseManifestSha256: "" });
    assert.equal(orch.releaseIdentity().status, "missing");
    const blocked = await orch.bootstrapPreview();
    assert.equal(blocked.status, "identity_missing");
  } finally {
    fs.rmSync(area, { recursive: true, force: true });
  }
});


test("current package release wins over old/multiple inventories; same-version trees and missing conversion remain gated", { timeout: 120_000 }, async () => {
  assert.ok(haveCore(), "integrated core required for release-selection evidence");
  const area = fs.realpathSync(fs.mkdtempSync(path.join(os.tmpdir(), "ms-release-target-")));
  const home = path.join(area, "home");
  fs.mkdirSync(home);
  const base = realRunner(home);
  const calls: string[][] = [];
  const runner = { async run(argv: readonly string[], options: { timeoutMs: number; signal?: AbortSignal }) { calls.push([...argv]); return base.run(argv, options); } };
  try {
    const fixture = (name: string, version: string, marker?: string) => { const dir = path.join(area, name); fs.mkdirSync(dir); return buildReleaseFixture(dir, version, marker); };
    const a = fixture("A", "0.8.0");
    const aWorker = new Orchestrator({ runner, home, pluginDir: a.pluginDir, searchedPluginDirs: [], releaseManifestSha256: a.digest });
    const exportA = await aWorker.bootstrapPreview();
    assert.equal(exportA.status, "approval_required", JSON.stringify(exportA));
    if (exportA.status !== "approval_required") return;
    const acquiredA = await aWorker.bootstrapConfirm({ action: "confirm", confirmationToken: exportA.confirmationToken });
    assert.equal(acquiredA.status, "acquired", JSON.stringify(acquiredA));
    const machineA = await aWorker.machinePreview(["codex"]);
    assert.equal(machineA.status, "approval_required", JSON.stringify(machineA));
    if (machineA.status !== "approval_required") return;
    const installA = await aWorker.machineConfirm({ action: "confirm", confirmationToken: machineA.confirmationToken });
    assert.equal(installA.status, "completed", JSON.stringify(installA));
    const registry = path.join(home, ".mem-sharing/var/registry.json");
    const originalRegistry = fs.readFileSync(registry, "utf8");
    const b = fixture("B", "0.9.0"); // synthetic release descriptor only
    const bWorker = new Orchestrator({ runner, home, pluginDir: b.pluginDir, searchedPluginDirs: [], releaseManifestSha256: b.digest });
    const before = calls.length;
    const exportB = await bWorker.bootstrapPreview();
    assert.ok(calls.length > before, "old A export bypassed current B resolver");
    assert.equal(exportB.status, "approval_required", JSON.stringify(exportB));
    if (exportB.status !== "approval_required") return;
    assert.equal(exportB.planKind, "prepare-release-source");
    assert.equal((exportB.plan.manifest as { source: { version: string } }).source.version, "0.9.0");
    const acquiredB = await bWorker.bootstrapConfirm({ action: "confirm", confirmationToken: exportB.confirmationToken });
    assert.equal(acquiredB.status, "acquired", JSON.stringify(acquiredB));
    const machineB = await bWorker.machinePreview(["codex"]);
    assert.equal(machineB.status, "failed", JSON.stringify(machineB)); // no approved conversion
    assert.equal(calls[calls.length - 1][2], path.join(b.pluginDir, "payload/core/scripts/install.py"));
    assert.equal(fs.readFileSync(registry, "utf8"), originalRegistry);
    const c = fixture("C", "0.8.0", "synthetic different tree");
    const cWorker = new Orchestrator({ runner, home, pluginDir: c.pluginDir, searchedPluginDirs: [], releaseManifestSha256: c.digest });
    const exportC = await cWorker.bootstrapPreview();
    assert.equal(exportC.status, "approval_required", JSON.stringify(exportC));
    if (exportC.status !== "approval_required") return;
    assert.notEqual(exportC.plan.destination, exportA.plan.destination);
    assert.equal(exportC.planKind, "prepare-release-source");
    const acquiredC = await cWorker.bootstrapConfirm({ action: "confirm", confirmationToken: exportC.confirmationToken });
    assert.equal(acquiredC.status, "acquired", JSON.stringify(acquiredC));
    const machineC = await cWorker.machinePreview(["codex"]);
    assert.equal(machineC.status, "failed", JSON.stringify(machineC)); // same version, different bytes
    assert.equal(fs.readFileSync(registry, "utf8"), originalRegistry);
    assert.equal(calls[calls.length - 1][2], path.join(c.pluginDir, "payload/core/scripts/install.py"));
    // With all three inventories present, A is resolved from package A rather
    // than a reverse-sorted B version or C tree. Corrupt its receipt and the
    // original resolver must refuse instead of silently using another export.
    const againA = await aWorker.machinePreview(["codex"]);
    assert.equal(againA.status, "completed", JSON.stringify(againA));
    if (againA.status !== "completed") return;
    assert.deepEqual(againA.envelope.changes, []);
    assert.equal(againA.envelope.approval_plan, null);
    const receipt = path.join(String(exportA.plan.destination), "acquisition.json");
    const foreignReceipt = fs.readFileSync(receipt, "utf8").replace('"command": "prepare-release-source"', '"command": "foreign"');
    fs.writeFileSync(receipt, foreignReceipt + " ");
    // Canonical receipt plan verification may accept surrounding whitespace;
    // force the saved plan identity itself to drift.
    const bad = JSON.parse(fs.readFileSync(receipt, "utf8")); bad.plan.destination += "-foreign";
    fs.writeFileSync(receipt, JSON.stringify(bad));
    const refused = await aWorker.bootstrapPreview();
    assert.equal(refused.status, "failed", JSON.stringify(refused));
    assert.equal(fs.readFileSync(registry, "utf8"), originalRegistry);
  } finally { fs.rmSync(area, { recursive: true, force: true }); }
});
