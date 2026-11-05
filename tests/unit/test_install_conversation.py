"""Synthetic actual TTY frontend and exact semantic source proposals."""
import copy, io, json, os, pty, select, subprocess, sys, time, unittest
from pathlib import Path
from unittest.mock import patch
from test_m404_install import InstallFixture, approved
from test_m408_installer import cli
import test_generated_wrapper_retirement as wrapper_fixture
from agm_core import user_rules_organize as org, memory_share, uninstall

EVIDENCE=Path('/tmp/msf-install-conversation-output');EVIDENCE.mkdir(mode=0o700,exist_ok=True)

class ConversationTests(unittest.TestCase):
    def fixture(self):
        f=InstallFixture();f.setUp();self.addCleanup(f.doCleanups);f.codex()
        f.home.joinpath('.codex').mkdir();f.home.joinpath('.codex/AGENTS.md').write_text('# 用户规则\n\n- 合成规则正文。\n')
        source=f.area/'source.json';source.write_text(json.dumps(f.request['source']))
        req=f.area/'request.json';req.write_text(json.dumps({'search_paths':f.request['search_paths'],'app_directories':[]}))
        return f,source,req

    def tty(self,f,source,req,answers):
        master,slave=pty.openpty();env=dict(os.environ,HOME=str(f.home),PYTHONDONTWRITEBYTECODE='1')
        p=subprocess.Popen([sys.executable,'-B',str(f.source/'scripts/install.py'),'--source-manifest',str(source),'--request-file',str(req)],stdin=slave,stdout=slave,stderr=slave,env=env);os.close(slave)
        output=b'';sent=False;end=time.monotonic()+25
        try:
            while time.monotonic()<end:
                if select.select([master],[],[],.05)[0]:
                    try:b=os.read(master,65536)
                    except OSError:break
                    if not b:break
                    output+=b
                    if not sent and '按回车开始安装'.encode() in output:
                        os.write(master,answers);sent=True
                if p.poll() is not None:break
            if p.poll() is None:p.kill()
            p.wait()
        finally:os.close(master)
        path=EVIDENCE/(self._testMethodName+'.txt');path.write_bytes(output);path.chmod(0o600)
        return p.returncode,output.decode(errors='replace')

    def test_real_tty_enter_view_selection_then_CK_skip(self):
        f,s,r=self.fixture();rc,out=self.tty(f,s,r,b'\n'+ '查看1\n再加入1\n跳过\n'.encode())
        self.assertEqual(rc,0,out);self.assertIn('memSharing 已安装。',out);self.assertIn('需要你确认是否合并',out);self.assertNotIn('建议合并的相同规则',out)
        self.assertIn('来源：Codex（~/.codex/AGENTS.md）',out);self.assertIn('公共用户记忆已整理完成',out)
        self.assertLess(out.index('公共用户记忆已整理完成'),out.index('需要再安装 Context Keeper'))
        self.assertEqual(out.count('按回车开始安装'),1);self.assertNotIn('确认执行',out);self.assertNotIn('CK 安装预览暂不可用',out);self.assertNotIn('再加入7',out);self.assertNotIn('不合并2',out)
        self.assertTrue((f.runtime.root/'memories/user-rules.md').is_file())
        self.assertNotIn('- 合成规则正文。',f.home.joinpath('.codex/AGENTS.md').read_text())

    def test_real_tty_EOF_never_approves(self):
        f,s,r=self.fixture();rc,out=self.tty(f,s,r,b'\x04');self.assertEqual(rc,0,out);self.assertIn('尚未安装',out);self.assertFalse(f.runtime.root.exists())

    def test_non_tty_newline_is_preview_only(self):
        f,s,r=self.fixture();p=subprocess.run([sys.executable,'-B',str(f.source/'scripts/install.py'),'--source-manifest',str(s),'--request-file',str(r)],input='\n',capture_output=True,text=True,env=dict(os.environ,HOME=str(f.home)))
        self.assertEqual(p.returncode,5,p.stdout);self.assertFalse(f.runtime.root.exists())
        (EVIDENCE/'non-tty.json').write_text(p.stdout)

