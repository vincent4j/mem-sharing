"""Real P=27d6e26 -> T development snapshots, temporary Git commits only.

P installs itself in a synthetic HOME. T contains the actual changed product
files, with P as its Git parent. No version-string-only fixture proves upgrade.
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

P_COMMIT='27d6e26'


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
        cls.p=cls.base/'P';cls.t=cls.base/'T'
        subprocess.run(['git','clone','--quiet','--no-hardlinks',str(REPO),str(cls.p)],check=True,capture_output=True)
        git('checkout','--quiet','--detach',P_COMMIT,cwd=cls.p)
        subprocess.run(['git','clone','--quiet','--no-hardlinks',str(cls.p),str(cls.t)],check=True,capture_output=True)
        for original in [REPO/'SKILL.md',*(REPO/'scripts').rglob('*.py'),REPO/'scripts/agents.json']:
            rel=original.relative_to(REPO);target=cls.t/rel;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(original,target)
        git('add','--','scripts','SKILL.md',cwd=cls.t)
        git('-c','user.name=AGM isolated fixture','-c','user.email=fixture@invalid',
            '-c','commit.gpgsign=false','commit','--quiet','-m','Actual M4-07 implementation snapshot for isolated acceptance',cwd=cls.t)
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
        # P 是真实历史快照:其安装器按当时(v1.11 之前)的路径表合同工作,仍读取
        # user_skill_roots 等本轮已移除的字段。给 P 的自装请求配 P 自己的表,
        # 保证“P 用自己的安装器与表完成安装”;T 侧流程照旧用当前表(新代码不再读该字段)。
        p_config=json.loads((self.p/'scripts/agents.json').read_text())['platforms']['darwin']
        p_request=dict(self.request,platform_config=p_config,
                       search_paths=[self.seed_codex()] if codex else [])
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
        self.assertFalse(versions.root(self.runtime).exists(),'Historical P really uses its original installer')
        result=self.command('check-memory','--all')
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(json.loads(result.stdout)['command'],'check-memory')
        before=json.loads(self.runtime.registry.read_bytes())['product']
        target,_=install._source({'source':self.t_source})
        self.conversion={'before':{'schema_version':2,'product_structure_version':1,
            'product_code_version':before['product_code_version'],'source':before['source']},
            'after':{'schema_version':2,'product_structure_version':1,'product_code_version':'0.4.1',
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
        self.assertEqual(data['schema_version'],2);self.assertEqual(data['product']['product_structure_version'],1)
        install._code_matches(self.runtime,data['product'])
        self.assertEqual(self.user_before,{name:(self.runtime.root/name).read_bytes() for name in self.user_before})
        result=self.command('--help');self.assertEqual(result.returncode,0,result.stderr)
        self.assertFalse(upgrade.marker(self.runtime).exists())
        return data

    def test_actual_development_chain_upgrade_noop_and_persistent_rollback(self):
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
            'P_self_installed':True,'P_command_ran':True,'T_command_ran':True,'same_version_zero_mtime':True}))
        # Register a project after upgrading. A release rollback must retain it.
        project=self.area/'project';project.mkdir();git('init','--quiet',cwd=project)
        request=dict(home=str(self.home),project=str(project),platform_config=self.config,agents=['codex'],memory_choice='no',
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

    def test_upgrade_makes_legacy_projection_inert_and_idempotent(self):
        # 主 Agent 裁定 A 用例:P 带投影与旧入口合同装机 → T 升级:
        # 升级成功、用户内容字节不变、旧投影对象在 T 下退化为惰性(不再被规划触碰)、
        # 同版重装幂等。
        fixture=RealUpgradeTests();fixture.setUp(codex=True)
        try:
            entry=fixture.home/'.codex/AGENTS.md'
            projection=fixture.home/'.codex/skills/agent-group-memory'
            self.assertTrue(entry.is_file(),entry)
            self.assertTrue(projection.is_symlink(),projection)
            link_target=os.readlink(projection);entry_bytes=entry.read_bytes()
            plan=fixture.plan();result=fixture.apply(plan)
            self.assertEqual(result['status'],'completed',result)
            data=fixture.verify('0.4.1')
            # 旧入口块原文与投影链接字节/目标不变(entries:'preserve';投影惰性保留)。
            self.assertEqual(entry.read_bytes(),entry_bytes)
            self.assertTrue(projection.is_symlink())
            self.assertEqual(os.readlink(projection),link_target)
            # 转换处理器注销账内旧投影登记(磁盘链接原地保留);入口对象仍在账内。
            self.assertNotIn('skill_symlink',{o['kind'] for o in data['machine']['objects'].values()})
            self.assertIn(str(entry)+'#public-source',data['machine']['objects'])
            # T 下对已装 codex 重跑入口装配:零差异完成,不再触碰投影位。
            request={'home':str(fixture.home),'platform_config':fixture.config,'agents':['codex'],
                     'search_paths':[fixture.codex_bin],'app_directories':[]}
            outcome=user_entries.run_user_entries(request)
            self.assertEqual(outcome['status'],'completed',outcome)
            self.assertEqual(os.readlink(projection),link_target)
            self.assertFalse(any(c for c in outcome['changes']))
            # 同版重装幂等:零写入、零 mtime 变化。
            before=fixture.snapshot()
            same=upgrade.plan_upgrade(dict(fixture.request,operation_id='inert-same'))
            self.assertTrue(same['noop']);self.assertTrue(upgrade.execute_upgrade(same)['noop'])
            self.assertEqual(before,fixture.snapshot())
            print('REAL_INERT_PROJECTION link_preserved; t_entry_assembly_zero_diff; same_release_noop')
        finally:fixture.doCleanups()

    def test_entry_contract_hash_outside_whitelist_still_rejected(self):
        # 负例:user_entries.py 哈希落在精确白名单之外(即使转换表其余部分完全合法)
        # 仍按“无转换处理器”拒绝,零写入。
        t2=self.base/'T-mismatch'
        subprocess.run(['git','clone','--quiet','--no-hardlinks',str(self.t),str(t2)],check=True,capture_output=True)
        victim=t2/'scripts/agm_core/user_entries.py'
        victim.write_bytes(victim.read_bytes()+b'\n# fixture contract hash mismatch\n')
        git('add','--','scripts/agm_core/user_entries.py',cwd=t2)
        git('-c','user.name=AGM isolated fixture','-c','user.email=fixture@invalid',
            '-c','commit.gpgsign=false','commit','--quiet','-m','contract mismatch variant',cwd=t2)
        t2_source=source(t2,'0.4.2')
        fresh,_=install._source({'source':t2_source})
        request=dict(self.request,source=t2_source,operation_id='contract-mismatch',conversions=[{
            'before':self.conversion['before'],
            'after':{'schema_version':2,'product_structure_version':1,'product_code_version':'0.4.2',
                     'source':{k:fresh[k] for k in ('url','commit','tree_sha256')}},
            'direction':'upgrade','entries':'preserve'}])
        registry_before=self.runtime.registry.read_bytes();tree_before=self.snapshot()
        with self.assertRaises(upgrade.UpgradeError) as ctx:
            upgrade.plan_upgrade(request)
        self.assertIn('no handler',str(ctx.exception))
        self.assertEqual(self.runtime.registry.read_bytes(),registry_before)
        self.assertEqual(self.snapshot(),tree_before)
        print('REAL_CONTRACT_WHITELIST mismatch_hash_rejected_zero_writes')

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
