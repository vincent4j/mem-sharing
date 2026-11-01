"""One outer approval for old public-layout migration and new onboarding.

Uses real historical kernels in temporary HOME, with synthetic detection only.
"""
import copy
import json
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_public_layout as cases


class UpgradeEntryProjectionTests(unittest.TestCase):
    def setUp(self):
        self.fixture = cases.PublicLayoutMigrationFixture(
            'test_upgrade_runs_migration_to_v2_and_preserves_private_bytes')
        if self._testMethodName.endswith('_v012'):
            self.fixture.VERSION = '0.1.2'
        self.addCleanup(self.fixture.doCleanups)
        self.fixture.setUp()
        f = self.fixture
        facts = cases.detect.detect_agents(f.config, None, home=str(f.home),
            search_paths=[str(f.bin_dir)], app_directories=[])
        for agent in ('opencode', 'zcode'):
            facts['agents'][agent] = copy.deepcopy(facts['agents']['codex'])
        self.addCleanup(patch.stopall)
        patch.object(cases.detect, 'detect_agents', return_value=facts).start()
        patch.dict(os.environ, {'XDG_CONFIG_HOME': '', 'OPENCODE_CONFIG_DIR': '',
                              'OPENCODE_CONFIG': '', 'DSH_HOME': ''}).start()

    def test_default_migration_and_onboarding_share_one_exact_approval(self):
        f = self.fixture
        before = f.snapshot()
        plan, request = f.plan()
        self.assertEqual(before, f.snapshot())
        self.assertFalse(plan['entry_followup'])
        self.assertEqual(plan['entry_plan']['effective'], ['codex', 'zcode', 'opencode'])
        self.assertEqual(plan['entry_plan']['machine_agents'], ['opencode', 'zcode'])
        # Migrated existing entries are already at V2 in the entry preview.
        self.assertEqual({c['path'] for c in plan['entry_plan']['changes']},
            {str(f.home / '.zcode/AGENTS.md'),
             str(f.home / '.config/opencode/AGENTS.md')})
        done = f.apply(plan, request)
        self.assertEqual(done['status'], 'completed', done)
        self.assertEqual(done['entries']['status'], 'completed')
        self.assertEqual(done['result']['migration']['migration_phase'], 'committed')
        self.assertEqual(set(f.ledger()['machine']['agents']),
                         {'codex', 'claude', 'workbuddy', 'zcode', 'opencode'})
        self.assertEqual(done['entries']['changes'], plan['entry_plan']['changes'])
        self.assertIsNone(cases.user_entries._PREVIEW_STATE.get())

    def test_explicit_scope_keeps_all_existing_migration_dependencies(self):
        f = self.fixture
        plan, request = f.plan(agents=['opencode'])
        self.assertEqual(plan['requested_agents'], ['opencode'])
        self.assertEqual(plan['entry_plan']['effective'], ['opencode'])
        targets = plan['plan']['migration_plan']['targets']
        for path in (f.home / '.codex/AGENTS.md', f.home / '.claude/CLAUDE.md',
                     f.home / '.workbuddy/MEMORY.md'):
            self.assertIn(str(path), {t['path'] for t in targets})
        done = f.apply(plan, request)
        self.assertEqual(done['status'], 'completed', done)
        self.assertFalse((f.home / '.zcode').exists())
        self.assertTrue((f.home / '.config/opencode/AGENTS.md').is_file())

    def test_entry_plan_tamper_rejected_before_any_write(self):
        f = self.fixture
        plan, request = f.plan()
        approval = cases.approved(copy.deepcopy(plan))
        approval['entry_plan']['effective'] = []
        before = f.snapshot()
        with self.assertRaises(cases.cli.InstallError):
            cases.cli.execute_machine(plan, approval, request=request)
        self.assertEqual(before, f.snapshot())

    def test_default_onboarding_from_historical_v012(self):
        f = self.fixture
        plan, request = f.plan()
        self.assertIsNotNone(plan['entry_plan'])
        self.assertEqual(f.apply(plan, request)['status'], 'completed')
        self.assertIn('opencode', f.ledger()['machine']['agents'])

    def test_same_source_repeat_discovers_new_agent_without_migration(self):
        f = self.fixture
        first, request = f.plan(agents=['opencode'])
        self.assertEqual(f.apply(first, request)['status'], 'completed')
        before = f.snapshot()
        plan, request = f.plan(operation_id='onboard-after-migration')
        self.assertTrue(plan['plan']['noop'])
        self.assertIsNone(plan['plan']['migration_plan'])
        self.assertEqual(plan['entry_plan']['machine_agents'], ['zcode'])
        self.assertEqual(before, f.snapshot())
        done = f.apply(plan, request)
        self.assertEqual(done['status'], 'completed', done)
        self.assertIn('zcode', f.ledger()['machine']['agents'])

    def test_fresh_install_keeps_full_default_scope(self):
        f = self.fixture
        home = f.area / 'fresh-home'
        home.mkdir()
        request = dict(f.req13, home=str(home), operation_id='fresh-default', conversions=[])
        plan = cases.cli.plan_machine(request)
        self.assertEqual(plan['requested_agents'], list(cases.paths.AGENT_ORDER))
        self.assertIn('opencode', plan['plan']['entry_plan']['effective'])
        self.assertFalse(any(home.iterdir()))
        done = cases.cli.execute_machine(plan, cases.approved(plan), request=request)
        self.assertEqual(done['status'], 'completed', done)
        self.assertTrue((home / '.config/opencode/AGENTS.md').is_file())

    def test_real_post_migration_drift_is_not_replaced_by_prediction(self):
        f = self.fixture
        plan, request = f.plan()
        migrate = cases.public_layout.execute_migration
        path = f.home / '.config/opencode/AGENTS.md'

        def changed(*args, **kwargs):
            result = migrate(*args, **kwargs)
            path.parent.mkdir(parents=True)
            path.write_bytes(b'new private rules after migration\n')
            return result

        with patch.object(cases.public_layout, 'execute_migration', side_effect=changed):
            done = f.apply(plan, request)
        self.assertEqual(done['status'], 'partial', done)
        self.assertEqual(done['entries']['errors'][0]['code'], 'approval_mismatch')
        self.assertEqual(path.read_bytes(), b'new private rules after migration\n')
        self.assertNotIn('opencode', f.ledger()['machine']['agents'])

    def test_prediction_context_cannot_execute_and_always_resets(self):
        f = self.fixture
        plan, request = f.plan()
        migration = plan['plan']['migration_plan']
        ledger = json.loads(bytes.fromhex(migration['v2_registry_hex']))
        before = f.snapshot()
        with cases.user_entries._preview_state(f.runtime, ledger, {}):
            result = cases.user_entries.run_user_entries(dict(request, approval={}))
            self.assertEqual(result['errors'][0]['code'], 'installer_context_required')
            result = cases.user_entries.run_user_entries(dict(request, interactive=True))
            self.assertEqual(result['errors'][0]['code'], 'installer_context_required')
        self.assertIsNone(cases.user_entries._PREVIEW_STATE.get())
        self.assertEqual(before, f.snapshot())


if __name__ == '__main__':
    unittest.main()
