"""Frozen synthetic schema 3 T0 -> T1 Git releases in a synthetic HOME.

The pair exercises the formal release contract; neither snapshot is a published
release or a promise to migrate development installations.
"""
import copy
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(REPO/'scripts'))
sys.path.insert(0,str(REPO/'tests/unit'))
from agm_core import upgrade, user_install as install, registry, legacy_import as legacy, paths, versions, enable, user_entries
from test_m404_install import approved
from runtime_fixture import seed_project_executors




def git(*args,cwd):
    return subprocess.run(['git','-C',str(cwd),*args],check=True,capture_output=True,text=True,
        env=dict(os.environ,GIT_AUTHOR_DATE='2026-10-30T00:00:00Z',GIT_COMMITTER_DATE='2026-10-30T00:00:00Z')).stdout.strip()


def source(root,version):
    names=git('ls-tree','-r','--name-only','HEAD','--','scripts','SKILL.md',cwd=root).splitlines()
    return {'root':str(root),'version':version,'url':'fixture://agent-group-memory-development',
            'commit':git('rev-parse','HEAD',cwd=root),
            'files':{name:legacy.digest((root/name).read_bytes()) for name in names}}


class RealUpgradeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bundle=tempfile.TemporaryDirectory();cls.base=Path(cls.bundle.name).resolve()
        cls.p=cls.base/'T0';cls.t=cls.base/'T1';cls.p.mkdir()
        for original in [REPO/'SKILL.md',*(REPO/'scripts').rglob('*.py'),REPO/'scripts/agents.json']:
            rel=original.relative_to(REPO)
            if str(rel).startswith(('scripts/backups/', 'scripts/.agm.lock/')): continue
            target=cls.p/rel;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(original,target)
        git('init','--quiet',cwd=cls.p)
        git('add','--','scripts','SKILL.md',cwd=cls.p)
        git('-c','user.name=AGM isolated fixture','-c','user.email=fixture@invalid',
            '-c','commit.gpgsign=false','commit','--quiet','-m','Frozen synthetic formal T0 schema3',cwd=cls.p)
        subprocess.run(['git','clone','--quiet','--no-hardlinks',str(cls.p),str(cls.t)],check=True,capture_output=True)
        for name in ('upgrade.py','versions.py','user_install.py'):
            target=cls.t/'scripts/agm_core'/name
            target.write_bytes(target.read_bytes()+b'\n# Synthetic T1 release revision.\n')
        git('add','--','scripts','SKILL.md',cwd=cls.t)
        git('-c','user.name=AGM isolated fixture','-c','user.email=fixture@invalid',
            '-c','commit.gpgsign=false','commit','--quiet','-m','Frozen synthetic formal T1 schema3',cwd=cls.t)
        cls.p_source=source(cls.p,'0.4.0');cls.t_source=source(cls.t,'0.4.1')
        cls.parent=git('rev-parse','HEAD^',cwd=cls.t)
        cls.changed=git('diff','--name-only',cls.parent,'HEAD',cwd=cls.t).splitlines()
        export=os.environ.get('AGM_M407_EXPORT')
        if export:
            output=Path(export);output.mkdir(parents=True,exist_ok=True)
            git('bundle','create',str(output/'T.bundle'),'HEAD','^'+cls.parent,cwd=cls.t)
            for name,checkout in [('P',cls.p),('T',cls.t)]:
                subprocess.run(['git','-C',str(checkout),'-c','tar.umask=0022','archive','--format=tar','--output='+str(output/(name+'.tar')),'HEAD','scripts','SKILL.md'],check=True,capture_output=True)
            metadata={name:{k:v for k,v in package.items() if k!='root'} for name,package in [('P',cls.p_source),('T',cls.t_source)]}
            metadata.update(T_parent=cls.parent,changed_files=cls.changed)
            (output/'releases.json').write_text(json.dumps(metadata,indent=2)+'\n')
        if cls.parent!=cls.p_source['commit']:raise AssertionError('T must be a real child of P')
        if not {'scripts/agm_core/upgrade.py','scripts/agm_core/versions.py'}<=set(cls.changed):
            raise AssertionError('T must include actual executable implementation changes')

    @classmethod
    def tearDownClass(cls):cls.bundle.cleanup()

    def seed_codex(self):
        package=self.area/'npm';(package/'bin').mkdir(parents=True)
        exe=package/'bin/codex';exe.write_text('#!/bin/sh\n');exe.chmod(0o755)
        (package/'package.json').write_text(json.dumps({'name':'@openai/codex','version':'1.0','bin':{'codex':'bin/codex'}}))
        self.codex_bin=str(package/'bin');return self.codex_bin

    def setUp(self,codex=False):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.area=Path(self.temp.name).resolve();self.home=self.area/'home';self.home.mkdir()
        self.config=paths.select_platform(paths.load_agents_table(),'darwin')
        self.request={'home':str(self.home),'platform_config':self.config,'agents':None,'search_paths':[],
                      'app_directories':[],'operation_id':'actual-p-install','source':copy.deepcopy(self.p_source)}
        p_request=dict(self.request,search_paths=[self.seed_codex()] if codex else [])
        request_file=self.area/'p-request.json';request_file.write_text(json.dumps(p_request))
        program='''import json,sys
sys.path.insert(0,sys.argv[1]+"/scripts")
from agm_core import user_install
request=json.load(open(sys.argv[2]));plan=user_install.plan_install(request)
result=user_install.execute_install(plan,dict(plan,confirmed_at="2026-10-30T00:00:00Z",reference="real P self-install"),request=request)
print(json.dumps(result))
'''
        result=subprocess.run([sys.executable,'-B','-c',program,str(self.p),str(request_file)],
            env=dict(os.environ,HOME=str(self.home),PYTHONDONTWRITEBYTECODE='1'),capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr)
        self.runtime=install._runtime(self.request)
        self.assertTrue(versions.root(self.runtime).exists())
        before=json.loads(self.runtime.registry.read_bytes())['product']
        target,_=install._source({'source':self.t_source})
        self.conversion={'before':{'schema_version':3,'product_structure_version':1,
            'product_code_version':before['product_code_version'],'source':before['source']},
            'after':{'schema_version':3,'product_structure_version':1,'product_code_version':'0.4.1',
            'source':{k:target[k] for k in ('url','commit','tree_sha256')}},'direction':'upgrade','entries':'preserve'}
        self.request.update(source=copy.deepcopy(self.t_source),operation_id='actual-p-to-t',conversions=[self.conversion])
        for name in ('memories/user.bin','references/user.bin','skills/other/user.bin','mcp/user.bin'):
            target=self.runtime.root/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(b'user bytes\x00\xff\r\n')
        self.user_before={name:(self.runtime.root/name).read_bytes() for name in ('memories/user.bin','references/user.bin','skills/other/user.bin','mcp/user.bin')}

    def command(self,*args):
        return subprocess.run([sys.executable,'-B',str(self.runtime.code/'scripts/agm.py'),*args],
            env=dict(os.environ,HOME=str(self.home),PYTHONDONTWRITEBYTECODE='1'),capture_output=True,text=True)

    def plan(self):return upgrade.plan_upgrade(self.request)
    def apply(self,plan=None,hook=None):
        plan=plan or self.plan()
        return upgrade.execute_upgrade(plan,approved(plan),request=self.request,hook=hook)
    def snapshot(self):
        return {str(p.relative_to(self.home)):(p.lstat().st_mode,p.lstat().st_mtime_ns,p.read_bytes() if p.is_file() else None)
                for p in [self.home,*self.home.rglob('*')] if not p.is_symlink()}

    def verify(self,version):
        allowed=paths.allowed_user_paths(self.request['platform_config'],None,home=str(self.home))
        data=registry.require_installed(registry.load_registry(self.runtime.registry,allowed_user_paths=allowed))
        self.assertEqual(data['product']['product_code_version'],version)
        self.assertEqual(data['schema_version'],3);self.assertEqual(data['product']['product_structure_version'],1)
        install._code_matches(self.runtime,data['product'])
        self.assertEqual(self.user_before,{name:(self.runtime.root/name).read_bytes() for name in self.user_before})
        result=self.command('--help');self.assertEqual(result.returncode,0,result.stderr)
        self.assertFalse(upgrade.marker(self.runtime).exists())
        return data

    def test_frozen_formal_chain_upgrade_noop_and_persistent_rollback(self):
        plan=self.plan();result=self.apply(plan);self.assertEqual(result['status'],'completed')
        self.verify('0.4.1')
        self.assertEqual(install.inspect_machine(self.request)['scene'],'same')
        # Ordinary CLI use must not create foreign __pycache__ files in C.
        result=subprocess.run([sys.executable,str(self.runtime.code/'scripts/agm.py'),'check-memory','--all'],
            env=dict(os.environ,HOME=str(self.home)),capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertFalse(list(self.runtime.code.rglob('__pycache__')))
        versions.verify(self.runtime,plan['before_inventory']);versions.verify(self.runtime,plan['target_inventory'])
        before=self.snapshot();same=upgrade.plan_upgrade(dict(self.request,operation_id='same-t'))
        self.assertTrue(same['noop']);self.assertTrue(upgrade.execute_upgrade(same)['noop'])
        self.assertEqual(before,self.snapshot())
        print('REAL_CHAIN',json.dumps({'P_commit':self.p_source['commit'],'T_commit':self.t_source['commit'],
            'T_parent':self.parent,'P_manifest':plan['before_inventory']['release']['source']['tree_sha256'],
            'T_manifest':plan['target_inventory']['release']['source']['tree_sha256'],'changed_files':self.changed,
            'T0_self_installed':True,'T0_command_ran':True,'T1_command_ran':True,'same_version_zero_mtime':True}))
        # Register a project after upgrading. A release rollback must retain it.
        project=self.area/'project';project.mkdir();git('init','--quiet',cwd=project)
        request=dict(home=str(self.home),project=str(project),platform_config=self.config,agents=['codex'],
                     **seed_project_executors(self.home))
        preview=enable.run(request);self.assertEqual(preview['status'],'approval_required',preview)
        request['approval']=approved(json.loads(preview['next_action']))
        result=enable.run(request);self.assertEqual(result['status'],'completed',result)
        projects=copy.deepcopy(registry.load_registry(self.runtime.registry)['projects'])
        self.request.update(rollback_target={'version':'0.4.0','tree_sha256':plan['before_inventory']['release']['source']['tree_sha256']},direction='rollback',operation_id='actual-t-to-p',
            conversions=[{'before':self.conversion['after'],'after':self.conversion['before'],'direction':'rollback','entries':'preserve'}])
        self.apply();data=self.verify('0.4.0');self.assertEqual(data['projects'],projects)
        print('REAL_ROLLBACK version=0.4.0; post-upgrade project and authorization preserved; user bytes unchanged')

    def test_real_six_phase_faults_continue_or_rollback(self):
        for phase in upgrade.PHASES:
            for action in ('continue','rollback'):
                with self.subTest(phase=phase,action=action):
                    fixture=RealUpgradeTests();fixture.setUp()
                    try:
                        plan=fixture.plan()
                        def fault(event,path):
                            if event=='after_phase:'+phase:raise RuntimeError('real phase fault')
                        with self.assertRaises(RuntimeError):fixture.apply(plan,fault)
                        if phase=='commit' and action=='rollback':
                            with self.assertRaises(upgrade.UpgradeError):upgrade.plan_recovery(plan['journal'],action=action)
                            action_to_run='continue'
                        else:action_to_run=action
                        recovery=upgrade.plan_recovery(plan['journal'],action=action_to_run)
                        result=upgrade.recover_upgrade(recovery,approved(recovery))
                        fixture.verify('0.4.1' if action_to_run=='continue' else '0.4.0')
                        print('REAL_PHASE',phase,action,result['status'],'finish_only' if result.get('finalized_only') else '')
                    finally:fixture.doCleanups()

    def test_each_real_code_file_replacement_window_and_registry_commit(self):
        initial=self.plan();changed=[x['path'] for x in initial['outputs'] if x['before']!=x['after']]
        for relative in [str(Path(p).relative_to(self.runtime.code)) for p in changed]:
            for when in ('before','after'):
                for action in ('continue','rollback'):
                    with self.subTest(file=relative,when=when,action=action):
                        fixture=RealUpgradeTests();fixture.setUp()
                        try:
                            plan=fixture.plan()
                            def fault(event,path):
                                if event==when+'_code_replace' and str(path.relative_to(fixture.runtime.code))==relative:
                                    raise RuntimeError('actual file window')
                            with self.assertRaises(RuntimeError):fixture.apply(plan,fault)
                            recovery=upgrade.plan_recovery(plan['journal'],action=action)
                            upgrade.recover_upgrade(recovery,approved(recovery))
                            fixture.verify('0.4.1' if action=='continue' else '0.4.0')
                            print('REAL_FILE_WINDOW',relative,when,action)
                        finally:fixture.doCleanups()

    def test_recovery_runs_from_fixed_toolkit_after_installer_self_replacement(self):
        plan=self.plan()
        def fault(event,path):
            if event=='after_code_replace' and path.name=='user_install.py':raise RuntimeError('self overwrite')
        with self.assertRaises(RuntimeError):self.apply(plan,fault)
        unavailable=self.base/'T-unavailable';self.t.rename(unavailable)
        try:
            launcher=Path(plan['bootstrap'])/'recover.py'
            env=dict(os.environ,HOME=str(self.home),PYTHONDONTWRITEBYTECODE='1')
            preview=subprocess.run([sys.executable,'-B',str(launcher),'preview',plan['journal'],'continue'],env=env,capture_output=True,text=True)
            self.assertEqual(preview.returncode,0,preview.stderr)
            approved_file=self.area/'recovery.json';approved_file.write_text(json.dumps(approved(json.loads(preview.stdout))))
            result=subprocess.run([sys.executable,'-B',str(launcher),'apply',str(approved_file)],env=env,capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr);self.assertEqual(json.loads(result.stdout)['status'],'completed')
            self.verify('0.4.1')
            print('REAL_FIXED_TOOLKIT source unavailable; installer replaced; fixed launcher recovered; T CLI runs')
        finally:unavailable.rename(self.t)
