import assert from "node:assert/strict";
import { test } from "node:test";
import { uninstallResult, externalSteps, publicPlan } from "../client/uninstall-result";

test("machine completion never turns host pending/disabled into overall success", () => {
  for (const host_plugin of ["pending", "disabled"]) {
    const shown = uninstallResult({ scope:"machine_and_paseo",machine_assets:"completed",host_plugin,overall:"partial" });
    assert.equal(shown.ok,false);assert.ok(shown.rows.some(r=>r.label==="host_plugin"&&r.value===host_plugin));
  }
  assert.equal(uninstallResult({scope:"standalone_declared",overall:"completed",host_plugin:"not_applicable"}).ok,true);
});
test("persistent external steps bind before remove, never reuse target on check, default retain", () => {
  const commands=externalSteps({manifest:"/backup with space/manifest.json"},{recovery_runtime:{interpreter:"/outside/python"},host_obligation:{plugin_id:"actual-alias"}});
  assert.ok(commands.indexOf("--bind-host-plugin")<commands.indexOf("plugin remove"));
  assert.ok(commands.includes("plugin remove 'actual-alias'"));
  assert.ok(commands.includes("--check-host-plugin\n"));
  assert.ok(commands.includes("--ck-choice retain"));assert.ok(commands.includes("--ck-approval-file"));
  assert.ok(commands.includes("-I -S -B '/backup with space/recover.py'"));
  assert.ok(commands.includes("--host-binding-approval-file"));
});
test("plan display excludes private byte snapshots recursively", () => {
  assert.deepEqual(publicPlan({changes:[{before_hex:"secret",path:"/entry",lifecycle:{unit_hex:"private",version:1}}]}),{changes:[{path:"/entry",lifecycle:{version:1}}]});
});
