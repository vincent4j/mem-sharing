"""One-journal dependency cycles; synthetic projects and real process interruption."""
import json
import subprocess
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'scripts'))
sys.path.insert(0,str(Path(__file__).resolve().parent))
import test_memory_fusion as fixture_module
from agm_core import user_rules_organize as org, fusion_recovery
from agm_core.transaction import Transaction, Change, TransactionError, read_snapshot

class PhaseTests(unittest.TestCase):
    def setUp(self):
        f=fixture_module.FusionTests('runTest');f.setUp();self.addCleanup(f.doCleanups);self.f=f
        self.root=f.home/'project';self.root.mkdir();subprocess.run(['git','init','-q',str(self.root)],check=True)
        self.public=self.root/'AGENTS.md';self.claude=self.root/'CLAUDE.md'
        self.wb=self.root/'.workbuddy/memory/MEMORY.md';self.wb.parent.mkdir(parents=True)
        self.public.write_text('# 约定\n- 保留本机。\n- 原公共。\n')
        self.claude.write_text('@AGENTS.md\n\n# 约定\n- 新共享内容。\n- 原公共。\n- 本机独有。\n')
        self.wb.write_text('<!-- mem-sharing:project-rules:start -->\n读取 AGENTS.md\n<!-- mem-sharing:project-rules:end -->\n\n# 约定\n- 新共享内容。\n- 原公共。\n')
        self.files=[self.public,self.claude,self.wb]
        self.before={str(p):p.read_bytes() for p in self.files}
        req=dict(f.req,scope='project',project=str(self.root))
        initial=org.plan_organize(req)['approval_plan']
        keep=next(g['number'] for g in initial['groups'] if '保留本机' in g['summary'])
        shared=next(g['number'] for g in initial['groups'] if '新共享内容' in g['summary'])
        self.req=dict(req,selection=f'共享 {shared}，不共享 {keep}',retentions={str(keep):'CLAUDE.md'})
        result=org.plan_organize(self.req);self.assertEqual(result['status'],'approval_required',result)
        self.plan=result['approval_plan'];self.assertTrue(self.plan['phased_writes'])

    def approve(self,p):return self.f.approve(p)

    def test_success_full_copy_before_each_delete_and_final_contents(self):
        stages=[]
        def check(event,path):
            if event=='before_write':
                step=self.plan['steps'][len(stages)]
                if step['stage']=='native_commit':
                    self.assertIn('保留本机',self.public.read_text())
                    self.assertIn('新共享内容',self.public.read_text())
                elif step['stage']=='public_remove':self.assertIn('保留本机',self.claude.read_text())
            if event=='after_write':stages.append(str(path))
        result=org.execute_organize(self.plan,self.approve(self.plan),hook=check)
        self.assertEqual(result['status'],'completed',result)
        self.assertNotIn('保留本机',self.public.read_text());self.assertIn('新共享内容',self.public.read_text())
        self.assertIn('保留本机',self.claude.read_text());self.assertIn('本机独有',self.claude.read_text())
        for p in (self.claude,self.wb):
            self.assertNotIn('新共享内容',p.read_text());self.assertNotIn('原公共',p.read_text())
        manifest=json.loads(Path(result['manifest']).read_text())
        self.assertTrue(manifest['phased_writes']);self.assertEqual(manifest['status'],'committed')
        self.assertEqual(sum(e['path']==str(self.public) for e in manifest['entries']),2)

    def test_exception_after_every_step_rolls_back_all_original_bytes(self):
        for fail_at in range(len(self.plan['steps'])):
            with self.subTest(step=fail_at):
                seen=[]
                def fail(event,path):
                    if event=='after_write':
                        seen.append(path)
                        if len(seen)==fail_at+1:raise TransactionError('synthetic phase failure')
                result=org.execute_organize(self.plan,self.approve(self.plan),hook=fail)
                self.assertEqual(result['status'],'failed',result)
                self.assertEqual({str(p):p.read_bytes() for p in self.files},self.before)

    def test_hard_exit_each_stage_same_manifest_restores_initial_bytes(self):
        planfile=self.f.home/'phase-plan.json'
        planfile.write_text(json.dumps({'plan':self.plan,'approval':self.approve(self.plan)}))
        code="""
import json,sys,os
from pathlib import Path
sys.path.insert(0,sys.argv[1])
from agm_core import user_rules_organize as org
x=json.loads(Path(sys.argv[2]).read_text());p=x['plan']
org._participants=lambda *a:(p['agents'],p['agent_facts'])
n=[]
def crash(event,path):
 if event=='after_write':
  n.append(path)
  if len(n)==int(sys.argv[3]):os._exit(73)
org.execute_organize(p,x['approval'],hook=crash)
"""
        for fail_at in range(1,len(self.plan['steps'])+1):
            with self.subTest(step=fail_at):
                prior=set(self.f.rt.backups.glob('*/manifest.json'))
                run=subprocess.run([sys.executable,'-B','-c',code,str(Path(__file__).resolve().parents[2]/'scripts'),str(planfile),str(fail_at)],capture_output=True)
                self.assertEqual(run.returncode,73,run.stderr.decode())
                manifest=(set(self.f.rt.backups.glob('*/manifest.json'))-prior).pop()
                request={'home':str(self.f.home),'manifest':str(manifest),'project':str(self.root)}
                preview=fusion_recovery.run(request);self.assertEqual(preview['status'],'approval_required',preview)
                blocked=fusion_recovery.run(dict(request,approval=self.approve(preview['approval_plan'])))
                self.assertEqual(blocked['status'],'recovery_required')
                # Confirmed dead fixture subprocess only. Never remove real locks.
                self.f.rt.transaction_lock.rmdir();self.f.rt.lock.rmdir()
                preview=fusion_recovery.run(request)
                done=fusion_recovery.run(dict(request,approval=self.approve(preview['approval_plan'])))
                self.assertEqual(done['status'],'completed',done)
                self.assertEqual({str(p):p.read_bytes() for p in self.files},self.before)

    def test_foreign_edit_between_phases_is_preserved_and_recovery_refuses(self):
        altered=[]
        def foreign(event,path):
            if event=='after_write' and path==self.public and not altered:
                altered.append(True);self.claude.write_bytes(self.claude.read_bytes()+b'foreign edit')
        result=org.execute_organize(self.plan,self.approve(self.plan),hook=foreign)
        self.assertEqual(result['status'],'failed',result)
        self.assertTrue(self.claude.read_bytes().endswith(b'foreign edit'))
        self.assertEqual(self.public.read_bytes(),self.before[str(self.public)])

    def test_broken_intermediate_chain_rejected_before_any_restore(self):
        seen=[]
        def fail(event,path):
            if event=='after_write':
                seen.append(path)
                if len(seen)==1:raise TransactionError('interrupted first stage')
            if event=='before_restore':raise TransactionError('restore unavailable')
        result=org.execute_organize(self.plan,self.approve(self.plan),hook=fail)
        self.assertEqual(result['status'],'recovery_required',result)
        manifest=next(self.f.rt.backups.glob('*/manifest.json'));data=json.loads(manifest.read_text())
        last=data['entries'][-1]
        backup=manifest.parent/last['before']['backup'];backup.write_bytes(self.before[str(self.public)])
        from agm_core import entries
        last['before']['fingerprint']=entries.sha256(backup.read_bytes())
        manifest.write_text(json.dumps(data))
        before={str(p):p.read_bytes() for p in self.files}
        request={'home':str(self.f.home),'project':str(self.root),'manifest':str(manifest)}
        self.assertEqual(fusion_recovery.run(request)['status'],'recovery_required')
        self.assertEqual({str(p):p.read_bytes() for p in self.files},before)

    def test_foreign_write_after_source_delete_is_not_overwritten_by_rollback_or_recovery(self):
        altered=[]
        def foreign(event,path):
            if event=='after_write' and path==self.claude and not altered:
                altered.append(True);self.claude.write_bytes(self.claude.read_bytes()+b'foreign edit')
        result=org.execute_organize(self.plan,self.approve(self.plan),hook=foreign)
        self.assertEqual(result['status'],'recovery_required',result)
        self.assertTrue(self.claude.read_bytes().endswith(b'foreign edit'))
        manifest=next(self.f.rt.backups.glob('*/manifest.json'))
        request={'home':str(self.f.home),'project':str(self.root),'manifest':str(manifest)}
        before={str(p):p.read_bytes() for p in self.files}
        self.assertEqual(fusion_recovery.run(request)['status'],'recovery_required')
        self.assertEqual({str(p):p.read_bytes() for p in self.files},before)

    def test_duplicate_path_still_rejected_without_explicit_fusion_opt_in(self):
        p=self.claude;snap=read_snapshot(p)
        first=Change.file(p,snap.data+b'x',expected=snap)
        second=Change.file(p,snap.data+b'y',expected=first.after)
        tx=Transaction(lock_path=self.f.rt.lock,backup_root=self.f.rt.backups,allowed_roots=[self.f.home])
        with self.assertRaises(TransactionError):tx.run([first,second])
        self.assertEqual(p.read_bytes(),snap.data)

if __name__=='__main__':unittest.main()
