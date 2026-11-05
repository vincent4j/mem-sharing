"""Exact generated-topic proofs; synthetic 36-source exit/reinstall lifecycle."""
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch
from test_m404_install import InstallFixture, approved
from test_uninstall import approval
from agm_core import detect, paths, user_rules_organize as org
from agm_core import uninstall, uninstall_memory as memory, memory_share as share
from agm_core import uninstall_recovery as recovery

class GeneratedWrapperTests(InstallFixture):
    def setUp(self):
        super().setUp();real=detect.detect_agents
        def installed(*args,**kwargs):
            kwargs.update(search_paths=[],app_directories=[]);d=real(*args,**kwargs)
            for row in d['agents'].values():row['status']='installed'
            return d
        mock=patch.object(detect,'detect_agents',side_effect=installed);mock.start();self.addCleanup(mock.stop)
        self.rules=[('%d. 完整合成规则%d。\n'%(n,n)).encode() for n in range(1,7)];self.native={};self.original={}
        for agent,cfg in self.config.items():
            p=Path(paths.expand_path(cfg['user_entry'],home=str(self.home)));p.parent.mkdir(parents=True,exist_ok=True)
            head='# 通用规则\n\n- Agent 专属三条保持。\n\n' if agent=='opencode' else '# 用户规则\n\n'
            raw=('# 专属规则\n\n'+agent+' Skill 私文保留。\n\n'+head).encode()+b'\n'.join(self.rules)
            p.write_bytes(raw);self.native[agent]=p;self.original[agent]=raw
        self.execute();self.req={k:v for k,v in self.request.items() if k in ('home','platform_config','search_paths','app_directories')};self.topic=self.runtime.root/'memories/user-rules.md'

    def move(self,agents,**kw):
        request=dict(self.req,agents=agents,**kw);plan=org.plan_organize(request)['approval_plan'];done=org.execute_organize(plan,approved(plan),request=request);self.assertEqual(done['status'],'completed',done);return done

    def chain(self):
        self.move(['codex'],selection='共享 1、2、3、4、5、6')
        self.move(['claude','workbuddy','dsh','zcode'])
        req=dict(self.req,agents=['opencode']);p=org.plan_organize(req)['approval_plan'];public=self.topic.read_bytes();target={bytes.fromhex(r['text_hex']):r for r in share._available_migrations(self.runtime).values()};bindings=[]
        for i in p['items']:
            raw=i['text'].encode()
            if raw not in self.rules:continue
            r=target[raw];bindings.append({'source':i['source'],'start':i['start'],'end':i['end'],'source_context':i['context'],'source_basis':share.entries.sha256(self.native['opencode'].read_bytes()),'public_basis':share.entries.sha256(public),'public_start':r['public_offset'],'public_end':r['public_end'],'public_context':r['context'],'text_sha256':i['sha256'],'equivalent':True,'reason':'Synthetic global scopes explicitly compared.'})
        self.assertEqual(len(bindings),6);self.move(['opencode'],public_reuse=bindings)
        self.assertEqual(len(share._available_migrations(self.runtime)),36)

    def test_36_sources_exit_external_restore_fresh_fusion_no_empty_wrappers(self):
        self.chain();before=recovery.tree(self.home);backup=self.area/'exit';plan=uninstall.preview(home=self.home,backup_dir=backup)
        for a,p in self.native.items():
            raw=bytes.fromhex(next(c['after']['hex'] for c in plan['changes'] if c['path']==str(p)))
            self.assertEqual([x for x in raw.splitlines() if x.strip()],[x for x in self.original[a].splitlines() if x.strip()],a)
            if a=='claude': self.assertEqual(raw,self.original[a])
        uninstall.execute(approval(recovery.summary(plan)),home=self.home,backup_dir=backup)
        tool=[sys.executable,'-I','-S','-B',str(backup/'recover.py'),'--manifest',str(backup/'manifest.json'),'--action','restore'];env=dict(os.environ,HOME=str(self.home));child=subprocess.run(tool,capture_output=True,text=True,env=env);self.assertEqual(child.returncode,5,child.stdout)
        a=self.area/'restore.json';a.write_text(json.dumps(approval(json.loads(child.stdout)['plan'])));child=subprocess.run(tool+['--approval-file',str(a)],capture_output=True,text=True,env=env);self.assertEqual(child.returncode,0,child.stdout);self.assertEqual(recovery.tree(self.home),before)
        second=self.area/'exit2';p=uninstall.preview(home=self.home,backup_dir=second);uninstall.execute(approval(recovery.summary(p)),home=self.home,backup_dir=second)
        self.request['operation_id']='second-fresh';self.execute();self.chain()
        for agent,p in self.native.items():
            raw=p.read_bytes();self.assertNotIn('# 用户规则'.encode(),raw,agent)
            for rule in self.rules:self.assertNotIn(rule,raw)
        self.assertIn('# 通用规则'.encode(),self.native['opencode'].read_bytes())

    def test_user_authored_same_empty_heading_is_not_retired(self):
        self.topic.write_bytes('# 用户规则\n'.encode());self.chain();original=memory.public_sources(self.runtime);_,residual=memory.source_returns(self.runtime,original,{str(p) for p in self.native.values()})
        self.assertIn('# 用户规则'.encode(),bytes.fromhex(residual[str(self.topic)]['hex']))

    def test_inserted_user_body_is_not_retired(self):
        self.chain();self.topic.write_bytes(self.topic.read_bytes()+b'user-authored insertion\n');original=memory.public_sources(self.runtime);_,residual=memory.source_returns(self.runtime,original,{str(p) for p in self.native.values()})
        self.assertIn(b'user-authored insertion',bytes.fromhex(residual[str(self.topic)]['hex']))

    def test_tampered_producer_context_does_not_prove_wrapper(self):
        self.chain();manifest=next(Path(r['manifest_path']) for r in share._available_migrations(self.runtime).values() if r['agent']=='codex');data=json.loads(manifest.read_text());data['operation_metadata']['share_user_memory']['migrations'][0]['context']=[[1,'fake',1]];manifest.write_text(json.dumps(data));original=memory.public_sources(self.runtime);_,residual=memory.source_returns(self.runtime,original,{str(p) for p in self.native.values()})
        self.assertIn('# 用户规则'.encode(),bytes.fromhex(residual[str(self.topic)]['hex']))

    def test_tampered_public_before_backup_rejects(self):
        self.topic.write_bytes('# 用户规则\n'.encode());self.chain()
        record=next(r for r in share._available_migrations(self.runtime).values() if r['agent']=='codex')
        manifest=Path(record['manifest_path']);data=json.loads(manifest.read_text());row=next(x for x in data['entries'] if x['path']==str(self.topic))
        (manifest.parent/row['before']['backup']).write_bytes(b'tampered before')
        with self.assertRaisesRegex(ValueError,'backup drift'):
            memory.source_returns(self.runtime,memory.public_sources(self.runtime),{str(p) for p in self.native.values()})
