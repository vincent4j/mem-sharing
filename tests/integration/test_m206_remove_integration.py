"""Real temp-file removal transactions, fault injection and O2 lifecycle."""
import copy
import importlib.util
import os
import unittest
from pathlib import Path

spec = importlib.util.spec_from_file_location('m206_fixtures', Path(__file__).parents[1] / 'unit/test_m206_remove.py')
fixtures = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixtures)
from agm_core.entries import sha256
from agm_core.registry import load_registry
from agm_core.transaction import Transaction


class RemoveIntegrationTests(fixtures.RemoveFixture):
    def test_whole_created_file_removed_reused_base_and_import_survive(self):
        whole = self.repo / 'created-rule.md'
        whole.write_bytes(b'created whole file')
        self.add_object('file', whole)
        self.add_object('file', self.entry, 'reused', oid='base')
        imported = self.repo / 'CLAUDE.md'
        imported.write_bytes(b'@AGENTS.md\n')
        self.add_object('import', imported, 'reused')
        self.data['projects'][self.main].update(memory_authorization='yes',
            authorization_evidence={'confirmed_at': '2026-10-29T00:00:00Z', 'reference': 'test approval'})
        self.approve()
        result = self.call()
        self.assertEqual(result['status'], 'completed', result)
        self.assertFalse(whole.exists())
        self.assertEqual(imported.read_bytes(), b'@AGENTS.md\n')
        data = load_registry(self.registry)
        project = data['projects'][self.main]
        self.assertEqual(project['memory_authorization'], 'yes')
        self.assertEqual(project['checkouts'][self.main]['store']['path'], str(self.store))
        self.assertEqual(set(project['checkouts'][self.main]['objects']), {'base', str(imported)})

    def test_corrupt_missing_registry_and_unknown_project_never_infer_ownership(self):
        original = self.entry.read_bytes()
        self.assertEqual(self.call()['status'], 'completed')
        self.registry.write_bytes(b'{bad')
        self.assertEqual(self.call()['errors'][0]['code'], 'registry_invalid')
        self.registry.write_bytes(fixtures.serialize_registry(fixtures.empty_registry()))
        self.assertEqual(self.call()['status'], 'completed')
        self.assertEqual(self.entry.read_bytes(), original)
        self.assertFalse((self.install / 'backups').exists())

    def test_approval_target_rejected_before_registry_read(self):
        from unittest.mock import patch
        self.request['approval'] = {'command': 'remove-memory', 'main_checkout': '/different'}
        with patch('agm_core.remove.load_registry', side_effect=AssertionError('registry accessed')):
            result = self.call()
        self.assertEqual(result['errors'][0]['code'], 'approval_mismatch')

    def test_registry_failure_and_restore_failure_reports_recovery_manifest(self):
        self.approve()
        def factory(**kwargs):
            verify = kwargs['hook']
            def hook(event, path):
                verify(event, path)
                if (event == 'before_write' and path == self.registry or
                        event == 'before_restore' and path == self.entry):
                    raise OSError('injected recovery failure')
            kwargs['hook'] = hook
            return Transaction(**kwargs)
        result = self.call(transaction_factory=factory)
        self.assertEqual(result['status'], 'recovery_required', result)
        manifest = Path(result['errors'][0]['recovery'])
        self.assertTrue(manifest.is_file())
        self.assertTrue(all(not c['applied'] for c in result['changes']))

    def test_success_preserves_memory_and_second_remove_noop(self):
        self.approve()
        result = self.call()
        self.assertEqual(result['status'], 'completed', result)
        self.assertTrue(all(c['applied'] for c in result['changes']))
        self.assertEqual((self.store / 'memory-keeper.md').read_bytes(), b'private memory')
        old = self.registry.read_bytes(), self.registry.stat().st_mtime_ns
        second = self.call()
        self.assertEqual(second['status'], 'completed', second)
        self.assertEqual(second['changes'], [])
        self.assertEqual(old, (self.registry.read_bytes(), self.registry.stat().st_mtime_ns))

    def test_shared_two_consumers_then_zero_keeps_bytes_and_evidence(self):
        other = self.root / 'other'
        other.mkdir()
        subprocess = fixtures.subprocess
        subprocess.run(['git', 'init', '-q', str(other)], check=True, capture_output=True)
        identity = fixtures.resolve_project(other)
        self.data['projects'][str(other)] = fixtures.new_project(identity, ['codex'])
        shared_path = self.home / '.codex/AGENTS.md'
        shared_path.parent.mkdir()
        shared_path.write_bytes(fixtures.BLOCK)
        obj = copy.deepcopy(self.assembly['objects'][str(self.entry)])
        obj.update(scope='user', kind='user_convention', path=str(shared_path), consumers=[self.main, str(other)])
        self.data['shared_objects']['shared'] = obj
        self.assembly['shared_object_ids'] = ['shared']
        self.data['projects'][str(other)]['checkouts'][str(other)]['shared_object_ids'] = ['shared']
        self.approve()
        self.assertEqual(self.call()['status'], 'completed')
        allowed = [str(shared_path)]
        data = load_registry(self.registry, allowed_user_paths=allowed)
        self.assertEqual(data['shared_objects']['shared']['consumers'], [str(other)])
        self.repo, self.identity, self.main = other, identity, str(other)
        self.data = data
        self.assembly = data['projects'][str(other)]['checkouts'][str(other)]
        self.store = None
        self.request.update(project=str(other), approval=None)
        self.save()
        preview = self.call()
        self.request['approval'] = {'command': 'remove-memory', 'main_checkout': str(other), 'checkout': str(other),
            'git_common_dir': str(identity.git_common_dir), 'agents': ['codex'], 'memory_authorization': None,
            'store_path': None, 'provider_source': None, 'provider_fingerprints': [],
            'changes': [{k: v for k, v in c.items() if k in ('path', 'operation', 'before_fingerprint', 'after_fingerprint')} for c in preview['changes']]}
        self.assertEqual(self.call()['status'], 'completed')
        data = load_registry(self.registry, allowed_user_paths=allowed)
        expected = copy.deepcopy(obj)
        expected['consumers'] = []
        self.assertEqual(data['shared_objects']['shared'], expected)
        self.assertEqual(shared_path.read_bytes(), fixtures.BLOCK)

    def test_preview_and_stale_approval_no_outputs_or_backups(self):
        original = self.entry.read_bytes()
        self.approve()
        self.assertEqual(self.entry.read_bytes(), original)
        self.assertFalse((self.install / 'backups').exists())
        self.entry.write_bytes(original + b'new outside')
        result = self.call()
        self.assertEqual(result['errors'][0]['code'], 'approval_mismatch', result)
        self.assertFalse((self.install / 'backups').exists())

    def test_created_relative_symlink_removed_source_survives(self):
        source = self.repo / 'source'
        source.mkdir()
        (source / 'SKILL.md').write_bytes(b'source')
        link = self.repo / 'context-keeper'
        link.symlink_to('source', target_is_directory=True)
        self.add_object('skill_symlink', link)
        self.approve()
        self.assertEqual(self.call()['status'], 'completed')
        self.assertFalse(link.is_symlink())
        self.assertEqual((source / 'SKILL.md').read_bytes(), b'source')

    def test_registry_failure_restores_entries_and_raw_symlink(self):
        source = self.repo / 'source'
        source.mkdir()
        link = self.repo / 'context-keeper'
        link.symlink_to('source', target_is_directory=True)
        self.add_object('skill_symlink', link)
        self.approve()
        before = self.entry.read_bytes(), self.registry.read_bytes()
        def factory(**kwargs):
            verify = kwargs['hook']
            def hook(event, path):
                verify(event, path)
                if event == 'before_write' and path == self.registry:
                    raise OSError('injected registry failure')
            kwargs['hook'] = hook
            return Transaction(**kwargs)
        result = self.call(transaction_factory=factory)
        self.assertEqual(result['status'], 'failed', result)
        self.assertTrue(all(not c['applied'] for c in result['changes']))
        self.assertEqual(before, (self.entry.read_bytes(), self.registry.read_bytes()))
        self.assertEqual(os.readlink(link), 'source')

    def test_late_drift_rejected_before_any_output_write(self):
        self.approve()
        before = self.registry.read_bytes()
        def factory(**kwargs):
            self.entry.write_bytes(b'external edit')
            return Transaction(**kwargs)
        result = self.call(transaction_factory=factory)
        self.assertEqual(result['errors'][0]['code'], 'drift', result)
        self.assertEqual(self.entry.read_bytes(), b'external edit')
        self.assertEqual(self.registry.read_bytes(), before)
        self.assertFalse((self.install / 'backups').exists())

    def test_drift_blocks_all_created_removals(self):
        path = self.repo / 'owned.md'
        path.write_bytes(b'owned')
        self.add_object('file', path)
        self.save()
        self.entry.write_bytes(b'drift')
        result = self.call()
        self.assertEqual(result['errors'][0]['code'], 'drift', result)
        self.assertEqual(path.read_bytes(), b'owned')
        self.assertFalse((self.install / 'backups').exists())


if __name__ == '__main__':
    unittest.main()
