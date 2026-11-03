"""Desktop adapter contracts using synthetic apps/HOMEs only; no desktop acceptance."""
import copy
import json
import os
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_m404_install import InstallFixture, approved
from test_m204_enable import EnableFixture
from test_m405_detect import DetectFixture, fake_codesign
from agm_core import check, detect, enable, paths, registry, user_entries, user_install

DESKTOP = ('dsh', 'zcode')


def snapshot(root):
    return {str(p.relative_to(root)): (p.lstat().st_mode, p.lstat().st_mtime_ns,
            os.readlink(p) if p.is_symlink() else p.read_bytes() if p.is_file() else None)
            for p in [root, *root.rglob('*')]}


def installed_facts(config, home):
    facts = detect.detect_agents(config, None, home=str(home), search_paths=[], app_directories=[])
    for agent in DESKTOP:
        facts['agents'][agent].update(status='installed', summary='synthetic installed desktop')
    return facts


class DesktopDetectionTests(DetectFixture):
    def test_signed_bundles_and_all_five_enumerated(self):
        for agent in DESKTOP:
            signal = self.config[agent]['installation_signals'][1]
            self.app_bundle(self.apps, signal['bundle_name'], product=signal['product_name'], version='1.0')
        before = snapshot(self.area)
        result = self.detect(runner=fake_codesign(identifier='com.example.fixture'))
        self.assertEqual(list(result['agents']), list(paths.AGENT_ORDER))
        for agent in DESKTOP:
            self.assertEqual(result['agents'][agent]['status'], 'installed')
        self.assertEqual(snapshot(self.area), before)
        self.assertEqual(paths.resolve_agents(), ['codex', 'claude', 'workbuddy'])
        allowed = paths.allowed_user_paths(self.config, None, home=str(self.home))
        for agent in DESKTOP:
            self.assertIn(str(self.home / ('.'+agent) / 'AGENTS.md'), allowed)

    def test_desktop_signature_does_not_block_but_version_and_hint_remain_checked(self):
        for agent in DESKTOP:
            with self.subTest(agent=agent):
                (self.home / ('.'+agent)).mkdir()
                self.assertEqual(self.detect([agent])['agents'][agent]['status'], 'unknown')
                signal = self.config[agent]['installation_signals'][1]
                self.app_bundle(self.apps, signal['bundle_name'], product=signal['product_name'], version='1.0')
                bad = self.detect([agent], runner=fake_codesign(identifier='wrong'))
                self.assertEqual(bad['agents'][agent]['status'], 'installed')
                bad = self.detect([agent], runner=fake_codesign(identifier='com.example.fixture', verify_rc=1))
                self.assertEqual(bad['agents'][agent]['status'], 'installed')
                info = self.apps / signal['bundle_name'] / 'Contents/Info.plist'
                import plistlib
                data = plistlib.loads(info.read_bytes()); data.pop('CFBundleShortVersionString')
                info.write_bytes(plistlib.dumps(data))
                self.assertEqual(self.detect([agent], runner=fake_codesign(identifier='com.example.fixture'))['agents'][agent]['status'], 'unknown')


