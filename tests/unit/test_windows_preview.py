"""Product-byte lifecycle and failure tests, portable plus native Windows replay."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'scripts'))
from agm_core import windows_preview as wp
from agm_core import transaction as tx

SOURCE = Path(__file__).resolve().parents[2]


class PreviewTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name).resolve()
        self.home = self.root / 'home'; self.home.mkdir()

    def tearDown(self):
        self.temp.cleanup()

    def install(self):
        p = wp.install_plan(self.home, SOURCE)
        result = wp.execute(p, wp.digest(wp.encoded(p)))
        self.assertEqual(result['status'], 'committed')
        return p, result

    def apply(self, p, **kwargs):
        return wp.execute(p, wp.digest(wp.encoded(p)), **kwargs)

    def test_lifecycle_preserves_bom_crlf_private_and_exports_new_memories(self):
        original = b'\xef\xbb\xbf# private\r\nsecret-private-keep\r\nno-trailing-newline'
        native = self.home / wp.NATIVE[0]; native.parent.mkdir(); native.write_bytes(original)
        p, result = self.install()
        self.assertTrue(native.read_bytes().startswith(original))
        manifest = json.loads(Path(result['manifest']).read_bytes())
        e = next(e for e in manifest['entries'] if e['path'] == str(native))
        self.assertEqual((Path(result['manifest']).parent / e['before']['backup']).read_bytes(), original)
        self.apply(wp.add_plan(self.home, 'ZCode shared record'))
        self.apply(wp.add_plan(self.home, 'WorkBuddy shared record'))
        public = (self.home / wp.PUBLIC).read_bytes()
        exit_plan = wp.exit_plan(self.home)
        self.assertEqual(exit_plan['operations'][0]['relative'].split('/')[0], '.mem-sharing-preview-exports')
        out = self.apply(exit_plan)
        self.assertEqual(Path(out['export']['path']).read_bytes(), public)
        self.assertEqual(out['export']['sha256'], hashlib.sha256(public).hexdigest())
        self.assertEqual(native.read_bytes(), original)
        for name in wp.NATIVE[1:] + (wp.PUBLIC, wp.RECEIPT):
            self.assertFalse((self.home / name).exists(), name)
        self.assertFalse(any(p.is_file() for p in (self.home / wp.CODE).rglob('*')))

    def test_precise_approval_and_post_preview_foreign_edit_are_rejected(self):
        p = wp.install_plan(self.home, SOURCE)
        with self.assertRaises(wp.PreviewError):
            wp.execute(p, '0' * 64)
        native = self.home / wp.NATIVE[0]; native.parent.mkdir(); native.write_bytes(b'foreign')
        with self.assertRaises(wp.PreviewError):
            self.apply(p)
        self.assertEqual(native.read_bytes(), b'foreign')
        self.assertFalse((self.home / wp.RECEIPT).exists())

    def test_existing_install_or_skill_is_not_adopted(self):
        s = self.home / wp.NATIVE[2]; s.parent.mkdir(parents=True); s.write_bytes(b'unknown skill')
        with self.assertRaises(wp.PreviewError):
            wp.install_plan(self.home, SOURCE)
        self.assertEqual(s.read_bytes(), b'unknown skill')

    def test_external_edit_blocks_exit_without_deleting_shared_or_private(self):
        self.install()
        native = self.home / wp.NATIVE[1]
        external = native.read_bytes() + b'\r\nprivate edit after install\r\n'
        native.write_bytes(external)
        public = (self.home / wp.PUBLIC).read_bytes()
        with self.assertRaises(wp.PreviewError):
            wp.exit_plan(self.home)
        self.assertEqual(native.read_bytes(), external)
        self.assertEqual((self.home / wp.PUBLIC).read_bytes(), public)
        self.assertTrue((self.home / wp.RECEIPT).exists())

    def test_unknown_owned_tree_content_is_preserved(self):
        self.install()
        extra = self.home / wp.CODE / 'not-owned.txt'; extra.write_bytes(b'foreign')
        with self.assertRaises(wp.PreviewError):
            wp.exit_plan(self.home)
        self.assertEqual(extra.read_bytes(), b'foreign')

    def test_parent_link_is_rejected_before_any_write(self):
        elsewhere = self.root / 'elsewhere'; elsewhere.mkdir()
        link = self.home / '.zcode'
        try:
            link.symlink_to(elsewhere, target_is_directory=True)
        except OSError:
            # Ordinary Windows users may create junctions without symlink rights.
            if os.name != 'nt':
                raise
            r = subprocess.run(['C:\\Windows\\System32\\cmd.exe', '/d', '/c', 'mklink', '/J', str(link), str(elsewhere)], capture_output=True)
            self.assertEqual(r.returncode, 0, r.stderr)
        try:
            with self.assertRaises(wp.PreviewError):
                wp.install_plan(self.home, SOURCE)
            self.assertEqual(list(elsewhere.iterdir()), [])
        finally:
            if link.is_symlink(): link.unlink()
            else: link.rmdir()

    def test_keyboard_interrupt_rolls_back_original_bytes(self):
        original = b'\xef\xbb\xbfprivate\r\n'
        native = self.home / wp.NATIVE[0]; native.parent.mkdir(); native.write_bytes(original)
        p = wp.install_plan(self.home, SOURCE)
        def interrupt(event, path):
            if event == 'after_write' and path == native:
                raise KeyboardInterrupt('controlled interrupt')
        with self.assertRaises(tx.TransactionError) as caught:
            self.apply(p, hook=interrupt)
        m = json.loads(Path(caught.exception.manifest).read_bytes())
        self.assertEqual(m['status'], 'rolled_back')
        self.assertEqual(native.read_bytes(), original)
        self.assertFalse((self.home / wp.RECEIPT).exists())
        self.assertFalse((self.home / wp.LOCK).exists())

    def test_exit_failure_keeps_public_and_restores_installed_entries(self):
        self.install()
        p = wp.exit_plan(self.home)
        before = {op['relative']: wp.snap(self.home / op['relative']) for op in p['operations']}
        def fail(event, path):
            if event == 'after_write' and path == self.home / wp.NATIVE[0]:
                raise OSError('injected exit failure')
        with self.assertRaises(tx.TransactionError):
            self.apply(p, hook=fail)
        for rel, value in before.items():
            self.assertEqual(wp.snap(self.home / rel), value, rel)

    def test_unexpected_edit_during_rollback_requires_inspection(self):
        p = wp.install_plan(self.home, SOURCE)
        target = self.home / wp.NATIVE[0]
        def fail(event, path):
            if event == 'after_write' and path == target:
                path.write_bytes(b'external actor')
                raise OSError('foreign edit then failure')
        with self.assertRaises(tx.TransactionError) as caught:
            self.apply(p, hook=fail)
        self.assertEqual(caught.exception.code, 'recovery_required')
        self.assertEqual(target.read_bytes(), b'external actor')

    def test_export_failure_does_not_remove_native_or_public_data(self):
        self.install()
        public = (self.home / wp.PUBLIC).read_bytes()
        native = {n: (self.home / n).read_bytes() for n in wp.NATIVE}
        def fail(event, path):
            if event == 'before_write' and '.mem-sharing-preview-exports' in path.parts:
                raise OSError('export unavailable')
        with self.assertRaises(tx.TransactionError):
            self.apply(wp.exit_plan(self.home), hook=fail)
        self.assertEqual((self.home / wp.PUBLIC).read_bytes(), public)
        for n, b in native.items(): self.assertEqual((self.home / n).read_bytes(), b)

    def test_hard_process_exit_recovers_from_durable_manifest(self):
        native = self.home / wp.NATIVE[0]; native.parent.mkdir()
        original = b'\xef\xbb\xbfprivate-before-crash\r\n'; native.write_bytes(original)
        script = self.root / 'crash.py'
        script.write_text('import sys,os\nfrom pathlib import Path\n'
                          + 'sys.path.insert(0,' + repr(str(SOURCE / 'scripts')) + ')\n'
                          + 'from agm_core import windows_preview as w\n'
                          + 'h=Path(' + repr(str(self.home)) + ')\n'
                          + 'p=w.install_plan(h,Path(' + repr(str(SOURCE)) + '))\n'
                          + 'def crash(event,path):\n'
                          + ' if event=="after_write" and path==h/w.NATIVE[0]:os._exit(73)\n'
                          + 'w.execute(p,w.digest(w.encoded(p)),hook=crash)\n', encoding='utf-8')
        child = subprocess.run([sys.executable, '-I', '-S', '-B', str(script)], capture_output=True, timeout=60)
        self.assertEqual(child.returncode, 73, child.stderr)
        manifest, = (self.home / wp.BACKUPS).glob('*/manifest.json')
        self.assertEqual(json.loads(manifest.read_bytes())['status'], 'applying')
        # Operator action in this unique synthetic HOME only: the exact child
        # has exited. Production recovery never steals an unknown stale lock.
        lock = self.home / wp.LOCK
        identity = lock.lstat()
        self.assertFalse(lock.is_symlink())
        self.assertEqual((lock.lstat().st_dev, lock.lstat().st_ino), (identity.st_dev, identity.st_ino))
        lock.rmdir()
        self.assertEqual(wp.recover(self.home, manifest)['status'], 'rolled_back')
        self.assertEqual(native.read_bytes(), original)
        self.assertFalse((self.home / wp.RECEIPT).exists())


if __name__ == '__main__':
    unittest.main()
