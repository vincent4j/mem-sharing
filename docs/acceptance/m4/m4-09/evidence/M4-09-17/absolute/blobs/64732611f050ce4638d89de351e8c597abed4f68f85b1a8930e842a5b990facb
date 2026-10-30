"""Retired development ledgers are strict diagnostic inputs, never write authority."""
import copy
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'scripts'))
sys.path.insert(0, str(Path(__file__).parent))
from agm_core import migrate, registry, paths
from agm_core.layout import resolve_layout
from runtime_fixture import installed_registry

OLD_COMMIT = 'a' * 40
NOW = '2026-10-30T00:00:00Z'


def approved(plan):
    return dict(plan, confirmed_at=NOW, reference='synthetic explicit user confirmation')


class MigrationFixture(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.area = Path(self.temp.name).resolve(); self.home = self.area / 'home'; self.home.mkdir()
        self.runtime = resolve_layout(self.home)
        self.source = self.area / 'old-product'; (self.source / 'scripts').mkdir(parents=True)
        self.old = self.source / 'scripts/registry.json'
        self.original = {'schema_version': 1, 'projects': {}, 'shared_objects': {}}
        self.old.write_bytes(json.dumps(self.original).encode()); self.old.chmod(0o640)
        self.before_raw = self.old.read_bytes()
        self.config = paths.select_platform(paths.load_agents_table(), 'darwin')
        self.allowed = paths.allowed_user_paths(self.config, None, home=str(self.home))
        self.evidence = self.area / 'approval-evidence.txt'; self.evidence.write_bytes(b'original evidence\xff\r\n')
        self.product = installed_registry()['product']
        self.plan = {'command': 'migrate-machine', 'operation_id': 'old-op', 'schema_version': 1}

    def make_plan(self, **kwargs):
        return migrate.plan_migration(self.runtime, [self.old], source_commits={str(self.old): OLD_COMMIT},
                                      product=self.product, allowed_user_paths=self.allowed, **kwargs)

    def apply(self, hook=None):
        return migrate.execute_migration(self.plan, approved(self.plan), hook=hook)

    def load(self):
        return registry.load_registry(self.runtime.registry, allowed_user_paths=self.allowed)

    def snapshot(self):
        return {str(p): (p.lstat().st_mode, p.lstat().st_mtime_ns,
                        os.readlink(p) if p.is_symlink() else p.read_bytes() if p.is_file() else None)
                for p in self.area.rglob('*')}


class MigrationTests(MigrationFixture):
    def test_strict_legacy_diagnostic_preserves_original_bytes_and_metadata(self):
        before = self.snapshot()
        result = registry.load_diagnostic_registry(self.old, allowed_user_paths=self.allowed)
        self.assertEqual(result, self.original)
        self.assertEqual(migrate.inspect_migration(self.runtime, [self.old])['channel'], 'stop')
        self.assertEqual(before, self.snapshot())

    def test_all_migration_and_old_journal_replay_routes_refuse_zero_writes(self):
        journal = self.area / 'old-journal.json'; journal.write_text(json.dumps(self.plan))
        before = self.snapshot()
        for action in (self.make_plan, self.apply,
                       lambda: migrate.plan_recovery(journal, action='continue'),
                       lambda: migrate.plan_recovery(journal, action='rollback'),
                       lambda: migrate.recover_migration(self.plan, approved(self.plan)),
                       lambda: migrate._load_journal(journal)):
            with self.subTest(action=action):
                with self.assertRaises(migrate.MigrationError) as ctx: action()
                self.assertEqual(ctx.exception.code, 'migration_unsupported')
                self.assertEqual(before, self.snapshot())

    def test_old_approval_never_authorizes_conversion(self):
        for approval in ({}, approved(self.plan), dict(approved(self.plan), reference='new approval')):
            before = self.snapshot()
            with self.assertRaises(migrate.MigrationError): migrate.execute_migration(self.plan, approval)
            self.assertEqual(before, self.snapshot())

    def test_old_schema_cannot_be_loaded_as_active(self):
        with self.assertRaises(registry.RegistryError): registry.load_registry(self.old)
        self.assertFalse(self.runtime.registry.exists())

    def test_schema2_is_strict_readonly_without_contract_normalization(self):
        data = installed_registry(); data['schema_version'] = 2
        data['product']['product_id'] = 'agent-group-memory'
        self.old.write_text(json.dumps(data)); before = self.snapshot()
        self.assertEqual(registry.load_diagnostic_registry(self.old), data)
        self.assertEqual(before, self.snapshot())
        with self.assertRaises(registry.RegistryError): registry.load_registry(self.old)

    def test_bad_future_duplicate_and_unknown_fields_refuse_without_repair(self):
        for raw in (b'{', b'{"schema_version":1,"schema_version":1,"projects":{},"shared_objects":{}}',
                    b'{"schema_version":4,"projects":{},"shared_objects":{}}',
                    b'{"schema_version":1,"projects":{},"shared_objects":{},"extra":1}'):
            self.old.write_bytes(raw); before = self.snapshot()
            self.assertEqual(migrate.inspect_migration(self.runtime, [self.old])['scene'], 'conflict')
            self.assertEqual(before, self.snapshot())

    def test_dual_regular_ledgers_never_choose_mtime_winner(self):
        self.runtime.var.mkdir(parents=True)
        self.runtime.registry.write_bytes(registry.serialize_registry(installed_registry()))
        before = self.snapshot()
        self.assertEqual(migrate.inspect_migration(self.runtime, [self.old])['scene'], 'dual_conflict')
        self.assertEqual(before, self.snapshot())

    def test_symlink_or_missing_legacy_source_is_conflict(self):
        link = self.area / 'link.json'; link.symlink_to(self.old)
        for path in (link, self.area / 'missing.json'):
            before = self.snapshot()
            self.assertEqual(migrate.inspect_migration(self.runtime, [path])['scene'], 'conflict')
            self.assertEqual(before, self.snapshot())

    def test_no_ledger_does_not_initialize(self):
        before = self.snapshot()
        self.assertEqual(migrate.inspect_migration(self.runtime)['scene'], 'no_ledger')
        self.assertEqual(before, self.snapshot())

    def test_schema3_is_the_only_installed_authority(self):
        self.runtime.var.mkdir(parents=True)
        self.runtime.registry.write_bytes(registry.serialize_registry(installed_registry()))
        before = self.snapshot()
        self.assertEqual(migrate.inspect_migration(self.runtime)['scene'], 'installed_only')
        self.assertEqual(before, self.snapshot())

    def test_exact_approval_helper_rejects_missing_extra_and_changed_values(self):
        for approval in ({}, dict(approved(self.plan), extra=True), dict(approved(self.plan), operation_id='other')):
            with self.assertRaises(migrate.MigrationError): migrate._approval(self.plan, approval)
        migrate._approval(self.plan, approved(self.plan))

    def test_active_or_unknown_writer_locks_are_not_stolen(self):
        plan = dict(self.plan, plan_sha256='a' * 64, layout=self.runtime.describe())
        lock = self.home / 'lock'
        with migrate._lock(lock, plan):
            before = self.snapshot()
            with self.assertRaises(migrate.MigrationError): migrate._stale_observation(lock, plan)
            self.assertEqual(before, self.snapshot())
        lock.mkdir(); (lock / 'unknown').write_bytes(b'owner')
        before = self.snapshot()
        with self.assertRaises(migrate.MigrationError): migrate._stale_observation(lock, plan)
        self.assertEqual(before, self.snapshot())
