"""Synthetic HOME and pinned exported M3 code. No live installation is touched."""
import copy
from functools import lru_cache
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / 'scripts'))
sys.path.insert(0, str(Path(__file__).parent))
from agm_core import migrate, registry, check, enable, remove, paths
from agm_core.entries import sha256
from agm_core.layout import resolve_layout
from agm_core.project import resolve_project
from agm_core.transaction import Transaction, Change, read_snapshot, write_lock, TransactionError
from runtime_fixture import installed_registry

OLD_COMMIT = 'aff8864a62aaa11f654dbbb803d1d62d611a2bc6'
NOW = '2026-10-30T00:00:00Z'
START, END = '<!-- fixture:start -->', '<!-- fixture:end -->'
BLOCK = (START + '\noriginal rule\n' + END).encode()


@lru_cache(maxsize=1)
def legacy_code():
    # Actual pre-M4-02 source, exported rather than patched to mimic an old writer.
    result = subprocess.run(['git', '-C', str(REPO), 'archive', OLD_COMMIT, 'scripts', 'SKILL.md'], capture_output=True)
    if result.returncode:
        raise unittest.SkipTest('Pinned legacy source object is unavailable in this checkout')
    with tarfile.open(fileobj=io.BytesIO(result.stdout)) as archive:
        return {entry.name: archive.extractfile(entry).read() for entry in archive.getmembers() if entry.isfile()}


def approved(plan):
    return dict(plan, confirmed_at=NOW, reference='synthetic explicit user confirmation')


