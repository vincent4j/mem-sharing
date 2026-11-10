import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import uuid

HELPER=Path(__file__).resolve().parents[1]/'fixtures/windows_case_admin_v2.py'
spec=importlib.util.spec_from_file_location('case_admin_v2',HELPER)
helper=importlib.util.module_from_spec(spec);spec.loader.exec_module(helper)


class FakeRuntime:
    def __init__(self):
        self.flag=False;self.calls=0;self.snapshots=0;self.mode='ok';self.drift=False
    def validate_support_paths(self,root):pass
    def identity(self,path):
        if path.name=='owner.json':
            stat=path.stat();return stat.st_dev,stat.st_ino
        return (1,'lock') if not self.drift else (1,'other-lock')
    def snapshot(self,case):
        self.snapshots+=1
        if self.mode=='post_snapshot' and self.snapshots>=2:raise OSError('synthetic post-query failure')
        return dict(volume_id=1,file_id='case' if self.mode!='case_drift' or not self.calls else 'other-case',
                    case_sensitive_directory=self.flag,security={'sha256':'security'})
    def command(self,case,operation):
        self.calls+=1;self.flag=(operation=='enable')
        if self.mode=='timeout':raise subprocess.TimeoutExpired(['fsutil'],10,output=b'partial',stderr=b'late')
        if self.mode=='nonzero':return subprocess.CompletedProcess(['fsutil'],5,b'output',b'access denied')
        if self.mode=='lock_drift':self.drift=True
        return subprocess.CompletedProcess(['fsutil'],0,b'changed',b'')