class DesktopInstallTests(InstallFixture):
    def setUp(self):
        super().setUp()
        self.facts = installed_facts(self.config, self.home)
        self.addCleanup(patch.stopall)
        patch.object(detect, 'detect_agents', return_value=self.facts).start()
        patch.dict(os.environ, {'DSH_HOME': ''}).start()

    def test_default_connects_all_installed_desktop_agents(self):
        self.assertEqual(self.plan()['effective_agents'], list(DESKTOP))
        self.execute()
        for agent in DESKTOP:
            self.assertTrue((self.home / ('.'+agent) / 'AGENTS.md').is_file())

    def test_explicit_install_preserves_private_bytes_and_is_idempotent(self):
        self.request['agents'] = list(DESKTOP)
        private = b'\xef\xbb\xbfprivate\xff\r\n<!-- context-keeper:start -->\nprivate CK\n<!-- context-keeper:end -->'
        for agent in DESKTOP:
            p = self.home / ('.'+agent) / 'AGENTS.md'; p.parent.mkdir(); p.write_bytes(private); remember_mode(self, p)
        before = snapshot(self.home)
        plan = self.plan()
        self.assertEqual(before, snapshot(self.home))
        self.assertEqual(plan['effective_agents'], list(DESKTOP))
        self.assertEqual(self.execute(plan)['status'], 'completed')
        ledger = registry.load_registry(self.runtime.registry,
            allowed_user_paths=paths.allowed_user_paths(self.config, None, home=str(self.home)))
        self.assertEqual(list(ledger['machine']['agents']), list(DESKTOP))
        for agent in DESKTOP:
            p = self.home / ('.'+agent) / 'AGENTS.md'
            assert_opaque(self, p.read_bytes(), private, index=self.runtime.root/"memories/MEMORY.md", path=p)
            self.assertIn(user_entries.NATIVE_FALLBACK_TEXTS[agent].encode(), p.read_bytes())
            self.assertNotIn(user_entries.CODEX_FALLBACK_TEXT.encode(), p.read_bytes())
            self.assertFalse((p.parent / 'skills').exists())
            self.assertEqual(user_entries.connection_status(self.runtime, self.config, ledger, [agent])[agent]['status'], 'connected')
        before = snapshot(self.home)
        same = user_entries.run_user_entries(self.request)
        self.assertEqual(same['status'], 'completed', same)
        self.assertEqual(snapshot(self.home), before)
        p = self.home / '.zcode/AGENTS.md'; p.write_bytes(p.read_bytes().replace(b'AGENTS.md', b'BROKEN.md'))
        before = snapshot(self.home)
        result = user_entries.run_user_entries(self.request)
        self.assertEqual(result['status'], 'failed', result)
        self.assertEqual(snapshot(self.home), before)

    def test_absent_unknown_and_wrong_approval_zero_write(self):
        self.request['agents'] = list(DESKTOP)
        for status in ('absent', 'unknown'):
            self.facts['agents']['zcode']['status'] = status
            before = snapshot(self.home)
            with self.assertRaises(ValueError): self.plan()
            self.assertEqual(snapshot(self.home), before)
        self.facts['agents']['zcode']['status'] = 'installed'
        plan = self.plan(); before = snapshot(self.home)
        with self.assertRaises(ValueError): self.execute(dict(plan, effective_agents=['dsh']))
        self.assertEqual(snapshot(self.home), before)

    def test_redirect_stops_whole_install_without_echoing_private_value(self):
        self.request['agents'] = list(DESKTOP)
        sentinel = str(self.area / 'PRIVATE_SENTINEL')
        with patch.dict(os.environ, DSH_HOME=sentinel):
            before = snapshot(self.home)
            with self.assertRaises(ValueError) as ctx: self.plan()
            self.assertNotIn(sentinel, str(ctx.exception))
            self.assertIn('dsh_home_redirected', str(ctx.exception))
            self.assertEqual(snapshot(self.home), before)

    def test_dsh_backslash_prefix_allows_default_install_and_rejects_private_root(self):
        self.request['agents'] = ['dsh']
        with patch.dict(os.environ, DSH_HOME=r'~\.dsh'):
            plan = self.plan()
            self.assertEqual(plan['effective_agents'], ['dsh'])
            self.assertEqual(self.execute(plan)['status'], 'completed')
        sentinel = r'~\PRIVATE_SENTINEL'
        with patch.dict(os.environ, DSH_HOME=sentinel):
            before = snapshot(self.home)
            result = user_entries.run_user_entries(self.request)
            self.assertEqual(result['status'], 'failed', result)
            self.assertEqual(result['errors'][0]['code'], 'dsh_home_redirected')
            self.assertNotIn(sentinel, json.dumps(result))
            self.assertNotIn('PRIVATE_SENTINEL', json.dumps(result))
            self.assertEqual(snapshot(self.home), before)

    def test_dsh_root_resolution_matches_relative_and_tilde_contract(self):
        cwd = os.getcwd(); os.chdir(self.home); self.addCleanup(os.chdir, cwd)
        for value in ('', ' \t\n', '~/.dsh', str(self.home / '.dsh'), '.dsh', './other/../.dsh', r'~\.dsh'):
            with self.subTest(value=value), patch.dict(os.environ, DSH_HOME=value):
                self.assertFalse(user_entries.dsh_home_redirected(self.home))
        for value in ('~', ' .dsh ', str(self.home / '.dsh')+' ', 'elsewhere', '~\\', r'~\other', r'~\.dsh\child', r'~/.dsh\child'):
            with self.subTest(value=value), patch.dict(os.environ, DSH_HOME=value):
                self.assertTrue(user_entries.dsh_home_redirected(self.home))
        with patch.dict(os.environ, clear=True):
            self.assertFalse(user_entries.dsh_home_redirected(self.home))