class MigrationFixture(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.area = Path(self.temp.name).resolve()
        self.home = self.area / 'home'
        self.home.mkdir()
        self.runtime = resolve_layout(self.home)
        self.source = self.area / 'old-product'
        for name, raw in legacy_code().items():
            path = self.source / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(raw)
        self.old = self.source / 'scripts/registry.json'
        self.repo = self.area / 'project'
        self.repo.mkdir()
        subprocess.run(['git', 'init', '-q', str(self.repo)], check=True, capture_output=True)
        self.identity = resolve_project(self.repo)
        self.config = json.loads(legacy_code()['scripts/agents.json'])['platforms']['darwin']
        # v1.11:路径表不再有用户级 Skill 根字段;旧 agents.json 直接可用。
        self.allowed = [str(self.home / path) for path in ('.codex/AGENTS.md', '.claude/CLAUDE.md', '.workbuddy/MEMORY.md')]
        self.user = self.home / '.workbuddy/MEMORY.md'
        self.user.parent.mkdir(parents=True)
        self.user.write_bytes(b'# preexisting user notes\n')
        self.evidence = self.area / 'approval-evidence.txt'
        self.evidence.write_bytes(b'synthetic approval record')
        self.store = self.area / 'custom-store'
        self.store.mkdir()
        self.tx = Transaction(lock_path=self.old.parent / '.agm.lock', backup_root=self.old.parent / 'backups',
                              allowed_roots=[self.repo, self.user, self.old], operation='enable-memory')
        self.original = {'schema_version': 1, 'projects': {}, 'shared_objects': {}}
        self.old.write_bytes(json.dumps(self.original).encode())
        self.old.chmod(0o640)
        project = registry.new_project(self.identity, ['codex', 'claude', 'workbuddy'])
        key = str(self.repo)
        self.original['projects'][key] = project
        project['memory_authorization'] = 'yes'
        project['authorization_evidence'] = {'confirmed_at': NOW, 'reference': str(self.evidence)}
        assembly = project['checkouts'][key]
        assembly['store'] = {'path': str(self.store), 'location_approved': True,
                             'approval_evidence': {'confirmed_at': NOW, 'reference': 'explicit custom store'}}
        def obj(path, scope, ownership, kind='block', marker=True):
            return {'kind': kind, 'path': str(path), 'scope': scope, 'agents': ['codex'], 'ownership': ownership,
                    'marker': {'start': START, 'end': END} if marker else None,
                    'fingerprint': {'algorithm': 'sha256', 'basis': 'block_bytes' if marker else 'file_bytes',
                                    'value': sha256(BLOCK) if marker else sha256(path.read_bytes())},
                    'original_existed': ownership != 'created', 'link_target': None,
                    'backup_manifest': str(self.tx.manifest_path) if ownership == 'created' else None,
                    'consumers': [key]}
        self.entry = self.repo / 'AGENTS.md'
        self.claude = self.repo / 'CLAUDE.md'
        self.claude.write_bytes(b'@AGENTS.md\n')
        assembly['objects'] = {'project-rule': obj(self.entry, 'project', 'created'),
                               'existing-import': obj(self.claude, 'project', 'reused', 'import', False)}
        self.original['shared_objects']['user-rule'] = obj(self.user, 'user', 'created', 'user_convention')
        assembly['shared_object_ids'] = ['user-rule']
        self.tx.run([Change.file(self.entry, BLOCK, expected=read_snapshot(self.entry)),
                     Change.file(self.user, self.user.read_bytes() + BLOCK, expected=read_snapshot(self.user))],
                    registry_change=Change.file(self.old, json.dumps(self.original, ensure_ascii=False).encode(), expected=read_snapshot(self.old)))
        registry.load_legacy_registry(self.old, allowed_user_paths=self.allowed)
        self.before_raw = self.old.read_bytes()
        self.product = installed_registry()['product']
        self.plan = self.make_plan()

    def make_plan(self, **kwargs):
        arguments = dict(source_commits={str(self.old): OLD_COMMIT}, product=self.product,
                         allowed_user_paths=self.allowed, operation_id='fixture-m403')
        arguments.update(kwargs)
        return migrate.plan_migration(self.runtime, [self.old], **arguments)

    def apply(self, hook=None):
        return migrate.execute_migration(self.plan, approved(self.plan), hook=hook)

    def load(self):
        return registry.load_registry(self.runtime.registry, allowed_user_paths=self.allowed)

    def snapshot(self):
        data = {}
        for path in self.area.rglob('*'):
            info = path.lstat()
            data[str(path)] = ('link', os.readlink(path)) if path.is_symlink() else (
                ('file', path.read_bytes(), info.st_mtime_ns, info.st_mode) if path.is_file() else ('directory',))
        return data

    def interrupt(self, event):
        def hook(actual, path):
            if actual == event:
                raise RuntimeError('injected ' + event)
        with self.assertRaisesRegex(RuntimeError, 'injected'):
            self.apply(hook)


class MigrationTests(MigrationFixture):
    def test_planning_and_scene_inspection_are_zero_write(self):
        before = self.snapshot()
        same = self.make_plan()
        self.assertEqual(same, self.plan)
        scene = migrate.inspect_migration(self.runtime, [self.old], allowed_user_paths=self.allowed)
        self.assertEqual(scene['scene'], 'legacy_only')
        self.assertEqual(self.snapshot(), before)
        self.assertFalse(self.runtime.root.exists())

    def test_exact_approval_is_required_before_any_write(self):
        before = self.snapshot()
        for approval in (None, {}, dict(approved(self.plan), operation_id='other')):
            with self.assertRaises(migrate.MigrationError):
                migrate.execute_migration(self.plan, approval)
            self.assertEqual(self.snapshot(), before)

    def test_migration_preserves_every_project_field_except_archive_pointer(self):
        result = self.apply()
        self.assertEqual(result['status'], 'committed')
        model = self.load()
        expected = copy.deepcopy(self.original)
        for obj in registry._objects(expected).values():
            if obj['backup_manifest']:
                obj['backup_manifest'] = model['migration']['reference_map'][obj['backup_manifest']]['path']
        self.assertEqual(model['projects'], expected['projects'])
        self.assertEqual(model['shared_objects'], expected['shared_objects'])
        self.assertEqual(model['machine'], {'agents': {}, 'objects': {}})
        self.assertEqual(migrate.resolve_reference(model, self.old).read_bytes(), self.before_raw)
        identity = json.loads((Path(self.plan['archive_root']) / 'source-identity.json').read_bytes())
        self.assertEqual(identity['source_version'], 'm2-schema1')
        self.assertEqual(identity['original_backup_manifests']['project-rule'], str(self.tx.manifest_path))
        registry.require_installed(model)
        self.assertEqual(migrate.inspect_migration(self.runtime, [self.old], allowed_user_paths=self.allowed)['scene'], 'migrated')
        self.assertFalse(self.runtime.lock.exists())
        self.assertFalse((self.old.parent / '.agm.lock').exists())
        self.assertFalse((self.home / '.agents-group-install.lock').exists())

    def test_archived_materials_remain_usable_after_old_backup_and_evidence_removed(self):
        self.apply()
        model = self.load()
        shutil.rmtree(self.old.parent / 'backups')
        self.evidence.unlink()
        model = self.load()
        self.assertEqual(migrate.resolve_reference(model, self.evidence).read_bytes(), b'synthetic approval record')
        descriptor = migrate.archived_recovery_descriptor(model, self.tx.manifest_path)
        self.assertEqual(descriptor['manifest'], json.loads(migrate.resolve_reference(model, self.tx.manifest_path).read_bytes()))
        self.assertIn(str(self.old), descriptor['registry_outputs_requiring_explicit_reconciliation'])
        for old, archived in descriptor['before_files'].items():
            self.assertTrue(Path(archived).is_file())
        self.assertTrue(self.old.is_dir())
        registry.require_installed(model)

    def test_passed_runtime_receipt_preserves_original_path_and_survives_source_removal(self):
        receipt = self.area / 'old-runtime-receipt.txt'
        receipt.write_bytes(b'synthetic historical runtime evidence')
        self.original['projects'][str(self.repo)]['checkouts'][str(self.repo)]['runtime_acceptance'] = {
            'status': 'passed', 'evidence_path': str(receipt)}
        self.old.write_bytes(json.dumps(self.original).encode())
        self.plan = self.make_plan()
        self.apply()
        receipt.unlink()
        model = self.load()
        runtime = model['projects'][str(self.repo)]['checkouts'][str(self.repo)]['runtime_acceptance']
        self.assertEqual(runtime, {'status': 'passed', 'evidence_path': str(receipt)})
        self.assertEqual(migrate.resolve_reference(model, receipt).read_bytes(), b'synthetic historical runtime evidence')
        registry.require_installed(model)

    def test_archive_corruption_and_missing_required_evidence_are_rejected(self):
        self.apply()
        model = self.load()
        evidence = migrate.resolve_reference(model, self.tx.manifest_path)
        evidence.write_bytes(b'corrupt archive')
        with self.assertRaises(registry.RegistryError):
            self.load()
        before = self.snapshot()
        self.assertEqual(migrate.inspect_migration(self.runtime, [self.old], allowed_user_paths=self.allowed)['scene'], 'conflict')
        self.assertEqual(before, self.snapshot())

    def test_source_drift_before_execution_refuses_before_lock_or_archive(self):
        self.evidence.write_bytes(b'changed evidence')
        before = self.snapshot()
        with self.assertRaises(migrate.MigrationError):
            self.apply()
        self.assertEqual(before, self.snapshot())
        self.assertFalse(self.runtime.root.exists())

    def test_source_drift_at_commit_keeps_target_absent_and_stops(self):
        def hook(event, path):
            if event == 'before_commit':
                self.evidence.write_bytes(b'foreign change before commit')
        with self.assertRaises(migrate.MigrationError):
            self.apply(hook)
        self.assertFalse(self.runtime.registry.exists())
        self.assertTrue(self.old.is_dir())
        self.assertEqual(migrate.inspect_migration(self.runtime, [self.old])['scene'], 'interrupted')
        before = self.snapshot()
        with self.assertRaises(migrate.MigrationError):
            migrate.plan_recovery(self.plan['journal'], action='continue')
        self.assertEqual(before, self.snapshot())

    def test_dual_regular_ledgers_refuse_even_if_equal_or_mtime_newer(self):
        self.runtime.var.mkdir(parents=True)
        for raw in (self.before_raw, registry.serialize_registry(installed_registry())):
            self.runtime.registry.write_bytes(raw)
            os.utime(self.runtime.registry, (2000000000, 2000000000))
            before = self.snapshot()
            self.assertEqual(migrate.inspect_migration(self.runtime, [self.old])['scene'], 'dual_conflict')
            with self.assertRaises(migrate.MigrationError):
                self.make_plan()
            self.assertEqual(before, self.snapshot())

    def test_only_v_is_installed_without_legacy_fallback(self):
        self.runtime.var.mkdir(parents=True)
        self.runtime.registry.write_bytes(registry.serialize_registry(installed_registry()))
        before = self.snapshot()
        self.assertEqual(migrate.inspect_migration(self.runtime)['scene'], 'installed_only')
        self.assertEqual(before, self.snapshot())

    def test_bad_future_and_unknown_input_never_become_v0(self):
        for raw in (b'{bad', b'{"schema_version":3}', b'{"schema_version":1,"projects":{},"shared_objects":{},"extra":0}'):
            self.old.write_bytes(raw)
            before = self.snapshot()
            with self.assertRaises((ValueError, OSError)):
                self.make_plan()
            self.assertEqual(before, self.snapshot())

    def test_tombstone_corruption_and_identity_mismatch_refuse(self):
        self.apply()
        (self.old / 'redirect.json').chmod(0o600)
        (self.old / 'redirect.json').write_bytes(b'{}')
        before = self.snapshot()
        self.assertEqual(migrate.inspect_migration(self.runtime, [self.old], allowed_user_paths=self.allowed)['scene'], 'conflict')
        with self.assertRaises(registry.RegistryError):
            registry.require_installed(self.load())
        self.assertEqual(before, self.snapshot())

    def test_existing_old_or_new_writer_locks_are_not_stolen(self):
        old_lock = self.old.parent / '.agm.lock'
        old_lock.mkdir()
        before = self.snapshot()
        with self.assertRaises(migrate.MigrationError):
            self.apply()
        self.assertEqual(before, self.snapshot())
        old_lock.rmdir()
        self.runtime.var.mkdir(parents=True)
        self.runtime.lock.mkdir()
        before = self.runtime.lock.stat().st_ino
        with self.assertRaises(migrate.MigrationError):
            self.apply()
        self.assertTrue(self.runtime.lock.is_dir())
        self.assertEqual(self.runtime.lock.stat().st_ino, before)

    def test_lock_order_and_both_old_and_new_writers_are_blocked_during_handoff(self):
        seen = []
        def hook(event, path):
            if event != 'before_commit':
                return
            for lock in migrate._lock_paths(self.runtime, self.plan):
                self.assertTrue(lock.is_dir())
            with self.assertRaises(TransactionError):
                with write_lock(self.old.parent / '.agm.lock'):
                    self.fail('legacy writer acquired migration lock')
            with self.assertRaises(TransactionError):
                with write_lock(self.runtime.lock):
                    self.fail('new writer acquired migration lock')
            seen.append(path)
        self.apply(hook)
        self.assertTrue(seen)

    def test_unfinished_target_is_not_writable_or_reported_ready(self):
        self.interrupt('after_commit')
        model = self.load()
        with self.assertRaisesRegex(registry.RegistryError, 'interrupted'):
            registry.require_installed(model)
        request = {'home': str(self.home), 'platform_config': self.config, 'project': str(self.repo), 'all': True,
                   'agents': ['codex'], 'memory_choice': 'no', 'approval': None, 'interactive': False}
        before = self.snapshot()
        self.assertEqual(enable.run(request)['status'], 'failed')
        self.assertEqual(remove.run(request)['status'], 'failed')
        self.assertEqual(check.run(request)['status'], 'gaps')
        self.assertEqual(before, self.snapshot())

    def test_readonly_scene_diagnostic_and_normal_check_do_not_rewrite(self):
        self.apply()
        request = {'home': str(self.home), 'platform_config': self.config, 'all': True}
        before = self.snapshot()
        self.assertEqual(migrate.inspect_migration(self.runtime, [self.old], allowed_user_paths=self.allowed)['scene'], 'migrated')
        result = check.run(request)
        self.assertNotEqual(result['status'], 'failed', result)
        self.assertEqual(before, self.snapshot())

    def test_multiple_known_legacy_writers_are_all_frozen_and_archived(self):
        other = self.area / 'second-product'
        shutil.copytree(self.source, other)
        second = other / 'scripts/registry.json'
        plan = migrate.plan_migration(self.runtime, [second, self.old],
            source_commits={str(second): OLD_COMMIT, str(self.old): OLD_COMMIT}, product=self.product,
            allowed_user_paths=self.allowed, operation_id='multi-source')
        migrate.execute_migration(plan, approved(plan))
        model = self.load()
        self.assertEqual(set(model['migration']['tombstones']), {str(self.old), str(second)})
        self.assertTrue(self.old.is_dir() and second.is_dir())
        self.assertEqual(migrate.resolve_reference(model, second).read_bytes(), self.before_raw)
        registry.require_installed(model)

    def test_historical_ledger_before_files_pull_in_older_manifest_closure(self):
        tx = Transaction(lock_path=self.old.parent / '.agm.lock', backup_root=self.old.parent / 'backups',
                         allowed_roots=[self.repo, self.old], operation='enable-memory')
        newer = copy.deepcopy(self.original)
        block = BLOCK.replace(b'original rule', b'updated rule')
        obj = newer['projects'][str(self.repo)]['checkouts'][str(self.repo)]['objects']['project-rule']
        obj['backup_manifest'] = str(tx.manifest_path)
        obj['fingerprint']['value'] = sha256(block)
        tx.run([Change.file(self.entry, block, expected=read_snapshot(self.entry))],
            registry_change=Change.file(self.old, json.dumps(newer).encode(), expected=read_snapshot(self.old)))
        self.plan = self.make_plan()
        self.apply()
        model = self.load()
        for manifest in (self.tx.manifest_path, tx.manifest_path):
            descriptor = migrate.archived_recovery_descriptor(model, manifest)
            self.assertTrue(descriptor['before_files'])
        archived_source = json.loads(migrate.resolve_reference(model, self.old).read_bytes())
        self.assertEqual(archived_source, newer)

    def test_missing_or_modified_before_file_refuses_zero_write(self):
        tx_data = json.loads(self.tx.manifest_path.read_bytes())
        entry = next(entry for entry in tx_data['entries'] if entry['before']['kind'] == 'file')
        before_file = self.tx.manifest_path.parent / entry['before']['backup']
        before_file.write_bytes(b'changed recovery snapshot')
        before = self.snapshot()
        with self.assertRaises(migrate.MigrationError):
            self.make_plan()
        self.assertEqual(before, self.snapshot())

    def test_malformed_legacy_snapshot_metadata_is_not_archived_as_valid(self):
        original = json.loads(self.tx.manifest_path.read_bytes())
        for mutate in (lambda d: d['entries'][0]['after'].update(mode=True),
                       lambda d: d['entries'][0]['after'].update(existed=1),
                       lambda d: d['entries'][0]['after'].update(backup='../escape'),
                       lambda d: d['entries'][0]['after'].update(fingerprint='bad')):
            data = copy.deepcopy(original)
            mutate(data)
            self.tx.manifest_path.write_text(json.dumps(data))
            before = self.snapshot()
            with self.assertRaises(ValueError):
                self.make_plan()
            self.assertEqual(before, self.snapshot())

    def test_changed_installed_identity_cannot_reuse_another_migration_journal(self):
        self.apply()
        model = self.load()
        model['product']['installation_id'] = 'another-machine-installation'
        self.runtime.registry.write_bytes(registry.serialize_registry(model, allowed_user_paths=self.allowed))
        with self.assertRaisesRegex(registry.RegistryError, 'identity changed'):
            registry.require_installed(self.load())


class RecoveryTests(MigrationFixture):
    def test_continue_and_rollback_each_transition_window(self):
        # Every subtest has a fresh operation and no real HOME dependency.
        events = ('after_copy', 'after_old_unlink', 'after_tombstone_mkdir', 'after_redirect', 'after_commit', 'before_finish')
        for action in ('continue', 'rollback'):
            for event in events:
                with self.subTest(action=action, event=event):
                    fixture = MigrationFixture('setUp')
                    fixture.setUp()
                    try:
                        fixture.interrupt(event)
                        before = fixture.snapshot()
                        recovery = migrate.plan_recovery(fixture.plan['journal'], action=action)
                        self.assertEqual(before, fixture.snapshot())
                        result = migrate.recover_migration(recovery, approved(recovery))
                        if action == 'continue':
                            self.assertEqual(result['status'], 'committed')
                            registry.require_installed(fixture.load())
                            self.assertTrue(fixture.old.is_dir())
                        else:
                            self.assertEqual(result['status'], 'rolled_back')
                            self.assertEqual(fixture.old.read_bytes(), fixture.before_raw)
                            self.assertFalse(fixture.runtime.registry.exists())
                            registry.load_legacy_registry(fixture.old, allowed_user_paths=fixture.allowed)
                    finally:
                        fixture.doCleanups()

    def test_trusted_journal_dual_before_after_ledgers_require_explicit_recovery(self):
        self.interrupt('after_copy')
        journal, _ = migrate._load_journal(Path(self.plan['journal']))
        migrate._copy_materials(journal, lambda event, path: None)
        self.runtime.registry.write_bytes(migrate._bytes(self.plan['after_registry']))
        self.runtime.registry.chmod(0o600)
        before = self.snapshot()
        scene = migrate.inspect_migration(self.runtime, [self.old], allowed_user_paths=self.allowed)
        self.assertEqual(scene['scene'], 'interrupted')
        self.assertEqual(before, self.snapshot())
        recovery = migrate.plan_recovery(self.plan['journal'], action='continue')
        self.assertEqual(recovery['scene']['sources'][str(self.old)], 'before')
        result = migrate.recover_migration(recovery, approved(recovery))
        self.assertEqual(result['status'], 'committed')
        self.assertTrue(self.old.is_dir())
        registry.require_installed(self.load())

    def test_after_commit_only_finalizes_from_archive_without_old_sources_or_ledger_rewrite(self):
        self.interrupt('after_commit')
        before = self.runtime.registry.read_bytes(), self.runtime.registry.stat().st_mtime_ns
        shutil.rmtree(self.old.parent / 'backups')
        shutil.rmtree(self.old.parent / 'agm_core')
        self.evidence.unlink()
        with self.assertRaises(migrate.MigrationError):
            migrate.plan_recovery(self.plan['journal'], action='rollback')
        recovery = migrate.plan_recovery(self.plan['journal'], action='continue')
        self.assertTrue(recovery['finish_only'])
        result = migrate.recover_migration(recovery, approved(recovery))
        self.assertTrue(result['finish_only'])
        self.assertEqual((self.runtime.registry.read_bytes(), self.runtime.registry.stat().st_mtime_ns), before)
        registry.require_installed(self.load())

    def test_recovery_approval_and_scene_fingerprint_are_required(self):
        self.interrupt('after_redirect')
        recovery = migrate.plan_recovery(self.plan['journal'], action='continue')
        before = self.snapshot()
        with self.assertRaises(migrate.MigrationError):
            migrate.recover_migration(recovery, None)
        self.assertEqual(before, self.snapshot())
        (self.old / 'redirect.json').chmod(0o600)
        (self.old / 'redirect.json').write_bytes(b'foreign bytes')
        with self.assertRaises(migrate.MigrationError):
            migrate.recover_migration(recovery, approved(recovery))
        self.assertFalse(self.runtime.registry.exists())

    def test_closed_migration_is_not_a_downgrade_or_replay_entry(self):
        self.apply()
        before = self.snapshot()
        for action in ('rollback', 'continue'):
            with self.assertRaises(migrate.MigrationError):
                migrate.plan_recovery(self.plan['journal'], action=action)
        self.assertEqual(before, self.snapshot())

    def test_unknown_or_active_lock_is_never_automatically_removed(self):
        self.interrupt('after_redirect')
        self.runtime.lock.mkdir()
        before = self.snapshot()
        with self.assertRaises(migrate.MigrationError):
            migrate.plan_recovery(self.plan['journal'], action='continue')
        self.assertEqual(before, self.snapshot())
        self.runtime.lock.rmdir()
        with migrate._lock(self.runtime.lock, self.plan):
            with self.assertRaisesRegex(migrate.MigrationError, 'still exists'):
                migrate.plan_recovery(self.plan['journal'], action='continue')


if __name__ == '__main__':
    unittest.main()
