"""Approved recovery wraps the original Transaction journal, synthetic HOME."""
import copy
import subprocess
import io
import json
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'scripts'))
sys.path.insert(0,str(Path(__file__).resolve().parent))
from agm_core import fusion_recovery as recovery
from agm_core.transaction import TransactionError
import test_memory_fusion as fixture_module

class RecoveryTests(unittest.TestCase):
    def setUp(self):
        self.fixture=fixture_module.FusionTests('runTest');self.fixture.setUp();self.addCleanup(self.fixture.doCleanups)
        f=self.fixture
        self.before=[p.read_bytes() for p in f.files]
        def fail(event,path):
            if event=='after_write' and path in f.files:raise TransactionError('interrupted')
            if event=='before_restore':raise TransactionError('restore unavailable')
        result=f.execute(f.plan(),fail)
        self.assertEqual(result['status'],'recovery_required',result)
        self.manifest=next(f.rt.backups.glob('*/manifest.json'))
        self.req={'home':str(f.home),'manifest':str(self.manifest)}

    def approval(self,plan):
        return dict(plan,confirmed_at='2026-11-03T07:00:00Z',reference='synthetic final recovery confirmation')

    def test_readonly_preview_exact_confirmation_and_existing_recovery(self):
        f=self.fixture; state=f.snapshot() if hasattr(f,'snapshot') else [p.read_bytes() for p in f.files]
        r=recovery.run(self.req);self.assertEqual(r['status'],'approval_required',r)
        self.assertEqual([p.read_bytes() for p in f.files],state)
        a=self.approval(r['approval_plan']);a['action']='other'
        self.assertEqual(recovery.run(dict(self.req,approval=a))['status'],'recovery_required')
        done=recovery.run(dict(self.req,approval=self.approval(r['approval_plan'])))
        self.assertEqual(done['status'],'completed',done);self.assertEqual(done['recovery_status'],'rolled_back')
        self.assertEqual([p.read_bytes() for p in f.files],self.before)

    def test_cli_preview_approval_and_backup_drift_zero_restore(self):
        import agm
        out=io.StringIO()
        rc=agm.main(['recover-memory-fusion','--manifest',str(self.manifest)],home=str(self.fixture.home),stdout=out,stderr=io.StringIO())
        self.assertEqual(rc,5,out.getvalue())
        plan=json.loads(out.getvalue())['approval_plan']
        approval=self.approval(plan)
        file=self.fixture.home/'approval.json';file.write_text(json.dumps(approval))
        backup=next(self.manifest.parent.glob('*.before'));backup.write_bytes(backup.read_bytes()+b'foreign')
        before=[p.read_bytes() for p in self.fixture.files]
        out=io.StringIO()
        rc=agm.main(['recover-memory-fusion','--manifest',str(self.manifest),'--approval-file',str(file)],home=str(self.fixture.home),stdout=out,stderr=io.StringIO())
        self.assertEqual(rc,2,out.getvalue());self.assertEqual([p.read_bytes() for p in self.fixture.files],before)

    def test_true_process_exit_keeps_manifest_and_cli_restores_after_stale_lock_review(self):
        f=fixture_module.FusionTests('runTest');f.setUp();self.addCleanup(f.doCleanups)
        before=[p.read_bytes() for p in f.files]
        p=f.plan(); approval=f.approve(p)
        plan_file=f.home/'plan.json';plan_file.write_text(json.dumps({'plan':p,'approval':approval}))
        code="""
import sys,os,json
from pathlib import Path
sys.path.insert(0,sys.argv[1])
from agm_core import user_rules_organize as org
x=json.loads(Path(sys.argv[2]).read_text()); p=x['plan']
org._participants=lambda *a:(p['agents'],p['agent_facts'])
org.user_entries.connection_status=lambda *a:{k:{'status':'connected'} for k in p['agents']}
def crash(event,path):
 if event=='after_write' and str(path) not in p['public_paths']:os._exit(73)
org.execute_organize(p,x['approval'],hook=crash)
"""
        done=subprocess.run([sys.executable,'-B','-c',code,str(Path(__file__).resolve().parents[2]/'scripts'),str(plan_file)],capture_output=True)
        self.assertEqual(done.returncode,73,done.stderr.decode())
        manifest=next(f.rt.backups.glob('*/manifest.json'))
        req={'home':str(f.home),'manifest':str(manifest)}
        preview=recovery.run(req); self.assertEqual(preview['status'],'approval_required',preview)
        blocked=recovery.run(dict(req,approval=self.approval(preview['approval_plan'])))
        self.assertEqual(blocked['status'],'recovery_required');self.assertTrue(f.rt.lock.exists())
        # Confirmed dead subprocess, and only its synthetic fixture locks removed.
        f.rt.transaction_lock.rmdir();f.rt.lock.rmdir()
        self.assertEqual(fixture_module.org.plan_organize(f.req)['status'],'failed')
        preview=recovery.run(req)
        done=recovery.run(dict(req,approval=self.approval(preview['approval_plan'])))
        self.assertEqual(done['status'],'completed',done)
        self.assertEqual([p.read_bytes() for p in f.files],before)

    def test_source_drift_stops_restore_and_stale_lock_not_stolen(self):
        r=recovery.run(self.req)
        self.fixture.files[0].write_bytes(b'foreign edit')
        done=recovery.run(dict(self.req,approval=self.approval(r['approval_plan'])))
        self.assertEqual(done['status'],'recovery_required');self.assertEqual(self.fixture.files[0].read_bytes(),b'foreign edit')

if __name__=='__main__':unittest.main()
