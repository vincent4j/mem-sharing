"""Explicit semantic decisions reuse proven spans without changing old producer records."""
import copy
import io
from contextlib import redirect_stdout
import json
import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch
from test_m404_install import InstallFixture, approved
from test_m408_installer import cli
from agm_core import detect, user_rules_organize as org, legacy_import as legacy
from agm_core import uninstall_recovery as recovery

PIN='ed3fd58be3107b0180f7ac4f5a64be96eca46942'

class ExplicitReuseTests(InstallFixture):
    def setUp(self):
        super().setUp()
        # Exact fixed historical managed bytes, not a copy of the new working kernel.
        repo=Path(__file__).resolve().parents[2]
        names=subprocess.check_output(['git','-C',str(repo),'ls-tree','-r','--name-only',PIN],text=True).splitlines()
        from agm_core.plugin_release import managed_source
        for name in names:
            if managed_source(name):
                p=self.source/name;p.parent.mkdir(parents=True,exist_ok=True)
                p.write_bytes(subprocess.check_output(['git','-C',str(repo),'show',PIN+':'+name]))
        self.request['source'].update(commit=PIN,version='0.1.7',files={str(p.relative_to(self.source)):legacy.digest(p.read_bytes()) for p in self.source.rglob('*') if p.is_file()})
        real=detect.detect_agents
        def installed(*args,**kwargs):
            kwargs.update(search_paths=[],app_directories=[])
            d=real(*args,**kwargs)
            for row in d['agents'].values():row['status']='installed'
            return d
        m=patch.object(detect,'detect_agents',side_effect=installed);m.start();self.addCleanup(m.stop)
        self.raw=b'- Keep the complete original user rule.\n'
        self.codex=self.home/'.codex/AGENTS.md';self.codex.parent.mkdir();self.codex.write_bytes(b'# User rules\n\n'+self.raw)
        self.open=self.home/'.config/opencode/AGENTS.md';self.open.parent.mkdir(parents=True);self.open.write_bytes(b'# General rules\n\n- Extra constraint stays.\n\n'+self.raw+self.raw)
        self.execute()
        self.req={k:v for k,v in self.request.items() if k in ('home','platform_config','search_paths','app_directories')}
        req=dict(self.req,agents=['codex'],selection='共享 1');p=org.plan_organize(req)['approval_plan'];org.execute_organize(p,approved(p),request=req)
        self.topic=self.runtime.root/'memories/user-rules.md';self.public=self.topic.read_bytes()
        self.req.update(agents=['opencode'])
        original=org.plan_organize(self.req)['approval_plan'];items=[i for i in original['items'] if i['text'].encode()==self.raw]
        records=__import__('agm_core.memory_share',fromlist=['x'])._available_migrations(self.runtime)
        target=next(iter(records.values()))
        self.bindings=[{'source':i['source'],'start':i['start'],'end':i['end'],'source_context':i['context'],
            'public_start':target['public_offset'],'public_end':target['public_end'],'public_context':target['context'],
            'source_basis':legacy.digest(self.open.read_bytes()),'public_basis':legacy.digest(self.public),
            'text_sha256':i['sha256'],'equivalent':True,'reason':'Agent read both complete sections: both are global user constraints.'} for i in items]

    def reuse_plan(self,bindings=None):
        return org.plan_organize(dict(self.req,public_reuse=self.bindings if bindings is None else bindings))

    def test_explicit_reuse_old_ed3_uninstall_and_external_restore(self):
        plain=org.plan_organize(self.req)['approval_plan'];g=next(g for g in plain['groups'] if g['sources'][0]['text'].encode()==self.raw)
        self.assertFalse(g['existing_public']);self.assertNotIn(g['number'],plain['selected_numbers'])
        p=self.reuse_plan()['approval_plan'];done=org.execute_organize(p,approved(p),request=dict(self.req,public_reuse=self.bindings))
        self.assertEqual(self.topic.read_bytes(),self.public);self.assertNotIn(self.raw,self.open.read_bytes());self.assertIn(b'# General rules\n\n- Extra constraint stays.',self.open.read_bytes())
        records=json.loads(Path(done['manifest']).read_text())['operation_metadata']['share_user_memory']['migrations']
        self.assertEqual(len(records),2);self.assertTrue(all(r['context']==[[1,'General rules',1]] for r in records))
        # Exact ed3 consumer, from installed C, restores the original section and both occurrences.
        before=recovery.tree(self.home);backup=self.area/'exit';cmd=[sys.executable,'-B',str(self.runtime.code/'scripts/agm.py'),'uninstall-machine','--backup-dir',str(backup)]
        child=subprocess.run(cmd,capture_output=True,text=True,env=dict(os.environ,HOME=str(self.home)));self.assertEqual(child.returncode,5,child.stdout+child.stderr);view=json.loads(child.stdout)['plan']
        a=self.area/'exit-approval.json';a.write_text(json.dumps({'plan':view,'reference':'explicit fixture exit','confirmed_at':'2026-11-05T00:00:00Z'}))
        child=subprocess.run(cmd+['--approval-file',str(a)],capture_output=True,text=True,env=dict(os.environ,HOME=str(self.home)));self.assertEqual(child.returncode,0,child.stdout+child.stderr)
        self.assertEqual(self.open.read_bytes().count(self.raw),2);self.assertIn(b'# General rules',self.open.read_bytes())
        tool=[sys.executable,'-I','-S','-B',str(backup/'recover.py'),'--manifest',str(backup/'manifest.json'),'--action','restore'];child=subprocess.run(tool,capture_output=True,text=True,env=dict(os.environ,HOME=str(self.home)));self.assertEqual(child.returncode,5,child.stdout)
        a.write_text(json.dumps({'plan':json.loads(child.stdout)['plan'],'reference':'explicit fixture restore','confirmed_at':'2026-11-05T00:00:00Z'}));child=subprocess.run(tool+['--approval-file',str(a)],capture_output=True,text=True,env=dict(os.environ,HOME=str(self.home)));self.assertEqual(child.returncode,0,child.stdout+child.stderr);self.assertEqual(recovery.tree(self.home),before)
        # A fresh identical occurrence under the same alternate heading is NOT a permanent alias.
        self.open.write_bytes(self.open.read_bytes()+self.raw)
        p=org.plan_organize(self.req)['approval_plan'];g=next(g for g in p['groups'] if g['sources'][0]['text'].encode()==self.raw);self.assertFalse(g['existing_public'])

    def test_cli_reuse_file_and_original_ed3_return_consumer(self):
        evidence=self.area/'reuse.json';evidence.write_text(json.dumps(self.bindings))
        out=io.StringIO()
        with patch.dict(os.environ,HOME=str(self.home)),redirect_stdout(out):
            rc=org.cli(['organize-user-memory','--agent','opencode','--public-reuse-file',str(evidence)],home=self.home)
        self.assertEqual(rc,5,out.getvalue());shown=json.loads(out.getvalue())['approval_plan']
        self.assertEqual(shown['request']['public_reuse'],self.bindings)
        self.assertIn('需要你确认是否合并' if not shown['default_numbers'] else '建议合并的相同规则',org.present(shown))
        self.assertIn('来源：',org.present(shown))
        org.execute_organize(shown,approved(shown),request=dict(self.req,public_reuse=self.bindings))
        from agm_core.memory_share import _available_migrations
        refs=[(key,record) for key,record in _available_migrations(self.runtime).items() if record['path']==str(self.open)]
        proposal={'schema_version':1,'basis':{str(self.topic):legacy.digest(self.topic.read_bytes()),str(self.open):legacy.digest(self.open.read_bytes())},'items':[
            {'ref':key[0],'migration':key[1],'public_span':{'start':record['public_offset'],'end':record['public_end'],'text_hex':record['text_hex']},
             'target':{'path':str(self.open),'mode':'in_place'}} for key,record in refs]}
        file=self.area/'return.json';file.write_text(json.dumps(proposal))
        cmd=[sys.executable,'-B',str(self.runtime.code/'scripts/memory_share.py'),'return-user-memory','--agent','opencode','--return-plan-file',str(file)]
        env=dict(os.environ,HOME=str(self.home));child=subprocess.run(cmd,capture_output=True,text=True,env=env);self.assertEqual(child.returncode,5,child.stdout+child.stderr)
        result=json.loads(child.stdout);plan=result['approval_plan'];a=self.area/'return-approval.json';a.write_text(json.dumps(approved(plan)))
        child=subprocess.run([sys.executable,'-B',str(self.runtime.code/'scripts/memory_share.py'),'return-user-memory','--approval-file',str(a),'--return-plan-file',str(file)],capture_output=True,text=True,env=env)
        self.assertEqual(child.returncode,0,child.stdout+child.stderr);self.assertEqual(self.open.read_bytes().count(self.raw),2);self.assertIn(b'# General rules',self.open.read_bytes())

    def test_invalid_binding_and_partial_group_are_zero_write(self):
        before=recovery.tree(self.home)
        for field,value in [('source',[]),('source_context',{}),('public_context',{}),('public_context',[[1,'wrong',1]]),('source_context',[[1,'wrong',1]]),('public_start',0),('text_sha256','0'*64),('equivalent',False),('source_basis','0'*64),('public_basis','0'*64)]:
            with self.subTest(field=field,value=value):
                b=copy.deepcopy(self.bindings);b[0][field]=value;out=self.reuse_plan(b);self.assertEqual(out['status'],'failed',out);self.assertEqual(recovery.tree(self.home),before)
        self.assertEqual(self.reuse_plan(self.bindings[:1])['status'],'failed');self.assertEqual(recovery.tree(self.home),before)

    def test_source_and_public_drift_reject_approved_plan(self):
        for target in [self.open,self.topic]:
            p=self.reuse_plan()['approval_plan'];original=target.read_bytes();target.write_bytes(original+b'private concurrent addition\n');before=recovery.tree(self.home)
            self.assertEqual(self.reuse_plan()['status'],'failed')
            result=org.execute_organize(p,approved(p),request=dict(self.req,public_reuse=self.bindings));self.assertEqual(result['status'],'failed');self.assertEqual(recovery.tree(self.home),before);target.write_bytes(original)
