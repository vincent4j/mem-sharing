"""Real CLI subprocess contract with synthetic HOME and executor installations."""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / 'scripts'))
sys.path.insert(0, str(REPO / 'tests/unit'))
from runtime_fixture import CLI_DETECTION_BOOTSTRAP, seed_project_executors, seed_runtime


class BatchCliTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.area = Path(self.temp.name).resolve()
        self.home = self.area / 'home'
        self.home.mkdir()
        self.runtime = seed_runtime(self.home)
        self.signals = seed_project_executors(self.home)
        self.directory = self.area / '目录 with spaces'
        self.directory.mkdir()
        self.args = ['enable-memory-batch', '--directory', str(self.directory)]

    def repo(self, name):
        path = self.directory / name
        path.mkdir()
        subprocess.run(['git', 'init', '-q', str(path)], check=True, capture_output=True)
        return path

    def cli(self, args):
        env = dict(os.environ, HOME=str(self.home), PATH=self.signals['search_paths'][0], PYTHONDONTWRITEBYTECODE='1')
        proc = subprocess.run([sys.executable, '-B', '-c', CLI_DETECTION_BOOTSTRAP,
                               str(REPO / 'scripts/agm.py'), *args], env=env, cwd=self.area, capture_output=True, text=True)
        return proc.returncode, json.loads(proc.stdout)

    def approval(self):
        rc, preview = self.cli(self.args)
        self.assertEqual(rc, 5, preview)
        plan = json.loads(preview['next_action'])
        plan.update(confirmed_at='2026-10-30T00:00:00Z', reference='one synthetic CLI approval')
        approval = self.area / 'approval.json'
        approval.write_text(json.dumps(plan, ensure_ascii=False))
        return approval, preview

    def test_preview_approve_execute_noop_json_envelope(self):
        root = self.repo('一'); self.repo('二')
        registry_before = self.runtime.registry.read_bytes()
        approval, preview = self.approval()
        self.assertFalse((root / 'AGENTS.md').exists())
        self.assertEqual(self.runtime.registry.read_bytes(), registry_before)
        self.assertFalse(self.runtime.lock.exists())
        self.assertFalse(self.runtime.backups.exists())
        self.assertEqual(len(preview['projects']), 2)
        rc, executed = self.cli(self.args + ['--approval-file', str(approval)])
        self.assertEqual(rc, 0, executed)
        self.assertEqual(executed['command'], 'enable-memory-batch')
        self.assertEqual({r['result'] for r in executed['projects']}, {'completed'})
        self.assertTrue(all(c['applied'] for c in executed['changes']))
        self.assertFalse((root / 'CLAUDE.md').exists())
        rc, repeated = self.cli(self.args)
        self.assertEqual(rc, 0, repeated)
        self.assertEqual(repeated['changes'], [])
        self.assertEqual({r['state'] for r in repeated['projects']}, {'enabled'})

    def test_explicit_agent_creates_claude_with_same_kernel(self):
        root = self.repo('claude')
        self.args += ['--agent', 'claude']
        approval, _ = self.approval()
        rc, result = self.cli(self.args + ['--approval-file', str(approval)])
        self.assertEqual(rc, 0, result)
        self.assertEqual((root / 'CLAUDE.md').read_bytes(), b'@AGENTS.md\n')

    def test_stale_directory_plan_is_rejected_before_any_write(self):
        root = self.repo('a')
        approval, _ = self.approval()
        self.repo('b')
        before = self.runtime.registry.read_bytes()
        rc, result = self.cli(self.args + ['--approval-file', str(approval)])
        self.assertEqual(rc, 5, result)
        self.assertEqual(result['errors'][0]['code'], 'approval_mismatch')
        self.assertEqual(self.runtime.registry.read_bytes(), before)
        self.assertFalse((root / 'AGENTS.md').exists())

    def test_duplicate_approval_keys_rejected(self):
        root = self.repo('a')
        approval = self.area / 'bad.json'
        approval.write_text('{"command":"enable-memory-batch","command":"enable-memory"}')
        rc, result = self.cli(self.args + ['--approval-file', str(approval)])
        self.assertEqual(rc, 2, result)
        self.assertEqual(result['errors'][0]['code'], 'approval_file_invalid')
        self.assertFalse((root / 'AGENTS.md').exists())

    def test_duplicate_and_unknown_arguments_rejected(self):
        for tail in (['--directory', str(self.directory)], ['--memory'], ['--all'], ['--agent', 'invalid']):
            rc, result = self.cli(self.args + tail)
            self.assertEqual(rc, 2, result)
            self.assertEqual(result['command'], 'enable-memory-batch')


if __name__ == '__main__':
    unittest.main()
