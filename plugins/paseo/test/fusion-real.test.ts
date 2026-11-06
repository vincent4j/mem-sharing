// Production orchestrator -> real Python CLI; synthetic HOME only, no App.
import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { test } from "node:test";
import { Orchestrator, realRunner } from "../server/orchestrator";
const core = process.env.MEMSHARING_TEST_FUSION_CORE ?? path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../../..");
test("real CLI fusion: preview/view/decline/drift/selection executes exact scene", { timeout: 90_000 }, async t => {
  if (!fs.existsSync(path.join(core, "tests/unit/test_memory_fusion.py"))) { t.skip("current fusion core unavailable; set MEMSHARING_TEST_FUSION_CORE"); return; }
  const setup = `
import sys,json
sys.path[:0]=[sys.argv[1]+'/scripts',sys.argv[1]+'/tests/unit']
from test_m405_user_entries import UserEntryFixture
f=UserEntryFixture();f.setUp();f.seed_codex_package()
r=f.execute(agents=['codex']);assert r['status']=='completed',r
f.memory_index.parent.mkdir(parents=True,exist_ok=True);f.memory_index.write_text('# 用户记忆\\n')
p=f.home/'.codex/AGENTS.md';p.write_text(p.read_text()+'\\n# 自定义\\n- 桥接测试完整原文。\\n')
f.temp._finalizer.detach()
print(json.dumps({'area':str(f.area),'home':str(f.home),'bin':str(f.bin_dir)}))
`;
  const f = JSON.parse(execFileSync("python3", ["-B", "-c", setup, core], { encoding: "utf8" }));
  try {
    const base = realRunner(f.home); const calls: string[][] = [];
    const bootstrap = "import runpy,sys;from pathlib import Path;sys.path.insert(0,str(Path(sys.argv[1]).parent));from agm_core import detect;detect.STANDARD_APP_DIRECTORIES=();sys.argv=sys.argv[1:];runpy.run_path(sys.argv[0],run_name='__main__')";
    const orch = new Orchestrator({ home: f.home, pluginDir: null, searchedPluginDirs: [],
      runner: { run(argv, options) { calls.push([...argv]); return base.run([argv[0], "-B", "-c", bootstrap, ...argv.slice(2)], { ...options, env: { ...options.env, PATH: f.bin + ":/usr/bin:/bin:/usr/sbin:/sbin" } }); } },
      pythonProbe: async () => ({ status: "ready", selected: { origin: "system", path: "/usr/bin/python3", status: "ready", probe: { pythonVersion: "3.9.6", executable: "/usr/bin/python3", machine: "arm64", platform: "Darwin", stdlibOk: true } }, candidates: [], evidence: "temporary HOME" }) });
    const initial = await orch.fusionPreview({ scope: "user" }); assert.equal(initial.status, "completed", JSON.stringify(initial)); assert.equal(initial.approval, undefined);
    const plan = initial.envelope.approval_plan as { groups: { number: number; summary: string }[] };
    const num = plan.groups.find(g => g.summary.includes("桥接测试完整原文"))?.number; assert.ok(num);
    const source = path.join(f.home, ".codex/AGENTS.md"); const before = fs.readFileSync(source, "utf8");
    const viewed = await orch.fusionSelect({ scope: "user", contextToken: initial.contextToken, selection: `查看 ${num}` });
    assert.equal(viewed.status, "completed", JSON.stringify(viewed)); assert.equal(viewed.envelope.status, "viewed"); assert.equal(viewed.approval, undefined); assert.equal(fs.readFileSync(source, "utf8"), before);
    const declined = await orch.fusionSelect({ scope: "user", contextToken: initial.contextToken, decline: true });
    assert.equal(declined.envelope.fusion_status, "declined"); assert.equal(fs.readFileSync(source, "utf8"), before);
    const second = await orch.fusionPreview({ scope: "user" });
    fs.appendFileSync(source, "\n- 新增现场。\n");
    const drifted = await orch.fusionSelect({ scope: "user", contextToken: second.contextToken, selection: String(num) });
    assert.equal(drifted.status, "failed", JSON.stringify(drifted)); assert.ok(fs.readFileSync(source, "utf8").includes("桥接测试完整原文"));
    fs.writeFileSync(source, before);
    const third = await orch.fusionPreview({ scope: "user" });
    const done = await orch.fusionSelect({ scope: "user", contextToken: third.contextToken, selection: String(num) });
    assert.equal(done.status, "completed", JSON.stringify(done)); assert.equal(done.envelope.fusion_status, "completed");
    assert.equal((done.envelope.context_keeper as {status: string}).status, "pending_selection");
    assert.ok(!fs.readFileSync(source, "utf8").includes("桥接测试完整原文"));
    assert.ok(fs.readFileSync(path.join(f.home, ".mem-sharing/memories/user-rules.md"), "utf8").includes("- 桥接测试完整原文。"));
    assert.ok(calls.at(-1)?.includes("--selection-plan-file")); assert.ok(calls.at(-1)?.includes("--selection-reference"));
  } finally { fs.rmSync(f.area, { recursive: true, force: true }); }
});