class EquivalenceTests(unittest.TestCase):
    def setUp(self):
        self.f=wrapper_fixture.GeneratedWrapperTests();self.f.setUp();self.addCleanup(self.f.doCleanups);f=self.f
        self.req=dict(f.req,agents=list(f.native));p=org.plan_organize(self.req)['approval_plan'];self.declarations=[]
        for raw in f.rules:
            members=[i for i in p['items'] if i['text'].encode()==raw]
            self.declarations.append({'sources':[{'source':i['source'],'start':i['start'],'end':i['end'],'context':i['context'],'text_sha256':i['sha256'],'basis':memory_share.entries.sha256(Path(i['source']).read_bytes())} for i in members], 'canonical_context':members[0]['context'],'reason':'Read every full source: both headings express these same unrestricted cross-Agent user rules.'})
        self.req['equivalent_sources']=self.declarations

    def test_six_single_numbers_36_records_and_formal_exit(self):
        f=self.f;p=org.plan_organize(self.req)['approval_plan'];self.assertEqual(len(p['default_numbers']),6)
        self.assertEqual([len(g['sources']) for g in p['groups'] if g['number'] in p['default_numbers']],[6]*6)
        text=org.present(p);self.assertIn('建议合并的相同规则',text);self.assertIn('OpenCode（~/.config/opencode/AGENTS.md）',text)
        for g in p['groups']:
            self.assertEqual(text.count('\n%d. '%g['number']),1)
        (EVIDENCE/'six-agent-preview.txt').write_text(text)
        result=org.execute_organize(p,approved(p),request=self.req);self.assertEqual(result['status'],'completed',result)
        records=memory_share._available_migrations(f.runtime);self.assertEqual(len(records),36)
        public=f.topic.read_bytes()
        for raw in f.rules:self.assertEqual(public.count(raw),1)
        exit=uninstall.preview(home=f.home,backup_dir=f.area/'exit-new')
        for agent,native in f.native.items():
            b=bytes.fromhex(next(c['after']['hex'] for c in exit['changes'] if c['path']==str(native)))
            self.assertEqual([x for x in b.splitlines() if x.strip()],[x for x in f.original[agent].splitlines() if x.strip()],agent)
        from test_uninstall import approval
        from agm_core import uninstall_recovery as recovery
        before=recovery.tree(f.home)
        uninstall.execute(approval(recovery.summary(exit)),home=f.home,backup_dir=f.area/'exit-new')
        tool=[sys.executable,'-I','-S','-B',str(f.area/'exit-new/recover.py'),'--manifest',str(f.area/'exit-new/manifest.json'),'--action','restore']
        env=dict(os.environ,HOME=str(f.home));child=subprocess.run(tool,capture_output=True,text=True,env=env);self.assertEqual(child.returncode,5,child.stdout)
        file=f.area/'restore.json';file.write_text(json.dumps(approval(json.loads(child.stdout)['plan'])))
        child=subprocess.run(tool+['--approval-file',str(file)],capture_output=True,text=True,env=env);self.assertEqual(child.returncode,0,child.stdout);self.assertEqual(recovery.tree(f.home),before)
        # Without a fresh declaration there is no durable context alias.
        f.native['opencode'].write_bytes(f.native['opencode'].read_bytes()+b'\n'+f.rules[0])
        q=org.plan_organize(dict(f.req,agents=['opencode']))['approval_plan'];self.assertFalse(next(g for g in q['groups'] if g['sources'][0]['text'].encode()==f.rules[0])['existing_public'])

    def test_actual_cli_stable_mapping_view_zero_write_and_exclude(self):
        from contextlib import redirect_stdout
        f=self.f;file=f.area/'equivalence.json';file.write_text(json.dumps(self.declarations));args=['organize-user-memory','--equivalent-sources-file',str(file)]
        for agent in f.native:args+=['--agent',agent]
        def call(extra):
            out=io.StringIO()
            with patch.dict(os.environ,HOME=str(f.home)),redirect_stdout(out):
                rc=org.cli(args+extra,home=f.home)
            return rc,json.loads(out.getvalue())
        rc,shown=call([]);self.assertEqual(rc,5,shown);p=shown['approval_plan'];planfile=f.area/'shown.json';planfile.write_text(json.dumps(p));before=uninstall.recovery.tree(f.home)
        rc,view=call(['--selection','查看3']);self.assertEqual(rc,0,view);self.assertEqual(uninstall.recovery.tree(f.home),before)
        self.assertEqual([g['group_id'] for g in p['groups']],[g['group_id'] for g in view['approval_plan']['groups']]);self.assertIn(f.rules[2].decode().strip(),view['prompt'])
        rc,done=call(['--selection','不合并2','--selection-plan-file',str(planfile),'--selection-reference','Synthetic actual choice: 不合并2'])
        self.assertEqual(rc,0,done);self.assertEqual(len(memory_share._available_migrations(f.runtime)),30)
        for native in f.native.values():self.assertIn(f.rules[1],native.read_bytes())
        (EVIDENCE/'six-agent-cli-choice.json').write_text(json.dumps({'preview_prompt':shown['prompt'],'view_prompt':view['prompt'],'result_status':done['status'],'records':30},ensure_ascii=False,indent=2))

    def test_partial_wrong_hash_overlap_and_source_drift_zero_write(self):
        f=self.f
        for mode in ('partial','hash','overlap','context'):
            declarations=copy.deepcopy(self.declarations)
            if mode=='partial':declarations[0]['sources'].pop()
            if mode=='hash':declarations[0]['sources'][0]['basis']='0'*64
            if mode=='overlap':declarations[0]['sources'].append(declarations[0]['sources'][0])
            if mode=='context':declarations[0]['sources'][0]['context']=[]
            before=uninstall.recovery.tree(f.home);result=org.plan_organize(dict(self.req,equivalent_sources=declarations));self.assertEqual(result['status'],'failed',mode);self.assertEqual(uninstall.recovery.tree(f.home),before)
        p=org.plan_organize(self.req)['approval_plan'];f.native['codex'].write_bytes(f.native['codex'].read_bytes()+b'\nsource drift')
        before=uninstall.recovery.tree(f.home);self.assertEqual(org.execute_organize(p,approved(p),request=self.req)['status'],'failed');self.assertEqual(uninstall.recovery.tree(f.home),before)
