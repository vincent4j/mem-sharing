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
        self.assertEqual(result['versions'],{'schema_version':3,'product_structure_version':1,'product_code_version':'0.4.0'})
        self.assertEqual(list(self.home.rglob('__pycache__')),[])
        self.assertEqual(list(self.source.rglob('__pycache__')),[])
        installed=Path(result['layout']['code'])
        help_result=subprocess.run([sys.executable,'-B',str(installed/'scripts/install.py'),'--help'],
                                   cwd=self.cwd,env=self.env,capture_output=True,text=True)
        self.assertEqual(help_result.returncode,0);self.assertIn('--recover',help_result.stdout)
        before=self.snapshot()
        code,again=self.run_cli('--source',str(self.source),'--commit',self.commit,'--version','0.4.0')
        self.assertEqual(code,0,again);self.assertIsNone(again['approval_plan'])
        self.assertFalse(again['approval_required']);self.assertEqual(again['changes'],[])
        self.assertIsNone(again['fusion'])
        code,noop=self.run_cli('--source',str(self.source),'--commit',self.commit,'--version','0.4.0')
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
        for args in (['check-memory','--all'],['enable-memory','--project',str(self.cwd)]):
            proc=subprocess.run([sys.executable,'-B',str(self.source/'scripts/agm.py'),*args],
                                cwd=self.cwd,env=self.env,capture_output=True,text=True)
            report=json.loads(proc.stdout)
            self.assertIn('scripts/install.py',report['next_action'],report)
            self.assertEqual(before,self.snapshot());self.assertFalse((self.home/'.mem-sharing').exists())

    def test_context_keeper_route_is_independent_and_uses_synthetic_pinned_source(self):
        sys.path.insert(0,str(REPO/'tests/unit'))
        from test_ck_install import UPSTREAM
        package=self.area/'codex-fixture';(package/'bin').mkdir(parents=True)
        exe=package/'bin/codex';exe.write_text('#!/bin/sh\n');exe.chmod(0o755)
        (package/'package.json').write_text(json.dumps({'name':'@openai/codex','version':'1.0','bin':{'codex':'bin/codex'}}))
        self.env['PATH']=str(package/'bin')+':'+self.env['PATH']
        # Hermetic detection: real /Applications (e.g. a host-installed WorkBuddy.app)
        # must not leak into connected; empty app_directories scopes detection to PATH.
        request_file=self.area/'ck-route-request.json'
        request_file.write_text(json.dumps({'app_directories':[]}))
        code,preview=self.run_cli('--request-file',str(request_file),
                                  '--source',str(self.source),'--commit',self.commit,'--version','0.4.0')
        self.assertEqual(code,5,preview)
        code,main=self.run_cli('--approval-file',self.approve(preview['approval_plan']))
        self.assertEqual(code,0,main)
        self.assertEqual(main['context_keeper']['status'],'skipped')
        self.assertEqual(main['agents']['connected'],['codex'])
        ck=self.area/'CK fixture';(ck/'scripts').mkdir(parents=True)
        (ck/'SKILL.md').write_text('name: context-keeper\n')
        (ck/'scripts/install.py').write_text(UPSTREAM)
        def git(*args):
            return subprocess.run(['git','-C',str(ck),*args],env=self.env,capture_output=True,text=True,check=True).stdout.strip()
        git('init');git('add','SKILL.md','scripts/install.py')
        git('-c','user.name=fixture','-c','user.email=fixture@example.invalid','commit','-m','isolated CK fixture')
        pin=git('rev-parse','HEAD')
        # Test-only subprocess shim: pin and durable-location check are replaced
        # for the synthetic temp checkout, without production override flags.
        shim=self.area/'ck-cli-fixture.py'
        shim.write_text('import sys\nsys.path.insert(0,'+repr(str(self.source/'scripts'))+')\n'
            'import install\ninstall.ck_install.PIN='+repr(pin)+'\n'
            'install.ck_install._durable_source=lambda *a:None\n'
            'raise SystemExit(install.main(sys.argv[1:]))\n')
        self.cli=shim
        before=self.snapshot()
        for args in (['--context-keeper','--acquire'],['--context-keeper','--recover','/x','--action','continue'],
                     ['--context-keeper','--version','0.4.0'],['--ck-source',str(ck)]):
            code,bad=self.run_cli(*args);self.assertEqual(code,2,bad)
            self.assertEqual(before,self.snapshot())
        code,preview=self.run_cli('--context-keeper','--ck-source',str(ck))
        self.assertEqual(code,5,preview);self.assertEqual(before,self.snapshot())
        plan=preview['approval_plan'];self.assertEqual(plan['command'],'install-context-keeper')
        self.assertEqual(plan['main_operation_id'],main['operation_id'])
        self.assertEqual(plan['agents'],['codex']);self.assertEqual(plan['source']['commit'],pin)
        code,result=self.run_cli('--context-keeper','--approval-file',self.approve(plan))
        self.assertEqual(code,0,result);self.assertEqual(result['status'],'configured')
        self.assertEqual(result['runtime_acceptance'],'pending')
        self.assertTrue((self.home/'.codex/skills/context-keeper').is_symlink())
        self.assertTrue(Path(result['journal']).is_file())

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
