"""Real synthetic CLI output and exact producer-owned separator retirement."""
import io,json,os,sys,unittest
from pathlib import Path
from unittest.mock import patch
from contextlib import redirect_stdout
import test_m404_install as install_fixture
import test_memory_share as user_fixture
import test_project_share as project_fixture
from agm_core import detect,uninstall,uninstall_recovery as recovery,memory_share as ms,project_share as ps

OUT=Path('/tmp/msf-interaction-cleanup-output');OUT.mkdir(mode=0o700,exist_ok=True)
class InteractionCleanupTests(unittest.TestCase):
    def test_user_and_project_real_cli_all_candidates_and_new_alias(self):
        for mod,klass,command in [(ms,user_fixture.MemoryShareChainTests,'share-user-memory'),(ps,project_fixture.ProjectShareTests,'share-project-memory')]:
            f=klass();f.setUp();self.addCleanup(f.doCleanups)
            proposal=f.standard_proposal() if mod is ms else f.proposal();file=OUT/(command+'-proposal.json');file.write_text(json.dumps(proposal));args=[command,'--proposal-file',str(file)]
            if mod is ps:args+=['--project',str(f.repo)]
            else:
                for agent in f.req['agents']:args+=['--agent',agent]
            def invoke(extra):
                out=io.StringIO()
                with patch.dict(os.environ,HOME=str(f.home)),redirect_stdout(out):rc=mod.cli(args+extra,home=f.home)
                return rc,json.loads(out.getvalue())
            rc,result=invoke([]);self.assertEqual(rc,5,result);p=result['approval_plan'];prompt=result['prompt'];(OUT/(command+'.txt')).write_text(prompt)
            self.assertNotIn('由你选择是否共享',prompt);self.assertNotIn('默认共享',prompt)
            self.assertIn('建议合并的相同规则',prompt)
            if p['optional_numbers'] or p['single_numbers']:self.assertIn('需要你确认是否合并',prompt)
            for g in p['groups']:self.assertEqual(prompt.count('\n%d. '%g['number']),1)
            single=(p['single_numbers'] or p['optional_numbers'])[0];rc,result=invoke(['--selection','再加入%d'%single]);self.assertEqual(rc,5,result);self.assertIn(single,result['approval_plan']['selected_numbers'])
            # Exact same shared CLI implements full plan-bound project selection execution.
            if mod is ps:
                shown=OUT/'project-shown.json';shown.write_text(json.dumps(p));before=recovery.tree(f.home)
                rc,result=invoke(['--selection','查看%d'%single]);self.assertEqual(rc,0,result);self.assertEqual(recovery.tree(f.home),before)
                rc,result=invoke(['--selection','再加入%d'%single,'--selection-plan-file',str(shown),'--selection-reference','actual fixture choice']);self.assertEqual(rc,0,result)

    def test_exact_WB_seven_to_twelve_candidates_are_not_hidden_in_actual_cli(self):
        import test_install_conversation as conversation
        from agm_core import user_rules_organize as org
        f=conversation.EquivalenceTests();f.setUp();self.addCleanup(f.doCleanups)
        wb=f.f.native['workbuddy'];wb.write_bytes(wb.read_bytes()+'\n# 待选\n'.encode()+b'\n'.join(('- 合成待选规则%d。\n'%i).encode() for i in range(7,13)))
        declarations=f.declarations
        for group in declarations:
            for source in group['sources']:
                if source['source']==str(wb):source['basis']=ms.entries.sha256(wb.read_bytes())
        file=f.f.area/'equivalence.json';file.write_text(json.dumps(declarations));out=io.StringIO()
        with patch.dict(os.environ,HOME=str(f.f.home)),redirect_stdout(out):rc=org.cli(['organize-user-memory','--equivalent-sources-file',str(file)],home=f.f.home)
        self.assertEqual(rc,5);d=json.loads(out.getvalue());self.assertEqual(d['approval_plan']['default_numbers'],list(range(1,7)));self.assertEqual(d['approval_plan']['single_numbers'],list(range(7,13)));self.assertIn('需要你确认是否合并',d['prompt'])
        for number in range(7,13):self.assertIn('\n%d. '%number,d['prompt'])
        self.assertIn('WorkBuddy（~/.workbuddy/MEMORY.md）',d['prompt']);(OUT/'WB7-12-real-cli.txt').write_text(d['prompt'])

    def claude_fixture(self,original):
        f=install_fixture.InstallFixture();f.setUp();self.addCleanup(f.doCleanups);f.request['agents']=['claude'];path=f.home/'.claude/CLAUDE.md';path.parent.mkdir();path.write_bytes(original(f) if callable(original) else original);prior=path.read_bytes();real=detect.detect_agents
        def detector(*args,**kwargs):
            kwargs.update(search_paths=[],app_directories=[]);d=real(*args,**kwargs);d['agents']['claude']['status']='installed';return d
        with patch.object(detect,'detect_agents',side_effect=detector):f.execute()
        return f,path,prior

    def test_claude_installed_separators_inverse_byte_exact(self):
        for prior in [b'private without newline',b'\n\nprivate\r\n\r\n',b'\xef\xbb\xbfprivate\n\n',b'private\n']:
            with self.subTest(prior=repr(prior)):
                f,path,original=self.claude_fixture(prior);p=uninstall.preview(home=f.home,backup_dir=f.area/'exit');after=bytes.fromhex(next(c['after']['hex'] for c in p['changes'] if c['path']==str(path)));self.assertEqual(after,original)

    def test_claude_existing_import_keeps_its_original_whitespace(self):
        f=install_fixture.InstallFixture();f.setUp();self.addCleanup(f.doCleanups);path=f.home/'.claude/CLAUDE.md';path.parent.mkdir();token=('@'+str(f.runtime.root/'memories/MEMORY.md')).encode();prior=b'\n\n'+token+b'\n\nprivate\r\n';path.write_bytes(prior);before=recovery.tree(f.home)
        with self.assertRaises(ValueError):f.plan()
        self.assertEqual(recovery.tree(f.home),before);self.assertEqual(path.read_bytes(),prior)

    def test_claude_drift_and_tampered_before_are_zero_write_rejections(self):
        for mode in ['native','producer']:
            f,path,prior=self.claude_fixture(b'\n\nprivate\n')
            if mode=='native':path.write_bytes(path.read_bytes()+b'user later edit')
            else:
                v=json.loads(f.runtime.registry.read_text());obj=next(o for o in v['machine']['objects'].values() if o.get('marker') and 'claude-fallback' in o['marker']['start']);manifest=Path(obj['backup_manifest']);receipt=json.loads(manifest.read_text());row=next(x for x in receipt['entries'] if x['path']==str(path));(manifest.parent/row['before']['backup']).write_bytes(b'forged before')
            before=recovery.tree(f.home)
            with self.assertRaises(ValueError):uninstall.preview(home=f.home,backup_dir=f.area/'exit')
            self.assertEqual(recovery.tree(f.home),before)
