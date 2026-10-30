"""Real child-process crashes and explicit exited-owner recovery, temporary HOME."""
import json
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'unit'))
from test_m404_install import InstallFixture, approved
from agm_core import user_install as install

CHILD = '''import json,os,sys
sys.dont_write_bytecode=True
sys.path.insert(0,sys.argv[1])
from agm_core import user_install,transaction
if sys.argv[3]=='entries_after_first_output':
    original_apply=transaction._apply
    def crashing_apply(path,snapshot,**kwargs):
        original_apply(path,snapshot,**kwargs)
        if str(path).endswith('/.codex/AGENTS.md'):os._exit(86)
    transaction._apply=crashing_apply
plan=json.load(open(sys.argv[2]))
approval=dict(plan,confirmed_at='2026-10-30T00:00:00Z',reference='explicit isolated process approval')
def hook(stage,path):
    if stage==sys.argv[3]:os._exit(86)
user_install.execute_install(plan,approval,hook=hook)
'''


class InstallProcessTests(InstallFixture):
    def record(self,value):
        value['run_id']=os.environ.get('M404_EVIDENCE_RUN','development')
        location=os.environ.get('M404_EVIDENCE_DIR')
        if location:
            with (Path(location)/'process-observations.jsonl').open('a') as stream:
                stream.write(json.dumps(value,ensure_ascii=False)+'\n')

    def crash(self,plan,event):
        path=self.area/'plan.json';path.write_text(json.dumps(plan))
        argv=[sys.executable,'-B','-c',CHILD,str(Path(__file__).resolve().parents[2]/'scripts'),str(path),event]
        child=subprocess.run(argv,capture_output=True,text=True,env=dict(os.environ,HOME=str(self.home)),timeout=30)
        self.record({'event':event,'argv':argv,'exit_code':child.returncode,'stdout':child.stdout,'stderr':child.stderr})
        self.assertEqual(child.returncode,86,child.stderr)

    def test_crashed_snapshot_move_outputs_and_commit_continue_or_rollback(self):
        for event in ('snapshot_complete','intent:snapshot_move','after_output','entries_after_first_output','after_entries','after_commit'):
            for action in ('continue','rollback'):
                with self.subTest(event=event,action=action):
                    fixture=InstallProcessTests();fixture.setUp()
                    try:
                        before=fixture.v0();fixture.codex();plan=fixture.plan()
                        fixture.crash(plan,event)
                        self.assertEqual(install.inspect_machine(fixture.request)['scene'],'interrupted')
                        recovery=install.plan_recovery(plan['journal'],action=action)
                        self.assertEqual(len(recovery['stale_locks']),3)
                        result=install.recover_install(recovery,approved(recovery),request=fixture.request)
                        fixture.record({'event':event,'action':action,'recovery_plan':recovery,'result':result})
                        self.assertEqual(result['status'],'completed' if action=='continue' else 'rolled_back')
                        if action=='continue':self.assertEqual(install.inspect_machine(fixture.request)['scene'],'same')
                        else:
                            self.assertFalse(fixture.runtime.registry.exists())
                            # §23:v0 源在历史位置,rollback 后整体原样;R 侧复制产物
                            # (新索引)已回退,v0 归档证据按 metadata_scopes 设计保留。
                            for rel,raw in before.items():self.assertEqual((fixture.runtime.legacy_root/rel).read_bytes(),raw)
                            self.assertFalse((fixture.runtime.root/'memories/MEMORY.md').exists())
                    finally:fixture.doCleanups()

    def test_fixed_toolkit_can_finish_after_commit_without_original_source(self):
        self.v0();plan=self.plan();self.crash(plan,'after_commit')
        import shutil
        shutil.rmtree(self.source)
        recovery=install.plan_recovery(plan['journal'],action='continue')
        path=self.area/'recovery.json';path.write_text(json.dumps(approved(recovery)))
        script='''import json,sys
sys.dont_write_bytecode=True
sys.path.insert(0,sys.argv[1])
from agm_core import user_install
approval=json.load(open(sys.argv[2]));plan={k:v for k,v in approval.items() if k not in ('confirmed_at','reference')}
print(json.dumps(user_install.recover_install(plan,approval)))
'''
        argv=[sys.executable,'-B','-c',script,str(Path(plan['bootstrap'])/'tools'),str(path)]
        child=subprocess.run(argv,capture_output=True,text=True,env=dict(os.environ,HOME=str(self.home)),timeout=30)
        self.record({'event':'toolkit_finalize','argv':argv,'exit_code':child.returncode,'stdout':child.stdout,'stderr':child.stderr})
        self.assertEqual(child.returncode,0,child.stderr)
        self.assertTrue(json.loads(child.stdout)['finalized_only'])
