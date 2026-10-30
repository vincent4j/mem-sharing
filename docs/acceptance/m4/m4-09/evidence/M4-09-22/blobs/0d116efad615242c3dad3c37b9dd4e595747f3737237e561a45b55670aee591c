"""Schema3 check: CK absence/policy are healthy; actual entry drift is read-only evidence."""
import json
import os
import subprocess
from pathlib import Path
from unittest.mock import patch
from test_m204_enable import EnableFixture
from agm_core import check, enable, registry, paths


class CheckTests(EnableFixture):
    def call(self, **fields):
        return check.run(dict(self.request, **fields))

    def tree(self):
        return {str(p):(os.readlink(p) if p.is_symlink() else p.read_bytes(),p.lstat().st_mtime_ns)
                for p in self.area.rglob('*') if p.is_file() or p.is_symlink()}

    def codes(self,result):
        return [g['code'] for p in result['projects'] for g in p['gaps']]

    def test_healthy_without_ck_or_store(self):
        self.apply('follow_ck',True)
        import shutil
        shutil.rmtree(self.source)
        result=self.call();self.assertEqual(result['status'],'completed',result)
        self.assertFalse((self.root/'docs/context-keeper').exists())
        self.assertEqual(result['changes'],[])

    def test_disabled_is_not_gap(self):
        self.apply('disabled',True)
        result=self.call();self.assertEqual(result['status'],'completed',result)
        self.assertEqual(result['projects'][0]['memory_policy'],'disabled')

    def test_claude_waiting_actual_use_is_not_gap(self):
        self.request['agents']=None
        self.apply(None)
        self.assertFalse((self.root/'CLAUDE.md').exists())
        self.assertEqual(self.call()['status'],'completed')
        (self.root/'CLAUDE.md').write_bytes(b'preexisting private rules\xff')
        before=self.tree();self.assertEqual(self.call()['status'],'completed');self.assertEqual(self.tree(),before)

    def test_native_directory_pending_not_gap(self):
        self.apply('follow_ck')
        result=self.call();self.assertEqual(result['status'],'completed',result)
        self.assertFalse((self.root/'.workbuddy').exists())

    def test_project_protocol_drift_is_gap(self):
        self.apply('follow_ck',True)
        path=self.root/'AGENTS.md';path.write_bytes(path.read_bytes().replace('职责'.encode(),b'edited'))
        before=self.tree();result=self.call()
        self.assertEqual(result['status'],'gaps',result)
        self.assertIn('object_drifted',self.codes(result))
        self.assertEqual(self.tree(),before)

    def test_missing_workbuddy_pointer_is_gap_and_no_repair(self):
        self.apply('follow_ck',True)
        path=self.root/'.workbuddy/memory/MEMORY.md';path.unlink()
        before=self.tree();result=self.call()
        self.assertEqual(result['status'],'gaps',result);self.assertEqual(before,self.tree())
        self.assertFalse(path.exists())

    def test_claude_reference_missing_is_gap(self):
        self.apply('follow_ck',True);(self.root/'CLAUDE.md').write_bytes(b'custom rules')
        self.assertIn('import_reference_missing',self.codes(self.call()))

    def test_outside_native_bytes_are_not_drift(self):
        self.apply('follow_ck',True)
        path=self.root/'.workbuddy/memory/MEMORY.md';path.write_bytes(path.read_bytes()+b'private\xff\r\n')
        self.assertEqual(self.call()['status'],'completed')

    def test_override_warning_does_not_repair(self):
        self.apply('follow_ck',True);(self.root/'AGENTS.override.md').write_bytes(b'override')
        before=self.tree();result=self.call()
        self.assertTrue(any('override' in w.lower() for w in result['warnings']))
        self.assertEqual(before,self.tree())

    def test_no_write_and_no_keeper_subprocess(self):
        self.apply('follow_ck',True);before=self.tree();original=subprocess.run
        def git_only(command,*args,**kwargs):
            self.assertEqual(command[0],'git');return original(command,*args,**kwargs)
        with patch('subprocess.run',side_effect=git_only),patch('os.mkdir',side_effect=AssertionError('mkdir')):
            result=self.call()
        self.assertEqual(result['status'],'completed',result);self.assertEqual(before,self.tree())

    def test_readonly_tree_check(self):
        self.apply('follow_ck',True)
        targets=[self.root/'AGENTS.md',self.runtime.registry]
        for p in targets:p.chmod(0o400)
        before=self.tree();self.assertEqual(self.call()['status'],'completed');self.assertEqual(before,self.tree())

    def test_registry_corrupt_only_observes(self):
        self.apply('follow_ck',True);self.runtime.registry.write_bytes(b'{broken')
        before=self.tree();result=self.call()
        self.assertIn('registry_unavailable',self.codes(result));self.assertEqual(before,self.tree())

    def test_registry_missing_all_incomplete_and_no_scan(self):
        self.runtime.registry.unlink();before=self.tree();result=self.call(all=True)
        self.assertEqual(result['status'],'gaps');self.assertEqual(result['projects'],[])
        self.assertTrue(any('check_scope_incomplete' in w for w in result['warnings']))
        self.assertEqual(before,self.tree())

    def test_all_only_registered_projects(self):
        self.apply('follow_ck',True)
        other=self.area/'unregistered';other.mkdir();subprocess.run(['git','init','-q',str(other)],check=True)
        before=self.tree();result=self.call(all=True)
        self.assertEqual([p['main_checkout'] for p in result['projects']],[str(self.root)])
        self.assertEqual(before,self.tree())

    def test_identity_mismatch_reported(self):
        self.apply('follow_ck',True);data=self.load();a=data['projects'][str(self.root)]['checkouts'][str(self.root)]
        a['git_common_dir']=str(self.area)
        self.runtime.registry.write_bytes(registry.serialize_registry(data,allowed_user_paths=paths.allowed_user_paths(self.config,None,home=str(self.home))))
        self.assertIn('identity_mismatch',self.codes(self.call()))

    def test_missing_checkout_reported_all(self):
        self.apply('follow_ck',True);self.root.rename(self.area/'moved')
        self.assertIn('checkout_missing',self.codes(self.call(all=True)))

    def test_runtime_passed_only_with_valid_entries(self):
        self.apply('follow_ck',True);data=self.load();a=data['projects'][str(self.root)]['checkouts'][str(self.root)]
        proof=self.area/'proof';proof.write_bytes(b'isolated proof')
        a['runtime_acceptance']={'status':'passed','evidence_path':str(proof)}
        self.runtime.registry.write_bytes(registry.serialize_registry(data,allowed_user_paths=paths.allowed_user_paths(self.config,None,home=str(self.home))))
        self.assertEqual(self.call()['projects'][0]['runtime_acceptance']['status'],'passed')
        (self.root/'CLAUDE.md').write_bytes(b'edited')
        self.assertEqual(self.call()['projects'][0]['runtime_acceptance']['status'],'pending')

    def test_store_and_foreign_skill_never_probed(self):
        self.apply('follow_ck',True)
        (self.root/'context-keeper.json').write_bytes(b'{bad')
        target=self.root/'.codex/skills/context-keeper';target.mkdir(parents=True);(target/'unknown').write_bytes(b'untouched')
        before=self.tree();self.assertEqual(self.call()['status'],'completed');self.assertEqual(before,self.tree())

    def test_invalid_project_failed_no_write(self):
        before=self.tree();result=self.call(project=str(self.area))
        self.assertEqual(result['status'],'failed');self.assertEqual(before,self.tree())

    def test_gap_contract(self):
        result=self.call()
        for project in result['projects']:
            for gap in project['gaps']:self.assertEqual(set(gap),{'code','agent','path','detail','suggestion'})
