"""Uninstall recognition, externalization and restore of completed CK audits.

The var/ guard admits registry.json plus only strictly corroborated
'configured' CK audit journals written by the real ck_install producer.
Failed/unclear operations, locks, forged names, drifted identities and
unknown material keep failing closed with zero writes.
"""
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest

import test_uninstall as fixtures
from agm_core import ck_install, legacy_import as legacy
from agm_core import uninstall, uninstall_recovery as recovery

CONFLICT = 'Unknown runtime metadata or writer lock'


class CKAuditFixture(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.UninstallTests(); self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.home = self.fixture.home; self.runtime = self.fixture.runtime
        self.var = self.runtime.var; self.journal = self.var / 'ck-install-fixture-m404.json'
        self.write_audit(self.audit())

    def audit(self):
        main = self.home / '.mem-sharing-install-fixture-m404' / 'journal.json'
        skills = [str(self.home / '.agents/skills/context-keeper'),
                  str(self.home / '.codex/skills/context-keeper')]
        rules = [str(self.home / '.codex/AGENTS.md')]
        plan = {'schema_version': 1, 'command': 'install-context-keeper', 'scope': 'user',
                'main_operation_id': 'fixture-m404', 'home': str(self.home),
                'platform_config': {}, 'registry_path': str(self.runtime.registry),
                'registry_sha256': 'a' * 64, 'agents': ['codex'], 'skipped_upstream_agents': [],
                'main_journal': {'path': str(main), 'fingerprint': {'kind': 'file'}},
                'source': {'root': '/durable/synthetic/ck-source', 'commit': ck_install.PIN,
                           'files': {'SKILL.md': {'sha256': 'b' * 64, 'mode': 0o644},
                                     'scripts/install.py': {'sha256': 'd' * 64, 'mode': 0o755}}},
                'preview_argv': ['/usr/bin/python3', '-I', '-B', '/durable/synthetic/ck-source/scripts/install.py', '--codex'],
                'argv': ['/usr/bin/python3', '-I', '-B', '/durable/synthetic/ck-source/scripts/install.py', '--codex', '--approved'],
                'interpreter': {'path': '/usr/bin/python3', 'fingerprint': {'kind': 'file'}},
                'upstream_preview': {'approval_required': True}, 'observations': {},
                'skill_entries': skills, 'rule_files': rules,
                'journal': str(self.journal), 'metadata_scopes': [str(self.journal)],
                'changes': []}
        plan['plan_sha256'] = legacy.digest(legacy.encoded(plan))
        document = {'plan': plan,
                    'approval': dict(plan, confirmed_at='2026-11-02T06:00:00Z',
                                     reference='synthetic faithful audit for uninstall recognition'),
                    'status': 'configured',
                    'result': {'scope': 'user', 'project': None, 'configured_agents': ['Codex'],
                               'installed': skills, 'removed': [],
                               'bridges': [{'file': rules[0], 'action': 'created'}]},
                    'after': {skills[0]: {'kind': 'symlink', 'target': '/durable/synthetic/ck-source'},
                              skills[1]: {'kind': 'symlink', 'target': '/durable/synthetic/ck-source'},
                              rules[0]: {'kind': 'file', 'sha256': 'c' * 64, 'mode': 0o644}}}
        return document

    def write_audit(self, document, name=None, mode=0o600):
        target = self.var / (name or self.journal.name)
        target.write_text(json.dumps(document, ensure_ascii=False))
        os.chmod(target, mode)
        return target

    def refreshed(self, document):
        """Recompute the canonical plan digest after mutating plan fields."""
        plan = document['plan']
        plan.pop('plan_sha256', None)
        plan['plan_sha256'] = legacy.digest(legacy.encoded(plan))
        document['approval'] = dict(plan, confirmed_at=document['approval']['confirmed_at'],
                                    reference=document['approval']['reference'])
        return document

    def plan_uninstall(self):
        return uninstall.preview(home=self.home, backup_dir=self.fixture.backup)


class CKAuditJournalTests(CKAuditFixture):
    def test_completed_synthetic_audit_permits_preview_and_exact_external_restore(self):
        import stat as stat_module
        before_bytes = self.journal.read_bytes()
        before_mode = stat_module.S_IMODE(self.journal.stat().st_mode)
        plan = self.plan_uninstall()  # the old guard raised Conflict here
        entry = next(change for change in plan['changes']
                     if change['path'] == str(self.journal))
        self.assertEqual(entry['stage'], 'delete_product')
        self.assertEqual(entry['before']['kind'], 'file')
        self.assertEqual(bytes.fromhex(entry['before']['hex']), before_bytes)
        self.assertEqual(entry['before']['mode'], before_mode)
        result = self.fixture.apply_uninstall()
        self.assertEqual(result['status'], 'completed')
        self.assertFalse(self.runtime.root.exists())
        self.assertFalse(self.journal.exists())
        manifest = self.fixture.backup / 'manifest.json'
        preview = recovery.recover(manifest)
        approved = self.fixture.area / 'restore-approval.json'
        approved.write_text(json.dumps(fixtures.approval(preview['plan'])))
        child = subprocess.run([sys.executable, '-B', str(self.fixture.backup / 'recover.py'),
                                '--manifest', str(manifest), '--approval-file', str(approved)],
                               capture_output=True, text=True, timeout=30)
        self.assertEqual(child.returncode, 0, child.stdout + child.stderr)
        self.assertEqual(self.journal.read_bytes(), before_bytes)
        self.assertEqual(stat_module.S_IMODE(self.journal.stat().st_mode), before_mode)

    def test_validator_matrix_rejects_every_malformed_or_foreign_shape_with_zero_writes(self):
        base = self.audit()
        stranger = self.var / 'ck-install-other-op.json'
        cases = []
        for status in ('running', 'approval_required', 'unknown'):
            document = self.audit(); document['status'] = status
            if status == 'unknown': document['errors'] = [{'code': 'ck_result_unknown', 'message': 'x'}]
            cases.append(('status:' + status, self.journal, document))
        document = self.audit(); document['extra'] = 1
        cases.append(('unknown top key', self.journal, document))
        document = self.audit(); del document['after']
        cases.append(('missing after', self.journal, document))
        document = self.audit(); document['plan']['agents'] = ['codex', 'claude']
        cases.append(('plan digest mismatch', self.journal, document))
        document = self.audit(); document['approval']['scope'] = 'project'
        cases.append(('approval plan part mismatch', self.journal, document))
        for field, value in (('home', '/other/home'), ('registry_path', '/other/registry.json'),
                             ('journal', '/other/ck-install-fixture-m404.json'),
                             ('command', 'install-machine'), ('scope', 'project')):
            document = self.audit(); document['plan'][field] = value
            self.refreshed(document)
            cases.append(('plan ' + field, self.journal, document))
        document = self.audit(); document['plan']['metadata_scopes'] = ['/other']
        self.refreshed(document)
        cases.append(('metadata scopes', self.journal, document))
        document = self.audit(); document['plan']['main_operation_id'] = 'other-op'
        self.refreshed(document)
        cases.append(('filename/main-op mismatch', self.journal, document))
        document = self.audit(); document['plan']['source']['commit'] = 'f' * 40
        self.refreshed(document)
        cases.append(('source commit drift', self.journal, document))
        document = self.audit(); document['result']['removed'] = [str(self.home / 'x')]
        cases.append(('result removed non-empty', self.journal, document))
        document = self.audit(); document['result']['bridges'] = []
        cases.append(('bridges do not match rules', self.journal, document))
        document = self.audit(); document['after'][document['plan']['skill_entries'][0]] = \
            {'kind': 'symlink', 'target': '/somewhere/else'}
        cases.append(('after skill target foreign absolute', self.journal, document))
        document = self.audit()
        document['after'][document['plan']['skill_entries'][0]]['target'] = '../../../../foreign-ck'
        cases.append(('after skill relative target escapes source', self.journal, document))
        document = self.audit()
        document['after'][document['plan']['rule_files'][0]].update(sha256='not-a-hash', mode=-1)
        cases.append(('after rule invalid hash and mode', self.journal, document))
        document = self.audit()
        document['after'][document['plan']['skill_entries'][0]]['mode'] = 0o644
        cases.append(('after skill node extra field', self.journal, document))
        document = self.audit()
        del document['after'][document['plan']['rule_files'][0]]['mode']
        cases.append(('after rule node missing mode', self.journal, document))
        document = self.audit(); del document['after'][document['plan']['rule_files'][0]]
        cases.append(('after missing rule node', self.journal, document))
        document = self.audit(); document['plan']['source']['files'] = {}
        self.refreshed(document)
        cases.append(('source files empty with recomputed plan', self.journal, document))
        document = self.audit()
        document['plan']['source']['files']['../escape'] = {'sha256': 'e' * 64, 'mode': 0o644}
        self.refreshed(document)
        cases.append(('source files path escape', self.journal, document))
        document = self.audit()
        document['plan']['source']['files']['/absolute'] = {'sha256': 'e' * 64, 'mode': 0o644}
        self.refreshed(document)
        cases.append(('source files absolute path', self.journal, document))
        document = self.audit()
        document['plan']['source']['files']['SKILL.md']['sha256'] = 'not-a-hash'
        self.refreshed(document)
        cases.append(('source files invalid entry hash', self.journal, document))
        document = self.audit()
        del document['plan']['source']['files']['scripts/install.py']
        self.refreshed(document)
        cases.append(('source files missing required file', self.journal, document))
        document = self.audit(); document['plan']['skill_entries'] = document['plan']['skill_entries'][:1]
        document['result']['installed'] = document['plan']['skill_entries']
        self.refreshed(document)
        cases.append(('skill set derivation mismatch', self.journal, document))
        other_home = self.audit(); other_home['plan']['home'] = '/other/home'
        self.refreshed(other_home)
        cases.append(('foreign home journal', stranger, other_home))
        for label, target, document in cases:
            with self.subTest(case=label):
                self.write_audit(document, name=target.name)
                tree = recovery.tree(self.home)
                with self.assertRaises(recovery.Conflict) as raised:
                    self.plan_uninstall()
                self.assertEqual(str(raised.exception), CONFLICT)
                self.assertEqual(recovery.tree(self.home), tree)
                self.assertFalse(self.fixture.backup.exists())
            target.unlink(missing_ok=True)
        # Valid audit stays acceptable between negative probes.
        self.write_audit(base)
        self.plan_uninstall()

    def test_var_strangers_locks_symlinks_and_modes_still_block(self):
        probe = self.audit()
        strangers = {'stranger.txt': b'?'}
        for name, raw in strangers.items():
            (self.var / name).write_bytes(raw)
            tree = recovery.tree(self.home)
            with self.assertRaises(recovery.Conflict) as raised:
                self.plan_uninstall()
            self.assertEqual(str(raised.exception), CONFLICT)
            self.assertEqual(recovery.tree(self.home), tree)
            (self.var / name).unlink()
        # A writer lock is refused by the pre-existing marker/lock guard.
        (self.var / '.agm.lock').write_bytes(b'')
        tree = recovery.tree(self.home)
        with self.assertRaises(recovery.Conflict) as raised:
            self.plan_uninstall()
        self.assertIn('writer lock', str(raised.exception))
        self.assertEqual(recovery.tree(self.home), tree)
        (self.var / '.agm.lock').unlink()
        forged = self.var / 'ck-install-forged.json'
        forged.symlink_to(self.journal)
        with self.assertRaises(recovery.Conflict) as raised:
            self.plan_uninstall()
        self.assertEqual(str(raised.exception), CONFLICT)
        forged.unlink()
        hidden = self.audit()
        self.write_audit(hidden, name='ck-install-.hidden.json')
        with self.assertRaises(recovery.Conflict) as raised:
            self.plan_uninstall()
        self.assertEqual(str(raised.exception), CONFLICT)
        (self.var / 'ck-install-.hidden.json').unlink()
        self.write_audit(probe, mode=0o644)
        with self.assertRaises(recovery.Conflict) as raised:
            self.plan_uninstall()
        self.assertEqual(str(raised.exception), CONFLICT)
        self.write_audit(probe)
        self.plan_uninstall()

    def test_later_main_operation_version_does_not_invalidate_historical_audit(self):
        ledger = json.loads(self.runtime.registry.read_text())
        self.assertEqual(ledger['product']['last_operation_id'], 'fixture-m404')
        ledger['product']['last_operation_id'] = '20990101T000000Z-latermainop'
        self.runtime.registry.write_text(json.dumps(ledger, ensure_ascii=False))
        plan = self.plan_uninstall()  # historical audit still recognized
        self.assertTrue(any(change['path'] == str(self.journal) for change in plan['changes']))

    def test_drift_after_preview_refuses_before_any_backup_write(self):
        plan = self.plan_uninstall()
        drifted = self.audit()
        drifted['approval']['reference'] = 'changed after approval'
        self.write_audit(drifted)
        tree = recovery.tree(self.home)
        with self.assertRaises(ValueError):
            uninstall.execute(fixtures.approval(recovery.summary(plan)),
                              home=self.home, backup_dir=self.fixture.backup)
        self.assertEqual(recovery.tree(self.home), tree)
        self.assertFalse(self.fixture.backup.exists())

    def test_validator_returns_configured_document_for_valid_audit(self):
        document = uninstall._ck_audit_journal(self.journal, self.runtime)
        self.assertEqual(document['status'], 'configured')
        self.assertEqual(document['plan']['command'], 'install-context-keeper')

    def test_legitimate_relative_skill_link_is_accepted(self):
        import os
        plan_skills = self.audit()['plan']['skill_entries']
        root = '/durable/synthetic/ck-source'
        document = self.audit()
        for name in plan_skills:
            document['after'][name] = {'kind': 'symlink',
                                       'target': os.path.relpath(root, Path(name).parent)}
        self.write_audit(document)
        recognized = uninstall._ck_audit_journal(self.journal, self.runtime)
        self.assertEqual(recognized['status'], 'configured')
        self.plan_uninstall()  # full preview accepts the historical relative links


class RealProducerAuditTests(CKAuditFixture):
    """Real pinned CK producer through the whole uninstall/restore cycle."""

    def setUp(self):
        from test_m404_install import InstallFixture
        self.fixture = fixtures.UninstallTests(); InstallFixture.setUp(self.fixture)
        self.addCleanup(self.fixture.doCleanups)
        self.fixture.codex()
        self.home = self.fixture.home; self.runtime = self.fixture.runtime
        entry = self.home / '.codex/AGENTS.md'
        entry.parent.mkdir(parents=True, exist_ok=True)
        self.fixture.entry = entry
        self.fixture.backup = self.fixture.area/'independent-backup'
        self.private_before = b'private\x00\r\nprivate footer\r\n'
        entry.write_bytes(self.private_before)
        self.fixture.execute()
        self.var = self.runtime.var; self.journal = self.var / 'ck-install-fixture-m404.json'
        source = os.environ.get('CK_PINNED_SOURCE_FIXTURE')
        if not source:
            self.skipTest('Set CK_PINNED_SOURCE_FIXTURE to a clean pinned CK checkout for real-producer acceptance')
        self.source = Path(source)

    def install_real_ck(self):
        plan = ck_install.plan_context_keeper(self.fixture.request, 'fixture-m404', self.source)
        evidence = {'confirmed_at': '2026-11-02T06:00:00Z',
                    'reference': 'real pinned producer fixture for uninstall audit acceptance'}
        report = ck_install.execute_context_keeper(plan, dict(plan, **evidence),
                                                   request=self.fixture.request)
        self.assertEqual(report['status'], 'configured', report)
        return report

    def test_postinstall_private_prefix_blocks_real_producer_zero_write(self):
        entry = self.home / '.codex/AGENTS.md'
        entry.write_bytes(b'new private prefix\r\n' + entry.read_bytes())
        before = recovery.tree(self.home)
        from agm_core import user_entries
        ledger = json.loads(self.runtime.registry.read_bytes())
        proof = user_entries.connection_status(self.runtime, self.fixture.config, ledger, ['codex'])
        self.assertEqual(proof['codex']['reason'], 'entry_layout_not_top')
        with self.assertRaisesRegex(ValueError, 'verified public-memory entry'):
            ck_install.plan_context_keeper(self.fixture.request, 'fixture-m404', self.source)
        self.assertEqual(recovery.tree(self.home), before)

    def test_real_configured_audit_full_cycle_with_ck_retained_and_byte_restore(self):
        import stat as stat_module
        self.install_real_ck()
        self.assertTrue(self.journal.is_file())
        before_bytes = self.journal.read_bytes()
        before_mode = stat_module.S_IMODE(self.journal.stat().st_mode)
        skill = self.home / '.codex/skills/context-keeper'
        entry = self.fixture.entry.read_bytes()
        self.assertIn(b'<!-- context-keeper:start -->', entry)
        result = self.fixture.apply_uninstall()
        self.assertEqual(result['status'], 'completed')
        self.assertFalse(self.runtime.root.exists())
        self.assertFalse(self.journal.exists())
        # CK installation itself is retained: link and rule block survive.
        self.assertTrue(skill.is_symlink())
        self.assertEqual(skill.resolve(), self.source.resolve())
        self.assertIn(b'<!-- context-keeper:start -->', self.fixture.entry.read_bytes())
        manifest = self.fixture.backup / 'manifest.json'
        preview = recovery.recover(manifest)
        approved = self.fixture.area / 'restore-approval.json'
        approved.write_text(json.dumps(fixtures.approval(preview['plan'])))
        child = subprocess.run([sys.executable, '-B', str(self.fixture.backup / 'recover.py'),
                                '--manifest', str(manifest), '--approval-file', str(approved)],
                               capture_output=True, text=True, timeout=30)
        self.assertEqual(child.returncode, 0, child.stdout + child.stderr)
        self.assertEqual(self.journal.read_bytes(), before_bytes)
        self.assertEqual(stat_module.S_IMODE(self.journal.stat().st_mode), before_mode)
        self.assertEqual(recovery.digest(before_bytes), recovery.digest(self.journal.read_bytes()))
        # A replayed audit on the restored scene is still recognized, not executed.
        document = uninstall._ck_audit_journal(self.journal, self.runtime)
        self.assertEqual(document['status'], 'configured')
