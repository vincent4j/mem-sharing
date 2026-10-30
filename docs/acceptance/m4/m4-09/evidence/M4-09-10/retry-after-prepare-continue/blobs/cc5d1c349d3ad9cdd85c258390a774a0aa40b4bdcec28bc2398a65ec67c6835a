"""Project transactions preserve CK assets and never execute upstream scripts."""
import json
import sys
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'unit'))
from test_m204_enable import EnableFixture
from agm_core import enable


class SubprocessTests(EnableFixture):
    def test_registry_last_and_single_committed_manifest(self):
        events=[];self.request['transaction_hook']=lambda event,path:events.append((event,path))
        self.apply('follow_ck',True)
        self.assertEqual([p for e,p in events if e=='before_write'][-1],self.runtime.registry)
        manifests=list(self.runtime.backups.rglob('manifest.json'))
        self.assertEqual(len(manifests),1);self.assertEqual(json.loads(manifests[0].read_bytes())['status'],'committed')
        self.assertFalse(self.runtime.lock.exists())

    def test_upstream_scripts_and_partial_store_never_called_or_mutated(self):
        sentinel=self.source/'called'
        for name in ('install.py','context_keeper_probe.py'):
            (self.source/'scripts'/name).write_text('from pathlib import Path\nPath('+repr(str(sentinel))+').write_text("called")\nraise SystemExit(3)')
        store=self.root/'docs/context-keeper';store.mkdir(parents=True);(store/'memory-keeper.md').write_bytes(b'partial data')
        self.request.pop('runner');self.apply('follow_ck',True)
        self.assertFalse(sentinel.exists());self.assertEqual((store/'memory-keeper.md').read_bytes(),b'partial data')
        self.assertFalse((store/'plans').exists())

    def test_config_fault_rolls_back_and_preserves_old_registry(self):
        plan=self.preview('follow_ck',True);self.request['approval']=plan;before=self.runtime.registry.read_bytes()
        def fail(event,path):
            if event=='before_write' and path==self.root/'CLAUDE.md':raise OSError('injected config fault')
        self.request['transaction_hook']=fail
        self.assertEqual(enable.run(self.request)['status'],'failed')
        self.assertEqual(self.runtime.registry.read_bytes(),before);self.assertFalse((self.root/'AGENTS.md').exists())

    def test_rollback_failure_exposes_manifest_without_overclaim(self):
        plan=self.preview(None);self.request['approval']=plan
        def fail(event,path):
            if event in ('after_write','before_restore'):raise OSError('fault and rollback fault')
        self.request['transaction_hook']=fail
        result=enable.run(self.request);self.assertEqual(result['status'],'recovery_required',result)
        self.assertTrue(Path(result['errors'][0]['recovery']).is_file());self.assertEqual(self.load()['projects'],{})

    def test_identity_change_after_approval_rolls_back(self):
        plan=self.preview(None);self.request['approval']=plan
        original=enable.project.resolve_project;calls=[]
        def changed(*args,**kwargs):
            obj=original(*args,**kwargs);calls.append(1)
            if len(calls)>1:
                from dataclasses import replace
                obj=replace(obj,git_common_dir=self.area)
            return obj
        with patch('agm_core.enable.project.resolve_project',side_effect=changed):
            result=enable.run(self.request)
        self.assertEqual(result['status'],'approval_required',result)
        self.assertFalse((self.root/'AGENTS.md').exists())

    def test_ck_alias_is_never_taken_over(self):
        alias=self.root/'.agents/skills/context-keeper';alias.parent.mkdir(parents=True);alias.symlink_to(self.source)
        before=alias.lstat().st_mtime_ns;self.apply('follow_ck',True)
        self.assertTrue(alias.is_symlink());self.assertEqual(alias.lstat().st_mtime_ns,before)
        objects=self.load()['projects'][str(self.root)]['checkouts'][str(self.root)]['objects']
        self.assertFalse(any(o['kind']=='skill_symlink' for o in objects.values()))

    def test_old_bridge_conversion_preserves_raw_outside_bytes(self):
        raw=b'old rules\xff\r\n';old=enable._block(enable.LEGACY_KEEPER_MARKER,'old CK')
        (self.root/'AGENTS.md').write_bytes(raw+old)
        self.apply('follow_ck',True)
        self.assertTrue((self.root/'AGENTS.md').read_bytes().startswith(raw))
        self.assertNotIn(old,(self.root/'AGENTS.md').read_bytes())

    def test_approved_source_update_is_irrelevant_to_project_policy(self):
        plan=self.preview(None);(self.source/'SKILL.md').write_bytes(b'updated')
        self.request['approval']=plan;self.assertEqual(enable.run(self.request)['status'],'completed')
        self.assertEqual(self.calls,[])
