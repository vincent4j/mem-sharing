"""M4 §7/§8 and review R1/R4; all mutations use explicit synthetic HOME."""
import copy
import json
import os
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parent))
from test_m204_enable import EnableFixture
from agm_core import enable, entries, registry, remove, check, user_entries
from runtime_fixture import seed_project_executors
from agm_core.transaction import read_snapshot

NOW='2026-10-30T00:00:00Z'


class LifecycleTests(EnableFixture):
    def execute_preview(self,result):
        self.assertEqual(result['status'],'approval_required',result)
        approval=json.loads(result['next_action']);approval.update(confirmed_at=NOW,reference='explicit lifecycle test confirmation')
        self.request['approval']=approval
        return enable.run(self.request)

    def remove_project(self):
        request=dict(self.request,approval=None)
        preview=remove.run(request)
        if preview['status']=='completed':return preview
        self.assertEqual(preview['status'],'approval_required',preview)
        p=self.load()['projects'][str(self.root)];a=p['checkouts'][str(self.root)]
        approval={'command':'remove-memory','main_checkout':str(self.root),'checkout':str(self.root),
            'git_common_dir':a['git_common_dir'],'agents':a['agents'],'memory_authorization':None,
            'store_path':a['store']['path'],'provider_source':p['provider_source'],'provider_fingerprints':[],
            'changes':[{k:c[k] for k in ('path','operation','before_fingerprint','after_fingerprint')} for c in preview['changes']],
            'confirmed_at':NOW,'reference':'explicit removal approval'}
        return remove.run(dict(request,approval=approval))

    def report(self):
        return check.run(dict(self.request,approval=None,agents=None,all=False))

    def test_AGENTS_rules_are_free_and_file_survives_remove(self):
        self.apply('yes',True);path=self.root/'AGENTS.md';raw=path.read_bytes()
        body=raw.replace(b'# '+self.root.name.encode(),b'# User title')+b'\nUser rules\xff\r\n'
        path.write_bytes(body)
        self.request['approval']=None
        result=enable.run(self.request)
        self.assertEqual(result['status'],'completed',result)
        self.assertEqual(path.read_bytes(),body)
        self.assertFalse(any(o['status']=='drifted' and o['path']==str(path) for o in self.report()['projects'][0]['objects']))
        removed=self.remove_project();self.assertEqual(removed['status'],'completed',removed)
        self.assertTrue(path.is_file());self.assertIn(b'User rules\xff\r\n',path.read_bytes())
        self.assertNotIn(enable.KEEPER_MARKER['start'].encode(),path.read_bytes())

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
        self.assertEqual(self.remove_project()['status'],'completed')
        self.assertTrue(path.exists());self.assertIn(b'free historical body',path.read_bytes())

    def test_managed_bridge_edit_still_stops_enable_and_remove(self):
        self.apply('yes',True);path=self.root/'AGENTS.md'
        path.write_bytes(path.read_bytes().replace(b'Keeper rules',b'foreign bridge'))
        before=self.runtime.registry.read_bytes();self.request['approval']=None
        self.assertEqual(enable.run(self.request)['errors'][0]['code'],'drift')
        self.assertEqual(remove.run(dict(self.request,approval=None))['errors'][0]['code'],'drift')
        self.assertEqual(self.runtime.registry.read_bytes(),before)

    def test_new_pure_CLAUDE_file_deleted_native_WB_directory_retained(self):
        self.apply('yes',True)
        result=self.remove_project();self.assertEqual(result['status'],'completed',result)
        self.assertFalse((self.root/'CLAUDE.md').exists())
        self.assertFalse((self.root/'.workbuddy/memory/MEMORY.md').exists())
        self.assertTrue((self.root/'.workbuddy/memory').is_dir())
        self.assertTrue((self.root/'AGENTS.md').is_file())
        self.assertTrue((self.root/'docs/context-keeper/memory-keeper.md').exists())

    def test_CLAUDE_added_user_bytes_preserved_without_whole_file_guard(self):
        self.apply('yes',True);path=self.root/'CLAUDE.md';user=b'\r\nUser rules\xff\n'
        path.write_bytes(path.read_bytes()+user)
        result=self.remove_project();self.assertEqual(result['status'],'completed',result)
        self.assertEqual(path.read_bytes(),user)

    def test_CLAUDE_existing_no_newline_body_only_created_reference_removed(self):
        path=self.root/'CLAUDE.md';original=b'Existing bytes\xff';path.write_bytes(original)
        self.apply()
        result=self.remove_project();self.assertEqual(result['status'],'completed',result)
        self.assertEqual(path.read_bytes(),original)

    def test_duplicate_or_edited_created_reference_stops_without_partial_removal(self):
        self.apply();path=self.root/'CLAUDE.md';original=path.read_bytes();before=self.runtime.registry.read_bytes()
        for raw in (original+original,b'  @AGENTS.md\n',b'@different.md\n'):
            path.write_bytes(raw);self.request['approval']=None
            self.assertEqual(remove.run(dict(self.request,approval=None))['errors'][0]['code'],'drift')
            self.assertEqual(self.runtime.registry.read_bytes(),before)
            self.assertNotEqual(enable.run(self.request)['status'],'completed')

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
        self.assertEqual(self.remove_project()['status'],'completed');self.assertEqual(path.read_bytes(),b'@AGENTS.md\n')

    def test_yes_to_no_plan_revokes_created_triggers_keeps_store_and_source(self):
        self.apply('yes',True);store=self.root/'docs/context-keeper';before={str(p):p.read_bytes() for p in store.rglob('*') if p.is_file()}
        self.calls.clear();self.request.update(approval=None,memory_choice='no')
        preview=enable.run(self.request);plan=json.loads(preview['next_action'])
        self.assertTrue(any(c['operation']=='remove' for c in plan['changes']))
        self.assertEqual(plan['memory_transition']['after'],'no');self.assertTrue(plan['changes'])
        result=self.execute_preview(preview);self.assertEqual(result['status'],'completed',result)
        p=self.load()['projects'][str(self.root)];self.assertEqual(p['memory_authorization'],'no')
        self.assertEqual(self.calls,[])
        for path in (self.root/'AGENTS.md',self.root/'CLAUDE.md',self.root/'.workbuddy/memory/MEMORY.md'):
            if path.exists():self.assertNotIn(b'<!-- context-keeper:',path.read_bytes())
        self.assertIn(enable.DENIED_MARKER['start'].encode(),(self.root/'AGENTS.md').read_bytes())
        self.assertFalse((self.root/'.codex/skills/context-keeper').is_symlink())
        self.assertEqual(before,{str(p):p.read_bytes() for p in store.rglob('*') if p.is_file()})
        self.assertTrue((self.source/'scripts/install.py').exists())
        print('DECLINE',json.dumps({'authorization':p['memory_authorization'],'created_bridges_removed':True,'denial_guard':True,'store_preserved':True,'plan_changes':len(plan['changes'])}))

    def test_reused_bridge_preserved_with_denial_even_after_project_remove(self):
        self.apply('yes',True);data=self.load();a=data['projects'][str(self.root)]['checkouts'][str(self.root)]
        obj=next(o for o in a['objects'].values() if o['path']==str(self.root/'CLAUDE.md') and o['kind']=='block')
        unit=bytes.fromhex(obj['lifecycle']['unit_hex']);obj.pop('lifecycle');obj.update(ownership='reused',original_existed=True,backup_manifest=None)
        from agm_core.paths import allowed_user_paths
        self.runtime.registry.write_bytes(registry.serialize_registry(data,allowed_user_paths=allowed_user_paths(self.config,None,home=str(self.home))))
        self.request.update(approval=None,memory_choice='no');result=self.execute_preview(enable.run(self.request))
        self.assertEqual(result['status'],'completed',result)
        path=self.root/'CLAUDE.md';self.assertIn(unit,path.read_bytes());self.assertIn(enable.DENIED_MARKER['start'].encode(),path.read_bytes())
        self.assertEqual(self.remove_project()['status'],'completed')
        self.assertIn(unit,path.read_bytes());self.assertIn(enable.DENIED_MARKER['start'].encode(),path.read_bytes())
        self.assertEqual(self.load()['projects'][str(self.root)]['memory_authorization'],'no')

    def test_reenable_removes_only_owned_denial_with_explicit_plan(self):
        self.apply('yes',True);self.request.update(approval=None,memory_choice='no');self.execute_preview(enable.run(self.request))
        self.request.update(approval=None,memory_choice='yes')
        result=self.execute_preview(enable.run(self.request));self.assertEqual(result['status'],'completed',result)
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
        self.assertEqual(enable.run(self.request)['errors'][0]['code'],'agent_not_installed');self.assertEqual(self.runtime.registry.read_bytes(),before)

    def test_no_installed_executor_does_not_create_project_entries(self):
        self.request.update(agents=None,search_paths=[],app_directories=[])
        import shutil
        shutil.rmtree(self.home/'Applications/WorkBuddy.app')
        before=self.runtime.registry.read_bytes();result=enable.run(self.request)
        self.assertEqual(result['status'],'gaps',result);self.assertFalse((self.root/'AGENTS.md').exists())
        self.assertEqual(self.runtime.registry.read_bytes(),before)

    def test_WorkBuddy_installed_without_native_directory_is_partial_without_mkdir(self):
        self.request.update(agents=['workbuddy'],memory_choice='yes')
        preview=enable.run(self.request)
        self.assertEqual(json.loads(preview['next_action'])['native_pending'],['workbuddy'])
        self.assertFalse((self.root/'.workbuddy/memory').exists())
        result=self.execute_preview(preview);self.assertEqual(result['status'],'gaps',result)
        self.assertFalse((self.root/'.workbuddy/memory').exists());self.assertEqual(self.calls,[])
        a=self.load()['projects'][str(self.root)]['checkouts'][str(self.root)]
        self.assertEqual(a['states']['bridge_assembled']['workbuddy']['status'],'blocked')

    def test_project_remove_retains_machine_installation_and_user_objects(self):
        self.runtime.code.mkdir(parents=True);(self.runtime.code/'SKILL.md').write_text('# installed product\n')
        request={k:self.request[k] for k in ('home','platform_config','search_paths','app_directories','detect_runner')}
        request['agents']=None
        preview=user_entries.run_user_entries(request);approval=json.loads(preview['next_action']);approval.update(confirmed_at=NOW,reference='machine entry confirmation')
        result=user_entries.run_user_entries(dict(request,approval=approval));self.assertEqual(result['status'],'completed',result)
        machine=copy.deepcopy(self.load()['machine']);code=(self.runtime.code/'SKILL.md').read_bytes()
        self.apply('yes',True)
        self.assertEqual(self.remove_project()['status'],'completed')
        self.assertEqual(self.load()['machine'],machine);self.assertEqual((self.runtime.code/'SKILL.md').read_bytes(),code)
        self.assertTrue((self.home/'.codex/AGENTS.md').is_file())
        self.assertTrue(all(obj['consumers']==[] for obj in self.load()['machine']['objects'].values()))

    def test_R4_missing_source_scripts_is_readonly_gap_not_ready(self):
        self.apply('yes',True);(self.source/'scripts/install.py').unlink();(self.source/'scripts/context_keeper_probe.py').unlink()
        before={str(p):(p.read_bytes(),p.stat().st_mtime_ns) for p in self.area.rglob('*') if p.is_file() and not p.is_symlink()}
        with patch('agm_core.enable._call',side_effect=AssertionError('check must not call provider')):
            result=self.report()
        report=result['projects'][0];self.assertEqual(report['states']['source_available']['status'],'missing')
        self.assertIn('source_missing',{g['code'] for g in report['gaps']})
        self.assertEqual(before,{str(p):(p.read_bytes(),p.stat().st_mtime_ns) for p in self.area.rglob('*') if p.is_file() and not p.is_symlink()})
        print('SOURCE',json.dumps({'source_status':report['states']['source_available']['status'],'gap_codes':[g['code'] for g in report['gaps']]}))

    def test_R4_wrong_source_type_or_changed_approved_bytes_blocks(self):
        self.apply('yes',True);path=self.source/'scripts/install.py';original=path.read_bytes()
        path.write_bytes(original+b'\n# changed')
        report=self.report()['projects'][0];self.assertEqual(report['states']['source_available']['status'],'blocked')
        path.unlink();path.symlink_to(self.source/'scripts/context_keeper_probe.py')
        report=self.report()['projects'][0];self.assertEqual(report['states']['source_available']['status'],'blocked')


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
        self.assertEqual(self.remove_project()['status'],'completed')
        self.assertTrue(path.exists())

    def test_revocation_succeeds_when_all_registered_executors_are_now_absent(self):
        self.apply('yes',True)
        self.request.update(search_paths=[],app_directories=[],user_candidates={},
            agents=None,approval=None,memory_choice='no')
        # Existing configuration produces only unknown hints, never installed facts.
        (self.home/'Applications/WorkBuddy.app').rename(self.area/'retired-WorkBuddy.app')
        result=self.execute_preview(enable.run(self.request))
        self.assertEqual(result['status'],'completed',result)
        self.assertEqual(self.load()['projects'][str(self.root)]['memory_authorization'],'no')
        self.assertNotIn(enable.KEEPER_MARKER['start'].encode(),(self.root/'AGENTS.md').read_bytes())
        self.assertIn(enable.DENIED_MARKER['start'].encode(),(self.root/'AGENTS.md').read_bytes())

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
        self.assertEqual(self.remove_project()['status'],'completed')
        self.assertFalse((self.root/'CLAUDE.md').exists())
