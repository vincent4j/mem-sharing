"""M2-04 contract tests; every mutable path and provider lives in TemporaryDirectory."""
import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "unit"))
from runtime_fixture import seed_runtime, installed_registry, seed_project_executors
from agm_core import enable, paths, registry
from agm_core.registry import serialize_registry
from agm_core.entries import sha256


class EnableFixture(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.area = Path(self.temp.name).resolve()
        self.root = self.area / "project with spaces"
        self.root.mkdir()
        subprocess.run(["git", "init", "-q", str(self.root)], check=True)
        self.install = self.area / "agm/scripts"
        self.install.mkdir(parents=True)
        self.home = self.area / "home"
        self.home.mkdir()
        self.runtime = seed_runtime(self.home)
        self.install = self.runtime.var
        self.source = self.area / "keeper"
        (self.source / "scripts").mkdir(parents=True)
        subprocess.run(["git", "init", "-q", str(self.source)], check=True)
        (self.source / "SKILL.md").write_text("name: context-keeper\n")
        (self.source / "scripts/install.py").write_text("raise AssertionError('project must not invoke CK')\n")
        (self.source / "scripts/context_keeper_probe.py").write_text("raise AssertionError('project must not invoke CK')\n")
        self.config = paths.select_platform(paths.load_agents_table(), "darwin")
        self.calls = []
        self.request = {"project": str(self.root), "agents": ["codex", "claude", "workbuddy"],
                        "approval": None, "interactive": False,
                        "home": str(self.home), "platform_config": self.config,
                        "runtime_layout": self.runtime, "runner": self.runner}

        self.request.update(seed_project_executors(self.home))

    def runner(self, argv, **kwargs):
        self.calls.append(argv)
        raise AssertionError("Project rules must never invoke CK")

    def preview(self, memory=None, source=False, store=None):
        # 2026-11-01 经历开关退役:memory 参数仅为旧调用点签名兼容,忽略取值,
        # 不再进入 request(显式 memory_choice 由 retired_option 测试另行拒绝)。
        self.request.pop("memory_choice", None)
        self.request["approval"] = None
        if source and "workbuddy" in self.request["agents"]:
            (self.root/".workbuddy/memory").mkdir(parents=True,exist_ok=True)
        result = enable.run(self.request)
        self.assertEqual(result["status"],"approval_required",result)
        plan=json.loads(result["next_action"])
        plan.update(confirmed_at="2026-10-30T00:00:00Z",reference="exact fixture confirmation")
        return plan

    def apply(self, memory=None, source=False):
        self.request["approval"]=self.preview(memory,source)
        result=enable.run(self.request)
        self.assertEqual(result["status"],"completed",result)
        return result

    def apply_tombstone(self):
        """历史 disabled 项目:现场按历史 --no-memory 后的状态保留。"""
        data=self.load();p=data["projects"][str(self.root)]
        p["memory_policy"]="disabled"
        allowed=paths.allowed_user_paths(self.config,None,home=str(self.home))
        self.runtime.registry.write_bytes(serialize_registry(data,allowed_user_paths=allowed))

    def load(self):
        return registry.load_registry(self.runtime.registry,allowed_user_paths=paths.allowed_user_paths(self.config,None,home=str(self.home)))


class EnableTests(EnableFixture):
    def test_preview_is_zero_write(self):
        plan=self.preview(None)
        self.assertEqual(plan['memory_policy'],'follow_ck')
        self.assertFalse((self.root/'AGENTS.md').exists())
        self.assertFalse(self.runtime.lock.exists())
        self.assertFalse(self.runtime.backups.exists())
        self.assertEqual(self.calls,[])

    def test_schema3_has_only_policy_and_rule_objects(self):
        self.apply(None)
        data=self.load();p=data['projects'][str(self.root)];a=p['checkouts'][str(self.root)]
        self.assertEqual(data['schema_version'],3)
        self.assertEqual(set(p),{'main_checkout','memory_policy','checkouts'})
        self.assertEqual(set(a),{'git_common_dir','agents','objects','shared_object_ids','runtime_acceptance'})
        self.assertFalse((self.root/'docs/context-keeper').exists())
        self.assertEqual(self.calls,[])

    def test_missing_ck_never_blocks_rules(self):
        import shutil
        shutil.rmtree(self.source)
        self.apply(None)
        self.assertIn(b'@AGENTS.md',(self.root/'CLAUDE.md').read_bytes())

    def test_tombstone_data_retained_on_default_skip(self):
        # 历史停用登记(disabled)默认跳过:经历库与 Skill 链接保全,零写入。
        store=self.root/'docs/context-keeper';store.mkdir(parents=True);(store/'memory-keeper.md').write_bytes(b'private')
        link=self.root/'.agents/skills/context-keeper';link.parent.mkdir(parents=True);link.symlink_to(self.source)
        (self.root/'AGENTS.md').write_bytes(b'user rules\r\n'+enable._block(enable.DENIED_MARKER,enable.DENIED_TEXT))
        self.apply(None)
        self.apply_tombstone()
        self.request.update(approval=None)
        result=enable.run(self.request)
        self.assertEqual(result['status'],'gaps',result)
        self.assertEqual(self.load()['projects'][str(self.root)]['memory_policy'],'disabled')
        self.assertEqual((store/'memory-keeper.md').read_bytes(),b'private')
        self.assertTrue(link.is_symlink())
        body=(self.root/'AGENTS.md').read_bytes()
        self.assertIn(enable.DENIED_TEXT.encode(),body)  # 现场原样,不新增不撤销
        self.assertIn('历史停用登记',result['next_action'])

    def test_retired_memory_choice_is_rejected_not_treated_as_request(self):
        # 退役开关显式传值=旧合同残留,零写拒绝;不得当作默认请求继续。
        before={str(p):p.read_bytes() for p in self.area.rglob('*') if p.is_file()}
        result=enable.run(dict(self.request,memory_choice='follow_ck'))
        self.assertEqual(result['status'],'failed',result)
        self.assertEqual(result['errors'][0]['code'],'retired_option',result)
        self.assertEqual({str(p):p.read_bytes() for p in self.area.rglob('*') if p.is_file()},before)

    def test_short_protocol_only_agents_and_claude_import(self):
        self.apply('follow_ck',True)
        raw=(self.root/'AGENTS.md').read_bytes();span=enable.entries.managed_span(raw,**enable.KEEPER_MARKER)
        self.assertEqual(len(raw[span[0]:span[1]].splitlines()),5)
        self.assertEqual((self.root/'CLAUDE.md').read_bytes(),b'@AGENTS.md\n')
        self.assertNotIn(b'context-keeper:start',raw)
        self.assertEqual(self.calls,[])

    def test_claude_existing_raw_bytes_preserved(self):
        raw=b'custom\r\n\xfftail';(self.root/'CLAUDE.md').write_bytes(raw)
        self.apply('follow_ck')
        self.assertEqual((self.root/'CLAUDE.md').read_bytes(),raw+b'\n@AGENTS.md\n')

    def test_idempotent_no_byte_or_mtime_change(self):
        self.apply('follow_ck',True)
        before={p:(p.read_bytes(),p.stat().st_mtime_ns) for p in (self.root/'AGENTS.md',self.root/'CLAUDE.md')}
        old=self.load();self.request['approval']=None
        result=enable.run(self.request);self.assertEqual(result['status'],'completed',result)
        self.assertEqual(result['changes'],[])
        self.assertEqual(self.load(),old)
        self.assertEqual({p:(p.read_bytes(),p.stat().st_mtime_ns) for p in before},before)

    def test_workbuddy_waits_for_native_directory(self):
        self.apply(None)
        self.assertFalse((self.root/'.workbuddy').exists())
        self.assertEqual(self.calls,[])

    def test_workbuddy_top_preserves_native_bytes(self):
        path=self.root/'.workbuddy/memory/MEMORY.md';path.parent.mkdir(parents=True);path.write_bytes(b'native\r\n\xff')
        self.apply('follow_ck')
        self.assertTrue(path.read_bytes().startswith(enable.WORKBUDDY_MARKER['start'].encode()))
        self.assertTrue(path.read_bytes().endswith(b'native\r\n\xff'))

    def test_selected_codex_does_not_prebuild_other_entries(self):
        self.request['agents']=['codex'];self.apply(None)
        self.assertFalse((self.root/'CLAUDE.md').exists());self.assertFalse((self.root/'.workbuddy').exists())

    def test_default_installed_claude_is_not_precreated(self):
        self.request['agents']=None
        plan=self.preview(None)
        self.assertEqual(plan['agents'],['codex','claude','workbuddy'])
        self.assertNotIn(str(self.root/'CLAUDE.md'),[c['path'] for c in plan['changes']])
        self.request['approval']=plan
        self.assertEqual(enable.run(self.request)['status'],'completed')
        self.assertFalse((self.root/'CLAUDE.md').exists())
        self.assertFalse((self.root/'.workbuddy').exists())

    def test_default_does_not_patch_existing_claude_body(self):
        path=self.root/'CLAUDE.md';path.write_bytes(b'user rules\xff\r\n')
        before=path.read_bytes(),path.stat().st_mtime_ns
        self.request['agents']=None
        self.apply(None)
        self.assertEqual((path.read_bytes(),path.stat().st_mtime_ns),before)
        self.assertFalse(any(o['kind']=='import' for o in self.load()['projects'][str(self.root)]['checkouts'][str(self.root)]['objects'].values()))

    def test_claude_legacy_conversion_requires_explicit_project_target(self):
        path=self.root/'CLAUDE.md';old=enable._block(enable.LEGACY_KEEPER_MARKER,'old CK rules')
        path.write_bytes(b'user rules\xff\r\n'+old)
        before=path.read_bytes(),path.stat().st_mtime_ns
        self.request['agents']=None
        self.apply(None)
        self.assertEqual((path.read_bytes(),path.stat().st_mtime_ns),before)
        self.request['agents']=['claude']
        plan=self.preview(None)
        self.assertEqual([item['path'] for item in plan['legacy_bridge_transition']],[str(path)])
        self.request['approval']=plan
        self.assertEqual(enable.run(self.request)['status'],'completed')
        self.assertNotIn(old,path.read_bytes())
        self.assertIn(b'@AGENTS.md',path.read_bytes())
        self.assertTrue(path.read_bytes().startswith(b'user rules\xff\r\n'))

    def test_new_agent_requires_exact_approval(self):
        self.request['agents']=['codex'];self.apply(None)
        self.request.update(agents=['codex','claude'],approval=None)
        self.assertEqual(enable.run(self.request)['status'],'approval_required')

    def test_before_fingerprint_changed_invalidates_approval(self):
        plan=self.preview(None);(self.root/'CLAUDE.md').write_bytes(b'external')
        self.request['approval']=plan
        result=enable.run(self.request);self.assertEqual(result['errors'][0]['code'],'approval_mismatch')
        self.assertFalse((self.root/'AGENTS.md').exists())

    def test_approval_binds_identity_policy_agents_and_changes(self):
        plan=self.preview(None)
        for key,value in [('main_checkout',str(self.area)),('git_common_dir',str(self.area)),('memory_policy','disabled'),('agents',['codex']),('changes',[])]:
            with self.subTest(key=key):
                self.request['approval']=dict(plan,**{key:value})
                self.assertEqual(enable.run(self.request)['status'],'approval_required')
        self.assertFalse((self.root/'AGENTS.md').exists())

    def test_created_drift_stops_whole_order(self):
        self.apply('follow_ck',True)
        path=self.root/'AGENTS.md';path.write_bytes(path.read_bytes().replace('职责'.encode(),b'edited'))
        before=self.runtime.registry.read_bytes();self.request['approval']=None
        result=enable.run(self.request)
        self.assertEqual(result['errors'][0]['code'],'drift');self.assertEqual(self.runtime.registry.read_bytes(),before)

    def test_missing_registered_protocol_repairs_exact_unit(self):
        self.apply('follow_ck',True)
        path=self.root/'.workbuddy/memory/MEMORY.md';raw=path.read_bytes();path.unlink()
        self.request['approval']=None
        result=enable.run(self.request);self.assertEqual(result['status'],'completed',result)
        self.assertEqual(path.read_bytes(),raw)

    def test_old_unregistered_bridge_requires_bytes_review(self):
        old=enable._block(enable.LEGACY_KEEPER_MARKER,'legacy CK rules')
        path=self.root/'AGENTS.md';path.write_bytes(b'prefix\xff\r\n'+old+b'\r\nsuffix')
        plan=self.preview(None);transition=plan['legacy_bridge_transition'][0]
        self.assertEqual(bytes.fromhex(transition['before_hex']),old)
        self.assertEqual(transition['ownership'],'reused')
        self.assertIn(old,path.read_bytes())
        self.request['approval']=plan
        self.assertEqual(enable.run(self.request)['status'],'completed')
        self.assertIn(b'prefix\xff\r\n\r\nsuffix',path.read_bytes())
        self.assertNotIn(old,path.read_bytes())

    def test_registered_created_legacy_retired_with_explicit_plan(self):
        self.apply('follow_ck')
        data=self.load();p=data['projects'][str(self.root)];a=p['checkouts'][str(self.root)]
        obj=next(o for o in a['objects'].values() if o['marker']==enable.KEEPER_MARKER)
        old=enable._block(enable.LEGACY_KEEPER_MARKER,'legacy')
        path=self.root/'AGENTS.md';path.write_bytes(path.read_bytes().replace(enable._block(enable.KEEPER_MARKER,enable.EXPERIENCE_TEXT),old))
        obj['marker']=enable.LEGACY_KEEPER_MARKER;obj['fingerprint']['value']=sha256(old)
        obj['lifecycle']['unit_hex']=old.hex()
        self.runtime.registry.write_bytes(registry.serialize_registry(data,allowed_user_paths=paths.allowed_user_paths(self.config,None,home=str(self.home))))
        self.request.update(approval=None)
        result=enable.run(self.request);self.assertEqual(result['status'],'approval_required',result)
        plan=json.loads(result['next_action']);self.assertEqual(plan['legacy_bridge_transition'][0]['ownership'],'created')
        plan.update(confirmed_at='2026-10-30T00:00:00Z',reference='retire old created block')
        self.request['approval']=plan
        self.assertEqual(enable.run(self.request)['status'],'completed')

    def test_old_bridge_stale_approval_and_malformed_markers_zero_write(self):
        path=self.root/'AGENTS.md';old=enable._block(enable.LEGACY_KEEPER_MARKER,'old');path.write_bytes(old)
        plan=self.preview(None);path.write_bytes(old.replace(b'old',b'changed'));self.request['approval']=plan
        self.assertEqual(enable.run(self.request)['status'],'approval_required')
        path.write_bytes(old+old);self.request['approval']=None
        self.assertEqual(enable.run(self.request)['status'],'failed')
        self.assertEqual(path.read_bytes(),old+old)

    def test_retired_product_marker_is_drift(self):
        path=self.root/'AGENTS.md';path.write_bytes(b'<!-- agent-group-memory:rules:start -->')
        self.request['memory_choice']=None
        self.assertEqual(enable.run(self.request)['errors'][0]['code'],'drift')

    def test_source_content_and_store_config_irrelevant(self):
        plan=self.preview(None);(self.source/'SKILL.md').write_text('changed');(self.root/'context-keeper.json').write_text('{invalid')
        self.request['approval']=plan
        self.assertEqual(enable.run(self.request)['status'],'completed')
        self.assertEqual(self.calls,[])

    def test_fault_rolls_back_all_project_writes(self):
        before=self.runtime.registry.read_bytes();plan=self.preview(None);self.request['approval']=plan
        def hook(event,path):
            if event=='before_write' and path==self.runtime.registry: raise OSError('fault')
        self.request['transaction_hook']=hook
        self.assertEqual(enable.run(self.request)['status'],'failed')
        self.assertEqual(self.runtime.registry.read_bytes(),before)
        self.assertFalse((self.root/'AGENTS.md').exists())

    def test_interactive_exact_plan_decline_and_accept(self):
        self.request.update(memory_choice=None,interactive=True,confirm=lambda prompt:False)
        self.assertEqual(enable.run(self.request)['status'],'approval_required')
        self.request['confirm']=lambda prompt:True
        self.assertEqual(enable.run(self.request)['status'],'completed')

    def test_lock_not_stolen(self):
        self.runtime.lock.mkdir();self.request['memory_choice']=None
        self.assertEqual(enable.run(self.request)['errors'][0]['code'],'lock_conflict')
        self.assertTrue(self.runtime.lock.exists())

    def test_worktree_rejected(self):
        subprocess.run(['git','-C',str(self.root),'-c','user.name=Fixture','-c','user.email=f@example.invalid','commit','--allow-empty','-qm','fixture'],check=True)
        tree=self.area/'linked';subprocess.run(['git','-C',str(self.root),'worktree','add','-qb','fixture',str(tree)],check=True,capture_output=True)
        self.request.update(project=str(tree),memory_choice=None)
        self.assertEqual(enable.run(self.request)['errors'][0]['code'],'worktree_unsupported')

    def test_corrupt_registry_never_rebuilt_implicitly(self):
        self.runtime.registry.write_bytes(b'{broken');self.request['memory_choice']=None
        result=enable.run(self.request);self.assertEqual(result['status'],'failed')
        self.assertEqual(self.runtime.registry.read_bytes(),b'{broken')
        self.assertFalse(self.runtime.backups.exists())
