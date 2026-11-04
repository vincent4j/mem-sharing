"""Actual pinned historical producer subprocesses, isolated HOME and code trees."""
import copy
import hashlib
import json
import os
import shutil
import subprocess
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent))
import test_m404_install as fixtures
from runtime_fixture import seed_project_executors
from agm_core import uninstall, uninstall_recovery as recovery, memory_share as share
from test_uninstall import approval
PIN='1b995587aeb1e55eed6f8a79e116c40541ff9103'
REPO=Path(__file__).resolve().parents[2]

class HistoricalExitTests(unittest.TestCase):
    def setUp(self):
        f=fixtures.InstallFixture();f.setUp();self.addCleanup(f.doCleanups);self.f=f
        # All shipped code/docs are actual fixed Git objects, not modified current code.
        shutil.rmtree(f.source); f.source.mkdir()
        names=subprocess.check_output(['git','-C',str(REPO),'ls-tree','-r','--name-only',PIN],text=True).splitlines()
        shipped={'SKILL.md','README.md','INSTALL.md','llms.txt','DESIGN.md','docs/architecture.md','docs/operations.md','docs/uninstall-design.md'}
        for name in names:
            if not (name.startswith('scripts/') or name in shipped):continue
            p=f.source/name;p.parent.mkdir(parents=True,exist_ok=True)
            p.write_bytes(subprocess.check_output(['git','-C',str(REPO),'show',PIN+':'+name]))
        f.request['source'].update(commit=PIN,files={str(p.relative_to(f.source)):hashlib.sha256(p.read_bytes()).hexdigest() for p in f.source.rglob('*') if p.is_file()})
        f.request.update(seed_project_executors(f.home));f.request['agents']=['codex','claude']
        self.native={}
        for agent,name in [('codex','AGENTS.md'),('claude','CLAUDE.md')]:
            p=f.home/('.'+agent)/name;p.parent.mkdir(exist_ok=True);p.write_text('# 约定\n\n- 提交信息使用中文。\n')
            self.native[agent]=p
        self.assertEqual(f.execute()['status'],'completed')
        self.env=dict(os.environ,HOME=str(f.home),PATH=os.pathsep.join(f.request['search_paths']))
        scan=self.old('share-user-memory')
        self.text='- 提交信息使用中文。\n'
        parts=[p for p in scan['segments'] if p['text']==self.text]
        proposal={'schema_version':1,'basis':scan['basis'],'groups':[{'summary':'中文提交','same_content':True,'items':[{'agent':p['agent'],'start':p['start'],'end':p['end']} for p in parts]}]}
        p=f.area/'proposal.json';p.write_text(json.dumps(proposal))
        result=self.old('share-user-memory','--proposal-file',str(p))
        self.shared=self.apply_old(result['approval_plan'],'share-user-memory')
        self.assertEqual(self.shared['status'],'completed',self.shared)

    def old(self, command,*flags):
        f=self.f
        run=subprocess.run([sys.executable,'-B',str(f.runtime.code/'scripts/memory_share.py'),command,'--home',str(f.home),'--agent','codex','--agent','claude',*flags],env=self.env,capture_output=True,text=True)
        result=json.loads(run.stdout);self.assertIn(run.returncode,(0,5),(result,run.stderr));return result

    def apply_old(self,plan,command,extra=()):
        path=self.f.area/('approve-'+command+'.json');path.write_text(json.dumps(dict(plan,confirmed_at='2026-11-04T11:00:00Z',reference='synthetic actual historical producer approval')))
        # Historical approval CLI forbids mixing new participant flags.
        run=subprocess.run([sys.executable,'-B',str(self.f.runtime.code/'scripts/memory_share.py'),command,'--home',str(self.f.home),'--approval-file',str(path),*extra],env=self.env,capture_output=True,text=True)
        result=json.loads(run.stdout);self.assertEqual(run.returncode,0,(result,run.stderr));return result

    def exit(self):
        f=self.f; before=recovery.tree(f.home); backup=f.area/'exit'
        plan=uninstall.preview(home=f.home,backup_dir=backup)
        self.assertEqual(recovery.tree(f.home),before)
        result=uninstall.execute(approval(recovery.summary(plan)),home=f.home,backup_dir=backup)
        self.assertEqual(result['status'],'completed')
        for p in self.native.values():
            raw=p.read_bytes();self.assertIn(self.text.encode(),raw);self.assertNotIn(share.ENTRY_MARKER['start'],raw)
        r=recovery.recover(backup/'manifest.json')
        self.assertEqual(recovery.recover(backup/'manifest.json',approval=approval(r['plan']))['status'],'restored')
        self.assertEqual(recovery.tree(f.home),before)

    def test_historical_created_entry_is_consumed_by_formal_uninstall(self):
        self.assertIn(share.ENTRY_MARKER['start'],self.native['codex'].read_bytes())
        self.exit()

    def return_old(self):
        f=self.f;topic=f.runtime.root/'memories/user-rules.md';raw=topic.read_bytes()
        available=share._available_migrations(f.runtime)
        rp={'schema_version':1,'basis':{str(topic):share.entries.sha256(raw)},'items':[],'remove_entries':True}
        for (name,i),record in available.items():
            start,end=record['public_offset'],record['public_end']
            rp['items'].append({'ref':name,'migration':i,'public_span':{'start':start,'end':end,'text_hex':raw[start:end].hex()},'target':{'path':record['path'],'mode':'in_place'}})
        path=f.area/'return.json';path.write_text(json.dumps(rp))
        result=self.old('return-user-memory','--return-plan-file',str(path))
        return self.apply_old(result['approval_plan'],'return-user-memory',('--return-plan-file',str(path)))

    def test_historical_return_retires_stale_import_without_V_washing(self):
        before=self.f.runtime.registry.read_bytes();self.return_old()
        self.assertEqual(self.f.runtime.registry.read_bytes(),before)
        self.assertNotIn(b'@'+str(self.f.runtime.root/'memories/MEMORY.md').encode(),self.native['claude'].read_bytes())
        self.exit()

    def assert_rejected_zero_write(self):
        before=recovery.tree(self.f.home)
        with self.assertRaises(ValueError):uninstall.preview(home=self.f.home,backup_dir=self.f.area/'rejected')
        self.assertEqual(recovery.tree(self.f.home),before)
        self.assertFalse((self.f.area/'rejected').exists())

    def test_created_entry_missing_proof_or_native_drift_is_zero_write(self):
        manifest=Path(self.shared['manifest']);original=manifest.read_bytes()
        data=json.loads(original);data['operation_metadata']['share_user_memory']['entries_created']=[]
        manifest.write_text(json.dumps(data));self.assert_rejected_zero_write();manifest.write_bytes(original)
        data=json.loads(original);data['operation_metadata']['share_user_memory']['entries_created'][0]['bytes_hex']=b'unknown'.hex()
        manifest.write_text(json.dumps(data));self.assert_rejected_zero_write();manifest.write_bytes(original)
        path=self.native['codex'];path.write_bytes(path.read_bytes()+b'new unapproved private text\n')
        self.assert_rejected_zero_write()

    def test_retired_import_wrong_refs_backup_or_resealed_private_drift_reject(self):
        result=self.return_old();manifest=Path(result['manifest']);original=manifest.read_bytes()
        data=json.loads(original);row=next(r for r in data['entries'] if r['path']==str(self.native['claude']))
        for change in ('missing','wrong_index','after'):
            candidate=copy.deepcopy(data)
            if change=='missing':candidate['operation_metadata']['return_user_memory']['consumed'][0]['manifest']='missing'
            elif change=='wrong_index':candidate['operation_metadata']['return_user_memory']['consumed'][0]['migration']=99999
            else:next(r for r in candidate['entries'] if r['path']==str(self.native['claude']))['after']['fingerprint']='0'*64
            manifest.write_text(json.dumps(candidate));self.assert_rejected_zero_write();manifest.write_bytes(original)
        backup=manifest.parent/row['before']['backup'];raw=backup.read_bytes()
        backup.write_bytes(raw+b'drift');self.assert_rejected_zero_write();backup.write_bytes(raw)
        path=self.native['claude'];path.write_bytes(path.read_bytes()+b'new unapproved private text\n')
        candidate=copy.deepcopy(data)
        next(r for r in candidate['entries'] if r['path']==str(path))['after']['fingerprint']=share.entries.sha256(path.read_bytes())
        manifest.write_text(json.dumps(candidate));self.assert_rejected_zero_write()
