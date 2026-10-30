"""Cold CLI subprocesses from non-Git cwd. All writes/commits use temporary fixtures."""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO=Path(__file__).resolve().parents[2]


class InstallerCLITests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.area=Path(self.tmp.name).resolve();self.home=self.area/'home';self.home.mkdir()
        self.cwd=self.area/'not-a-project';self.cwd.mkdir()
        self.source=self.area/'verified source';(self.source/'scripts/agm_core').mkdir(parents=True)
        for path in [REPO/'SKILL.md',REPO/'scripts/agents.json',*sorted((REPO/'scripts').glob('*.py')),
                     *sorted((REPO/'scripts/agm_core').glob('*.py'))]:
            target=self.source/path.relative_to(REPO);target.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(path,target)
        self.env=dict(os.environ,HOME=str(self.home),PATH='/usr/bin:/bin:/usr/sbin:/sbin',PYTHONDONTWRITEBYTECODE='1')
        self.git('init');self.git('add','SKILL.md','scripts')
        self.git('-c','user.name=fixture','-c','user.email=fixture@example.invalid','commit','-m','isolated installer snapshot')
        self.commit=self.git('rev-parse','HEAD')
        self.cli=self.source/'scripts/install.py'

    def git(self,*args):
        return subprocess.run(['git','-C',str(self.source),*args],env=self.env,capture_output=True,text=True,check=True).stdout.strip()

    def run_cli(self,*args):
        proc=subprocess.run([sys.executable,'-B',str(self.cli),*args],cwd=self.cwd,env=self.env,
                            capture_output=True,text=True)
        self.assertFalse(proc.stderr,proc.stderr)
        return proc.returncode,json.loads(proc.stdout)

    def approve(self,plan):
        path=self.area/'approved.json'
        path.write_text(json.dumps(dict(plan,confirmed_at='2026-10-30T00:00:00Z',reference='isolated fixture explicit confirmation')))
        return str(path)

    def snapshot(self):
        return {str(p.relative_to(self.home)):(p.lstat().st_mode,p.lstat().st_mtime_ns,
                os.readlink(p) if p.is_symlink() else p.read_bytes() if p.is_file() else None)
                for p in [self.home,*self.home.rglob('*')]}

    def test_non_git_blank_environment_full_workflow_and_same_release(self):
        before=self.snapshot()
        code,preview=self.run_cli('--source',str(self.source),'--commit',self.commit,'--version','0.4.0',
                                  '--project',str(self.cwd))
        self.assertEqual(code,5,preview);self.assertEqual(before,self.snapshot())
        plan=preview['approval_plan'];self.assertEqual(plan['source']['commit'],self.commit)
        code,result=self.run_cli('--approval-file',self.approve(plan),'--project',str(self.cwd))
        self.assertEqual(code,0,result);self.assertEqual(result['status'],'completed')
        self.assertIn(str(self.cwd),result['project_commands'][0]);self.assertFalse(result['project_root_required'])
        self.assertEqual(result['versions'],{'schema_version':2,'product_structure_version':1,'product_code_version':'0.4.0'})
        self.assertEqual(list(self.home.rglob('__pycache__')),[])
        self.assertEqual(list(self.source.rglob('__pycache__')),[])
        installed=Path(result['layout']['code'])
        help_result=subprocess.run([sys.executable,'-B',str(installed/'scripts/install.py'),'--help'],
                                   cwd=self.cwd,env=self.env,capture_output=True,text=True)
        self.assertEqual(help_result.returncode,0);self.assertIn('--recover',help_result.stdout)
        before=self.snapshot()
        code,again=self.run_cli('--source',str(self.source),'--commit',self.commit,'--version','0.4.0')
        self.assertEqual(code,5,again);self.assertTrue(again['approval_plan']['plan']['noop'])
        self.assertEqual(again['approval_plan']['changes'],[])
        code,noop=self.run_cli('--approval-file',self.approve(again['approval_plan']))
        self.assertEqual(code,0,noop);self.assertEqual(before,self.snapshot())
        print('M408 COLD',self.commit,'non_git_cwd completed; same_release zero_writes_mtimes; runtime pending')

    def test_help_import_and_invalid_cli_do_not_create_home_or_caches(self):
        before=self.snapshot()
        proc=subprocess.run([sys.executable,'-B',str(self.cli),'--help'],cwd=self.cwd,env=self.env,capture_output=True,text=True)
        self.assertEqual(proc.returncode,0)
        code,result=self.run_cli('--unknown');self.assertEqual(code,2,result)
        code,result=self.run_cli('--version','0.4.0','--commit','f'*40)
        self.assertEqual(code,2,result);self.assertEqual(result['errors'][0]['code'],'source_drift')
        self.assertEqual(before,self.snapshot());self.assertEqual(list(self.source.rglob('__pycache__')),[])

    def test_three_project_commands_missing_product_guide_only_no_implicit_install(self):
        before=self.snapshot()
        for args in (['check-memory','--all'],['remove-memory','--project',str(self.cwd)],
                     ['enable-memory','--project',str(self.cwd),'--memory']):
            proc=subprocess.run([sys.executable,'-B',str(self.source/'scripts/agm.py'),*args],
                                cwd=self.cwd,env=self.env,capture_output=True,text=True)
            report=json.loads(proc.stdout)
            self.assertIn('scripts/install.py',report['next_action'],report)
            self.assertEqual(before,self.snapshot());self.assertFalse((self.home/'.mem-sharing').exists())

    def test_acquisition_is_separate_approved_and_pinned_using_local_git_transport(self):
        # The product transport is fixed to OFFICIAL. Only this child process gets
        # a Git URL rewrite to the isolated fixture; no external network request.
        config=self.area/'git-fixture.config'
        config.write_text('[url "'+str(self.source)+'"]\n\tinsteadOf = https://github.com/vincent4j/mem-sharing\n')
        self.env['GIT_CONFIG_GLOBAL']=str(config);self.env['GIT_CONFIG_NOSYSTEM']='1'
        stage=self.area/'approved stage'
        code,preview=self.run_cli('--acquire','--commit',self.commit,'--version','0.4.0','--staging',str(stage))
        self.assertEqual(code,5,preview);self.assertFalse(stage.exists())
        code,result=self.run_cli('--acquire','--commit',self.commit,'--version','0.4.0','--staging',str(stage),
                                 '--approval-file',self.approve(preview['approval_plan']))
        self.assertEqual(code,0,result);self.assertEqual(result['status'],'acquired')
        self.assertFalse(result['installation_complete']);self.assertEqual(list(self.home.iterdir()),[])
        self.assertEqual(result['source']['commit'],self.commit)
        journal=json.loads((stage/'acquisition.json').read_bytes());self.assertEqual(journal['status'],'acquired')
        code,plan=self.run_cli('--source',str(stage/'checkout'),'--commit',self.commit,'--version','0.4.0')
        self.assertEqual(code,5,plan);self.assertEqual(list(self.home.iterdir()),[])
        code,done=self.run_cli('--approval-file',self.approve(plan['approval_plan']))
        self.assertEqual(code,0,done);self.assertEqual(done['status'],'completed')
        print('M408 ACQUIRE',self.commit,'local transport acquired; separate read_only plan; installation completed')
