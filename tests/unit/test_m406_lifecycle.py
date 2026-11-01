"""M4 §7/§8 and review R1/R4; all mutations use explicit synthetic HOME."""
import copy
import json
import os
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parent))
from test_m204_enable import EnableFixture
from agm_core import enable, entries, registry, check, user_entries
from agm_core.registry import serialize_registry
from runtime_fixture import seed_project_executors
from agm_core.transaction import read_snapshot

NOW='2026-10-30T00:00:00Z'


class LifecycleTests(EnableFixture):
    def execute_preview(self,result):
        self.assertEqual(result['status'],'approval_required',result)
        approval=json.loads(result['next_action']);approval.update(confirmed_at=NOW,reference='explicit lifecycle test confirmation')
        self.request['approval']=approval
        return enable.run(self.request)

    def tombstone(self):
        """历史 remove/--no-memory 后的登记态:默认流程只跳过、不重建(删除语义归卸载核心)。"""
        data=self.load();data['projects'][str(self.root)]['memory_policy']='disabled'
        from agm_core import paths as _paths
        self.runtime.registry.write_bytes(serialize_registry(data,allowed_user_paths=_paths.allowed_user_paths(self.config,None,home=str(self.home))))

    def report(self):
        return check.run(dict(self.request,approval=None,agents=None,all=False))

    def test_AGENTS_rules_are_free_and_file_survives_tombstone_skip(self):
        self.apply(None,True);path=self.root/'AGENTS.md';raw=path.read_bytes()
        body=raw.replace(b'# '+self.root.name.encode(),b'# User title')+b'\nUser rules\xff\r\n'
        path.write_bytes(body)
        self.request['approval']=None
        result=enable.run(self.request)
        self.assertEqual(result['status'],'completed',result)
        self.assertEqual(path.read_bytes(),body)
        self.assertFalse(any(o['status']=='drifted' and o['path']==str(path) for o in self.report()['projects'][0]['objects']))
        self.tombstone();self.request['approval']=None
        result=enable.run(self.request);self.assertEqual(result['status'],'gaps',result)
        self.assertTrue(path.is_file());self.assertIn(b'User rules\xff\r\n',path.read_bytes())
        self.assertIn(enable.KEEPER_MARKER['start'].encode(),path.read_bytes())  # 跳过=原样保留,不重建不删改

    def test_old_base_marker_is_history_not_a_guard_or_deletion_right(self):
        self.apply('yes',True)
        data=self.load();a=data['projects'][str(self.root)]['checkouts'][str(self.root)]
        path=self.root/'AGENTS.md';old=entries.managed_span(path.read_bytes(),**enable.KEEPER_MARKER)
        # Synthetic old M2 whole-file base, with existing real creation manifest.
        bridge=next(o for o in a['objects'].values() if o['path']==str(path))
        base=dict(bridge,kind='file',marker=None,fingerprint={'algorithm':'sha256','basis':'file_bytes','value':entries.sha256(path.read_bytes())})
        base.pop('lifecycle',None);a['objects'][str(path)+'#old-base']=base
        self.runtime.registry.write_bytes(registry.serialize_registry(data,allowed_user_paths=__import__('agm_core.paths',fromlist=['']).allowed_user_paths(self.config,None,home=str(self.home))))
        path.write_bytes(path.read_bytes()+b'free historical body\n');self.request['approval']=None
        self.assertEqual(enable.run(self.request)['status'],'completed')
        self.tombstone();self.request['approval']=None
        self.assertEqual(enable.run(self.request)['status'],'gaps')
        self.assertTrue(path.exists());self.assertIn(b'free historical body',path.read_bytes())

    def test_managed_bridge_edit_still_stops_enable(self):
        # 受管块漂移阻断 enable(零写);单元删除/漂移拒绝语义由卸载核心套件承载。
        self.apply(None,True);path=self.root/'AGENTS.md'
        path.write_bytes(path.read_bytes().replace(enable.EXPERIENCE_TEXT.encode(),b'foreign bridge'))
        before=self.runtime.registry.read_bytes();self.request['approval']=None
        self.assertEqual(enable.run(self.request)['errors'][0]['code'],'drift')
        self.assertEqual(self.runtime.registry.read_bytes(),before)

    def test_tombstone_skip_keeps_entries_and_native_directory_retained(self):
        # 入口删除语义归卸载核心;本套件守护:历史停用登记跳过=全部入口原样零写。
        self.apply(None,True);self.tombstone();self.request['approval']=None
        result=enable.run(self.request);self.assertEqual(result['status'],'gaps',result)
        self.assertTrue((self.root/'CLAUDE.md').exists())
        self.assertTrue((self.root/'.workbuddy/memory/MEMORY.md').exists())
        self.assertTrue((self.root/'.workbuddy/memory').is_dir())
        self.assertTrue((self.root/'AGENTS.md').is_file())

    def test_CLAUDE_added_user_bytes_preserved_on_tombstone_skip(self):
        self.apply(None,True);path=self.root/'CLAUDE.md';user=path.read_bytes()+b'\r\nUser rules\xff\n'
        path.write_bytes(user)
        self.tombstone();self.request['approval']=None
        result=enable.run(self.request);self.assertEqual(result['status'],'gaps',result)
        self.assertEqual(path.read_bytes(),user)

    def test_CLAUDE_existing_body_preserved_on_tombstone_skip(self):
        path=self.root/'CLAUDE.md';original=b'Existing bytes\xff';path.write_bytes(original)
        self.apply(None)
        self.tombstone();self.request['approval']=None
        result=enable.run(self.request);self.assertEqual(result['status'],'gaps',result)
        self.assertTrue(path.read_bytes().startswith(original))  # 原文在前,仅追加引用

    def test_duplicate_or_edited_created_reference_stops_enable(self):
        # 引用漂移阻断 enable(零写);移除路径的漂移拒绝由卸载核心套件承载。
        self.apply(None);path=self.root/'CLAUDE.md';original=path.read_bytes();before=self.runtime.registry.read_bytes()
        for raw in (original+original,b'  @AGENTS.md\n',b'@different.md\n'):
            path.write_bytes(raw);self.request['approval']=None
            self.assertNotEqual(enable.run(self.request)['status'],'completed')
            self.assertEqual(self.runtime.registry.read_bytes(),before)

    def test_legacy_reused_reference_never_promoted_or_deleted(self):
        self.apply();path=self.root/'CLAUDE.md';data=self.load();a=data['projects'][str(self.root)]['checkouts'][str(self.root)]
        obj=next(o for o in a['objects'].values() if o['kind']=='import')
        with self.assertRaises(registry.RegistryError):
            registry.validate_registry_v1({'schema_version':1,'projects':data['projects'],'shared_objects':data['shared_objects']},allowed_user_paths=[])
        obj.pop('lifecycle');obj.update(ownership='reused',original_existed=True,backup_manifest=None,
            fingerprint={'algorithm':'sha256','basis':'file_bytes','value':entries.sha256(path.read_bytes())})
        from agm_core.paths import allowed_user_paths
        self.runtime.registry.write_bytes(registry.serialize_registry(data,allowed_user_paths=allowed_user_paths(self.config,None,home=str(self.home))))
        self.request['approval']=None;self.assertEqual(enable.run(self.request)['status'],'completed')
        self.assertEqual(next(o for o in self.load()['projects'][str(self.root)]['checkouts'][str(self.root)]['objects'].values() if o['kind']=='import')['ownership'],'reused')
        self.tombstone();self.request['approval']=None
        result=enable.run(self.request);self.assertEqual(result['status'],'gaps',result)
        self.assertEqual(path.read_bytes(),b'@AGENTS.md\n')  # 跳过=原样,提升/删除语义归卸载核心

    def test_tombstone_skip_keeps_store_and_source_without_denial(self):
        # 经历开关退役:历史停用登记跳过=经历库/来源保全、零写入、不渲染任何 denied。
        store=self.root/'docs/context-keeper';store.mkdir(parents=True);(store/'memory-keeper.md').write_bytes(b'user store\xff\r\n')
        self.apply(None,True);before={str(p):p.read_bytes() for p in store.rglob('*') if p.is_file()}
        self.calls.clear();self.tombstone();self.request.update(approval=None)
        result=enable.run(self.request)
        self.assertEqual(result['status'],'gaps',result);self.assertIn('历史停用登记',result['next_action'])
        p=self.load()['projects'][str(self.root)];self.assertEqual(p['memory_policy'],'disabled')
        self.assertEqual(self.calls,[])
        self.assertNotIn(enable.DENIED_MARKER['start'].encode(),(self.root/'AGENTS.md').read_bytes())
        self.assertFalse((self.root/'.codex/skills/context-keeper').is_symlink())
        self.assertEqual(before,{str(p):p.read_bytes() for p in store.rglob('*') if p.is_file()})
        self.assertTrue((self.source/'scripts/install.py').exists())

    def test_reused_bridge_preserved_on_tombstone_skip_without_denial(self):
        self.apply(None,True);data=self.load();a=data['projects'][str(self.root)]['checkouts'][str(self.root)]
        obj=next(o for o in a['objects'].values() if o['path']==str(self.root/'AGENTS.md') and o['kind']=='block')
        unit=bytes.fromhex(obj['lifecycle']['unit_hex']);obj.pop('lifecycle');obj.update(ownership='reused',original_existed=True,backup_manifest=None)
        from agm_core.paths import allowed_user_paths
        self.runtime.registry.write_bytes(registry.serialize_registry(data,allowed_user_paths=allowed_user_paths(self.config,None,home=str(self.home))))
        self.tombstone();self.request.update(approval=None)
        result=enable.run(self.request);self.assertEqual(result['status'],'gaps',result)
        path=self.root/'AGENTS.md';self.assertIn(unit,path.read_bytes())
        self.assertNotIn(enable.DENIED_MARKER['start'].encode(),path.read_bytes())  # 不新增 denied
        self.assertEqual(self.load()['projects'][str(self.root)]['memory_policy'],'disabled')

    def test_retired_switch_rejected_and_no_denial_to_remove(self):
        # 退役开关无「解除」路径:显式传值拒绝;历史 denied 的清理归 migrate-policy。
        self.apply(None,True);self.request.update(approval=None)
        for choice in ('disabled','follow_ck'):
            result=enable.run(dict(self.request,memory_choice=choice))
            self.assertEqual(result['errors'][0]['code'],'retired_option',result)
        self.assertNotIn(enable.DENIED_MARKER['start'].encode(),(self.root/'AGENTS.md').read_bytes())
        self.assertIn(enable.KEEPER_MARKER['start'].encode(),(self.root/'AGENTS.md').read_bytes())

    def test_installed_filter_and_explicit_unknown_stop_without_foreign_entries(self):
        self.request.update(agents=None,search_paths=self.request['search_paths'],app_directories=[str(self.area/'no-apps')])
        # Remove synthetic non-Codex installations, leaving one valid source.
        (self.home/'fixture-executors/bin/claude').unlink()
        import shutil
        shutil.rmtree(self.home/'Applications/WorkBuddy.app')
        result=self.execute_preview(enable.run(self.request));self.assertEqual(result['status'],'completed',result)
        self.assertEqual(self.load()['projects'][str(self.root)]['checkouts'][str(self.root)]['agents'],['codex'])
        self.assertFalse((self.root/'CLAUDE.md').exists());self.assertFalse((self.home/'.workbuddy').exists())
        before=self.runtime.registry.read_bytes();self.request.update(agents=['claude'],approval=None)
        result=enable.run(self.request);self.assertEqual(result['errors'][0]['code'],'agent_not_installed',result)
        self.assertFalse(result['installation']['effective']);self.assertEqual(self.runtime.registry.read_bytes(),before)

    def test_no_installed_executor_does_not_create_project_entries(self):
        self.request.update(agents=None,search_paths=[],app_directories=[])
        import shutil
        shutil.rmtree(self.home/'Applications/WorkBuddy.app')
        before=self.runtime.registry.read_bytes();result=enable.run(self.request)
        self.assertEqual(result['status'],'gaps',result);self.assertFalse((self.root/'AGENTS.md').exists())
        self.assertEqual(self.runtime.registry.read_bytes(),before)

    def test_WorkBuddy_pointer_waits_for_native_directory_without_mkdir(self):
        self.request.update(agents=['workbuddy'])
        preview=enable.run(self.request)
        self.assertEqual(json.loads(preview['next_action'])['native_pending'],['workbuddy'])
        self.assertFalse((self.root/'.workbuddy/memory').exists())
        result=self.execute_preview(preview);self.assertEqual(result['status'],'completed',result)
        self.assertTrue(any('pointer waits for actual use' in w for w in result['warnings']))
        self.assertFalse((self.root/'.workbuddy/memory').exists());self.assertEqual(self.calls,[])
        a=self.load()['projects'][str(self.root)]['checkouts'][str(self.root)]
        self.assertNotIn('states',a)
        self.assertFalse(any(Path(o['path']).name=='MEMORY.md' for o in a['objects'].values()))

    def test_project_remove_retains_machine_installation_and_user_objects(self):
        self.runtime.code.mkdir(parents=True);(self.runtime.code/'SKILL.md').write_text('# installed product\n')
        request={k:self.request[k] for k in ('home','platform_config','search_paths','app_directories','detect_runner')}
        request['agents']=None
        preview=user_entries.run_user_entries(request);approval=json.loads(preview['next_action']);approval.update(confirmed_at=NOW,reference='machine entry confirmation')
        result=user_entries.run_user_entries(dict(request,approval=approval));self.assertEqual(result['status'],'completed',result)
        machine=copy.deepcopy(self.load()['machine']);code=(self.runtime.code/'SKILL.md').read_bytes()
        self.apply(None,True)
        self.tombstone();self.request.update(approval=None)
        result=enable.run(self.request);self.assertEqual(result['status'],'gaps',result)
        self.assertEqual(self.load()['machine'],machine);self.assertEqual((self.runtime.code/'SKILL.md').read_bytes(),code)
        self.assertTrue((self.home/'.codex/AGENTS.md').is_file())
        self.assertTrue(all(obj['consumers']==[] for obj in self.load()['machine']['objects'].values()))

    def test_missing_ck_scripts_has_no_health_gap_and_is_readonly(self):
        self.apply('yes',True);(self.source/'scripts/install.py').unlink();(self.source/'scripts/context_keeper_probe.py').unlink()
        before={str(p):(p.read_bytes(),p.stat().st_mtime_ns) for p in self.area.rglob('*') if p.is_file() and not p.is_symlink()}
        result=self.report()
        report=result['projects'][0];self.assertEqual(report['gaps'],[])
        self.assertTrue(set(report['states']).isdisjoint({'source_available','skill_installed','bridge_assembled','store_authorized_ready'}))
        self.assertEqual(before,{str(p):(p.read_bytes(),p.stat().st_mtime_ns) for p in self.area.rglob('*') if p.is_file() and not p.is_symlink()})

    def test_external_ck_source_changes_do_not_change_project_health(self):
        self.apply('yes',True);path=self.source/'scripts/install.py';original=path.read_bytes()
        path.write_bytes(original+b'\n# changed')
        report=self.report()['projects'][0];self.assertEqual(report['gaps'],[])
        path.unlink();path.symlink_to(self.source/'scripts/context_keeper_probe.py')
        report=self.report()['projects'][0];self.assertEqual(report['gaps'],[])


    def test_old_base_block_can_be_removed_as_free_rules(self):
        self.apply('yes',True)
        data=self.load();a=data['projects'][str(self.root)]['checkouts'][str(self.root)]
        path=self.root/'AGENTS.md'
        bridge=next(o for o in a['objects'].values() if o['path']==str(path))
        unit=enable._block(enable.BASE_MARKER,'old freely editable base')
        base=dict(bridge,marker=enable.BASE_MARKER,
            fingerprint={'algorithm':'sha256','basis':'block_bytes','value':entries.sha256(unit)})
        base.pop('lifecycle',None);a['objects'][str(path)+'#base']=base
        from agm_core.paths import allowed_user_paths
        self.runtime.registry.write_bytes(registry.serialize_registry(data,allowed_user_paths=allowed_user_paths(self.config,None,home=str(self.home))))
        # The old base is absent now, while the real Keeper bridge is intact.
        self.request['approval']=None
        self.assertEqual(enable.run(self.request)['status'],'completed')
        self.assertFalse(any(o['status']=='drifted' for o in self.report()['projects'][0]['objects']))
        self.tombstone();self.request['approval']=None
        self.assertEqual(enable.run(self.request)['status'],'gaps')
        self.assertTrue(path.exists())

    def test_absent_executors_and_tombstone_do_not_rebuild_or_add_denial(self):
        self.apply(None,True)
        self.request.update(search_paths=[],app_directories=[],user_candidates={},agents=None,approval=None)
        (self.home/'Applications/WorkBuddy.app').rename(self.area/'retired-WorkBuddy.app')
        self.tombstone()
        result=enable.run(self.request)
        self.assertEqual(result['status'],'gaps',result)
        self.assertEqual(self.load()['projects'][str(self.root)]['memory_policy'],'disabled')
        self.assertIn(enable.KEEPER_MARKER['start'].encode(),(self.root/'AGENTS.md').read_bytes())
        self.assertNotIn(enable.DENIED_MARKER['start'].encode(),(self.root/'AGENTS.md').read_bytes())

    def test_pure_reference_only_file_deleted_and_corrupt_lifecycle_rejected(self):
        self.apply()
        data=self.load();a=data['projects'][str(self.root)]['checkouts'][str(self.root)]
        obj=next(o for o in a['objects'].values() if o['kind']=='import')
        from agm_core.paths import allowed_user_paths
        for mutation in ({'unit_hex':'zz'}, {'version':2}, {'file_created':'true'}, {'container_units':[]}):
            bad=copy.deepcopy(data);ref=next(o for o in bad['projects'][str(self.root)]['checkouts'][str(self.root)]['objects'].values() if o['kind']=='import')
            ref['lifecycle'].update(mutation)
            with self.subTest(mutation=mutation),self.assertRaises(registry.RegistryError):
                registry.validate_registry(bad,allowed_user_paths=allowed_user_paths(self.config,None,home=str(self.home)))
        self.tombstone();self.request['approval']=None
        result=enable.run(self.request);self.assertEqual(result['status'],'gaps',result)
        self.assertTrue((self.root/'CLAUDE.md').exists())  # 纯引用文件删除语义归卸载核心
