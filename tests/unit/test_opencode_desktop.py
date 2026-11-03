"""Synthetic bundles/CLI and signature runner; no real App or session acceptance."""
import plistlib
import json
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).parent))
from test_m405_detect import DetectFixture, fake_codesign


class OpenCodeDesktopTests(DetectFixture):
    def desktop(self, directory=None, **changes):
        bundle = self.app_bundle(directory or self.apps, 'OpenCode.app', product='OpenCode',
                                 version='2.2.5', bundle_id='ai.opencode.desktop')
        plist = bundle / 'Contents/Info.plist'
        info = plistlib.loads(plist.read_bytes())
        info.update(CFBundleDisplayName='OpenCode', CFBundleVersion='2.2.5')
        info.update(changes)
        plist.write_bytes(plistlib.dumps(info))
        return bundle

    def cli(self, directory=None):
        target = (directory or self.bin_dir) / 'opencode'
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(bytes.fromhex('cffaedfe') + b'\x00' * 64)
        target.chmod(0o755)
        return target

    def result(self, **options):
        options.setdefault('runner', fake_codesign(identifier='ai.opencode.desktop'))
        return self.detect(['opencode'], **options)['agents']['opencode']

    def test_app_only_has_desktop_identity_version_and_zero_writes(self):
        self.desktop()
        before = {str(p): (p.stat().st_mtime_ns, p.read_bytes() if p.is_file() else None)
                  for p in self.area.rglob('*')}
        signer = fake_codesign(identifier='ai.opencode.desktop')
        result = self.result(runner=signer)
        self.assertEqual(result['status'], 'installed')
        self.assertEqual(result['surfaces']['desktop']['status'], 'verified')
        self.assertEqual(result['surfaces']['cli']['status'], 'unverified')
        record = next(r for r in result['evidence'] if r['result'] == 'verified')
        self.assertEqual((record['name'], record['version']), ('ai.opencode.desktop', '2.2.5'))
        self.assertEqual(signer.calls,[])
        self.assertEqual(record['signature_policy'],'not_required')
        self.assertEqual(before, {str(p): (p.stat().st_mtime_ns, p.read_bytes() if p.is_file() else None)
                                 for p in self.area.rglob('*')})

    def test_cli_only_does_not_prove_desktop_presence(self):
        self.cli()
        result = self.result()
        self.assertEqual(result['status'], 'installed')
        self.assertEqual(result['surfaces']['desktop']['status'], 'unverified')
        self.assertEqual(result['surfaces']['cli']['status'], 'verified')
        record = next(r for r in result['evidence'] if r['result'] == 'verified')
        self.assertNotIn('version', record)

    def test_official_native_cli_and_desktop_coexist(self):
        self.cli(); self.desktop()
        result = self.result()
        self.assertEqual(result['status'], 'installed')
        self.assertIn('CLI 与桌面 App 并装',result['summary'])
        self.assertIn('未校验发布者签名',result['summary'])
        self.assertEqual({s['status'] for s in result['surfaces'].values()}, {'verified'})
        self.assertEqual(len([r for r in result['evidence'] if r['result'] == 'verified']), 2)

    def test_fixed_plist_identity_cannot_be_replaced_by_display_name(self):
        for field, value in [('CFBundleIdentifier', 'evil.product'),
                             ('CFBundleExecutable', 'other'), ('CFBundleDisplayName', 'other')]:
            with self.subTest(field=field):
                self.desktop(**{field: value})
                self.assertEqual(self.result()['status'], 'unknown')

    def test_missing_or_conflicting_versions_fail_closed(self):
        for changes in ({'CFBundleVersion': ''}, {'CFBundleVersion': '2.2.4'},
                        {'CFBundleShortVersionString': ''},
                        {'CFBundleVersion': 'unknown', 'CFBundleShortVersionString': 'unknown'}):
            with self.subTest(changes=changes):
                self.desktop(**changes)
                self.assertEqual(self.result()['status'], 'unknown')

    def test_signature_failure_does_not_block_app_cli_coexistence(self):
        self.cli(); self.desktop()
        signer = fake_codesign(identifier='ai.opencode.desktop')
        def failed_app(command):
            if '--verify' in command and command[-1].endswith('.app'):
                return SimpleNamespace(returncode=1, stdout='', stderr='bad publisher')
            return signer(command)
        self.assertEqual(self.result(runner=failed_app)['status'], 'installed')
        self.assertEqual(self.result(runner=fake_codesign(identifier='wrong.id'))['status'], 'installed')

    def test_failed_cli_does_not_join_valid_app(self):
        self.cli(); self.desktop()
        signer = fake_codesign(identifier='ai.opencode.desktop')
        def failed_cli(command):
            if '--verify' in command and not command[-1].endswith('.app'):
                return SimpleNamespace(returncode=1, stdout='', stderr='bad publisher')
            return signer(command)
        self.assertEqual(self.result(runner=failed_cli)['status'], 'installed')

    def test_additional_verified_cli_is_a_real_conflict(self):
        self.cli(); self.desktop()
        extra = self.cli(self.area / 'extra-bin')
        result = self.result(search_paths=[str(self.bin_dir), str(extra.parent)])
        self.assertEqual(result['status'], 'unknown')

    def test_additional_verified_app_is_a_real_conflict(self):
        self.cli(); self.desktop()
        (self.home / 'Applications').mkdir()
        self.desktop(self.home / 'Applications')
        self.assertEqual(self.result()['status'], 'unknown')

    def test_supported_npm_cli_and_app_can_coexist_without_signature_gate(self):
        self.desktop()
        package = self.npm_package('@opencode/cli')
        (package / 'package.json').write_text(json.dumps({'name': '@opencode/cli', 'version': '2.2.5', 'bin': {'opencode': 'bin/cli'}}))
        link = self.bin_dir / 'opencode'
        link.symlink_to(package / 'bin/cli')
        (self.bin_dir / 'cli').unlink()
        result = self.result()
        self.assertEqual(result['status'], 'installed')
        self.assertEqual(len([r for r in result['evidence'] if r['result'] == 'verified']), 2)