class DesktopProjectTests(EnableFixture):
    def setUp(self):
        super().setUp()
        self.request['agents'] = list(DESKTOP)
        facts = installed_facts(self.config, self.home)
        self.addCleanup(patch.stopall)
        patch.object(detect, 'detect_agents', return_value=facts).start()

    def test_native_check_tombstone_disabled_and_private_bytes(self):
        private = b'\xef\xbb\xbfproject private\xff\r\n'
        entry = self.root / 'AGENTS.md'; entry.write_bytes(private)
        self.apply('follow_ck')
        for agent in DESKTOP:
            self.assertFalse((self.root / ('.'+agent)).exists())
        self.assertFalse((self.root / 'CLAUDE.md').exists())
        self.assertTrue(entry.read_bytes().startswith(private))
        before = snapshot(self.home), snapshot(self.root)
        result = check.run(self.request)
        self.assertEqual(result['status'], 'completed', result)
        self.assertEqual(result['projects'][0]['agents'], list(DESKTOP))
        self.assertEqual((snapshot(self.home), snapshot(self.root)), before)
        # 历史停用登记(remove 已退役):直接登记 disabled,默认流程跳过、私字节保全。
        data = self.load()
        data['projects'][str(self.root)]['memory_policy'] = 'disabled'
        allowed = paths.allowed_user_paths(self.config, None, home=str(self.home))
        self.runtime.registry.write_bytes(registry.serialize_registry(data, allowed_user_paths=allowed))
        self.assertIn(private, entry.read_bytes())
        self.request.update(approval=None)
        before = snapshot(self.home), snapshot(self.root)
        result = enable.run(self.request)
        self.assertEqual(result['status'], 'gaps', result)
        self.assertIn('历史停用登记', result['next_action'])
        self.assertEqual((snapshot(self.home), snapshot(self.root)), before)
        self.assertEqual(self.load()['projects'][str(self.root)]['memory_policy'], 'disabled')
        self.assertEqual(check.run(self.request)['status'], 'completed')
        self.assertTrue(any('历史停用登记' in w for w in check.run(self.request)['warnings']))

    def test_large_native_entry_does_not_inherit_codex_budget_warning(self):
        self.apply('follow_ck')
        entry = self.root / 'AGENTS.md'; entry.write_bytes(entry.read_bytes()+b'x'*40000)
        self.assertEqual(check._entry_warnings(DESKTOP, self.config, home=str(self.home), checkout=str(self.root)), [])
        warnings = check._entry_warnings(['codex'], self.config, home=str(self.home), checkout=str(self.root))
        self.assertTrue(any('32KiB' in w for w in warnings))

from entry_opaque_fixture import assert_opaque, remember_mode
