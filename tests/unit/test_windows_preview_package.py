"""Supply-chain boundaries for the independent preview archive, no network."""
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import shutil
import stat
import subprocess
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('preview_package', ROOT / 'tools/windows-preview/package.py')
pkg = importlib.util.module_from_spec(spec); spec.loader.exec_module(pkg)


class PackageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.area = Path(self.temp.name).resolve(); self.source = self.area / 'source'; self.source.mkdir()
        for name in (*pkg.CORE, 'scripts/core-version.json', pkg.GUIDE_SOURCE):
            path = self.source / name; path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / name, path)
        self.git('init')
        self.git('remote', 'add', 'origin', pkg.OFFICIAL + '.git')
        self.git('add', '.')
        self.git('-c', 'user.name=fixture', '-c', 'user.email=fixture@example.invalid', 'commit', '-m', 'fixed preview source')
        self.revision = self.git('rev-parse', 'HEAD').strip()

    def git(self, *args):
        return subprocess.run(['git', '-C', str(self.source), *args], capture_output=True,
                              text=True, check=True).stdout

    def build(self, name='preview.zip'):
        out = self.area / name
        report = pkg.build(self.source, self.revision, out)
        return out, report

    def rewritten(self, archive, *, transform=None, extra=None):
        output = self.area / 'changed.zip'
        with zipfile.ZipFile(archive) as old, zipfile.ZipFile(output, 'w') as new:
            for info in old.infolist():
                raw = old.read(info.filename)
                if transform: info, raw = transform(info, raw)
                new.writestr(info, raw)
            if extra: new.writestr(extra, b'foreign')
        return output

    def test_repeated_build_exact_and_core_bytes_match_git_objects(self):
        a, report = self.build('a.zip'); b, _ = self.build('b.zip')
        self.assertEqual(a.read_bytes(), b.read_bytes())
        self.assertEqual(report['members'], 10)
        self.assertEqual(report['preview_revision'], self.revision)
        with zipfile.ZipFile(a) as archive:
            manifest = json.loads(archive.read(pkg.MANIFEST))
            for name in pkg.CORE:
                raw = subprocess.run(['git', '-C', str(self.source), 'show', self.revision + ':' + name],
                                     capture_output=True, check=True).stdout
                self.assertEqual(archive.read(name), raw)
                self.assertEqual(manifest['files'][name], {'size': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()})
        self.assertEqual(pkg.verify(a, expected_sha256=report['sha256'], expected_revision=self.revision)['status'], 'verified')

    def test_dirty_checkout_not_packaged(self):
        (self.source / 'not-committed.txt').write_text('foreign')
        with self.assertRaises(pkg.PackageError): self.build()
        self.assertFalse((self.area / 'preview.zip').exists())

    def test_hidden_skip_worktree_change_cannot_replace_pinned_payload(self):
        name = pkg.CORE[0]
        self.git('update-index', '--skip-worktree', name)
        (self.source / name).write_bytes(b'changed but hidden from status')
        self.assertFalse(self.git('status', '--porcelain'))
        with self.assertRaises(pkg.PackageError): self.build()

    def test_payload_change_rejected_without_trusting_manifest_alone(self):
        archive, _ = self.build()
        def changed(info, raw):
            return info, raw + b'\nforeign' if info.filename == pkg.CORE[0] else raw
        with self.assertRaises(pkg.PackageError): pkg.verify(self.rewritten(archive, transform=changed))

    def test_duplicate_and_escape_members_rejected(self):
        archive, _ = self.build()
        for name in ('../escape', '/absolute', pkg.CORE[0]):
            with self.subTest(name=name):
                with self.assertRaises(pkg.PackageError): pkg.verify(self.rewritten(archive, extra=name))

    def test_symlink_member_rejected_even_with_expected_name(self):
        archive, _ = self.build()
        def linked(info, raw):
            if info.filename == pkg.CORE[0]: info.external_attr = (stat.S_IFLNK | 0o777) << 16
            return info, raw
        with self.assertRaises(pkg.PackageError): pkg.verify(self.rewritten(archive, transform=linked))

    def test_wrong_revision_checksum_and_publisher_scope_rejected(self):
        archive, _ = self.build()
        with self.assertRaises(pkg.PackageError): pkg.verify(archive, expected_revision='0' * 40)
        with self.assertRaises(pkg.PackageError): pkg.verify(archive, expected_sha256='0' * 64)
        def broad(info, raw):
            if info.filename == pkg.MANIFEST:
                value = json.loads(raw); value['general_windows_support'] = True; raw = pkg.canonical(value)
            return info, raw
        with self.assertRaises(pkg.PackageError): pkg.verify(self.rewritten(archive, transform=broad))

    def test_nonofficial_origin_and_existing_output_are_not_overwritten(self):
        self.git('remote', 'set-url', 'origin', 'https://example.invalid/not-the-source')
        with self.assertRaises(pkg.PackageError): self.build()
        self.git('remote', 'set-url', 'origin', pkg.OFFICIAL)
        archive, _ = self.build()
        before = archive.read_bytes()
        with self.assertRaises(FileExistsError): self.build()
        self.assertEqual(archive.read_bytes(), before)


if __name__ == '__main__':
    unittest.main()
