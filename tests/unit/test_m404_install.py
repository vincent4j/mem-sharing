"""Synthetic HOME/source only: first-install routing, v0 bytes and recovery."""
import copy
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'scripts'))
from agm_core import user_install as install, legacy_import as legacy, paths, registry, user_entries
from agm_core.layout import resolve_layout
from agm_core.transaction import read_snapshot


def approved(plan):
    return dict(plan,confirmed_at='2026-10-30T00:00:00Z',reference='explicit isolated user approval')


class InstallFixture(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.area=Path(self.temp.name).resolve();self.home=self.area/'home';self.home.mkdir()
        self.runtime=resolve_layout(self.home);self.source=self.area/'source'
        (self.source/'scripts/agm_core').mkdir(parents=True)
        for rel,raw in {'SKILL.md':b'# agent-group-memory\n','scripts/agm.py':b'print("fixture")\n','scripts/agm_core/__init__.py':b''}.items():
            (self.source/rel).write_bytes(raw)
        self.config=paths.select_platform(paths.load_agents_table(),'darwin')
        self.request={'home':str(self.home),'platform_config':self.config,'agents':None,'search_paths':[],
            'app_directories':[], 'operation_id':'fixture-m404',
            'source':{'root':str(self.source),'url':'fixture://verified','commit':'a'*40,'version':'0.4.0',
            'files':{str(p.relative_to(self.source)):legacy.digest(p.read_bytes()) for p in self.source.rglob('*') if p.is_file()}}}

    def v0(self):
        # §23:v0 内容在历史位置 ~/.agents-group(源,原地不动);R=~/.mem-sharing 是目标。
        for name in ('memories','references','skills','mcp'):(self.runtime.legacy_root/name).mkdir(parents=True)
        (self.runtime.legacy_root/'memories/MEMORY.md').write_bytes(b'\xef\xbb\xbf# Old\r\n[ref](../references/ops.md)\r\n[topic](topic.md)\xff')
        (self.runtime.legacy_root/'memories/topic.md').write_bytes(b'unchanged\r\n\xff')
        (self.runtime.legacy_root/'references/ops.md').write_bytes(b'private original\x00\n')
        (self.runtime.legacy_root/'skills/example.txt').write_bytes(b'skill\r\n')
        (self.runtime.legacy_root/'manage.py').write_bytes(b'old code do not run')
        (self.runtime.legacy_root/'mcp/private').write_bytes(b'untouched')
        return {str(p.relative_to(self.runtime.legacy_root)):p.read_bytes() for p in self.runtime.legacy_root.rglob('*') if p.is_file()}

    def plan(self):return install.plan_install(self.request)
    def execute(self,plan=None,hook=None):
        plan=plan or self.plan()
        return install.execute_install(plan,approved(plan),request=self.request,hook=hook)
    def recover(self,path,action):
        plan=install.plan_recovery(path,action=action)
        return install.recover_install(plan,approved(plan),request=self.request)
    def codex(self):
        package=self.area/'npm';(package/'bin').mkdir(parents=True)
        exe=package/'bin/codex';exe.write_text('#!/bin/sh\n');exe.chmod(0o755)
        (package/'package.json').write_text(json.dumps({'name':'@openai/codex','version':'1.0','bin':{'codex':'bin/codex'}}))
        self.request['search_paths']=[str(package/'bin')]


class InstallTests(InstallFixture):
    def test_empty_classification_and_preview_are_zero_write(self):
        self.assertEqual(install.inspect_machine(self.request)['scene'],'empty')
        plan=self.plan();self.assertEqual(plan['channel'],'fresh')
        self.assertEqual(list(self.home.iterdir()),[])
        with self.assertRaises(ValueError):install.execute_install(plan,{},request=self.request)
        self.assertEqual(list(self.home.iterdir()),[])

    def test_fresh_structure_code_C_and_no_fake_project_consumers(self):
        result=self.execute();self.assertEqual(result['status'],'completed')
        for rel in ('memories/topics','references','backups','var'):
            self.assertTrue((self.runtime.root/rel).is_dir(),rel)
        # v1.11:R 不建 skills/、mcp/。
        for rel in ('skills','mcp'):
            self.assertFalse((self.runtime.root/rel).exists(),rel)
        self.assertEqual((self.runtime.code/'SKILL.md').read_bytes(),(self.source/'SKILL.md').read_bytes())
        data=registry.require_installed(registry.load_registry(self.runtime.registry,allowed_user_paths=[]))
        self.assertEqual(data['projects'],{});self.assertEqual(data['machine'],{'agents':{},'objects':{}})
        before={str(p):p.stat().st_mtime_ns for p in self.home.rglob('*')}
        self.assertEqual(install.inspect_machine(self.request)['scene'],'same')
        self.assertEqual(before,{str(p):p.stat().st_mtime_ns for p in self.home.rglob('*')})
        self.assertFalse((self.runtime.root/'skills/agent-group-memory').exists())
        self.assertFalse((self.home/'.agents/skills').exists())

    def test_only_installed_codex_uses_existing_user_entry_API(self):
        self.codex();plan=self.plan()
        self.assertEqual(plan['effective_agents'],['codex'])
        self.assertIn('verified_product_source',plan['entry_plan'])
        self.execute(plan)
        entry=self.home/'.codex/AGENTS.md'
        self.assertTrue(entry.is_file())
        # v1.11:入口含治理条款与菜单;无 Skill 投影落点。
        body=entry.read_text()
        self.assertIn(user_entries.GOVERNANCE_RULES_TEXT,body)
        self.assertIn('/mem-sharing 菜单',body)
        self.assertFalse((self.home/'.codex/skills').exists())
        self.assertFalse((self.home/'.claude').exists());self.assertFalse((self.home/'.workbuddy').exists())
        data=registry.load_registry(self.runtime.registry,allowed_user_paths=paths.allowed_user_paths(self.config,None,home=str(self.home)))
        self.assertTrue(data['machine']['objects'])
        self.assertTrue(all(o['consumers']==[] for o in data['machine']['objects'].values()))

    def test_v0_exact_snapshot_legacy_package_and_same_op_no_reimport(self):
        old=self.v0();plan=self.plan()
        self.assertEqual(plan['legacy_identity'],'confirmed_v0')
        self.assertEqual(list(self.home.glob('.mem-sharing-install-*')),[])
        bad=approved(plan);bad['legacy_identity']=None
        with self.assertRaises(ValueError):install.execute_install(plan,bad)
        self.execute(plan)
        package=Path(plan['legacy_import']['package']);snapshot=Path(plan['legacy_import']['snapshot'])
        for rel,raw in old.items():
            self.assertEqual((self.runtime.legacy_root/rel).read_bytes(),raw)
            if rel.split('/')[0] in legacy.ROOTS:
                self.assertEqual((package/rel).read_bytes(),raw)
                self.assertEqual((snapshot/rel).read_bytes(),raw)
        # v1.11/§23:v0 源(历史位置)整体原地不动,不进阅读包/快照,只登记排除。
        self.assertEqual((self.runtime.legacy_root/'memories/MEMORY.md').read_bytes(),old['memories/MEMORY.md'])
        self.assertTrue((self.runtime.legacy_root/'skills/example.txt').is_file())
        self.assertFalse((package/'skills').exists());self.assertFalse((snapshot/'skills').exists())
        preserved={e['path'] for e in plan['legacy_import']['excluded'] if e.get('disposition')=='preserved_in_place'}
        self.assertEqual(preserved,{'skills','mcp'})
        self.assertIn(b'legacy-v0-fixture-m404/memories/MEMORY.md',(self.runtime.root/'memories/MEMORY.md').read_bytes())
        manifest=json.loads(Path(plan['legacy_import']['manifest']).read_bytes())
        self.assertEqual(manifest['status'],'committed')
        self.assertEqual(install.inspect_machine(self.request)['scene'],'same')
        with self.assertRaises(ValueError):self.execute(plan)
        self.assertEqual(len(list(self.runtime.backups.glob('v0-*'))),1)

    def test_source_and_destination_drift_stop_before_bootstrap(self):
        self.v0();plan=self.plan()
        (self.runtime.legacy_root/'references/ops.md').write_bytes(b'external')
        with self.assertRaises(ValueError):self.execute(plan)
        self.assertEqual(list(self.home.glob('.mem-sharing-install-*')),[])
        self.assertFalse(self.runtime.code.exists())

    def test_target_conflict_and_code_symlink_parents_are_zero_write(self):
        self.v0();package=self.runtime.root/'memories/legacy-v0-fixture-m404';package.mkdir(parents=True)
        (package/'MEMORY.md').write_bytes(b'conflict')
        with self.assertRaises(ValueError):self.plan()
        self.assertFalse(self.runtime.registry.exists())
        self.assertFalse(self.runtime.code.exists())
        (self.home/'.local').symlink_to(self.area,target_is_directory=True)
        self.assertEqual(install.inspect_machine(self.request)['channel'],'stop')

    def test_all_interruption_stages_continue_or_rollback_with_same_operation(self):
        for event in ('snapshot_complete','after_output','after_entries','before_commit','after_commit'):
            for action in ('continue','rollback'):
                with self.subTest(event=event,action=action):
                    fixture=InstallFixture();fixture.setUp()
                    try:
                        old=fixture.v0();plan=fixture.plan();seen=[]
                        def hook(stage,path):
                            if stage==event and not seen:
                                seen.append(True);raise RuntimeError('injected '+event)
                        with self.assertRaises(RuntimeError):fixture.execute(plan,hook)
                        self.assertEqual(install.inspect_machine(fixture.request)['scene'],'interrupted')
                        result=fixture.recover(plan['journal'],action)
                        self.assertEqual(result['status'],'completed' if action=='continue' else 'rolled_back',result)
                        if action=='continue':
                            self.assertTrue(fixture.runtime.registry.is_file())
                            self.assertEqual(len(list(fixture.runtime.backups.glob('v0-*'))),1)
                        else:
                            self.assertFalse(fixture.runtime.registry.exists())
                            for rel,raw in old.items():self.assertEqual((fixture.runtime.legacy_root/rel).read_bytes(),raw)
                    finally:fixture.doCleanups()

    def test_external_symlink_recorded_not_dereferenced_or_activated(self):
        self.v0();outside=self.area/'outside';outside.write_bytes(b'not copied')
        link=self.runtime.legacy_root/'references/external';link.symlink_to(outside)
        internal=self.runtime.legacy_root/'references/internal';internal.symlink_to('../references/ops.md')
        plan=self.plan()
        preserved={e['path'] for e in plan['legacy_import']['excluded'] if e.get('disposition')=='preserved_in_place'}
        self.assertEqual(preserved,{'skills','mcp'})
        self.assertEqual(len([e for e in plan['legacy_import']['excluded'] if e.get('disposition')=='excluded_link']),1)
        self.execute(plan);package=Path(plan['legacy_import']['package'])
        self.assertTrue(link.is_symlink());self.assertFalse((package/'references/external').exists())
        self.assertEqual(os.readlink(package/'references/internal'),'../references/ops.md')
        self.assertNotIn(b'not copied',Path(plan['legacy_import']['manifest']).read_bytes())
        # v0 skills 原文/链接原地保留,不复制不镜像。
        self.assertTrue((self.runtime.legacy_root/'skills/example.txt').is_file())
        self.assertFalse((package/'skills').exists())

    def test_cyclic_special_collisions_and_new_broken_link_stop_readonly(self):
        self.v0();link=self.runtime.legacy_root/'references/loop';link.symlink_to('loop')
        with self.assertRaises(ValueError):self.plan()
        link.unlink();(self.runtime.legacy_root/'memories/new.md').write_text('[bad](../manage.py)')
        with self.assertRaises(ValueError):self.plan()
        self.assertFalse(self.runtime.registry.exists())

    def test_future_bad_and_interrupted_routes(self):
        self.execute();path=self.runtime.registry;raw=path.read_bytes()
        data=json.loads(raw);data['schema_version']=99;path.write_text(json.dumps(data))
        self.assertEqual(install.inspect_machine(self.request)['scene'],'future')
        path.write_bytes(b'{bad')
        self.assertEqual(install.inspect_machine(self.request)['scene'],'bad_registry')
        path.write_bytes(raw);self.runtime.lock.mkdir()
        self.assertEqual(install.inspect_machine(self.request)['scene'],'interrupted')

    def test_installer_only_preview_extension_binds_source_and_execution_C(self):
        self.codex();fp=self.request['source']['files']['SKILL.md']
        req=install._entry_request(self.request,self.runtime,self.source)
        rejected=user_entries.run_user_entries(req)
        self.assertEqual(rejected['errors'][0]['code'],'installer_context_required')
        with user_entries._installer_source(self.runtime.code,fp,preview=True):
            preview=user_entries.run_user_entries(req)
        self.assertEqual(preview['status'],'approval_required',preview)
        req['approval']=approved({k:v for k,v in json.loads(preview['next_action']).items() if k not in ('confirmed_at','reference')})
        with user_entries._installer_source(self.runtime.code,fp,preview=False):
            missing=user_entries.run_user_entries(req)
        self.assertEqual(missing['errors'][0]['code'],'product_code_missing')
        self.runtime.code.mkdir(parents=True);(self.runtime.code/'SKILL.md').write_text('alien')
        with user_entries._installer_source(self.runtime.code,fp,preview=False):
            mismatch=user_entries.run_user_entries(req)
        self.assertEqual(mismatch['errors'][0]['code'],'product_code_drift')
        self.assertFalse((self.home/'.codex').exists())

    def test_v0_without_old_index_and_existing_empty_directory(self):
        (self.runtime.legacy_root/'references').mkdir(parents=True)
        (self.runtime.legacy_root/'references/only.txt').write_bytes(b'only reference')
        self.assertEqual(self.execute()['status'],'completed')
        self.assertTrue((self.runtime.root/'memories/MEMORY.md').is_file())

    def test_valid_old_M4_requires_explicit_conversion_whitelist_and_never_reinstalls(self):
        self.execute();data=json.loads(self.runtime.registry.read_bytes())
        self.request['source']['version']='0.5.0';self.request['source']['commit']='b'*40
        self.assertEqual(install.inspect_machine(self.request)['scene'],'future')
        self.request['supported_sources']=[{'version':'0.4.0','source':data['product']['source']}]
        self.assertEqual(install.inspect_machine(self.request)['scene'],'valid_old')
        with self.assertRaises(ValueError):self.plan()

    def test_legacy_product_and_v0_content_are_separate_sources(self):
        from test_m403_migrate import MigrationFixture, OLD_COMMIT
        fixture=MigrationFixture();fixture.setUp()
        try:
            root=fixture.runtime.legacy_root
            (root/'memories').mkdir(parents=True);(root/'memories/MEMORY.md').write_bytes(b'v0 old')
            request=dict(self.request,home=str(fixture.home),legacy_registries=[str(fixture.old)],
                         legacy_source_commits={str(fixture.old):OLD_COMMIT})
            before=fixture.old.read_bytes()
            scene=install.inspect_machine(request)
            self.assertEqual(scene['scene'],'valid_old',scene)
            self.assertTrue(scene['content_candidate'])
            with self.assertRaises(ValueError):install.plan_install(request)
            self.assertEqual(fixture.old.read_bytes(),before)
            self.assertEqual((root/'memories/MEMORY.md').read_bytes(),b'v0 old')
        finally:fixture.doCleanups()

    def test_late_source_foreign_entry_and_snapshot_corruption_stop(self):
        for stage in ('source','entry','snapshot'):
            with self.subTest(stage=stage):
                fixture=InstallFixture();fixture.setUp()
                try:
                    fixture.v0();fixture.codex();plan=fixture.plan()
                    def hook(event,path):
                        if event=='before_commit':
                            if stage=='source':(fixture.runtime.legacy_root/'references/ops.md').write_bytes(b'external')
                            if stage=='entry':(fixture.home/'.codex/AGENTS.md').write_bytes(b'external')
                            if stage=='snapshot':
                                p=Path(plan['legacy_import']['snapshot'])/'references/ops.md';p.chmod(0o600);p.write_bytes(b'corrupt')
                    with self.assertRaises(ValueError):fixture.execute(plan,hook)
                    self.assertFalse(fixture.runtime.registry.exists())
                    with self.assertRaises(ValueError):install.plan_recovery(plan['journal'],action='continue')
                finally:fixture.doCleanups()

    def test_partial_destination_foreign_bytes_are_never_overwritten_on_retry(self):
        self.v0();plan=self.plan();seen=[]
        def hook(event,path):
            if event=='after_output' and not seen:
                seen.append(path);raise RuntimeError('stop')
        with self.assertRaises(RuntimeError):self.execute(plan,hook)
        seen[0].write_bytes(b'foreign target')
        with self.assertRaises(ValueError):install.plan_recovery(plan['journal'],action='continue')
        self.assertEqual(seen[0].read_bytes(),b'foreign target')

    def test_rollback_intent_foreign_edits_are_preserved(self):
        for target in ('registry','index'):
            with self.subTest(target=target):
                fixture=InstallFixture();fixture.setUp()
                try:
                    fixture.v0();plan=fixture.plan()
                    def interrupt(stage,path):
                        if stage=='after_commit':raise RuntimeError('stop before footer')
                    with self.assertRaises(RuntimeError):fixture.execute(plan,interrupt)
                    recovery=install.plan_recovery(plan['journal'],action='rollback')
                    path=fixture.runtime.registry if target=='registry' else fixture.runtime.root/'memories/MEMORY.md'
                    def edit(stage,output):
                        if stage=='intent:rollback_'+('registry' if target=='registry' else 'output') and output==path:
                            path.write_bytes(b'external recovery edit')
                    with self.assertRaises(ValueError):
                        install.recover_install(recovery,approved(recovery),request=fixture.request,hook=edit)
                    self.assertEqual(path.read_bytes(),b'external recovery edit')
                finally:fixture.doCleanups()
