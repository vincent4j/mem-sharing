"""Bounded synthetic HOME tests; no native host or production writes."""
import copy
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import socket
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'scripts'))
from agm_core import staging_retirement as s
from agm_core import uninstall_recovery as r
from agm_core.layout import RuntimeLayout

class RetirementTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.base=Path(self.temp.name).resolve(); self.home=self.base/'home';self.home.mkdir()
        self.rt=RuntimeLayout(self.home);self.rt.var.mkdir(parents=True)
        self.root=self.rt.code.parent/'mem-sharing-plugin-staging';self.pending=self.root/'pending'
        self.pending.mkdir(parents=True,mode=0o700);os.chmod(self.root,0o700)
        self.evidence=self.base/'external';self.evidence.mkdir(mode=0o700)
        self.options={'tool_commit':'a'*40,'paseo_cli':'/official/paseo','cli_sha256':'b'*64,'server_id':'srv_test','plugin_id':'memsharing-synthetic-dev','evidence_dir':str(self.evidence)}
        self.tool={'root':'/trusted','commit':'a'*40};self.host={'removed':True}
        self.project=self.home/'project';self.project.mkdir()
        self.ledger={'projects':{str(self.project):{'main_checkout':str(self.project),'memory_policy':'follow_ck','checkouts':{}}}}
        self.installation=(self.ledger,'c'*64)
        self.operation={'id':'old','flow':'enable','phase':'execute','home':str(self.home),'host':socket.gethostname(),'state':'completed','started_at':'2020-01-01T00:00:00Z'}
        self.add('op-abc','operation.json',self.operation)
    def add(self,directory,name,value):
        d=self.pending/directory;d.mkdir(mode=0o700,exist_ok=True)
        f=d/name;f.write_text(json.dumps(value));os.chmod(f,0o600);os.utime(f,(1000000000,1000000000));return f
    def preview(self,rt=None,options=None,**kw):
        return s.preview(rt or self.rt,options or self.options,tool=self.tool,host=self.host,installation=self.installation,**kw)
    def approval(self,p):return {'plan':p,'reference':'Synthetic explicit approval','confirmed_at':'2021-01-01T00:00:00Z'}
    def test_round_trip_existing_consumer(self):
        p=self.preview();before=(self.pending/'op-abc/operation.json').read_bytes()
        with patch.object(s,'host_scene',return_value=self.host),patch.object(s,'installed',return_value=self.installation):
            result=s.execute(self.rt,self.approval(p),rebuild=self.preview)
        self.assertEqual(result['status'],'completed');self.assertEqual(set(x.name for x in self.root.iterdir()),{'host-receipt.json'})
        self.assertEqual((Path(result['backup_root'])/'op-abc/operation.json').read_bytes(),before)
        self.assertEqual((Path(result['backup_root'])/'op-abc/operation.json').stat().st_mtime_ns,1000000000000000000)
    def test_fusion_exact_producer_terminals_and_active_unknown_stay_blocked(self):
        for phase,states in [('preview',['completed','failed']),('execute',['completed','failed','rejected','stale_plan','no_pending_plan'])]:
            for state in states:
                self.add('op-abc','operation.json',dict(self.operation,flow='fusion',phase=phase,state=state))
                plan=self.preview();self.assertEqual(plan['terminal_evidence'][0]['record_state'],state)
        for state in ('running','unknown','approval_required','recovered','gaps'):
            self.add('op-abc','operation.json',dict(self.operation,flow='fusion',phase='preview',state=state))
            with self.assertRaises(ValueError):self.preview()
        self.add('op-abc','operation.json',dict(self.operation,flow='fusion',state='completed',journal='/any/manifest.json'))
        with self.assertRaises(ValueError):self.preview()

    def test_fusion_approval_requires_exact_terminal_transaction_proof(self):
        import test_fusion_phases as phase_fixture
        from agm_core import user_rules_organize as fusion
        fixture=phase_fixture.PhaseTests('runTest');fixture.setUp();self.addCleanup(fixture.doCleanups)
        approval=dict(fixture.plan,confirmed_at=datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),reference='Synthetic real fusion producer approval')
        artifact=fixture.f.home/'fusion-approval.json';artifact.write_text(json.dumps(approval));artifact.chmod(0o600)
        os.utime(artifact,(1000000000,1000000000))
        now=datetime.now(timezone.utc)
        with self.assertRaises(ValueError):s._artifact(artifact,fixture.f.rt,{},now)
        result=fusion.execute_organize(fixture.plan,approval);self.assertEqual(result['status'],'completed',result)
        meta,state=s._artifact(artifact,fixture.f.rt,{},now)
        self.assertEqual(state,'no_operation_record');self.assertTrue(meta['history'])
        manifest=Path(result['manifest']);saved=manifest.read_bytes()
        tx=json.loads(saved);tx['status']='applying';manifest.write_text(json.dumps(tx))
        with self.assertRaises(ValueError):s._artifact(artifact,fixture.f.rt,{},now)

    def test_running_blocks(self):
        self.operation['state']='running';self.add('op-abc','operation.json',self.operation)
        with self.assertRaises(ValueError):self.preview()
    def test_unknown_state_blocks(self):
        self.operation['state']='unknown';self.add('op-abc','operation.json',self.operation)
        with self.assertRaises(ValueError):self.preview()
    def test_wrong_home_blocks(self):
        self.operation['home']='/other';self.add('op-abc','operation.json',self.operation)
        with self.assertRaises(ValueError):self.preview()
    def test_unknown_artifact_not_claimed(self):
        self.add('op-abc','release-request.json',{'kind':'plugin-package'})
        with self.assertRaises(ValueError):self.preview()
    def legitimate_enable(self):
        # Execute the actual public producer in synthetic HOME, not an invented ledger.
        import subprocess
        from runtime_fixture import installed_registry, seed_project_executors
        from agm_core import registry, paths, enable
        self.rt.registry.write_bytes(registry.serialize_registry(installed_registry()));self.rt.registry.chmod(0o600)
        subprocess.run(['git','init','-q',str(self.project)],check=True)
        (self.project/'AGENTS.md').write_bytes(b'# Synthetic project\r\nPrivate fixture text')
        (self.project/'AGENTS.md').chmod(0o644)
        config=paths.select_platform(paths.load_agents_table(),'darwin')
        request={'project':str(self.project),'agents':['codex'],'home':str(self.home),
                 'runtime_layout':self.rt,'platform_config':config,'interactive':False,'preview':True}
        request.update(seed_project_executors(self.home))
        result=enable.run(request);self.assertEqual(result['status'],'approval_required',result)
        approval=json.loads(result['next_action']);approval.update(confirmed_at=datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),reference='Synthetic real producer approval')
        request.update(preview=False,approval=approval)
        result=enable.run(request);self.assertEqual(result['status'],'completed',result)
        allowed=paths.allowed_user_paths(config,None,home=str(self.home))
        self.ledger=registry.load_registry(self.rt.registry,allowed_user_paths=allowed)
        self.installation=(self.ledger,r.digest(self.rt.registry.read_bytes()))
        self.add('op-approval','enable-approval.json',approval)
        return approval
    def test_independent_enable_approval(self):
        self.legitimate_enable()
        p=self.preview();row=next(x for x in p['terminal_evidence'] if x['dir']=='op-approval')
        self.assertEqual(row['record_state'],'no_operation_record')
        self.assertEqual(len(p['historical_evidence']),4)
    def test_recent_orphan_blocks(self):
        f=self.pending/'op-abc/operation.json';os.utime(f,None)
        with self.assertRaises(ValueError):self.preview()
    def test_symlink_blocks(self):
        f=self.pending/'op-abc/operation.json';f.unlink();f.symlink_to('/etc/passwd')
        with self.assertRaises(ValueError):self.preview()
    def test_mode_blocks(self):
        os.chmod(self.pending/'op-abc/operation.json',0o644)
        with self.assertRaises(ValueError):self.preview()
    def test_duplicate_json_blocks(self):
        f=self.pending/'op-abc/operation.json';f.write_text('{"id":1,"id":2}');os.utime(f,(1000000000,1000000000))
        with self.assertRaises(ValueError):self.preview()
    def test_approval_drift_zero_write(self):
        p=self.preview();self.add('op-new','operation.json',self.operation)
        with self.assertRaises(ValueError):s.execute(self.rt,self.approval(p),rebuild=self.preview)
        self.assertFalse((self.evidence/'memsharing-host-staging').exists());self.assertTrue(self.pending.exists())
    def test_lock_blocks(self):
        self.rt.lock.mkdir()
        with self.assertRaises(ValueError):self.preview()
    def test_journal_not_guessed(self):
        self.operation['journal']=str(self.rt.backups/'old/manifest.json');self.add('op-abc','operation.json',self.operation)
        with self.assertRaises(ValueError):self.preview()
    def test_archive_failure_no_delete(self):
        p=self.preview()
        with patch.object(s,'_fsync',side_effect=OSError('synthetic fsync failure')):
            with self.assertRaises(OSError):s.execute(self.rt,self.approval(p),rebuild=self.preview)
        self.assertTrue((self.pending/'op-abc/operation.json').exists());self.assertTrue((self.evidence/'memsharing-host-staging').is_dir())
    def test_wrong_approval_zero_write(self):
        p=self.preview();a=self.approval(p);a['plan']=copy.deepcopy(p);a['plan']['home']='/other'
        with self.assertRaises(ValueError):s.execute(self.rt,a,rebuild=self.preview)
        self.assertFalse((self.evidence/'memsharing-host-staging').exists())
    def test_unknown_top_level_blocks(self):
        (self.root/'unknown').mkdir()
        with self.assertRaises(ValueError):self.preview()

    def test_added_candidate_after_archive_zero_deletion(self):
        p=self.preview()
        original=s._fsync
        calls=[]
        def change(path):
            original(path);calls.append(path)
            if len(calls)==1:self.add('op-late','operation.json',self.operation)
        with patch.object(s,'_fsync',side_effect=change),patch.object(s,'host_scene',return_value=self.host),patch.object(s,'installed',return_value=self.installation):
            with self.assertRaises(ValueError):s.execute(self.rt,self.approval(p),rebuild=self.preview)
        self.assertTrue((self.pending/'op-abc/operation.json').is_file())
    def test_multiple_artifacts_not_linked(self):
        self.add('op-abc','enable-approval.json',{})
        with self.assertRaises(ValueError):self.preview()
    def test_official_host_requires_absent_not_disabled(self):
        cli=self.base/'cli';cli.write_bytes(b'official fixture')
        scene={'home':str(self.home/'.paseo'),'serverId':'srv_test','pid':2,'startedAt':'today','localDaemon':'running','connectedDaemon':'reachable'}
        def output(value):
            from subprocess import CompletedProcess
            return CompletedProcess([],0,json.dumps(value).encode(),b'')
        with patch.object(s.subprocess,'run',side_effect=[output(scene),output([{'id':'memsharing-synthetic-dev','enabled':False}]),output(scene)]):
            with self.assertRaises(ValueError):s.host_scene(cli,r.digest(cli.read_bytes()),self.home/'.paseo','srv_test','memsharing-synthetic-dev')
    def test_official_host_changed_server_blocks(self):
        cli=self.base/'cli';cli.write_bytes(b'official fixture')
        scene={'home':str(self.home/'.paseo'),'serverId':'srv_test','pid':2,'startedAt':'today','localDaemon':'running','connectedDaemon':'reachable'}
        other=dict(scene,serverId='other')
        from subprocess import CompletedProcess
        results=[CompletedProcess([],0,json.dumps(x).encode(),b'') for x in (scene,[],other)]
        with patch.object(s.subprocess,'run',side_effect=results):
            with self.assertRaises(ValueError):s.host_scene(cli,r.digest(cli.read_bytes()),self.home/'.paseo','srv_test','memsharing-synthetic-dev')
    def test_approval_future_zero_write(self):
        p=self.preview();a=self.approval(p);a['confirmed_at']='2099-01-01T00:00:00Z'
        with self.assertRaises(ValueError):s.execute(self.rt,a,rebuild=self.preview)
        self.assertFalse((self.evidence/'memsharing-host-staging').exists())
    def test_archive_overlap_blocks(self):
        self.options['evidence_dir']=str(self.pending)
        with self.assertRaises(ValueError):self.preview()

    def test_hardlink_blocks(self):
        os.link(self.pending/'op-abc/operation.json',self.base/'outside-link')
        with self.assertRaises(ValueError):self.preview()
    def test_other_owner_id_blocks(self):
        with self.assertRaises(ValueError):s.host_scene('/missing','a'*64,self.home/'.paseo','srv_test','other')

    def test_independent_approval_round_trip_consumer(self):
        self.test_independent_enable_approval()
        p=self.preview()
        with patch.object(s,'host_scene',return_value=self.host),patch.object(s,'installed',return_value=self.installation):
            result=s.execute(self.rt,self.approval(p),rebuild=self.preview)
        receipt=json.loads(Path(result['receipt_path']).read_bytes())
        self.assertEqual(len(receipt['terminal_evidence']),2)
        self.assertEqual({x['record_state'] for x in receipt['terminal_evidence']},{'completed','no_operation_record'})

    def test_new_install_lock_after_archive_zero_delete(self):
        p=self.preview();original=s._fsync;calls=[]
        def change(path):
            original(path);calls.append(path)
            if len(calls)==1:(self.home/'.mem-sharing-install.lock').mkdir()
        with patch.object(s,'_fsync',side_effect=change),patch.object(s,'host_scene',return_value=self.host),patch.object(s,'installed',return_value=self.installation):
            with self.assertRaises(ValueError):s.execute(self.rt,self.approval(p),rebuild=self.preview)
        self.assertTrue((self.pending/'op-abc/operation.json').is_file())

    def test_registered_approval_disabled_rejected(self):
        self.legitimate_enable();self.ledger['projects'][str(self.project)]['memory_policy']='disabled'
        with self.assertRaises(ValueError):self.preview()
    def test_registered_approval_unknown_output_rejected(self):
        approval=self.legitimate_enable();approval['changes'][0]['path']=str(self.project/'unknown-private-file')
        self.add('op-approval','enable-approval.json',approval)
        with self.assertRaises(ValueError):self.preview()
    def test_registered_approval_forged_hash_rejected(self):
        approval=self.legitimate_enable();approval['changes'][0]['after_fingerprint']='2'*64
        self.add('op-approval','enable-approval.json',approval)
        with self.assertRaises(ValueError):self.preview()
    def test_historical_evidence_drift_zero_write(self):
        self.legitimate_enable();p=self.preview()
        manifest=next(Path(k) for k in p['historical_evidence'] if k.endswith('manifest.json'))
        data=json.loads(manifest.read_bytes());data['status']='prepared';manifest.write_text(json.dumps(data))
        with self.assertRaises(ValueError):s.execute(self.rt,self.approval(p),rebuild=self.preview)
        self.assertFalse((self.evidence/'memsharing-host-staging').exists())

    def test_registered_approval_missing_checkout_rejected(self):
        self.legitimate_enable();self.ledger['projects'][str(self.project)]['checkouts']={}
        with self.assertRaises(ValueError):self.preview()
    def test_registered_approval_missing_object_rejected(self):
        self.legitimate_enable();self.ledger['projects'][str(self.project)]['checkouts'][str(self.project)]['objects']={}
        with self.assertRaises(ValueError):self.preview()
    def test_historical_extra_output_rejected(self):
        self.legitimate_enable();obj=next(iter(self.ledger['projects'][str(self.project)]['checkouts'][str(self.project)]['objects'].values()))
        manifest=Path(obj['backup_manifest']);data=json.loads(manifest.read_bytes());data['entries'].append(copy.deepcopy(data['entries'][0]));manifest.write_text(json.dumps(data))
        with self.assertRaises(ValueError):self.preview()

    def test_self_reported_approval_and_journal_hash_not_authority(self):
        approval=self.legitimate_enable()
        obj=next(iter(self.ledger['projects'][str(self.project)]['checkouts'][str(self.project)]['objects'].values()))
        manifest=Path(obj['backup_manifest']);data=json.loads(manifest.read_bytes())
        data['entries'][0]['after']['fingerprint']='2'*64;manifest.write_text(json.dumps(data))
        approval['changes'][0]['after_fingerprint']='2'*64;self.add('op-approval','enable-approval.json',approval)
        with self.assertRaises(ValueError):self.preview()
    def test_unparseable_historical_registry_before_rejected(self):
        self.legitimate_enable()
        obj=next(iter(self.ledger['projects'][str(self.project)]['checkouts'][str(self.project)]['objects'].values()))
        manifest=Path(obj['backup_manifest']);data=json.loads(manifest.read_bytes());before=manifest.parent/'1.before'
        before.write_bytes(b'not JSON');data['entries'][1]['before']['fingerprint']=r.digest(before.read_bytes());manifest.write_text(json.dumps(data))
        with self.assertRaises(ValueError):self.preview()

if __name__=='__main__':unittest.main()
