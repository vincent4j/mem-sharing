"""Upgrade protocol fixtures. Real P/T Git snapshots live in integration tests."""
import copy
import json
import os
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parent))
from test_m404_install import InstallFixture, approved
from agm_core import upgrade, versions, user_install as install, legacy_import as legacy, registry


class UpgradeFixture(InstallFixture):
    def setUp(self):
        super().setUp()
        self.execute()
        self.p=copy.deepcopy(self.request['source'])
        self.target=self.area/'target';shutil.copytree(self.source,self.target)
        (self.target/'scripts/agm_core/revision.py').write_text('def recovery_features():\n    return ("upgrade", "rollback")\n')
        self.t=dict(self.p,root=str(self.target),version='0.4.1',commit='b'*40,
            files={str(p.relative_to(self.target)):legacy.digest(p.read_bytes()) for p in self.target.rglob('*') if p.is_file()})
        self.req=dict(self.request,source=self.t,operation_id='fixture-m407')
        old=self.product();target,_=install._source(self.req)
        self.forward={'before':{'schema_version':2,'product_structure_version':1,
            'product_code_version':old['product_code_version'],'source':old['source']},
            'after':{'schema_version':2,'product_structure_version':1,'product_code_version':target['version'],
                     'source':{k:target[k] for k in ('url','commit','tree_sha256')}},'direction':'upgrade','entries':'preserve'}
        self.req['conversions']=[self.forward]

    def product(self):return json.loads(self.runtime.registry.read_bytes())['product']
    def plan_upgrade(self):return upgrade.plan_upgrade(self.req)
    def execute_upgrade(self,plan=None,hook=None):
        plan=plan or self.plan_upgrade()
        return upgrade.execute_upgrade(plan,approved(plan),request=self.req,hook=hook)
    def recover_upgrade(self,path,action):
        plan=upgrade.plan_recovery(path,action=action)
        return upgrade.recover_upgrade(plan,approved(plan))
    def snapshot(self,root=None):
        root=root or self.home
        return {str(p.relative_to(root)):(p.lstat().st_mode,p.lstat().st_mtime_ns,p.read_bytes() if p.is_file() else None)
                for p in [root,*root.rglob('*')] if not p.is_symlink()}


