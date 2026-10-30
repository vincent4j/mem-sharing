"""Installer CLI: explicit approvals, isolated HOME, no network or runtime probes."""
import copy
import importlib.util
import io
import json
import os
import subprocess
import sys
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_m404_install import InstallFixture, approved
from test_m407_upgrade import UpgradeFixture
from test_m403_migrate import MigrationFixture, OLD_COMMIT
from agm_core import detect, legacy_import as legacy, user_entries, user_install, paths

spec = importlib.util.spec_from_file_location('m408_install', Path(__file__).resolve().parents[2]/'scripts/install.py')
cli = importlib.util.module_from_spec(spec); spec.loader.exec_module(cli)


class InstallerTests(InstallFixture):
    def setUp(self):
        super().setUp()
        self.manifest = self.area/'source.json'
        self.manifest.write_text(json.dumps(self.request['source']))
        original = detect.detect_agents
        def isolated(config, agents=None, **kwargs):
            kwargs.update(search_paths=kwargs.get('search_paths') or [], app_directories=[])
            return original(config, agents, **kwargs)
        self.addCleanup(patch.stopall)
        patch.object(detect, 'detect_agents', side_effect=isolated).start()

    def invoke(self, *args):
        out=io.StringIO()
        with patch.dict(os.environ, HOME=str(self.home)), redirect_stdout(out):
            code=cli.main(list(args))
        return code,json.loads(out.getvalue())

    def approval_file(self, plan):
        p=self.area/'approval.json';p.write_text(json.dumps(approved(plan)));return str(p)

    def snapshot(self):
        return {str(p.relative_to(self.home)):(p.lstat().st_mode,p.lstat().st_mtime_ns,
                p.read_bytes() if p.is_file() and not p.is_symlink() else None)
                for p in [self.home,*self.home.rglob('*')]}

    def test_blank_home_non_git_cwd_preview_apply_and_report(self):
        cwd=os.getcwd();os.chdir(self.area)
        self.addCleanup(os.chdir,cwd)
        before=self.snapshot()
        code,out=self.invoke('--source-manifest',str(self.manifest),'--project',str(self.area/'actual project'))
        self.assertEqual(code,5,out);self.assertEqual(before,self.snapshot())
        p=out['approval_plan'];self.assertEqual(p['schema_version'],1)
        for key in ('layout','source','versions','scene_sha256','changes','reference_map','legacy_identity','metadata_scopes'):
            self.assertIn(key,p)
        code,done=self.invoke('--approval-file',self.approval_file(p),'--project',str(self.area/'actual project'))
        self.assertEqual(code,0,done);self.assertEqual(done['status'],'completed')
        self.assertEqual(done['agents']['connected'],[]);self.assertTrue(done['connection_pending'])
        # 装机枚举逐家列出已适配执行器,默认全部接入,未适配不在覆盖范围。
        self.assertIn('默认全部接入',done['agents']['note'])
        self.assertEqual(sorted(done['agents']),['absent','connected','note','unknown','unselected'])
        # v1.11 裁定 §14.4:装完报告不再携带新会话自检提示。
        self.assertNotIn('runtime_acceptance',done)
        self.assertIn('/absolute/path/to/your/project',out['project_commands'][0]) if out['project_root_required'] else None
        self.assertIn('actual project',done['project_commands'][0]);self.assertEqual(done['layout']['code'],str(self.runtime.code))
        data=json.loads(self.runtime.registry.read_bytes());self.assertEqual(data['projects'],{})

    def test_exact_approval_unknown_field_and_scene_drift_stop(self):
        plan=cli.plan_machine(self.request);before=self.snapshot()
        approval=approved(plan);approval['surprise']=True
        with self.assertRaises(cli.InstallError):cli.execute_machine(plan,approval,request=self.request)
        self.assertEqual(before,self.snapshot())
        (self.home/'new-unused-user-file').write_text('outside observed scope')
        (self.source/'SKILL.md').write_text('source changed')
        before=self.snapshot()
        with self.assertRaises(ValueError):cli.execute_machine(plan,approved(plan),request=self.request)
        self.assertEqual(before,self.snapshot())

    def test_approval_cannot_redirect_home(self):
        _,out=self.invoke('--source-manifest',str(self.manifest))
        other=self.area/'otherhome';other.mkdir()
        with patch.dict(os.environ,HOME=str(other)),redirect_stdout(io.StringIO()) as output:
            code=cli.main(['--approval-file',self.approval_file(out['approval_plan'])])
        self.assertEqual(code,2);self.assertEqual(list(other.iterdir()),[])
        self.assertEqual(json.loads(output.getvalue())['errors'][0]['code'],'approval_mismatch')

    def test_same_release_reinstall_no_mtime_or_byte_changes(self):
        plan=cli.plan_machine(self.request);self.assertEqual(cli.execute_machine(plan,approved(plan),request=self.request)['status'],'completed')
        before=self.snapshot();same=cli.plan_machine(self.request)
        self.assertTrue(same['plan']['noop']);self.assertEqual(same['changes'],[])
        self.assertEqual(cli.execute_machine(same,approved(same),request=self.request)['status'],'completed')
        self.assertEqual(before,self.snapshot())

    def test_later_agent_requires_named_request_same_version_add_path(self):
        self.execute()
        self.codex()
        before=self.snapshot();plan=cli.plan_machine(self.request)
        self.assertEqual(plan['effective_agents'],[]);self.assertEqual(plan['changes'],[])
        with patch.object(user_entries,'run_user_entries',side_effect=AssertionError('no auto onboarding')):
            self.assertEqual(cli.execute_machine(plan,approved(plan),request=self.request)['status'],'completed')
        self.assertEqual(before,self.snapshot());self.assertFalse((self.home/'.codex').exists())
        named=dict(self.request,agents=['codex'])
        plan=cli.plan_machine(named);self.assertTrue(plan['plan']['noop'])
        self.assertTrue(plan['entry_plan']['changes']);self.assertEqual(plan['effective_agents'],['codex'])
        done=cli.execute_machine(plan,approved(plan),request=named)
        self.assertEqual(done['status'],'completed',done)
        entry=self.home/'.codex/AGENTS.md'
        self.assertTrue(entry.is_file())
        self.assertIn('/mem-sharing 菜单',entry.read_text())
        self.assertFalse((self.home/'.codex/skills').exists())

    def test_v0_layered_index_and_original_bytes_preserved(self):
        original=self.v0();plan=cli.plan_machine(self.request)
        self.assertEqual(plan['legacy_identity'],'confirmed_v0')
        self.assertEqual(plan['channel'],'legacy_copy')
        result=cli.execute_machine(plan,approved(plan),request=self.request)
        self.assertEqual(result['status'],'completed',result)
        index=(self.runtime.root/'memories/MEMORY.md').read_text()
        self.assertIn('L0 恒读',index)
        # v1.11/v1.12:治理条款、Claude 兜底条款与菜单进入 v0 新索引模板;
        # 指纹随模板由 manifest 绑定,v0 原文复制语义不变。
        self.assertIn(user_entries.GOVERNANCE_RULES_TEXT,index)
        self.assertIn(user_entries.CLAUDE_FALLBACK_TEXT,index)
        self.assertIn('/mem-sharing 菜单',index)
        package=Path(plan['plan']['legacy_import']['package'])
        self.assertEqual((package/'memories/MEMORY.md').read_bytes(),original['memories/MEMORY.md'])
        self.assertTrue((self.runtime.legacy_root/'skills/example.txt').is_file())
        self.assertFalse((package/'skills').exists())
        self.assertTrue(result['copies']);self.assertTrue(result['exclusions'])

    def test_fresh_l0_l1_l2_templates_no_sidecars(self):
        self.execute()
        index=(self.runtime.root/'memories/MEMORY.md').read_text()
        self.assertIn('L0 恒读 → 需要时读该主题 L1',index)
        self.assertIn('一句话当前结论 + 链接',index)
        self.assertIn('使用约定：',index);self.assertIn('(topics/使用约定.md)',index)
        self.assertIn(user_entries.GOVERNANCE_RULES_TEXT,index)
        self.assertIn(user_entries.CLAUDE_FALLBACK_TEXT,index)
        self.assertIn('/mem-sharing 菜单',index)
        self.assertIn('批量启用记忆',index)
        topic=(self.runtime.root/'memories/topics/使用约定.md').read_text()
        self.assertLess(topic.index('## L1 概要'),topic.index('## L2 正文'))
        self.assertIn('当前有效结论',topic);self.assertIn('待办',topic)
        self.assertIn(user_entries.GOVERNANCE_RULES_TEXT,topic)
        self.assertEqual({p.suffix for p in (self.runtime.root/'memories').rglob('*') if p.is_file()},{'.md'})

    def test_repeatable_agents_and_explicit_absent_reject_without_writes(self):
        code,out=self.invoke('--source-manifest',str(self.manifest),'--agent','claude','--agent','codex')
        self.assertEqual(code,2,out);self.assertEqual(list(self.home.iterdir()),[])
        self.assertIn('preflight',out['errors'][0]['message'].lower())
        parsed=cli.build_parser().parse_args(['--agent','codex','--agent','claude'])
        self.assertEqual(parsed.agent,['codex','claude'])

    def test_recovery_independent_preview_apply(self):
        p=self.plan()
        def fault(event,path):
            if event=='after_code':raise RuntimeError('fault')
        with self.assertRaises(RuntimeError):self.execute(p,fault)
        code,out=self.invoke('--recover',p['journal'],'--action','continue')
        self.assertEqual(code,5,out)
        code,out=self.invoke('--recover',p['journal'],'--action','continue','--approval-file',self.approval_file(out['approval_plan']))
        self.assertEqual(code,0,out);self.assertEqual(out['status'],'completed')

    def test_recovery_mixing_unknown_inputs_relative_approval_bad_evidence_reject(self):
        for args in (['--recover','/x','--action','continue','--version','0.4.0'],
                     ['--action','rollback'],['--approval-file','relative'],['--unknown']):
            with self.subTest(args=args):self.assertEqual(self.invoke(*args)[0],2)
        p=cli.plan_machine(self.request)
        for evidence in ({'confirmed_at':'<UTC>','reference':'user'}, {'confirmed_at':'nonsense','reference':'user'},
                         {'confirmed_at':'2026-10-30T00:00:00Z','reference':''}):
            with self.assertRaises(cli.InstallError):cli.execute_machine(p,dict(p,**evidence),request=self.request)
        self.assertEqual(list(self.home.iterdir()),[])

    def test_missing_git_diagnostic_no_installation(self):
        with patch.object(cli.shutil,'which',return_value=None):
            code,out=self.invoke('--source-manifest',str(self.manifest))
        self.assertEqual(code,2);self.assertEqual(out['errors'][0]['code'],'runtime_missing')
        self.assertIn('manually',out['errors'][0]['message']);self.assertEqual(list(self.home.iterdir()),[])

    def test_entry_failure_after_code_copy_is_partial_with_recovery(self):
        plan=cli.plan_machine(self.request)
        with patch.object(user_install,'_stage_entries',side_effect=ValueError('entry assembly failed')):
            result=cli.execute_machine(plan,approved(plan),request=self.request)
        self.assertEqual(result['status'],'partial');self.assertTrue(result['recovery_required'])
        self.assertTrue(Path(result['recovery']).is_file());self.assertFalse(self.runtime.registry.exists())
        self.assertTrue(self.runtime.code.is_dir());self.assertEqual(result['agents']['connected'],[])
        self.recover(result['recovery'],'rollback')

    def test_source_checkout_commit_and_dirty_are_verified_no_reset(self):
        def git(*args):return subprocess.run(['git','-C',str(self.source),*args],check=True,capture_output=True,text=True).stdout.strip()
        git('init');git('add','SKILL.md','scripts');git('-c','user.name=fixture','-c','user.email=fixture@example.invalid','commit','-m','fixture')
        commit=git('rev-parse','HEAD')
        source=cli.checkout_source(str(self.source),commit,'0.4.0')
        self.assertEqual(source['commit'],commit);self.assertEqual(source['files'],self.request['source']['files'])
        with self.assertRaises(ValueError):cli.checkout_source(str(self.source),'f'*40,'0.4.0')
        (self.source/'untracked-user-file').write_text('keep')
        with self.assertRaises(ValueError):cli.checkout_source(str(self.source),commit,'0.4.0')
        self.assertEqual((self.source/'untracked-user-file').read_text(),'keep')
        self.assertEqual(git('rev-parse','HEAD'),commit)

    def test_acquisition_preview_zero_write_and_no_network(self):
        stage=self.area/'acquisition'
        with patch.object(cli.subprocess,'run',side_effect=AssertionError('must not clone')):
            code,out=self.invoke('--acquire','--staging',str(stage),'--commit','a'*40,'--version','0.4.0')
        self.assertEqual(code,5,out);self.assertFalse(stage.exists())
        self.assertFalse(out['installation_complete']);self.assertEqual(out['acquisition'],'not_started')
        self.assertEqual(out['approval_plan']['source_url'],cli.OFFICIAL)

    def test_acquisition_failure_keeps_journal_and_reports_partial(self):
        stage=self.area/'acquisition';plan=cli.plan_acquisition('a'*40,str(stage),'0.4.0')
        with patch.object(cli.subprocess,'run',side_effect=subprocess.CalledProcessError(1,['git'])):
            result=cli.execute_acquisition(plan,approved(plan))
        self.assertEqual(result['status'],'partial');self.assertFalse(result['installation_complete'])
        journal=json.loads(Path(result['acquisition_manifest']).read_bytes())
        self.assertEqual(journal['plan'],plan);self.assertEqual(journal['status'],'partial')
        self.assertFalse(self.runtime.root.exists())


