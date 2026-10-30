"""M2-06 tests: every registry, entry and memory asset is a temp fixture."""
import copy
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'scripts'))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "unit"))
from runtime_fixture import seed_runtime, installed_registry
from agm_core.entries import sha256, link_fingerprint
from agm_core.paths import load_agents_table, select_platform
from agm_core.project import resolve_project
from agm_core.registry import empty_registry, new_project, serialize_registry, load_registry
from agm_core.remove import plan_remove, run, RemoveError

START, END = '<!-- test:start -->', '<!-- test:end -->'
BLOCK = (START + '\r\nowned\r\n' + END).encode()


class RemoveFixture(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.repo = self.root / 'repo'
        self.repo.mkdir()
        subprocess.run(['git', 'init', '-q', str(self.repo)], check=True, capture_output=True)
        self.identity = resolve_project(self.repo)
        self.home = self.root / 'home'
        self.home.mkdir()
        self.runtime = seed_runtime(self.home)
        self.install = self.runtime.var
        self.registry = self.install / 'registry.json'
        self.manifest = self.install / 'creation.json'
        self.manifest.write_text('{}')
        self.config = select_platform(load_agents_table(), 'darwin')
        self.request = {'project': str(self.repo), 'home': str(self.home),
                        'platform_config': self.config, 'approval': None}
        self.data = installed_registry()
        self.main = str(self.repo)
        self.data['projects'][self.main] = new_project(self.identity, ['codex'])
        self.assembly = self.data['projects'][self.main]['checkouts'][self.main]
        self.store = self.repo / 'docs/context-keeper'
        self.store.mkdir(parents=True)
        (self.store / 'memory-keeper.md').write_bytes(b'private memory')
        self.assembly['store']['path'] = str(self.store)
        self.entry = self.repo / 'AGENTS.md'
        self.entry.write_bytes(b'\xef\xbb\xbfoutside\xff\r\n' + BLOCK + b'\r\nnew user text')
        self.add_object('block', self.entry)

    def add_object(self, kind, path, ownership='created', oid=None):
        block = kind in ('block', 'user_convention')
        link = kind == 'skill_symlink'
        target = str(path.resolve()) if link else None
        obj = {'kind': kind, 'path': str(path), 'scope': 'project', 'agents': ['codex'],
               'ownership': ownership, 'marker': {'start': START, 'end': END} if block else None,
               'fingerprint': {'algorithm': 'sha256', 'basis': 'block_bytes' if block else ('link_target' if link else 'file_bytes'),
                               'value': sha256(BLOCK) if block else (link_fingerprint(target) if link else sha256(path.read_bytes()))},
               'original_existed': ownership == 'reused', 'link_target': target,
               'backup_manifest': str(self.manifest) if ownership == 'created' else None,
               'consumers': [self.main]}
        if ownership == 'unknown':
            obj['original_existed'] = None
        self.assembly['objects'][oid or str(path)] = obj
        return obj

    def save(self):
        allowed = [str(self.home / '.codex/AGENTS.md')]
        self.registry.write_bytes(serialize_registry(self.data, allowed_user_paths=allowed))

    def call(self, **kwargs):
        return run(self.request, registry_path=self.registry, **kwargs)

    def approve(self):
        self.save()
        preview = self.call()
        self.assertEqual(preview['status'], 'approval_required', preview)
        self.request['approval'] = {'command': 'remove-memory', 'main_checkout': self.main,
            'checkout': self.main, 'git_common_dir': str(self.identity.git_common_dir), 'agents': ['codex'],
            'memory_authorization': None, 'store_path': str(self.store), 'provider_source': None,
            'provider_fingerprints': [], 'changes': [{k: v for k, v in c.items() if k in
              ('path', 'operation', 'before_fingerprint', 'after_fingerprint')} for c in preview['changes']]}
        return preview


class RemoveUnitTests(RemoveFixture):
    def test_block_outside_bytes_and_input_unchanged(self):
        original = copy.deepcopy(self.data)
        updated, changes, _ = plan_remove(self.data, self.identity)
        self.assertEqual(self.data, original)
        self.assertEqual(changes[0].after.data, b'\xef\xbb\xbfoutside\xff\r\n\r\nnew user text')
        self.assertEqual(updated['projects'][self.main]['checkouts'][self.main]['objects'], {})

    def test_reused_unknown_and_import_preserved(self):
        for ownership in ('reused', 'unknown'):
            obj = self.assembly['objects'][str(self.entry)]
            obj.update(ownership=ownership, original_existed=True if ownership == 'reused' else None)
            updated, changes, warnings = plan_remove(self.data, self.identity)
            self.assertEqual(updated, self.data)
            self.assertEqual(changes, [])
            self.assertTrue(warnings)
        path = self.repo / 'CLAUDE.md'
        path.write_bytes(b'@AGENTS.md\n')
        self.add_object('import', path, 'reused')
        self.assertFalse(plan_remove(self.data, self.identity)[1])

    def test_created_drift_missing_duplicate_and_wrong_type(self):
        for content in (BLOCK.replace(b'owned', b'edited'), BLOCK + BLOCK, b'absent markers'):
            self.entry.write_bytes(content)
            with self.assertRaises(RemoveError) as caught:
                plan_remove(self.data, self.identity)
            self.assertEqual(caught.exception.code, 'drift')
        self.entry.unlink()
        with self.assertRaises(RemoveError):
            plan_remove(self.data, self.identity)
        self.entry.symlink_to(self.store)
        with self.assertRaises(RemoveError):
            plan_remove(self.data, self.identity)

    def test_protect_store_and_context_keeper_json_even_claimed_created(self):
        for path in (self.store / 'memory-keeper.md', self.repo / 'context-keeper.json'):
            path.write_bytes(b'asset')
            self.add_object('file', path)
            with self.assertRaises(RemoveError) as caught:
                plan_remove(self.data, self.identity)
            self.assertEqual(caught.exception.code, 'protected_memory_asset')
            del self.assembly['objects'][str(path)]

    def test_two_blocks_same_file_one_change(self):
        other_start, other_end = '<!-- second:start -->', '<!-- second:end -->'
        other = (other_start + 'two' + other_end).encode()
        self.entry.write_bytes(BLOCK + b'outside' + other)
        obj = self.add_object('block', self.entry, oid='second')
        obj['marker'] = {'start': other_start, 'end': other_end}
        obj['fingerprint']['value'] = sha256(other)
        changes = plan_remove(self.data, self.identity)[1]
        self.assertEqual(len(changes), 1)
        self.assertEqual(changes[0].after.data, b'outside')

    def test_shared_created_drift_refuses_consumer_release(self):
        path = self.home / 'user-entry'
        path.write_bytes(b'edited')
        obj = copy.deepcopy(self.assembly['objects'][str(self.entry)])
        obj.update(scope='user', kind='user_convention', path=str(path))
        self.data['shared_objects']['shared'] = obj
        self.assembly['shared_object_ids'] = ['shared']
        with self.assertRaises(RemoveError) as caught:
            plan_remove(self.data, self.identity)
        self.assertEqual(caught.exception.code, 'drift')
        self.assertEqual(obj['consumers'], [self.main])

    def test_private_auto_memory_guard(self):
        path = self.repo / '.codex/memories/topic.md'
        path.parent.mkdir(parents=True)
        path.write_bytes(b'private')
        self.add_object('file', path)
        with self.assertRaises(RemoveError) as caught:
            plan_remove(self.data, self.identity)
        self.assertEqual(caught.exception.code, 'protected_memory_asset')

    def test_whole_file_and_reused_unit_overlap_refused(self):
        self.add_object('file', self.entry, oid='whole')
        with self.assertRaises(RemoveError):
            plan_remove(self.data, self.identity)


if __name__ == '__main__':
    unittest.main()