class UpgradeTests(UpgradeFixture):
    def test_preview_and_same_version_are_zero_writes_and_mtimes(self):
        before=self.snapshot();self.assertEqual(install.inspect_machine(self.req)['scene'],'valid_old')
        plan=self.plan_upgrade();self.assertEqual(before,self.snapshot())
        self.assertTrue(plan['changes']);self.assertEqual(plan['channel'],'upgrade')
        request=dict(self.req,source=self.p)
        same=upgrade.plan_upgrade(request);self.assertTrue(same['noop'])
        self.assertEqual(upgrade.execute_upgrade(same)['changes'],[])
        self.assertEqual(before,self.snapshot())

    def test_first_install_has_durable_inventory_and_activation(self):
        source,files=install._source(self.request);item=versions.descriptor(self.runtime,source,files)
        versions.verify(self.runtime,item)
        self.assertTrue(versions.installed_before(self.runtime,item))
        self.assertFalse(Path(item['slot']).is_relative_to(self.runtime.backups))

    def test_upgrade_preserves_user_bytes_and_separate_versions(self):
        for name in ('memories/user.txt','references/ref.txt','skills/other/file','mcp/config'):
            p=self.runtime.root/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(b'user\xff\r\n')
        content={name:(self.runtime.root/name).read_bytes() for name in ('memories/user.txt','references/ref.txt','skills/other/file','mcp/config')}
        plan=self.plan_upgrade();installation_id=self.product()['installation_id']
        self.assertEqual(self.execute_upgrade(plan)['status'],'completed')
        self.assertEqual(self.product()['product_code_version'],'0.4.1')
        self.assertEqual(self.product()['installation_id'],installation_id)
        self.assertEqual(self.product()['product_structure_version'],1)
        self.assertEqual({name:(self.runtime.root/name).read_bytes() for name in content},content)
        self.assertTrue(versions.installed_before(self.runtime,plan['before_inventory']))
        self.assertTrue(versions.installed_before(self.runtime,plan['target_inventory']))
        self.assertEqual(install.inspect_machine(self.req)['scene'],'same')
        self.assertFalse(upgrade.marker(self.runtime).exists())
        for item in plan['outputs']:
            if item['before']['kind']=='file':self.assertEqual((Path(plan['archive'])/'code-before'/Path(item['path']).relative_to(self.runtime.code)).read_bytes(),(self.source/Path(item['path']).relative_to(self.runtime.code)).read_bytes() if Path(item['path']).name!='.agm-code-manifest.json' else bytes.fromhex(plan['before_inventory']['marker_hex']))

    def test_explicit_rollback_uses_installed_inventory_and_keeps_current_metadata(self):
        self.execute_upgrade()
        data=json.loads(self.runtime.registry.read_bytes());data['product']['installation_id']='current-installation'
        self.runtime.registry.write_bytes(registry.serialize_registry(data))
        reverse={'before':self.forward['after'],'after':self.forward['before'],'direction':'rollback','entries':'preserve'}
        old_source,_=install._source({'source':self.p})
        self.req.update(direction='rollback',operation_id='rollback-m407',conversions=[reverse],
            rollback_target={'version':'0.4.0','tree_sha256':old_source['tree_sha256']})
        self.req.pop('source');shutil.rmtree(self.source)
        # Persistent inventory is sufficient after historical recovery material cleanup.
        for op in self.home.glob('.agents-group-install-*'):shutil.rmtree(op)
        shutil.rmtree(self.runtime.backups)
        plan=self.plan_upgrade();result=self.execute_upgrade(plan)
        self.assertEqual(result['status'],'completed');self.assertEqual(self.product()['product_code_version'],'0.4.0')
        self.assertEqual(self.product()['installation_id'],'current-installation')
        self.assertFalse((self.runtime.code/'scripts/agm_core/revision.py').exists())

    def test_unknown_future_dirty_and_approval_drift_rejected_before_writes(self):
        before=self.snapshot();bad=dict(self.req,conversions=[])
        with self.assertRaises(ValueError):upgrade.plan_upgrade(bad)
        self.assertEqual(before,self.snapshot())
        (self.runtime.code/'foreign.txt').write_text('foreign')
        before=self.snapshot()
        with self.assertRaises(ValueError):self.plan_upgrade()
        self.assertEqual(before,self.snapshot());(self.runtime.code/'foreign.txt').unlink()
        plan=self.plan_upgrade();data=json.loads(self.runtime.registry.read_bytes());data['product']['last_operation_id']='changed'
        self.runtime.registry.write_bytes(registry.serialize_registry(data));before=self.snapshot()
        with self.assertRaises(ValueError):self.execute_upgrade(plan)
        self.assertEqual(before,self.snapshot())
        data['schema_version']=3;self.runtime.registry.write_text(json.dumps(data));before=self.snapshot()
        with self.assertRaises(ValueError):self.plan_upgrade()
        self.assertEqual(before,self.snapshot())

    def test_bad_ledger_and_foreign_inventory_are_never_repaired(self):
        raw=self.runtime.registry.read_bytes();self.runtime.registry.write_bytes(b'{broken')
        before=self.snapshot()
        with self.assertRaises(ValueError):self.plan_upgrade()
        self.assertEqual(before,self.snapshot());self.runtime.registry.write_bytes(raw)
        plan=self.plan_upgrade();slot=Path(plan['target_inventory']['slot']);slot.mkdir(parents=True);(slot/'foreign').write_text('foreign')
        before=self.snapshot()
        with self.assertRaises(ValueError):self.plan_upgrade()
        self.assertEqual(before,self.snapshot())

    def test_six_phases_before_after_continue_and_rollback(self):
        for phase in upgrade.PHASES:
            for when in ('before','after'):
                for action in ('continue','rollback'):
                    with self.subTest(phase=phase,when=when,action=action):
                        fixture=UpgradeFixture();fixture.setUp()
                        try:
                            plan=fixture.plan_upgrade();seen=[]
                            def hook(event,path):
                                if event==when+'_phase:'+phase and not seen:
                                    seen.append(True);raise RuntimeError('fault '+event)
                            with self.assertRaises(RuntimeError):fixture.execute_upgrade(plan,hook)
                            self.assertTrue(seen)
                            if phase=='commit' and when=='after' and action=='rollback':
                                with self.assertRaises(upgrade.UpgradeError):fixture.recover_upgrade(plan['journal'],action)
                                result=fixture.recover_upgrade(plan['journal'],'continue')
                                self.assertTrue(result['finalized_only']);expected='0.4.1'
                            else:
                                result=fixture.recover_upgrade(plan['journal'],action)
                                self.assertEqual(result['status'],'completed' if action=='continue' else 'rolled_back')
                                expected='0.4.1' if action=='continue' else '0.4.0'
                            self.assertEqual(fixture.product()['product_code_version'],expected)
                            install._code_matches(fixture.runtime,fixture.product())
                            self.assertFalse(upgrade.marker(fixture.runtime).exists())
                            print('PHASE',phase,when,action,result['status'],expected)
                        finally:fixture.doCleanups()

    def test_every_file_and_inventory_registry_rename_window(self):
        for event in ('before_code_replace','after_code_replace','before_version_rename','after_version_rename','before_registry_commit','after_registry_commit'):
            for action in ('continue','rollback'):
                with self.subTest(event=event,action=action):
                    fixture=UpgradeFixture();fixture.setUp()
                    try:
                        plan=fixture.plan_upgrade();seen=[]
                        def hook(stage,path):
                            if stage==event and not seen:seen.append(True);raise RuntimeError(stage)
                        with self.assertRaises(RuntimeError):fixture.execute_upgrade(plan,hook)
                        if event=='after_registry_commit' and action=='rollback':
                            with self.assertRaises(ValueError):fixture.recover_upgrade(plan['journal'],action)
                            fixture.recover_upgrade(plan['journal'],'continue')
                        else:fixture.recover_upgrade(plan['journal'],action)
                        install._code_matches(fixture.runtime,fixture.product())
                    finally:fixture.doCleanups()

    def test_third_state_bad_backup_or_after_mixed_requires_manual_recovery(self):
        plan=self.plan_upgrade()
        def fault(event,path):
            if event=='after_phase:code':raise RuntimeError('fault')
        with self.assertRaises(RuntimeError):self.execute_upgrade(plan,fault)
        output=next(x for x in plan['outputs'] if x['before']!=x['after'] and x['after']['kind']=='file')
        path=Path(output['path']);raw=path.read_bytes();path.write_bytes(b'third state')
        before=self.snapshot()
        with self.assertRaises(ValueError):upgrade.plan_recovery(plan['journal'],action='continue')
        self.assertEqual(before,self.snapshot());path.write_bytes(raw)
        backup=Path(plan['archive'])/'registry-before.json';backup.chmod(0o600);backup.write_bytes(b'bad backup')
        with self.assertRaises(ValueError):upgrade.plan_recovery(plan['journal'],action='rollback')

    def test_fixed_toolkit_recovers_without_source_or_active_installer(self):
        plan=self.plan_upgrade()
        def fault(event,path):
            if event=='after_phase:code':raise RuntimeError('fault')
        with self.assertRaises(RuntimeError):self.execute_upgrade(plan,fault)
        shutil.rmtree(self.target)
        launcher=Path(plan['bootstrap'])/'recover.py'
        env=dict(os.environ,HOME=str(self.home),PYTHONDONTWRITEBYTECODE='1')
        preview=subprocess.run([sys.executable,'-B',str(launcher),'preview',plan['journal'],'continue'],capture_output=True,text=True,env=env)
        self.assertEqual(preview.returncode,0,preview.stderr)
        recovery=json.loads(preview.stdout);approval=self.area/'recovery.json';approval.write_text(json.dumps(approved(recovery)))
        result=subprocess.run([sys.executable,'-B',str(launcher),'apply',str(approval)],capture_output=True,text=True,env=env)
        self.assertEqual(result.returncode,0,result.stderr);self.assertEqual(json.loads(result.stdout)['status'],'completed')

    def test_hard_exit_requires_approved_stale_lock_handoff(self):
        plan=self.plan_upgrade();saved=self.area/'request.json';saved.write_text(json.dumps(self.req))
        script='''import json,os,sys
from agm_core import upgrade
request=json.load(open(sys.argv[1]));plan=upgrade.plan_upgrade(request)
def hook(event,path):
    if event=="after_code_replace":os._exit(79)
upgrade.execute_upgrade(plan,dict(plan,confirmed_at="2026-10-30T00:00:00Z",reference="isolated crash"),request=request,hook=hook)
'''
        env=dict(os.environ,HOME=str(self.home),PYTHONDONTWRITEBYTECODE='1',PYTHONPATH=str(Path(__file__).resolve().parents[2]/'scripts'))
        result=subprocess.run([sys.executable,'-B','-c',script,str(saved)],env=env,capture_output=True,text=True)
        self.assertEqual(result.returncode,79,result.stderr)
        recovery=upgrade.plan_recovery(plan['journal'],action='continue');self.assertEqual(len(recovery['stale_locks']),3)
        self.assertTrue(self.runtime.lock.exists())
        done=upgrade.recover_upgrade(recovery,approved(recovery));self.assertEqual(done['status'],'completed')
        self.assertFalse(self.runtime.lock.exists())


    def test_repeated_successful_operation_is_readonly_noop(self):
        self.execute_upgrade();before=self.snapshot()
        plan=self.plan_upgrade();self.assertTrue(plan['noop'])
        self.assertTrue(upgrade.execute_upgrade(plan)['noop'])
        self.assertEqual(before,self.snapshot())

    def test_even_whitelisted_future_ledger_is_not_downgraded(self):
        data=json.loads(self.runtime.registry.read_bytes());data['product']['product_code_version']='9.0.0'
        self.runtime.registry.write_bytes(registry.serialize_registry(data))
        rule=copy.deepcopy(self.forward);rule['before']['product_code_version']='9.0.0'
        before=self.snapshot()
        with self.assertRaises(upgrade.UpgradeError):upgrade.plan_upgrade(dict(self.req,conversions=[rule]))
        self.assertEqual(before,self.snapshot())

    def test_v_after_with_mixed_code_never_replays_conversion(self):
        plan=self.plan_upgrade()
        def fault(event,path):
            if event=='after_registry_commit':raise RuntimeError('committed')
        with self.assertRaises(RuntimeError):self.execute_upgrade(plan,fault)
        item=next(x for x in plan['outputs'] if x['before']!=x['after'] and x['before']['kind']=='file')
        path=Path(item['path']);archive=Path(plan['archive'])/'code-before'/path.relative_to(self.runtime.code)
        path.write_bytes(archive.read_bytes());path.chmod(item['before']['mode'])
        before=self.snapshot()
        for action in ('continue','rollback'):
            with self.assertRaises(upgrade.UpgradeError):upgrade.plan_recovery(plan['journal'],action=action)
        self.assertEqual(before,self.snapshot())

    def test_upgrade_guard_blocks_all_project_and_machine_entries_readonly(self):
        from agm_core import enable,remove,check,user_entries
        guard=upgrade.marker(self.runtime);guard.write_text('upgrade interrupted')
        before=self.snapshot()
        request=dict(self.request,project=str(self.area),agents=None)
        for entry in (enable.run,remove.run,check.run,user_entries.run_user_entries):
            result=entry(request)
            self.assertEqual(result['errors'][0]['code'],'machine_upgrade_pending',result)
        self.assertEqual(before,self.snapshot())

    def test_new_agent_same_version_uses_separately_approved_entry_transaction(self):
        from runtime_fixture import seed_project_executors
        self.execute_upgrade();request=dict(self.req,agents=['codex'],**seed_project_executors(self.home))
        before=self.product();preview=upgrade.run_same_version_entries(request)
        self.assertEqual(preview['status'],'approval_required',preview)
        request['approval']=approved(json.loads(preview['next_action']))
        result=upgrade.run_same_version_entries(request);self.assertEqual(result['status'],'completed',result)
        self.assertEqual(self.product(),before)
        self.assertTrue((self.home/'.codex/skills/agent-group-memory').is_symlink())
        self.assertFalse(registry.load_registry(self.runtime.registry,allowed_user_paths=install.paths.allowed_user_paths(self.config,None,home=str(self.home)))['projects'])

    def test_first_install_inventory_rename_precedes_any_active_code(self):
        for event in ('before_version_rename','after_version_rename'):
            for action in ('continue','rollback'):
                with self.subTest(event=event,action=action):
                    fixture=InstallFixture();fixture.setUp()
                    try:
                        plan=fixture.plan();seen=[]
                        def fault(stage,path):
                            if stage==event and not seen:
                                self.assertFalse(fixture.runtime.code.exists());seen.append(True)
                                raise RuntimeError('version slot window')
                        with self.assertRaises(RuntimeError):fixture.execute(plan,fault)
                        self.assertTrue(seen)
                        result=fixture.recover(plan['journal'],action)
                        self.assertEqual(result['status'],'completed' if action=='continue' else 'rolled_back')
                    finally:fixture.doCleanups()

    def test_owned_obsolete_directory_removed_and_recovered_without_touching_user_dirs(self):
        for event in ('before_directory_remove','after_directory_remove'):
            for action in ('continue','rollback'):
                fixture=InstallFixture();fixture.setUp()
                try:
                    obsolete=fixture.source/'retired/helper.py';obsolete.parent.mkdir();obsolete.write_text('def previous_release():\n    return True\n')
                    fixture.request['source']['files']['retired/helper.py']=legacy.digest(obsolete.read_bytes())
                    fixture.execute();target=fixture.area/'next';shutil.copytree(fixture.source,target);shutil.rmtree(target/'retired')
                    source=dict(fixture.request['source'],root=str(target),version='0.4.1',commit='b'*40,
                        files={str(p.relative_to(target)):legacy.digest(p.read_bytes()) for p in target.rglob('*') if p.is_file()})
                    new,_=install._source({'source':source});old=registry.load_registry(fixture.runtime.registry)['product']
                    request=dict(fixture.request,source=source,operation_id='obsolete-dir',conversions=[{
                        'before':{'schema_version':2,'product_structure_version':1,'product_code_version':'0.4.0','source':old['source']},
                        'after':{'schema_version':2,'product_structure_version':1,'product_code_version':'0.4.1','source':{k:new[k] for k in ('url','commit','tree_sha256')}},
                        'direction':'upgrade','entries':'preserve'}])
                    user=fixture.runtime.root/'memories/user-directory';user.mkdir();(user/'record').write_text('user')
                    plan=upgrade.plan_upgrade(request)
                    def fault(stage,path):
                        if stage==event:raise RuntimeError('directory window')
                    with self.assertRaises(RuntimeError):upgrade.execute_upgrade(plan,approved(plan),request=request,hook=fault)
                    recovery=upgrade.plan_recovery(plan['journal'],action=action)
                    upgrade.recover_upgrade(recovery,approved(recovery))
                    self.assertEqual((fixture.runtime.code/'retired/helper.py').exists(),action=='rollback')
                    self.assertEqual((fixture.runtime.code/'retired').exists(),action=='rollback')
                    self.assertEqual((user/'record').read_text(),'user')
                    install._code_matches(fixture.runtime,registry.load_registry(fixture.runtime.registry)['product'])
                finally:fixture.doCleanups()


    def test_persistent_inventory_is_product_evidence_when_active_ledger_is_deleted(self):
        self.runtime.registry.unlink();shutil.rmtree(self.runtime.code)
        before=self.snapshot()
        scene=install.inspect_machine(self.req)
        self.assertEqual(scene['channel'],'stop',scene)
        self.assertNotIn(scene['scene'],('empty','v0'))
        self.assertEqual(before,self.snapshot())