class UpgradeInstallerTests(UpgradeFixture):
    def test_upgrade_cli_composition_and_partial_entries_failure(self):
        self.codex();self.req.update(agents=['codex'],search_paths=self.request['search_paths'])
        plan=cli.plan_machine(self.req)
        self.assertEqual(plan['channel'],'upgrade');self.assertFalse(plan['plan']['noop'])
        original=user_entries.run_user_entries
        def entries(request):
            if json.loads(self.runtime.registry.read_bytes())['product']['product_code_version']=='0.4.1':
                return {'status':'failed','errors':[{'code':'fixture_entry_failed'}]}
            return original(request)
        with patch.object(user_entries,'run_user_entries',side_effect=entries):
            result=cli.execute_machine(plan,approved(plan),request=self.req)
        self.assertEqual(result['status'],'partial');self.assertTrue(result['connection_pending'])
        self.assertEqual(self.product()['product_code_version'],'0.4.1')
        self.assertIn('fixture_entry_failed',str(result['entries']))

    def test_upgrade_without_release_conversion_is_rejected(self):
        request=dict(self.req,conversions=[])
        before=self.snapshot()
        with self.assertRaises(ValueError):cli.plan_machine(request)
        self.assertEqual(before,self.snapshot())


class MigrationInstallerTests(MigrationFixture):
    def test_schema1_routes_through_upgrade_migration_and_code_placement(self):
        target=self.area/'verified target';(target/'scripts/agm_core').mkdir(parents=True)
        for name,raw in {'SKILL.md':b'# verified target\n','scripts/agm.py':b'print("target")\n',
                         'scripts/agm_core/__init__.py':b''}.items():
            (target/name).write_bytes(raw)
        source={'root':str(target),'url':'fixture://target','commit':'c'*40,'version':'0.4.0',
                'files':{str(p.relative_to(target)):legacy.digest(p.read_bytes()) for p in target.rglob('*') if p.is_file()}}
        request={'home':str(self.home),'platform_config':paths.select_platform(paths.load_agents_table(),'darwin'),
                 'source':source,'agents':None,'search_paths':[],'app_directories':[],
                 'operation_id':'fixture-m408-schema1','legacy_registries':[str(self.old)],
                 'legacy_source_commits':{str(self.old):OLD_COMMIT}}
        plan=cli.plan_machine(request)
        self.assertEqual(plan['channel'],'upgrade');self.assertIsNotNone(plan['plan']['migration_plan'])
        self.assertFalse(plan['entry_requested'])
        result=cli.execute_machine(plan,approved(plan),request=request)
        self.assertEqual(result['status'],'completed',result)
        self.assertTrue(self.old.is_dir());self.assertTrue((self.old/'redirect.json').is_file())
        data=self.load()
        # M4-03 deliberately maps backup_manifest to its verified archived copy;
        # compare the exact approved migration output, not old physical paths.
        self.assertEqual(data['projects'],plan['plan']['migration_plan']['after_registry']['projects'])
        for key,old in self.original['projects'].items():
            self.assertEqual(data['projects'][key]['memory_authorization'],old['memory_authorization'])
            self.assertEqual(data['projects'][key]['authorization_evidence'],old['authorization_evidence'])
        self.assertEqual((self.runtime.code/'SKILL.md').read_bytes(),(target/'SKILL.md').read_bytes())