class CaseAdminV2Tests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);(self.root/'tmp').mkdir();(self.root/'evidence').mkdir()
        uid=str(uuid.uuid4());self.case=self.root/'synthetic-home'/('dell-fixture-'+uid)/'case';self.case.mkdir(parents=True)
        self.plan=dict(root=str(self.root),case_path=str(self.case),run_id=uid,identity={'volume_id':1,'file_id':'case'},security_sha256='security',helper_path='bound-helper-v2.py')
        self.runtime=FakeRuntime()
    def run_helper(self,action='prepare',writer=helper.persist):
        return helper.run(self.plan,action,self.runtime,writer=writer)
    def records(self,record):
        return Path(record['receipt'])
    def test_intent_exists_before_command_and_success_receipts(self):
        original=self.runtime.command
        def command(case,operation):
            intents=list((self.root/'evidence').glob('*/intent.json'))
            self.assertEqual(len(intents),1)
            self.assertEqual(json.loads(intents[0].read_text())['status'],'intent')
            return original(case,operation)
        self.runtime.command=command
        record=self.run_helper()
        self.assertEqual(record['status'],'succeeded');self.assertEqual(self.runtime.calls,1)
        self.assertTrue((self.records(record)/'result.json').exists())
        self.assertTrue((self.records(record)/'completion.json').exists())
        self.assertFalse(record['race_free']);self.assertFalse(record['identity_bound_during_fsutil'])
    def test_optimized_and_nonisolated_cli_refuse_before_work(self):
        for flags in (['-I','-S','-B','-O'],[]):
            cp=subprocess.run([sys.executable,*flags,str(HELPER),'prepare','--exclusive-fixture'],capture_output=True)
            self.assertEqual(cp.returncode,2)
            self.assertIn(b'refused' if '-O' in flags else b'isolated',cp.stderr)
    def test_explicit_guards_survive_optimization(self):
        code="import runpy; m=runpy.run_path(%r); m['require'](False,'guard survives')"%str(HELPER)
        cp=subprocess.run([sys.executable,'-I','-S','-B','-O','-c',code],capture_output=True)
        self.assertNotEqual(cp.returncode,0);self.assertIn(b'guard survives',cp.stderr)
    def test_nonempty_guard_refuses_and_records(self):
        (self.case/'unknown.txt').write_bytes(b'keep')
        record=self.run_helper();self.assertEqual(record['status'],'refused');self.assertEqual(self.runtime.calls,0)
        self.assertTrue((self.records(record)/'result.json').exists())
        self.assertEqual((self.case/'unknown.txt').read_bytes(),b'keep')
    def test_source_or_snapshot_guard_failure_no_command(self):
        self.plan['identity']['file_id']='wrong'
        record=self.run_helper();self.assertEqual(record['status'],'refused');self.assertEqual(self.runtime.calls,0)
    def test_intent_persistence_failure_no_command(self):
        def writer(path,value):
            if path.name=='intent.json':raise OSError('synthetic fsync failure')
            helper.persist(path,value)
        record=self.run_helper(writer=writer)
        self.assertEqual(self.runtime.calls,0);self.assertEqual(record['status'],'refused')
        self.assertTrue((self.records(record)/'result.json').exists())
    def test_timeout_after_change_records_state_and_restore_locator(self):
        self.runtime.mode='timeout';record=self.run_helper()
        self.assertEqual(record['status'],'needs_inspection');self.assertTrue(record['command']['timeout'])
        self.assertTrue(record['after']['case_sensitive_directory']);self.assertEqual(self.runtime.calls,1)
        self.assertEqual(record['restore']['action'],'restore');self.assertFalse(record['automatic_restore_attempted'])
        self.assertFalse(record['automatic_retry_attempted'])
        self.assertTrue((self.records(record)/'intent.json').exists());self.assertTrue((self.records(record)/'result.json').exists())
    def test_post_snapshot_failure_still_records_exit_and_error(self):
        self.runtime.mode='post_snapshot';record=self.run_helper()
        self.assertEqual(record['status'],'needs_inspection');self.assertEqual(record['command']['exit'],0)
        self.assertIn('after_error',record);self.assertTrue((self.records(record)/'result.json').exists())
    def test_post_identity_drift_is_detected_after_attempt_not_atomic_claim(self):
        self.runtime.mode='case_drift';record=self.run_helper()
        self.assertEqual(record['status'],'needs_inspection');self.assertTrue(record['command_attempted'])
        self.assertIn('identity drift',record['error']['message'])
        self.assertFalse(record['identity_bound_during_fsutil'])
    def test_nonzero_command_no_retry(self):
        self.runtime.mode='nonzero';record=self.run_helper()
        self.assertEqual(record['status'],'needs_inspection');self.assertEqual(record['command']['exit'],5)
        self.assertEqual(self.runtime.calls,1)
    def test_final_receipt_failure_retains_lock_and_signals_failure(self):
        def writer(path,value):
            if path.name=='result.json':raise OSError('disk full')
            helper.persist(path,value)
        record=self.run_helper(writer=writer)
        self.assertEqual(record['status'],'evidence_failed');self.assertTrue(record['lock_retained'])
        self.assertTrue((self.root/'tmp/case-admin-v2.lock').exists())
    def test_existing_lock_never_stolen(self):
        lock=self.root/'tmp/case-admin-v2.lock';lock.mkdir();(lock/'unknown').write_bytes(b'keep')
        record=self.run_helper();self.assertEqual(record['status'],'refused');self.assertEqual(self.runtime.calls,0)
        self.assertEqual((lock/'unknown').read_bytes(),b'keep')
    def test_lock_drift_not_deleted(self):
        self.runtime.mode='lock_drift';record=self.run_helper()
        self.assertEqual(record['status'],'needs_inspection');self.assertIn('lock_cleanup_error',record)
        self.assertTrue((self.root/'tmp/case-admin-v2.lock').exists())
    def test_check_has_intent_and_result_without_fsutil(self):
        record=self.run_helper('check');self.assertEqual(record['status'],'succeeded');self.assertEqual(self.runtime.calls,0)
    def test_interrupted_command_retains_lock_and_intent(self):
        def interrupted(case,operation):
            self.runtime.calls+=1;self.runtime.flag=True
            raise KeyboardInterrupt('synthetic interrupt')
        self.runtime.command=interrupted;record=self.run_helper()
        self.assertTrue(record['interrupted']);self.assertTrue(record['lock_retained'])
        self.assertEqual(record['status'],'needs_inspection')
        self.assertTrue((self.records(record)/'result.json').exists())
        self.assertTrue((self.root/'tmp/case-admin-v2.lock').exists())
    def test_source_closure_hash_and_exact_set_required(self):
        import hashlib
        names=['scripts/agm_core/__init__.py','scripts/agm_core/paths.py','scripts/agm_core/platform_diagnostics.py','scripts/agm_core/windows_native.py']
        hashes={}
        for name in names:
            path=self.root/'code'/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(b'fixed source')
            hashes[name]=hashlib.sha256(path.read_bytes()).hexdigest()
        self.plan['sources']=hashes;helper.verify_source_closure(self.plan)
        (self.root/'code'/names[1]).write_bytes(b'drift')
        with self.assertRaises(helper.Refused):helper.verify_source_closure(self.plan)
        self.plan['sources']={}
        with self.assertRaises(helper.Refused):helper.verify_source_closure(self.plan)
    def test_partial_intent_write_failure_is_retained_and_never_runs_command(self):
        def writer(path,value):
            if path.name=='intent.json':
                path.write_text('{partial')
                raise OSError('fsync failed after partial write')
            helper.persist(path,value)
        record=self.run_helper(writer=writer)
        self.assertEqual(self.runtime.calls,0)
        self.assertEqual((self.records(record)/'intent.json').read_text(),'{partial')
        self.assertTrue((self.records(record)/'result.json').exists())

    def test_committed_owner_deleted_retains_lock(self):
        original=self.runtime.command
        def command(case,operation):
            result=original(case,operation)
            (self.root/'tmp/case-admin-v2.lock/owner.json').unlink()
            return result
        self.runtime.command=command;record=self.run_helper()
        self.assertEqual(record['status'],'needs_inspection')
        self.assertTrue((self.root/'tmp/case-admin-v2.lock').exists())
        self.assertIn('owner missing',record['lock_cleanup_error']['message'])
    def test_committed_owner_corrupted_retains_lock(self):
        original=self.runtime.command
        def command(case,operation):
            result=original(case,operation)
            (self.root/'tmp/case-admin-v2.lock/owner.json').write_text('{broken')
            return result
        self.runtime.command=command;record=self.run_helper()
        self.assertEqual(record['status'],'needs_inspection')
        self.assertTrue((self.root/'tmp/case-admin-v2.lock').exists())
    def test_committed_owner_same_bytes_replaced_retains_lock(self):
        original=self.runtime.command
        def command(case,operation):
            result=original(case,operation);owner=self.root/'tmp/case-admin-v2.lock/owner.json'
            replacement=owner.with_name('replacement');replacement.write_bytes(owner.read_bytes());replacement.replace(owner)
            return result
        self.runtime.command=command;record=self.run_helper()
        self.assertEqual(record['status'],'needs_inspection')
        self.assertTrue((self.root/'tmp/case-admin-v2.lock').exists())
    def test_completion_failure_after_release_is_not_reported_as_retained_lock(self):
        def writer(path,value):
            if path.name=='completion.json':raise OSError('completion disk failure')
            helper.persist(path,value)
        record=self.run_helper(writer=writer)
        self.assertEqual(record['status'],'needs_inspection')
        self.assertTrue(record['lock_released_before_cleanup_error'])
        self.assertFalse((self.root/'tmp/case-admin-v2.lock').exists())
        self.assertTrue((self.records(record)/'cleanup-error.json').exists())
