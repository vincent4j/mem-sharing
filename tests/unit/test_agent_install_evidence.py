"""Signature-independent discovery through real installer, synthetic HOME only."""
import json
import plistlib
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'scripts'))
sys.path.insert(0,str(Path(__file__).resolve().parent))
import test_m404_install as install_fixture
from agm_core import detect, user_entries, user_install

class LocalEvidenceInstallTests(unittest.TestCase):
    def setUp(self):
        f=install_fixture.InstallFixture();f.setUp();self.addCleanup(f.doCleanups);self.f=f
        self.calls=[]
        def failed_signer(command):
            self.calls.append(command)
            return SimpleNamespace(returncode=3,stdout='',stderr='synthetic signature verification failed')
        f.request['detect_runner']=failed_signer
        self.agents=[a for a in f.config if any(s['kind']=='macos_app_bundle' for s in f.config[a]['installation_signals'])]
        self.assertEqual(len(self.agents),5)
        apps=f.home/'Applications';apps.mkdir()
        for agent in self.agents:
            signal=next(s for s in f.config[agent]['installation_signals'] if s['kind']=='macos_app_bundle')
            bundle=apps/signal['bundle_name'];(bundle/'Contents/MacOS').mkdir(parents=True)
            exe=signal['bundle_name'][:-4]
            info={'CFBundleName':signal['product_name'],'CFBundleDisplayName':signal['product_name'],
                  'CFBundleExecutable':exe,'CFBundleIdentifier':'ai.opencode.desktop' if agent=='opencode' else 'fixture.'+agent,
                  'CFBundleShortVersionString':'2.2.5','CFBundleVersion':'2.2.5'}
            (bundle/'Contents/Info.plist').write_bytes(plistlib.dumps(info))
            path=bundle/'Contents/MacOS'/exe;path.write_text('#!/bin/sh\nexit 0\n');path.chmod(0o755)
        self.original={}
        from agm_core import paths
        for agent in self.agents:
            path=Path(paths.expand_path(f.config[agent]['user_entry'],home=str(f.home)))
            path.parent.mkdir(parents=True,exist_ok=True)
            raw=('# '+agent+' 私有内容\r\n完整保留这段原文。\r\n').encode()
            path.write_bytes(raw);self.original[path]=raw

    def test_auto_five_real_bundles_not_rejected_by_signature_failure(self):
        f=self.f;plan=f.plan()
        self.assertEqual(set(plan['effective_agents']),set(self.agents))
        self.assertEqual(self.calls,[])
        result=f.execute(plan);self.assertEqual(result['status'],'completed',result)
        for path,raw in self.original.items():self.assertIn(raw,path.read_bytes())
        data=json.loads(f.runtime.registry.read_text())
        self.assertEqual(set(data['machine']['agents']),set(self.agents))
        statuses=user_entries.connection_status(f.runtime,f.config,data,self.agents)
        self.assertTrue(all(v['status']=='connected' for v in statuses.values()))
        self.assertFalse((f.home/'.claude').exists())
        self.assertEqual(self.calls,[])

    def test_explicit_targets_use_same_local_evidence_and_keep_originals(self):
        self.f.request['agents']=self.agents
        plan=self.f.plan();self.assertEqual(set(plan['effective_agents']),set(self.agents))
        result=self.f.execute(plan);self.assertEqual(result['status'],'completed',result)
        for path,raw in self.original.items():self.assertIn(raw,path.read_bytes())
        self.assertEqual(self.calls,[])

    def test_external_edit_after_preview_still_rejects_without_overwriting(self):
        f=self.f;f.request['agents']=['workbuddy'];plan=f.plan()
        path=next(p for p in self.original if '.workbuddy' in str(p))
        raw=path.read_bytes()+b'foreign edit';path.write_bytes(raw)
        with self.assertRaises(ValueError):f.execute(plan)
        self.assertEqual(path.read_bytes(),raw);self.assertFalse(f.runtime.registry.exists())

    def test_interrupted_signature_independent_install_reuses_rollback(self):
        f=self.f;f.request['agents']=['workbuddy'];plan=f.plan();seen=[]
        def fail(event,path):
            if event=='after_entries' and not seen:
                seen.append(True);raise RuntimeError('synthetic interrupted install')
        with self.assertRaises(RuntimeError):f.execute(plan,fail)
        done=f.recover(plan['journal'],'rollback');self.assertEqual(done['status'],'rolled_back',done)
        for path,raw in self.original.items():self.assertEqual(path.read_bytes(),raw)
        self.assertFalse(f.runtime.registry.exists())

    def test_bundle_executable_link_cannot_escape_application(self):
        f=self.f
        native=f.home/'Applications/WorkBuddy.app/Contents/MacOS/WorkBuddy'
        outside=f.area/'outside-executable';outside.write_text('#!/bin/sh\n');outside.chmod(0o755)
        native.unlink();native.symlink_to(outside)
        f.request['agents']=['workbuddy']
        with self.assertRaises(ValueError):f.plan()
        for path,raw in self.original.items():self.assertEqual(path.read_bytes(),raw)
        self.assertFalse(f.runtime.registry.exists())

    def test_product_source_hash_and_install_lock_remain_hard_gates(self):
        f=self.f
        source=f.request['source'];name='scripts/agm_core/detect.py'
        original=source['files'][name];source['files'][name]='0'*64
        with self.assertRaises(ValueError):f.plan()
        source['files'][name]=original
        (f.home/'.mem-sharing-install.lock').mkdir()
        with self.assertRaises(ValueError):f.plan()
        for path,raw in self.original.items():self.assertEqual(path.read_bytes(),raw)
        self.assertFalse(f.runtime.registry.exists())

    def test_empty_config_is_not_installed_and_untrusted_bundle_path_rejected(self):
        f=self.f
        empty=f.home/'.claude';empty.mkdir()
        record=detect.detect_agents(f.config,['claude'],home=str(f.home),search_paths=[],app_directories=[])['agents']['claude']
        self.assertEqual(record['status'],'unknown')
        bundle=f.home/'Applications/WorkBuddy.app';info=bundle/'Contents/Info.plist'
        body=plistlib.loads(info.read_bytes());body['CFBundleExecutable']='../../outside'
        info.write_bytes(plistlib.dumps(body))
        f.request['agents']=['workbuddy']
        with self.assertRaises(ValueError):f.plan()
        for path,raw in self.original.items():self.assertEqual(path.read_bytes(),raw)

if __name__=='__main__':unittest.main()
