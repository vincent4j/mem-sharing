"""Real filesystem rollback, writer exclusion and explicit crash recovery."""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
sys.path.insert(0, str(SCRIPTS))
from agm_core.entries import block_fingerprint, link_fingerprint, render_block
from agm_core.registry import empty_registry, load_registry, serialize_registry
from agm_core.transaction import (Change, Snapshot, Transaction, TransactionError,
                                  read_snapshot, recover_manifest, write_lock)


class TransactionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.output = self.root / "AGENTS.md"
        self.output.write_bytes(b"old\r\n\xff")
        self.output.chmod(0o640)
        self.registry = self.root / "registry.json"
        self.registry.write_bytes(serialize_registry(empty_registry()))
        self.lock = self.root / ".agm.lock"
        self.backups = self.root / "backups"

    def tx(self, hook=None):
        return Transaction(lock_path=self.lock, backup_root=self.backups,
                           allowed_roots=[self.root], hook=hook)

    def change(self, path=None, data=b"new"):
        path = path or self.output
        return Change.file(path, data, expected=read_snapshot(path))

    def manifest(self, tx):
        return json.loads(tx.manifest_path.read_bytes())

    def test_success_backups_mode_fingerprints_and_registry_last(self):
        events = []
        tx = self.tx(lambda event, path: events.append((event, path)))
        result = tx.run([self.change()], registry_change=self.change(self.registry, b'{"new": true}'))
        self.assertEqual(result["status"], "committed")
        self.assertEqual(self.output.read_bytes(), b"new")
        self.assertEqual(self.output.stat().st_mode & 0o777, 0o640)
        writes = [path for event, path in events if event == "before_write"]
        self.assertEqual(writes, [self.output, self.registry])
        self.assertIn(("before_readback", self.output), events[:events.index(("before_write", self.registry))])
        manifest = self.manifest(tx)
        self.assertEqual(manifest["status"], "committed")
        entry = manifest["entries"][0]
        self.assertEqual(entry["before"]["mode"], 0o640)
        self.assertTrue(entry["before"]["existed"])
        self.assertEqual((tx.directory / entry["before"]["backup"]).read_bytes(), b"old\r\n\xff")
        self.assertNotEqual(entry["before"]["fingerprint"], entry["after"]["fingerprint"])
        self.assertFalse(self.lock.exists())

    def test_identical_output_no_backup_or_mtime_change(self):
        before = self.output.stat().st_mtime_ns
        tx = self.tx()
        result = tx.run([self.change(data=self.output.read_bytes())])
        self.assertEqual(result["status"], "unchanged")
        self.assertEqual(before, self.output.stat().st_mtime_ns)
        self.assertFalse(self.backups.exists())
        self.assertFalse(self.lock.exists())

    def test_block_edit_preserves_outside_and_second_run_no_rewrite(self):
        start, end = b"<!-- start -->", b"<!-- end -->"
        block = start + b"\r\ncontent\r\n" + end
        before = b"\xef\xbb\xbfoutside\xff\r\n" + block + b"\r\nlast\xff"
        self.output.write_bytes(before)
        revised = start + b"\nchanged\n" + end
        changed = render_block(before, revised, start, end, expected_fingerprint=block_fingerprint(before, start, end))
        self.tx().run([self.change(data=changed)])
        self.assertEqual(self.output.read_bytes(), b"\xef\xbb\xbfoutside\xff\r\n" + revised + b"\r\nlast\xff")
        stamp = self.output.stat().st_mtime_ns
        self.tx().run([self.change(data=changed)])
        self.assertEqual(self.output.stat().st_mtime_ns, stamp)

    def test_all_preconditions_checked_before_any_backup_or_output_write(self):
        first = self.change()
        second = self.change(self.registry, b"changed")
        self.registry.write_bytes(b"external edit")
        tx = self.tx()
        with self.assertRaises(TransactionError) as caught:
            tx.run([first], registry_change=second)
        self.assertEqual(caught.exception.code, "drift")
        self.assertEqual(self.output.read_bytes(), first.expected.data)
        self.assertFalse(self.backups.exists())

    def test_real_replace_failure_restores_previous_output_and_never_commits_registry(self):
        other = self.root / "second.md"
        other.write_bytes(b"second old")
        original = os.replace
        failed = []

        def failing_replace(source, destination):
            if Path(destination) == other and not failed:
                failed.append(True)
                raise OSError("injected replace failure")
            return original(source, destination)

        tx = self.tx()
        old_registry = self.registry.read_bytes()
        with patch("agm_core.transaction.os.replace", side_effect=failing_replace):
            with self.assertRaises(TransactionError) as caught:
                tx.run([self.change(), self.change(other)], registry_change=self.change(self.registry, b"new registry"))
        self.assertEqual(caught.exception.code, "transaction_failed")
        self.assertEqual(self.output.read_bytes(), b"old\r\n\xff")
        self.assertEqual(other.read_bytes(), b"second old")
        self.assertEqual(self.registry.read_bytes(), old_registry)
        self.assertEqual(self.manifest(tx)["status"], "rolled_back")
        self.assertTrue(tx.directory.exists())

    def test_readback_failure_rolls_back_file_mode_and_absent_output(self):
        added = self.root / "new-dir" / "nested" / "MEMORY.md"
        fired = []

        def hook(event, path):
            if event == "before_readback" and path == added and not fired:
                fired.append(True)
                raise OSError("injected readback failure")

        tx = self.tx(hook)
        with self.assertRaises(TransactionError) as caught:
            tx.run([self.change(), self.change(added)], registry_change=self.change(self.registry, b"registry"))
        self.assertEqual(caught.exception.code, "transaction_failed")
        self.assertEqual(self.output.read_bytes(), b"old\r\n\xff")
        self.assertEqual(self.output.stat().st_mode & 0o777, 0o640)
        self.assertFalse((self.root / "new-dir").exists())
        self.assertEqual(self.manifest(tx)["status"], "rolled_back")

    def test_registry_write_failure_restores_all_configuration(self):
        def hook(event, path):
            if event == "before_write" and path == self.registry:
                raise OSError("registry unavailable")
        tx = self.tx(hook)
        before_registry = self.registry.read_bytes()
        with self.assertRaises(TransactionError):
            tx.run([self.change()], registry_change=self.change(self.registry, b"registry"))
        self.assertEqual(self.output.read_bytes(), b"old\r\n\xff")
        self.assertEqual(self.registry.read_bytes(), before_registry)

    def test_restore_failure_report_retains_scene_and_manifest(self):
        def hook(event, path):
            if path == self.output and event in ("before_readback", "before_restore"):
                raise OSError("injected " + event)
        tx = self.tx(hook)
        with self.assertRaises(TransactionError) as caught:
            tx.run([self.change()])
        error = caught.exception
        self.assertEqual(error.code, "recovery_required")
        self.assertEqual(error.manifest, str(tx.manifest_path))
        self.assertTrue(error.recovery_errors)
        self.assertEqual(self.output.read_bytes(), b"new")
        manifest = self.manifest(tx)
        self.assertEqual(manifest["status"], "recovery_required")
        self.assertIn("failed:", manifest["entries"][0]["restoration"])
        self.assertEqual((tx.directory / "0.before").read_bytes(), b"old\r\n\xff")
        recovered = recover_manifest(tx.manifest_path, lock_path=self.lock, allowed_roots=[self.root])
        self.assertEqual(recovered["status"], "rolled_back")
        self.assertEqual(self.output.read_bytes(), b"old\r\n\xff")

    def test_foreign_edits_during_readback_preserved_on_rollback(self):
        fired = []
        def hook(event, path):
            if event == "before_readback" and path == self.output and not fired:
                fired.append(True)
                self.output.write_bytes(b"foreign edit")
        tx = self.tx(hook)
        with self.assertRaises(TransactionError) as caught:
            tx.run([self.change()])
        self.assertEqual(caught.exception.code, "recovery_required")
        self.assertEqual(self.output.read_bytes(), b"foreign edit")
        with self.assertRaises(TransactionError):
            recover_manifest(tx.manifest_path, lock_path=self.lock, allowed_roots=[self.root])
        self.assertEqual(self.output.read_bytes(), b"foreign edit")

    def test_symlink_success_equivalent_noop_and_rollback_raw_target(self):
        target = self.root / "source"
        target.mkdir()
        link = self.root / "skill"
        new = Change.symlink(link, target, expected=read_snapshot(link))
        self.tx().run([new])
        self.assertEqual(link.resolve(), target)
        link.unlink()
        link.symlink_to("source", target_is_directory=True)
        equivalent = Change.symlink(link, target, expected=read_snapshot(link))
        self.assertEqual(self.tx().run([equivalent])["status"], "unchanged")
        self.assertEqual(os.readlink(link), "source")
        def hook(event, path):
            if event == "before_readback" and path == link:
                raise OSError("injected")
        with self.assertRaises(TransactionError):
            self.tx(hook).run([Change.delete(link, expected=read_snapshot(link))])
        self.assertEqual(os.readlink(link), "source")

    def test_copy_directory_foreign_link_and_file_symlink_conflicts(self):
        target = self.root / "source"
        target.mkdir()
        with self.assertRaises(TransactionError):
            Change.symlink(self.output, target, expected=read_snapshot(self.output))
        with self.assertRaises(TransactionError):
            read_snapshot(target)
        link = self.root / "skill"
        link.symlink_to(target, target_is_directory=True)
        with self.assertRaises(TransactionError):
            Change.symlink(link, self.root / "other", expected=read_snapshot(link))
        with self.assertRaises(TransactionError):
            Change.file(link, b"oops", expected=read_snapshot(link))

    def test_symlink_parent_and_scope_escape_rejected(self):
        link = self.root / "alias"
        link.symlink_to(self.root, target_is_directory=True)
        with self.assertRaises(TransactionError):
            read_snapshot(link / "AGENTS.md")
        outside = self.root.parent / (self.root.name + "-outside")
        with self.assertRaises(TransactionError):
            self.tx().run([Change.file(outside, b"bad", expected=Snapshot("absent"))])
        self.assertFalse(outside.exists())
        self.assertFalse(self.backups.exists())

    def test_concurrent_writer_in_subprocess_fails_without_stealing(self):
        code = 'import sys; from pathlib import Path; sys.path.insert(0,sys.argv[1]); from agm_core.transaction import write_lock;\nwith write_lock(Path(sys.argv[2])): pass'
        with write_lock(self.lock):
            before = self.lock.stat().st_ino
            result = subprocess.run([sys.executable, "-c", code, str(SCRIPTS), str(self.lock)], capture_output=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn(b"writer lock exists", result.stderr)
            self.assertEqual(self.lock.stat().st_ino, before)
        self.assertFalse(self.lock.exists())

    def test_readonly_inspection_does_not_create_lock_backup_or_rewrite_registry(self):
        before = {p.name: (p.read_bytes(), p.stat().st_mtime_ns) for p in self.root.iterdir() if p.is_file()}
        # A real write-blocking probe, in addition to byte/mtime inventory.
        with patch("pathlib.Path.mkdir", side_effect=AssertionError("mkdir in check")), \
             patch("os.replace", side_effect=AssertionError("replace in check")), \
             patch("pathlib.Path.write_bytes", side_effect=AssertionError("write in check")), \
             patch("pathlib.Path.write_text", side_effect=AssertionError("write in check")):
            self.assertEqual(load_registry(self.registry), empty_registry())
            self.assertEqual(read_snapshot(self.output).data, b"old\r\n\xff")
        after = {p.name: (p.read_bytes(), p.stat().st_mtime_ns) for p in self.root.iterdir() if p.is_file()}
        self.assertEqual(before, after)
        self.assertFalse(self.lock.exists())
        self.assertFalse(self.backups.exists())

    def test_crash_leaves_manifest_and_stale_lock_explicit_recovery(self):
        code = '''import os,sys
from pathlib import Path
sys.path.insert(0,sys.argv[1])
from agm_core.transaction import Transaction, Change, read_snapshot
root=Path(sys.argv[2])
def hook(event,path):
    if event == 'after_write': os._exit(81)
tx=Transaction(lock_path=root/'.agm.lock',backup_root=root/'backups',allowed_roots=[root],hook=hook)
tx.run([Change.file(root/'AGENTS.md', b'new', expected=read_snapshot(root/'AGENTS.md'))])
'''
        result = subprocess.run([sys.executable, "-c", code, str(SCRIPTS), str(self.root)], capture_output=True)
        self.assertEqual(result.returncode, 81, result.stderr)
        self.assertEqual(self.output.read_bytes(), b"new")
        manifest = next(self.backups.glob("*/manifest.json"))
        self.assertEqual(json.loads(manifest.read_bytes())["status"], "applying")
        with self.assertRaises(TransactionError) as caught:
            recover_manifest(manifest, lock_path=self.lock, allowed_roots=[self.root])
        self.assertEqual(caught.exception.code, "lock_conflict")
        self.lock.rmdir()  # Test operator confirms the child exited before removing its stale lock.
        recovered = recover_manifest(manifest, lock_path=self.lock, allowed_roots=[self.root])
        self.assertEqual(recovered["status"], "rolled_back")
        self.assertEqual(self.output.read_bytes(), b"old\r\n\xff")
        self.assertEqual(self.output.stat().st_mode & 0o777, 0o640)

    def test_backup_write_failure_does_not_change_outputs_and_reports_manifest(self):
        original = os.replace
        def failing_backup(source, destination):
            if str(destination).endswith(".before"):
                raise OSError("backup unavailable")
            return original(source, destination)
        tx = self.tx()
        with patch("agm_core.transaction.os.replace", side_effect=failing_backup):
            with self.assertRaises(TransactionError) as caught:
                tx.run([self.change()])
        self.assertEqual(caught.exception.code, "transaction_failed")
        self.assertEqual(self.output.read_bytes(), b"old\r\n\xff")
        self.assertEqual(caught.exception.manifest, str(tx.manifest_path))
        self.assertEqual(self.manifest(tx)["status"], "rolled_back")

    def test_manual_change_cannot_repoint_an_existing_link(self):
        link = self.root / "link"
        link.symlink_to("first", target_is_directory=True)
        with self.assertRaises(TransactionError):
            self.tx().run([Change(link, Snapshot("symlink", target="second"), read_snapshot(link))])
        self.assertEqual(os.readlink(link), "first")

    def test_readback_failure_on_restoration_is_recovery_required(self):
        def hook(event, path):
            if event in ("before_readback", "before_restore_readback"):
                raise OSError("cannot verify")
        tx = self.tx(hook)
        with self.assertRaises(TransactionError) as caught:
            tx.run([self.change()])
        self.assertEqual(caught.exception.code, "recovery_required")
        self.assertEqual(self.output.read_bytes(), b"old\r\n\xff")
        self.assertTrue(tx.manifest_path.exists())

    def test_manifest_link_hash_is_resolved_but_restore_target_is_raw(self):
        source = self.root / "source"
        source.mkdir()
        link = self.root / "skill"
        link.symlink_to("source", target_is_directory=True)
        tx = self.tx()
        tx.run([Change.delete(link, expected=read_snapshot(link))])
        before = self.manifest(tx)["entries"][0]["before"]
        self.assertEqual(before["link_target"], "source")
        self.assertEqual(before["fingerprint"], link_fingerprint(source))

    def test_malformed_manifest_reports_recovery_required_without_touching_output(self):
        manifest = self.root / "broken-manifest.json"
        manifest.write_bytes(b"broken")
        with self.assertRaises(TransactionError) as caught:
            recover_manifest(manifest, lock_path=self.lock, allowed_roots=[self.root])
        self.assertEqual(caught.exception.code, "recovery_required")
        self.assertEqual(caught.exception.manifest, str(manifest))
        self.assertEqual(manifest.read_bytes(), b"broken")
        self.assertEqual(self.output.read_bytes(), b"old\r\n\xff")

    def test_corrupt_backup_crash_recovery_refuses_before_mutation(self):
        def hook(event, path):
            if event in ("before_readback", "before_restore"):
                raise OSError("injected")
        tx = self.tx(hook)
        with self.assertRaises(TransactionError):
            tx.run([self.change()])
        (tx.directory / "0.before").write_bytes(b"tampered")
        with self.assertRaises(TransactionError):
            recover_manifest(tx.manifest_path, lock_path=self.lock, allowed_roots=[self.root])
        self.assertEqual(self.output.read_bytes(), b"new")


if __name__ == "__main__":
    unittest.main()
