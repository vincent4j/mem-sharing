"""Six native launchers: isolated HOME, existing transaction/uninstall machinery."""
import json
import os
import stat
from pathlib import Path
from unittest.mock import patch
from test_m404_install import InstallFixture, approved
from test_m408_installer import cli
from agm_core import detect, uninstall, uninstall_recovery as recovery
from test_uninstall import approval

ROOTS = {'codex': '.codex/skills', 'claude': '.claude/skills',
         'workbuddy': '.workbuddy/skills', 'dsh': '.dsh/skills',
         'zcode': '.zcode/skills', 'opencode': '.config/opencode/skills'}

class SixNativeSkillsTests(InstallFixture):
    def setUp(self):
        super().setUp()
        real = detect.detect_agents
        def installed(*args, **kwargs):
            data = real(*args, **kwargs)
            for row in data['agents'].values(): row['status'] = 'installed'
            return data
        self.mock = patch.object(detect, 'detect_agents', side_effect=installed)
        self.mock.start(); self.addCleanup(self.mock.stop)

    def tree(self, root=None):
        return {str(p): (p.read_bytes(), p.stat().st_mode, p.stat().st_mtime_ns)
                for p in (root or self.home).rglob('*') if p.is_file()}

    def skill(self, agent):
        return self.home/ROOTS[agent]/'mem-sharing/SKILL.md'

    def nofollow_tree(self):
        nodes = [self.home]
        for root, directories, files in os.walk(self.home, followlinks=False):
            nodes.extend(Path(root)/name for name in directories+files)
        result = {}
        for path in nodes:
            meta = path.lstat()
            payload = os.readlink(path) if stat.S_ISLNK(meta.st_mode) else path.read_bytes() if stat.S_ISREG(meta.st_mode) else None
            result[str(path)] = (meta.st_mode, meta.st_mtime_ns, meta.st_ino, payload)
        return result

    def install_selected(self, agents):
        self.request['agents'] = agents
        plan = cli.plan_machine(self.request)
        return cli.execute_machine(plan, approved(plan), request=self.request)

    def test_default_six_selected_and_global_uninstall_preserves_private(self):
        originals = {}
        for agent, cfg in self.config.items():
            path = self.home / cfg['user_entry'].replace('{home}/', '')
            path.parent.mkdir(parents=True, exist_ok=True)
            originals[agent] = (path, (agent+' private original\r\n').encode())
            path.write_bytes(originals[agent][1])
        self.install_selected(None)
        for agent in ROOTS:
            body = self.skill(agent).read_text()
            self.assertIn('name: mem-sharing', body)
            self.assertIn(str(self.runtime.code/'SKILL.md'), body)
            self.assertNotIn(str(self.source), body)
        before = self.tree()
        repeat = self.install_selected(None)
        self.assertEqual(repeat['changes'], [])
        self.assertIsNone(repeat['fusion'])
        self.assertEqual(self.tree(), before)
        backup = self.area/'uninstall-backup'
        plan = uninstall.preview(home=self.home, backup_dir=backup)
        done = uninstall.execute(approval(recovery.summary(plan)), home=self.home, backup_dir=backup)
        self.assertEqual(done['status'], 'completed', done)
        for agent, (path, private) in originals.items():
            self.assertFalse(self.skill(agent).exists())
            self.assertIn(private, path.read_bytes())

    def test_codex_then_each_other_agent_reuses_public_and_selected_scope(self):
        self.install_selected(['codex'])
        for agent in ROOTS:
            self.assertEqual(self.skill(agent).exists(), agent=='codex')
        public = self.tree(self.runtime.root/'memories')
        installed = {'codex'}
        for agent in ['workbuddy', 'dsh', 'zcode', 'opencode', 'claude']:
            self.install_selected([agent]); installed.add(agent)
            for name in ROOTS: self.assertEqual(self.skill(name).exists(), name in installed)
            self.assertEqual(self.tree(self.runtime.root/'memories'), public)
            before = self.tree()
            result = self.install_selected([agent])
            self.assertEqual(result['changes'], [])
            self.assertIsNone(result['fusion'])
            self.assertEqual(self.tree(), before)

    def test_unknown_same_name_symlink_and_managed_drift_zero_write(self):
        self.install_selected(['codex'])
        for agent in ['workbuddy', 'dsh', 'zcode', 'opencode']:
            path = self.skill(agent); path.parent.mkdir(parents=True)
            path.write_text('user original Skill')
            before = self.tree()
            with self.assertRaises(ValueError): self.install_selected([agent])
            self.assertEqual(self.tree(), before)
            path.unlink(); path.symlink_to(self.source/'SKILL.md')
            before_link = self.nofollow_tree()
            target = self.source/'SKILL.md'
            target_before = target.read_bytes(), target.stat().st_mtime_ns
            with self.assertRaises(ValueError): self.install_selected([agent])
            self.assertEqual(self.nofollow_tree(), before_link)
            self.assertEqual((target.read_bytes(), target.stat().st_mtime_ns), target_before)
            path.unlink()
            path.parent.rmdir()
            external = self.area/('parent-target-'+agent)
            external.mkdir(); (external/'SKILL.md').write_bytes(b'outside user Skill\r\n')
            path.parent.symlink_to(external, target_is_directory=True)
            before_parent = self.nofollow_tree()
            external_before = (external/'SKILL.md').read_bytes(), (external/'SKILL.md').stat().st_mtime_ns
            with self.assertRaises(ValueError): self.install_selected([agent])
            self.assertEqual(self.nofollow_tree(), before_parent)
            self.assertEqual(((external/'SKILL.md').read_bytes(), (external/'SKILL.md').stat().st_mtime_ns), external_before)
            path.parent.unlink(); path.parent.mkdir()
            self.install_selected([agent])
            path.write_text('drift')
            before = self.tree()
            with self.assertRaises(ValueError): self.install_selected([agent])
            self.assertEqual(self.tree(), before)
            # Restore exact owned bytes for the next independent scope.
            path.write_bytes(self.skill('codex').read_bytes())

    def test_workbuddy_redirect_rejects_without_disclosing_value(self):
        self.install_selected(['codex'])
        before = self.tree()
        with patch.dict('os.environ', WORKBUDDY_CONFIG_DIR='/private/custom-secret-root'):
            with self.assertRaises(ValueError) as exc: self.install_selected(['workbuddy'])
        self.assertNotIn('custom-secret-root', str(exc.exception))
        self.assertEqual(self.tree(), before)

    def test_six_launcher_install_failure_rolls_back_then_recovery(self):
        from agm_core import user_install
        self.request['agents'] = None
        plan = self.plan()
        def crash(event, path):
            if event == 'after_entries': raise RuntimeError('six-entry interruption')
        with self.assertRaises(RuntimeError): self.execute(plan, hook=crash)
        recovery_plan = user_install.plan_recovery(plan['journal'], action='rollback')
        done = user_install.recover_install(recovery_plan, approved(recovery_plan), request=self.request)
        self.assertEqual(done['status'], 'rolled_back', done)
        for agent in ROOTS: self.assertFalse(self.skill(agent).exists())
