"""Exited-process recovery from the external single-file standard-library tool.

Installation detection is synthetic. These tests prove temporary-HOME process
and filesystem recovery, not a real host or new-session rule load.
"""
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'unit'))
import test_uninstall as fixtures
from agm_core import uninstall, uninstall_recovery as recovery

CHILD = '''import json,os,sys
sys.dont_write_bytecode=True
sys.path.insert(0,sys.argv[1])
from agm_core import uninstall
approval=json.load(open(sys.argv[2]))
def crash(event,index,change):
    if event=='after_write' and change['path']==sys.argv[5]:os._exit(86)
uninstall.execute(approval,home=sys.argv[3],backup_dir=sys.argv[4],hook=crash)
'''


class UninstallProcessTests(unittest.TestCase):
    def test_real_process_exit_and_external_resume_or_restore(self):
        for stage in ('native_first','native_last','delete_product'):
            for action in ('resume','restore'):
                with self.subTest(stage=stage,action=action):
                    fixture = fixtures.MultiAgentUninstallTests();fixture.setUp()
                    try:
                        before = recovery.tree(fixture.home)
                        plan = uninstall.preview(home=fixture.home,backup_dir=fixture.backup)
                        natives=[c for c in plan['changes'] if c['stage']=='detach' and c['path'] in plan['native_identities']]
                        skills=[c for c in plan['changes'] if c['stage']=='detach' and c['path'].endswith('/skills/mem-sharing/SKILL.md')]
                        roots=('.codex','.claude','.workbuddy','.dsh','.zcode','.config/opencode')
                        self.assertEqual({c['path'] for c in skills},
                            {str(fixture.home/root/'skills/mem-sharing/SKILL.md') for root in roots})
                        self.assertTrue(all(c['after']['kind']=='absent' for c in skills))
                        self.assertEqual(len(natives),6)
                        target=(natives[0] if stage=='native_first' else natives[-1]) if stage!='delete_product' else next(
                            c for c in plan['changes'] if c['stage']=='delete_product' and c['before']['kind']=='file')
                        approval_file = fixture.area/'approval.json'
                        approval_file.write_text(json.dumps(fixtures.approval(recovery.summary(plan))))
                        child = subprocess.run([sys.executable,'-B','-c',CHILD,
                            str(Path(__file__).resolve().parents[2]/'scripts'),str(approval_file),
                            str(fixture.home),str(fixture.backup),target['path']],capture_output=True,text=True,
                            env=dict(os.environ,HOME=str(fixture.home)),timeout=30)
                        self.assertEqual(child.returncode,86,child.stdout+child.stderr)
                        manifest = fixture.backup/'manifest.json'
                        runner = fixture.backup/'recover.py'
                        child = subprocess.run([sys.executable,'-B',str(runner),'--manifest',str(manifest),
                            '--action',action],capture_output=True,text=True,timeout=30)
                        self.assertEqual(child.returncode,5,child.stdout+child.stderr)
                        view = json.loads(child.stdout)
                        self.assertEqual(view['plan']['stale_locks'],[])
                        self.assertFalse(any(path.exists() for path in recovery.lock_paths(fixture.home)))
                        if stage=='native_first' and action=='resume':
                            # A real external writer and third-state user edit
                            # both stop the standalone recovery before mutation.
                            lock=fixture.home/'.mem-sharing-install.lock';lock.mkdir()
                            blocked_before=recovery.tree(fixture.home)
                            denied=subprocess.run([sys.executable,'-B',str(runner),'--manifest',str(manifest),
                                '--action',action],capture_output=True,text=True,timeout=30)
                            self.assertEqual(denied.returncode,2,denied.stdout+denied.stderr)
                            self.assertEqual(recovery.tree(fixture.home),blocked_before);lock.rmdir()
                            entry=Path(natives[0]['path']);prior=entry.read_bytes()
                            entry.write_bytes(prior+b'new private edit after process exit')
                            blocked_before=recovery.tree(fixture.home)
                            denied=subprocess.run([sys.executable,'-B',str(runner),'--manifest',str(manifest),
                                '--action',action],capture_output=True,text=True,timeout=30)
                            self.assertEqual(denied.returncode,2,denied.stdout+denied.stderr)
                            self.assertEqual(recovery.tree(fixture.home),blocked_before)
                            entry.write_bytes(prior)  # Fixture explicitly restores its injected edit.
                        approved = fixture.area/'recovery-approval.json'
                        approved.write_text(json.dumps(fixtures.approval(view['plan'])))
                        child = subprocess.run([sys.executable,'-B',str(runner),'--manifest',str(manifest),
                            '--action',action,'--approval-file',str(approved)],capture_output=True,text=True,timeout=30)
                        self.assertEqual(child.returncode,0,child.stdout+child.stderr)
                        if action=='restore':self.assertEqual(recovery.tree(fixture.home),before)
                        else:
                            self.assertFalse(fixture.runtime.root.exists())
                            for change in plan['changes']:
                                self.assertEqual(recovery.snapshot(change['path']),change['after'])
                    finally:fixture.doCleanups()
