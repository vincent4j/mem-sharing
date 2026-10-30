"""Batch contract tests: all projects, executor signals and HOME are synthetic."""
import copy
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'scripts'))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import agm
from agm_core import batch_enable, enable, paths, registry, remove
from runtime_fixture import seed_runtime, seed_project_executors

NOW = '2026-10-30T00:00:00Z'


def snapshot(root):
    return {str(p.relative_to(root)): (p.lstat().st_mode, p.lstat().st_mtime_ns,
            os.readlink(p) if p.is_symlink() else p.read_bytes() if p.is_file() else None)
            for p in root.rglob('*')}


class BatchTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.area = Path(self.temp.name).resolve()
        self.home = self.area / 'home'
        self.home.mkdir()
        self.runtime = seed_runtime(self.home)
        self.directory = self.area / 'projects'
        self.directory.mkdir()
        self.config = paths.select_platform(paths.load_agents_table(), 'darwin')
        self.request = dict(directory=str(self.directory), agents=None, approval=None, interactive=False,
                            home=str(self.home), runtime_layout=self.runtime, platform_config=self.config)
        self.request.update(seed_project_executors(self.home))

    def git(self, *args):
        subprocess.run(['git', *map(str, args)], check=True, capture_output=True)

    def repo(self, name):
        root = self.directory / name
        root.mkdir(parents=True)
        self.git('init', '-q', root)
        return root

    def single(self, root, *, policy=None, removing=False):
        request = dict(self.request, project=str(root), agents=None, memory_choice=policy)
        runner = remove.run if removing else enable.run
        preview = runner(request)
        self.assertEqual(preview['status'], 'approval_required', preview)
        approval = json.loads(preview['next_action'])
        approval.update(confirmed_at=NOW, reference='synthetic single approval')
        result = runner(dict(request, approval=approval))
        self.assertEqual(result['status'], 'completed', result)

    def preview(self):
        before = snapshot(self.area)
        result = batch_enable.run(self.request)
        self.assertEqual(snapshot(self.area), before, result)
        self.assertEqual(result['status'], 'approval_required', result)
        plan = json.loads(result['next_action'])
        plan.update(confirmed_at=NOW, reference='one batch confirmation')
        return result, plan

    def execute(self, approval):
        return batch_enable.run(dict(self.request, approval=approval))

    def test_mixed_directory_preview_and_execute(self):
        fresh = self.repo('fresh 中文')
        old = self.repo('existing agents')
        original = b'# user rules\r\nuser\xff'
        (old / 'AGENTS.md').write_bytes(original)
        claude = self.repo('existing claude')
        (claude / 'CLAUDE.md').write_bytes(original)
        active = self.repo('enabled')
        self.single(active)
        disabled = self.repo('disabled')
        self.single(disabled, policy='disabled')
        removed = self.repo('removed')
        self.single(removed)
        self.single(removed, removing=True)
        plain = self.directory / 'plain'
        plain.mkdir()
        (plain / 'README').write_text('not git')
        preserved = {p: snapshot(p) for p in (active, disabled, removed, plain)}
        preview, approval = self.preview()
        self.assertEqual(len(preview['projects']), 6)
        states = {Path(row['path']).name: row['state'] for row in preview['projects']}
        self.assertEqual(states['disabled'], 'disabled')
        self.assertEqual(states['removed'], 'disabled')
        self.assertEqual(states['enabled'], 'enabled')
        self.assertTrue(all('需显式单独重新启用' in r['action'] for r in preview['projects'] if r['state'] == 'disabled'))
        with patch('builtins.input', side_effect=AssertionError('no per-project prompt')):
            result = self.execute(approval)
        self.assertEqual(result['status'], 'completed', result)
        for root in (fresh, old, claude):
            self.assertIn(enable.KEEPER_MARKER['start'].encode(), (root / 'AGENTS.md').read_bytes())
            self.assertFalse((root / '.workbuddy').exists())
            self.assertFalse((root / 'docs/context-keeper').exists())
        self.assertTrue((old / 'AGENTS.md').read_bytes().startswith(original))
        self.assertEqual((claude / 'CLAUDE.md').read_bytes(), original)
        self.assertFalse((fresh / 'CLAUDE.md').exists())
        for root, before in preserved.items():
            self.assertEqual(snapshot(root), before)
        self.assertEqual(len([r for r in result['projects'] if r['result'] == 'completed']), 3)
        before = snapshot(self.area)
        self.assertEqual(batch_enable.run(self.request)['status'], 'completed')
        self.assertEqual(snapshot(self.area), before)

    def test_explicit_claude_passthrough_and_native_workbuddy(self):
        root = self.repo('project')
        native = root / '.workbuddy/memory'
        native.mkdir(parents=True)
        raw = b'user native\xff\r\n'
        (native / 'MEMORY.md').write_bytes(raw)
        (root / 'CLAUDE.md').write_bytes(raw)
        self.request['agents'] = ['claude', 'workbuddy']
        _, approval = self.preview()
        self.assertEqual(self.execute(approval)['status'], 'completed')
        self.assertIn(b'@AGENTS.md', (root / 'CLAUDE.md').read_bytes())
        self.assertTrue((root / 'CLAUDE.md').read_bytes().startswith(raw))
        self.assertTrue((native / 'MEMORY.md').read_bytes().endswith(raw))
        self.assertIn(enable.WORKBUDDY_MARKER['start'].encode(), (native / 'MEMORY.md').read_bytes())

    def test_single_interactive_confirmation_and_decline(self):
        self.repo('a'); self.repo('b')
        calls = []
        before = snapshot(self.area)
        def decline(prompt):
            calls.append(prompt)
            return False
        request = dict(self.request, interactive=True, confirm=decline)
        self.assertEqual(batch_enable.run(request)['status'], 'approval_required')
        self.assertEqual(len(calls), 1)
        self.assertEqual(snapshot(self.area), before)
        calls.clear()
        def approve(prompt):
            calls.append(prompt)
            return True
        result = batch_enable.run(dict(request, confirm=approve))
        self.assertEqual(result['status'], 'completed', result)
        self.assertEqual(len(calls), 1)

    def test_directory_drift_invalidates_whole_approval(self):
        root = self.repo('a')
        _, approval = self.preview()
        self.repo('b')
        before = snapshot(self.area)
        result = self.execute(approval)
        self.assertEqual(result['status'], 'approval_required', result)
        self.assertEqual(result['errors'][0]['code'], 'approval_mismatch')
        self.assertEqual(snapshot(self.area), before)
        self.assertFalse((root / 'AGENTS.md').exists())

    def test_output_drift_invalidates_whole_approval(self):
        self.repo('a'); last = self.repo('z')
        _, approval = self.preview()
        (last / 'AGENTS.md').write_text('user changed after preview')
        before = snapshot(self.area)
        self.assertEqual(self.execute(approval)['status'], 'approval_required')
        self.assertEqual(snapshot(self.area), before)

    def test_registry_drift_invalidates_whole_approval(self):
        self.repo('a')
        _, approval = self.preview()
        self.single(self.repo('b'), policy='disabled')
        before = snapshot(self.area)
        self.assertEqual(self.execute(approval)['status'], 'approval_required')
        self.assertEqual(snapshot(self.area), before)

    def test_under_lock_recheck_precedes_any_project_write(self):
        first = self.repo('a'); last = self.repo('z')
        def approve(prompt):
            (last / 'AGENTS.md').write_text('changed at confirmation')
            return True
        result = batch_enable.run(dict(self.request, interactive=True, confirm=approve))
        self.assertEqual(result['status'], 'approval_required', result)
        self.assertFalse((first / 'AGENTS.md').exists())
        self.assertFalse(self.runtime.backups.exists())

    def test_lock_conflict_is_read_only(self):
        self.repo('a')
        self.runtime.lock.mkdir()
        before = snapshot(self.area)
        result = batch_enable.run(self.request)
        self.assertEqual(result['errors'][0]['code'], 'lock_conflict')
        self.assertEqual(snapshot(self.area), before)

    def test_corrupt_registry_blocks_without_rebuild(self):
        self.repo('a')
        self.runtime.registry.write_text('{bad')
        before = snapshot(self.area)
        result = batch_enable.run(self.request)
        self.assertEqual(result['status'], 'failed', result)
        self.assertEqual(snapshot(self.area), before)

    def test_blocked_project_prevents_entire_batch(self):
        first = self.repo('a'); last = self.repo('z')
        (last / 'AGENTS.md').mkdir()
        before = snapshot(self.area)
        result = batch_enable.run(self.request)
        self.assertEqual(result['status'], 'failed', result)
        self.assertEqual(snapshot(self.area), before)
        self.assertFalse((first / 'AGENTS.md').exists())

    def test_empty_and_non_git_directory_noop(self):
        (self.directory / 'plain').mkdir()
        before = snapshot(self.area)
        result = batch_enable.run(self.request)
        self.assertEqual(result['status'], 'completed')
        self.assertEqual(result['projects'], [])
        self.assertEqual(snapshot(self.area), before)

    def test_directory_itself_nested_repo_git_metadata_and_symlinks(self):
        root = self.repo('outer')
        nested = root / 'nested'
        nested.mkdir(); self.git('init', '-q', nested)
        fake = root / '.git/fake'
        fake.mkdir(); self.git('init', '-q', fake)
        (self.directory / 'alias').symlink_to(root, target_is_directory=True)
        self.request['directory'] = str(root)
        result, _ = self.preview()
        self.assertEqual({r['path'] for r in result['projects']}, {str(root), str(nested)})

    def test_worktree_excluded_separate_git_dir_is_main(self):
        main = self.repo('main')
        self.git('-C', main, '-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid', 'commit', '--allow-empty', '-qm', 'fixture')
        linked = self.directory / 'linked'
        self.git('-C', main, 'worktree', 'add', '--detach', linked)
        separate = self.directory / 'separate'
        self.git('init', '-q', '--separate-git-dir', self.area / 'metadata', separate)
        preview, approval = self.preview()
        rows = {Path(r['path']).name: r for r in preview['projects']}
        self.assertEqual(rows['linked']['state'], 'excluded')
        self.assertEqual(rows['separate']['state'], 'new')
        self.assertEqual(self.execute(approval)['status'], 'completed')
        self.assertFalse((linked / 'AGENTS.md').exists())

    def test_failure_after_first_project_preserves_completed_and_stops_rest(self):
        first = self.repo('a'); last = self.repo('b'); pending = self.repo('z')
        _, approval = self.preview()
        def hook(event, path):
            if event == 'before_write' and Path(path).is_relative_to(last):
                raise OSError('fixture write failure')
        result = batch_enable.run(dict(self.request, approval=approval, transaction_hook=hook))
        self.assertEqual(result['status'], 'failed', result)
        self.assertTrue((first / 'AGENTS.md').exists())
        self.assertFalse((last / 'AGENTS.md').exists())
        self.assertFalse((pending / 'AGENTS.md').exists())
        self.assertEqual([row['result'] for row in result['projects']], ['completed', 'failed', 'not_started'])
        self.assertTrue(result['changes'])

    def test_submodule_git_file_uses_same_main_checkout_rule(self):
        parent = self.repo('parent')
        child = parent / 'submodule'
        (parent / '.git/modules').mkdir()
        self.git('init', '-q', '--separate-git-dir', parent / '.git/modules/sub', child)
        from agm_core import project
        identity = project.resolve_project(child)
        self.assertEqual(identity.main_checkout, child)
        result, approval = self.preview()
        self.assertEqual({r['path'] for r in result['projects']}, {str(parent), str(child)})
        self.assertEqual(self.execute(approval)['status'], 'completed')

    def test_registered_rows_never_call_enable_even_if_entries_missing(self):
        active = self.repo('active'); disabled = self.repo('disabled')
        self.single(active); self.single(disabled, policy='disabled')
        (active / 'AGENTS.md').unlink()
        before = snapshot(self.area)
        with patch.object(enable, 'run', side_effect=AssertionError('registered row must not enable')):
            result = batch_enable.run(self.request)
        self.assertEqual(result['status'], 'completed', result)
        self.assertEqual({r['result'] for r in result['projects']}, {'skipped'})
        self.assertEqual(snapshot(self.area), before)

    def test_missing_machine_and_no_executor_do_not_initialize(self):
        root = self.repo('a')
        request = dict(self.request, agents=['codex'], search_paths=[], app_directories=[])
        before = snapshot(self.area)
        result = batch_enable.run(request)
        self.assertEqual(result['status'], 'failed', result)
        self.assertEqual(snapshot(self.area), before)
        self.runtime.registry.unlink()
        before = snapshot(self.area)
        result = batch_enable.run(self.request)
        self.assertEqual(result['errors'][0]['code'], 'machine_not_installed')
        self.assertEqual(snapshot(self.area), before)
        self.assertFalse((root / 'AGENTS.md').exists())

    def test_invalid_directory_and_symlink_root_rejected(self):
        root = self.repo('a')
        alias = self.area / 'alias'
        alias.symlink_to(root, target_is_directory=True)
        for target in (alias, self.area / 'missing'):
            before = snapshot(self.area)
            result = batch_enable.run(dict(self.request, directory=str(target)))
            self.assertEqual(result['status'], 'failed', result)
            self.assertEqual(snapshot(self.area), before)

    def test_git_identity_replacement_does_not_inherit_enabled_policy(self):
        root = self.repo('a')
        self.single(root)
        import shutil
        shutil.rmtree(root / '.git')
        self.git('init', '-q', '--separate-git-dir', self.area / 'new-metadata', root)
        before = snapshot(self.area)
        result = batch_enable.run(self.request)
        self.assertEqual(result['errors'][0]['code'], 'project_identity_mismatch')
        self.assertEqual(snapshot(self.area), before)

    def test_cli_parsing_and_batch_approval_structure(self):
        root = self.repo('a')
        _, approval = self.preview()
        batch_enable.validate_approval(approval, agents=paths.resolve_agents(None))
        for mutate in ('command', 'registry_sha256', 'projects', 'confirmed_at'):
            bad = copy.deepcopy(approval)
            bad[mutate] = None
            with self.assertRaises(ValueError):
                agm.validate_approval(bad, command=batch_enable.COMMAND, agents=paths.resolve_agents(None), memory_choice=None)
        args = agm.build_parser().parse_args([batch_enable.COMMAND, '--directory', str(root), '--agent', 'claude'])
        self.assertEqual(args.agent, ['claude'])
        for argv in ([batch_enable.COMMAND], [batch_enable.COMMAND, '--directory', str(root), '--no-memory']):
            out = io.StringIO()
            rc = agm.main(argv, stdout=out, stderr=io.StringIO(), home=str(self.home), platform='darwin', interactive=False)
            self.assertEqual(rc, 2)
            self.assertEqual(json.loads(out.getvalue())['command'], batch_enable.COMMAND)

    def test_tampered_subplan_rejected_without_writes(self):
        self.repo('a')
        _, approval = self.preview()
        approval['projects'][0]['enable_plan']['memory_policy'] = 'disabled'
        before = snapshot(self.area)
        self.assertEqual(self.execute(approval)['status'], 'failed')
        self.assertEqual(snapshot(self.area), before)


if __name__ == '__main__':
    unittest.main()
