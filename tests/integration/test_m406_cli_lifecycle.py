"""M4-06 CLI reversals through isolated copied product and synthetic executors."""
import json
import shutil
from test_m207_cli_cycle import CliHarness


class LifecycleCliTests(CliHarness):
    def test_DECLINE_revokes_owned_instructions_after_explicit_plan(self):
        rc,envelope=self.enable_memory();self.assertEqual(rc,0,envelope)
        before=self.snapshot(self.root,self.home,self.keeper,self.install.parent)
        for option in ('--memory','--no-memory'):
            rc,envelope=self.cli(['enable-memory','--project',str(self.root),option])
            self.assertEqual(rc,2,envelope)
            self.assertEqual(self.snapshot(self.root,self.home,self.keeper,self.install.parent),before)
        self.assertEqual(json.loads(self.registry.read_text())['projects'][str(self.root)]['memory_policy'],'follow_ck')
        self.assertNotIn(b'memory-denied',(self.root/'AGENTS.md').read_bytes())

    def test_SOURCE_missing_required_scripts_is_readonly_and_not_a_health_gap(self):
        rc, envelope = self.enable_memory(); self.assertEqual(rc, 0, envelope)
        (self.keeper/'scripts/install.py').unlink()
        (self.keeper/'scripts/context_keeper_probe.py').unlink()
        before = self.snapshot(self.root, self.home, self.keeper, self.install.parent)
        rc, envelope = self.check(); self.assertEqual(rc, 0, envelope)
        project = envelope['projects'][0]
        self.assertTrue(set(project['states']).isdisjoint({'source_available','skill_installed','bridge_assembled','store_authorized_ready'}))
        self.assertFalse(project['gaps'])
        self.assertEqual(self.snapshot(self.root, self.home, self.keeper, self.install.parent), before)
        print('CLI SOURCE missing CK has no health gap; zero persistent writes')

    def test_default_agent_scope_keeps_only_verified_installations(self):
        (self.home/'fixture-executors/bin/claude').unlink()
        shutil.rmtree(self.home/'Applications/WorkBuddy.app')
        rc, envelope = self.approve(['enable-memory', '--project', str(self.root)])
        self.assertEqual(rc, 0, envelope)
        self.assertEqual(envelope['projects'][0]['agents'], ['codex'])
        self.assertFalse((self.root/'CLAUDE.md').exists())
        self.assertFalse((self.home/'.workbuddy').exists())