test("real CLI Agent equivalence proposal preserves six-source context and executes one numbered scene", { timeout: 90_000 }, async () => {
  const setup = `
import sys,json
sys.path[:0]=[sys.argv[1]+'/scripts',sys.argv[1]+'/tests/unit']
from test_install_conversation import EquivalenceTests
f=EquivalenceTests();f.setUp();f.f.temp._finalizer.detach()
print(json.dumps({'area':str(f.f.area),'home':str(f.f.home),'declarations':f.declarations,'sources':{a:str(p) for a,p in f.f.native.items()}}))
`;
  const f = JSON.parse(execFileSync("python3", ["-B", "-c", setup, core], { encoding: "utf8" }));
  try {
    const base = realRunner(f.home);
    const bootstrap = "import runpy,sys;from pathlib import Path;sys.path.insert(0,str(Path(sys.argv[1]).parent));from agm_core import detect;original=detect.detect_agents;exec(\"def installed(*a,**kw):\\n kw.update(search_paths=[],app_directories=[]);r=original(*a,**kw)\\n for row in r['agents'].values():row['status']='installed'\\n return r\");detect.detect_agents=installed;sys.argv=sys.argv[1:];runpy.run_path(sys.argv[0],run_name='__main__')";
    const orch = new Orchestrator({ home: f.home, pluginDir: null, searchedPluginDirs: [], runner: { run(argv, options) { return base.run([argv[0], "-B", "-c", bootstrap, ...argv.slice(2)], options); } },
      pythonProbe: async () => ({ status: "ready", selected: { origin: "system", path: "/usr/bin/python3", status: "ready", probe: { pythonVersion: "3.9.6", executable: "/usr/bin/python3", machine: "arm64", platform: "Darwin", stdlibOk: true } }, candidates: [], evidence: "synthetic six installed Agent facts" }) });
    const initial = await orch.fusionPreview({ scope: "user" }); assert.equal(initial.status, "completed", JSON.stringify(initial));
    const before = Object.fromEntries(Object.entries(f.sources as Record<string, string>).map(([a, file]) => [a, fs.readFileSync(file, "utf8")]));
    const proposed = await orch.fusionPropose({ scope: "user", contextToken: initial.contextToken, equivalentSources: f.declarations });
    assert.equal(proposed.status, "completed", JSON.stringify(proposed));
    const plan = proposed.envelope.approval_plan as { default_numbers: number[]; groups: { number: number; sources: unknown[] }[] };
    assert.equal(plan.default_numbers.length, 6);
    for (const group of plan.groups.filter(g => plan.default_numbers.includes(g.number))) assert.equal(group.sources.length, 6);
    for (const [a, file] of Object.entries(f.sources as Record<string, string>)) assert.equal(fs.readFileSync(file, "utf8"), before[a]);
    const done = await orch.fusionSelect({ scope: "user", contextToken: proposed.contextToken, selection: "按默认方案" });
    assert.equal(done.status, "completed", JSON.stringify(done)); assert.equal(done.envelope.fusion_status, "completed");
    const publicText = fs.readFileSync(path.join(f.home, ".mem-sharing/memories/user-rules.md"), "utf8");
    for (let n = 1; n <= 6; n++) assert.equal(publicText.split(`${n}. 完整合成规则${n}。`).length - 1, 1);
    for (const file of Object.values(f.sources as Record<string, string>)) assert.ok(!fs.readFileSync(file, "utf8").includes("完整合成规则"));
  } finally { fs.rmSync(f.area, { recursive: true, force: true }); }
});
