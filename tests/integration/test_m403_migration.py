"""Subprocess legacy writer, real hard crashes and competing writers in fake HOME."""
import json
import os
from pathlib import Path
import selectors
import subprocess
import sys
import unittest

sys.path.insert(0, str(Path(__file__).parents[1] / 'unit'))
from test_m403_migrate import MigrationFixture, approved, OLD_COMMIT
from agm_core import migrate, registry

SCRIPTS = Path(__file__).resolve().parents[2] / 'scripts'
RUNNER = r'''
import json, os, sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
from agm_core import migrate
plan = json.loads(Path(sys.argv[2]).read_text())
event = sys.argv[3]
def hook(stage, path):
    if stage == event:
        if sys.argv[4] == 'crash':
            os._exit(86)
        print('READY', flush=True)
        if sys.stdin.readline().strip() != 'RELEASE':
            raise RuntimeError('fixture release missing')
result = migrate.execute_migration(plan, dict(plan, confirmed_at='2026-10-30T00:00:00Z', reference='subprocess fixture approval'), hook=hook)
print(json.dumps(result), flush=True)
'''


class MigrationProcessTests(MigrationFixture):
    def raw_observation(self, label, command, returncode, stdout, stderr, **extra):
        # Optional external test-driver evidence; never an application write or
        # a verdict file. Default test runs create no repository artifacts.
        directory = os.environ.get('M403_EVIDENCE_DIR')
        if directory:
            destination = Path(directory) / 'process-observations.jsonl'
            with destination.open('a') as stream:
                stream.write(json.dumps(dict(label=label, argv=command, exit_code=returncode,
                    stdout=stdout, stderr=stderr, **extra), ensure_ascii=False) + '\n')

    def child(self, stage, mode):
        path = self.area / 'migration-plan.json'
        path.write_text(json.dumps(self.plan))
        return subprocess.Popen([sys.executable, '-B', '-c', RUNNER, str(SCRIPTS), str(path), stage, mode],
            cwd=self.area, env=dict(os.environ, HOME=str(self.home), PYTHONDONTWRITEBYTECODE='1'),
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

    def test_actual_pre_m4_enable_hits_nonfile_tombstone_and_cannot_rebuild(self):
        self.apply()
        before = self.old.joinpath('redirect.json').read_bytes()
        result = subprocess.run([sys.executable, '-B', str(self.source / 'scripts/agm.py'), 'enable-memory',
            '--project', str(self.repo), '--no-memory'], cwd=self.area,
            env=dict(os.environ, HOME=str(self.home), PYTHONDONTWRITEBYTECODE='1'), capture_output=True, text=True)
        self.raw_observation('pinned-old-enable-tombstone', result.args, result.returncode, result.stdout, result.stderr)
        self.assertEqual(result.returncode, 2, result.stderr)
        envelope = json.loads(result.stdout)
        self.assertEqual(envelope['errors'][0]['code'], 'path_conflict', envelope)
        self.assertTrue(self.old.is_dir())
        self.assertEqual(self.old.joinpath('redirect.json').read_bytes(), before)
        registry.require_installed(self.load())

    def test_real_old_new_and_second_migrator_cannot_write_concurrently(self):
        child = self.child('before_commit', 'hold')
        self.addCleanup(lambda: child.poll() is None and child.kill())
        try:
            with selectors.DefaultSelector() as selector:
                selector.register(child.stdout, selectors.EVENT_READ)
                self.assertTrue(selector.select(timeout=15), 'migration child did not reach hold point')
            self.assertEqual(child.stdout.readline().strip(), 'READY')
            request = {'home': str(self.home), 'project': str(self.repo), 'platform_config': self.config,
                       'agents': ['codex'], 'memory_choice': 'no', 'approval': None, 'interactive': False}
            request_path = self.area / 'new-writer-request.json'
            request_path.write_text(json.dumps(request))
            new_writer = "import sys,json; from pathlib import Path; sys.path.insert(0,sys.argv[1]); from agm_core.enable import run; result=run(json.loads(Path(sys.argv[2]).read_text())); print(json.dumps(result)); sys.exit(2 if result['status']=='failed' else 0)"
            commands = [[sys.executable, '-B', str(self.source / 'scripts/agm.py'), 'enable-memory', '--project', str(self.repo), '--no-memory'],
                        [sys.executable, '-B', '-c', new_writer, str(SCRIPTS), str(request_path)]]
            for command in commands:
                result = subprocess.run(command,
                    env=dict(os.environ, HOME=str(self.home), PYTHONDONTWRITEBYTECODE='1'), capture_output=True, text=True, timeout=15)
                self.raw_observation('competing-writer', command, result.returncode, result.stdout, result.stderr)
                envelope = json.loads(result.stdout)
                self.assertEqual(result.returncode, 2, envelope)
                self.assertEqual(envelope['errors'][0]['code'], 'lock_conflict', envelope)
            with self.assertRaises(migrate.MigrationError):
                self.apply()
            self.assertFalse(self.runtime.registry.exists())
            output, error = child.communicate('RELEASE\n', timeout=15)
            self.raw_observation('holding-migrator-release', child.args, child.returncode, output, error)
            self.assertEqual(child.returncode, 0, error)
            self.assertEqual(json.loads(output)['status'], 'committed')
            registry.require_installed(self.load())
        finally:
            if child.poll() is None:
                child.kill()
                child.communicate()
            else:
                child.stdin.close()
                child.stdout.close()
                child.stderr.close()

    def test_crash_after_completed_journal_only_cleans_up_exited_locks(self):
        child = self.child('after_finish', 'crash')
        output, error = child.communicate(timeout=15)
        self.assertEqual(child.returncode, 86, error)
        before = self.runtime.registry.read_bytes(), self.runtime.registry.stat().st_mtime_ns
        with self.assertRaisesRegex(registry.RegistryError, 'lock handoff'):
            registry.require_installed(self.load())
        self.assertEqual(migrate.inspect_migration(self.runtime, [self.old], allowed_user_paths=self.allowed)['scene'], 'interrupted')
        with self.assertRaises(migrate.MigrationError):
            migrate.plan_recovery(self.plan['journal'], action='rollback')
        recovery = migrate.plan_recovery(self.plan['journal'], action='continue')
        self.assertTrue(recovery['cleanup_only'])
        result = migrate.recover_migration(recovery, approved(recovery))
        self.raw_observation('continue-after-completed-journal', child.args, child.returncode, output, error,
                             recovery_plan=recovery, recovery_result=result)
        self.assertTrue(result['cleanup_only'])
        self.assertEqual((self.runtime.registry.read_bytes(), self.runtime.registry.stat().st_mtime_ns), before)
        registry.require_installed(self.load())

    def test_hard_crash_explicit_stale_lock_approval_then_continue_or_rollback(self):
        for action in ('continue', 'rollback'):
            for event in ('after_copy', 'after_old_unlink', 'after_tombstone_mkdir', 'after_redirect', 'after_commit', 'before_finish'):
                with self.subTest(action=action, event=event):
                    fixture = MigrationProcessTests('setUp')
                    fixture.setUp()
                    try:
                        child = fixture.child(event, 'crash')
                        output, error = child.communicate(timeout=15)
                        self.assertEqual(child.returncode, 86, error)
                        recovery = migrate.plan_recovery(fixture.plan['journal'], action=action)
                        self.assertEqual(len(recovery['confirmed_stale_locks']), 4)
                        self.assertTrue(all(Path(item['path']).is_dir() for item in recovery['confirmed_stale_locks']))
                        result = migrate.recover_migration(recovery, approved(recovery))
                        fixture.raw_observation(action + '-' + event, child.args, child.returncode, output, error,
                            recovery_plan=recovery, recovery_result=result,
                            target_exists=fixture.runtime.registry.exists(), legacy_is_file=fixture.old.is_file(),
                            legacy_is_directory=fixture.old.is_dir())
                        self.assertEqual(result['status'], 'committed' if action == 'continue' else 'rolled_back')
                        if action == 'continue':
                            registry.require_installed(fixture.load())
                            self.assertTrue(fixture.old.is_dir())
                        else:
                            self.assertEqual(fixture.old.read_bytes(), fixture.before_raw)
                            self.assertFalse(fixture.runtime.registry.exists())
                        self.assertTrue(all(not Path(item['path']).exists() for item in recovery['confirmed_stale_locks']))
                    finally:
                        fixture.doCleanups()


if __name__ == '__main__':
    unittest.main()
