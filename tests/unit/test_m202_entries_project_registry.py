"""M2-02 contract tests using only stdlib and temporary repositories."""
import copy
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
from agm_core.entries import (EntryConflict, block_fingerprint, link_fingerprint,
                              managed_span, remove_block, render_block, sha256, verify_link)
from agm_core.project import ProjectError, WorktreeUnsupported, resolve_project
from agm_core.registry import (RegistryError, commit_registry, empty_registry, load_registry,
                               new_project, recovered_object, serialize_registry,
                               validate_ownership_transition, validate_registry)
from agm_core.transaction import Change, Snapshot, Transaction, read_snapshot

START, END = b"<!-- unit:start -->", b"<!-- unit:end -->"
BLOCK = START + b"\r\ntext\r\n" + END


class EntryTests(unittest.TestCase):
    def test_fingerprint_exact_marker_bytes(self):
        source = b"\xef\xbb\xbfoutside\r\n" + BLOCK + b"\r\n\xfftail"
        self.assertEqual(block_fingerprint(source, START, END), sha256(BLOCK))
        self.assertNotEqual(sha256(BLOCK), sha256(BLOCK.replace(b"\r\n", b"\n")))

    def test_preserve_all_outside_bytes_replace_and_remove(self):
        prefix, suffix = b"\xef\xbb\xbfraw\xff\r\n\n", b"\n\r\n\xffafter"
        source = prefix + BLOCK + suffix
        new = START + b"\nnew\n" + END
        self.assertEqual(render_block(source, new, START, END, expected_fingerprint=sha256(BLOCK)), prefix + new + suffix)
        self.assertEqual(remove_block(source, START, END, expected_fingerprint=sha256(BLOCK)), prefix + suffix)

    def test_same_block_is_byte_identical(self):
        source = b"prefix" + BLOCK + b"suffix"
        self.assertEqual(render_block(source, BLOCK, START, END, expected_fingerprint=sha256(BLOCK)), source)

    def test_drift_and_missing_rejected_before_edit(self):
        for source, expected in ((BLOCK, "0" * 64), (b"", sha256(BLOCK)), (BLOCK, None)):
            with self.subTest(source=source), self.assertRaises(EntryConflict):
                render_block(source, BLOCK, START, END, expected_fingerprint=expected)

    def test_malformed_duplicate_reversed_nested_markers(self):
        for source in (START, END, END + START, START + BLOCK + END, BLOCK + BLOCK):
            with self.subTest(source=source), self.assertRaises(EntryConflict):
                managed_span(source, START, END)
        with self.assertRaises(EntryConflict):
            managed_span(b"", START, START)

    def test_top_insertion_preserves_native_content(self):
        data = b"\xef\xbb\xbfnotes\r\n\xff"
        self.assertEqual(render_block(data, BLOCK, START, END, position="top"), BLOCK + b"\n" + data)
        with self.assertRaises(EntryConflict):
            render_block(b"prefix" + BLOCK, BLOCK, START, END, position="top", expected_fingerprint=sha256(BLOCK))

    def test_replacement_requires_marker_inclusive_unit(self):
        with self.assertRaises(EntryConflict):
            render_block(b"", BLOCK + b"\n", START, END)

    def test_link_resolution_and_copy_conflict(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            (root / "source").mkdir()
            (root / "link").symlink_to("source", target_is_directory=True)
            self.assertEqual(verify_link(root / "link", root / "source"), link_fingerprint(root / "source"))
            for path, target in ((root / "source", root / "source"), (root / "link", root / "foreign")):
                with self.assertRaises(EntryConflict):
                    verify_link(path, target)


class ProjectTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve() / "repo with space"
        self.root.mkdir()
        self.git("init", "-q")
        self.git("-c", "user.name=Test", "-c", "user.email=test@example.invalid", "commit", "--allow-empty", "-qm", "fixture")

    def git(self, *args):
        return subprocess.run(["git", "-C", str(self.root), *args], check=True, capture_output=True)

    def test_subdirectory_implicit_and_explicit_root(self):
        child = self.root / "child"
        child.mkdir()
        identity = resolve_project(cwd=child)
        self.assertEqual(identity.main_checkout, self.root)
        self.assertEqual(identity.git_common_dir, self.root / ".git")
        with self.assertRaises(ProjectError):
            resolve_project(child)

    def test_dirty_status_without_index_lock_or_checkout_change(self):
        (self.root / "dirty").write_bytes(b"untracked")
        before = (self.root / ".git/index").read_bytes() if (self.root / ".git/index").exists() else None
        identity = resolve_project(self.root)
        self.assertIn(b"?? dirty\0", identity.status)
        self.assertFalse((self.root / ".git/index.lock").exists())
        after = (self.root / ".git/index").read_bytes() if (self.root / ".git/index").exists() else None
        self.assertEqual(before, after)

    def test_linked_worktree_rejected_and_readonly_diagnostic(self):
        linked = self.root.parent / "linked"
        self.git("worktree", "add", "-qb", "linked", str(linked))
        with self.assertRaises(WorktreeUnsupported):
            resolve_project(linked)
        identity = resolve_project(linked, allow_worktree=True)
        self.assertFalse(identity.is_main)
        self.assertEqual(identity.main_checkout, self.root)
        with self.assertRaises(RegistryError):
            new_project(identity, ["codex"])

    def test_main_checkout_with_separate_git_dir(self):
        other = self.root.parent / "separate"
        gitdir = self.root.parent / "metadata"
        subprocess.run(["git", "init", "-q", "--separate-git-dir", str(gitdir), str(other)], check=True, capture_output=True)
        identity = resolve_project(other)
        self.assertTrue(identity.is_main)
        self.assertEqual(identity.git_common_dir, gitdir)
        data = empty_registry()
        data["projects"][str(other)] = new_project(identity, ["codex"])
        validate_registry(data)

    def test_clone_does_not_share_identity_by_remote_or_head(self):
        clone = self.root.parent / "clone"
        subprocess.run(["git", "clone", "-q", str(self.root), str(clone)], check=True, capture_output=True)
        self.assertNotEqual(resolve_project(clone).main_checkout, resolve_project(self.root).main_checkout)


class RegistryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.repo = self.root / "repo"
        self.repo.mkdir()
        subprocess.run(["git", "init", "-q", str(self.repo)], check=True, capture_output=True)
        self.identity = resolve_project(self.repo)
        self.data = empty_registry()
        self.data["projects"][str(self.repo)] = new_project(self.identity, ["workbuddy", "codex"])
        self.project = self.data["projects"][str(self.repo)]
        self.assembly = self.project["checkouts"][str(self.repo)]
        self.manifest = self.root / "manifest.json"
        self.manifest.write_text("{}")

    def obj(self, *, kind="block", ownership="created", path=None, scope="project"):
        return {"kind": kind, "path": str(path or self.repo / "AGENTS.md"), "scope": scope,
                "agents": ["codex"], "ownership": ownership,
                "marker": {"start": START.decode(), "end": END.decode()},
                "fingerprint": {"algorithm": "sha256", "basis": "block_bytes", "value": sha256(BLOCK)},
                "original_existed": ownership == "reused", "link_target": None,
                "backup_manifest": str(self.manifest) if ownership == "created" else None,
                "consumers": [str(self.repo)]}

    def add(self, obj=None):
        obj = obj or self.obj()
        self.assembly["objects"][obj["path"] + "#keeper"] = obj
        return obj

    def test_empty_and_full_roundtrip(self):
        self.assertEqual(validate_registry(empty_registry()), empty_registry())
        self.add()
        encoded = serialize_registry(self.data)
        self.assertEqual(json.loads(encoded), self.data)
        path = self.root / "registry.json"
        path.write_bytes(encoded)
        self.assertEqual(load_registry(path), self.data)

    def test_missing_unknown_fields_and_boolean_version(self):
        for mutate in (lambda d: d.pop("shared_objects"), lambda d: d.update(extra=1), lambda d: d.update(schema_version=True), lambda d: d.update(schema_version=2)):
            data = copy.deepcopy(self.data)
            mutate(data)
            with self.assertRaises(RegistryError):
                validate_registry(data)

    def test_duplicate_json_keys_not_silently_replaced(self):
        path = self.root / "registry.json"
        path.write_text('{"schema_version":1,"schema_version":1,"projects":{},"shared_objects":{}}')
        with self.assertRaises(RegistryError):
            load_registry(path)

    def test_missing_corrupt_registry_no_write_or_lock(self):
        path = self.root / "registry.json"
        for data in (None, b"not json", b"\xff"):
            if data is not None:
                path.write_bytes(data)
            before = {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in self.root.iterdir() if p.is_file()}
            with self.assertRaises(RegistryError):
                load_registry(path)
            after = {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in self.root.iterdir() if p.is_file()}
            self.assertEqual(before, after)
            self.assertFalse((self.root / ".agm.lock").exists())

    def test_required_created_and_reused_evidence(self):
        obj = self.add()
        for field, bad in (("fingerprint", None), ("original_existed", True), ("backup_manifest", None), ("backup_manifest", str(self.root / "missing"))):
            old = obj[field]
            obj[field] = bad
            with self.subTest(field=field), self.assertRaises(RegistryError):
                validate_registry(self.data)
            obj[field] = old
        obj["ownership"] = "reused"
        obj["original_existed"] = False
        with self.assertRaises(RegistryError):
            validate_registry(self.data)

    def test_unknown_enum_and_fingerprint(self):
        obj = self.add()
        for field, value in (("ownership", "ours"), ("kind", "directory"), ("scope", "user")):
            original = obj[field]
            obj[field] = value
            with self.assertRaises(RegistryError):
                validate_registry(self.data)
            obj[field] = original
        obj["fingerprint"]["basis"] = "file_bytes"
        with self.assertRaises(RegistryError):
            validate_registry(self.data)

    def test_project_path_escape_and_symlink_parent_rejected(self):
        obj = self.add()
        obj["path"] = str(self.root / "outside")
        with self.assertRaises(RegistryError):
            validate_registry(self.data)
        (self.repo / "aliased").symlink_to(self.root, target_is_directory=True)
        obj["path"] = str(self.repo / "aliased" / "AGENTS.md")
        with self.assertRaises(RegistryError):
            validate_registry(self.data)

    def test_duplicate_unit_and_global_object_id_rejected(self):
        obj = self.add()
        self.assembly["objects"]["second"] = copy.deepcopy(obj)
        with self.assertRaises(RegistryError):
            validate_registry(self.data)

    def test_authorization_and_store_are_independent(self):
        self.assembly["states"]["store_authorized_ready"] = {"status": "ready", "observed_at": "2026-10-29T12:00:00Z", "evidence": "probe"}
        with self.assertRaises(RegistryError):
            validate_registry(self.data)
        self.project["memory_authorization"] = "yes"
        self.project["authorization_evidence"] = {"confirmed_at": "2026-10-29T12:00:00Z", "reference": "approval"}
        self.assembly["store"].update(path=str(self.root / "store"), location_approved=True,
                                      approval_evidence=copy.deepcopy(self.project["authorization_evidence"]))
        validate_registry(self.data)

    def test_fact_requires_evidence_and_real_utc_timestamp(self):
        fact = self.assembly["states"]["source_available"]
        for value in ({"status": "ready", "observed_at": None, "evidence": None},
                      {"status": "ready", "observed_at": "2026-02-30T01:00:00Z", "evidence": "probe"},
                      {"status": "ready", "observed_at": "2026-10-29T01:00:00+08:00", "evidence": "probe"}):
            fact.update(value)
            with self.assertRaises(RegistryError):
                validate_registry(self.data)

    def test_fact_agent_set_must_match(self):
        self.assembly["states"]["skill_installed"].pop("codex")
        with self.assertRaises(RegistryError):
            validate_registry(self.data)

    def test_shared_references_are_bidirectional_and_user_allowlisted(self):
        path = self.root / "MEMORY.md"
        obj = self.obj(scope="user", path=path, ownership="reused", kind="user_convention")
        self.data["shared_objects"]["shared"] = obj
        with self.assertRaises(RegistryError):
            validate_registry(self.data, allowed_user_paths=[path])
        self.assembly["shared_object_ids"] = ["shared"]
        validate_registry(self.data, allowed_user_paths=[path])
        with self.assertRaises(RegistryError):
            validate_registry(self.data)
        obj["consumers"] = []
        with self.assertRaises(RegistryError):
            validate_registry(self.data, allowed_user_paths=[path])
        self.assembly["shared_object_ids"] = []
        validate_registry(self.data, allowed_user_paths=[path])  # O2 retains empty shared object.

    def test_rebuild_never_restores_created(self):
        original = self.obj()
        for verified, expected in ((False, "unknown"), (True, "reused")):
            obj = recovered_object(original, verified=verified)
            self.assertEqual(obj["ownership"], expected)
            self.assertIsNone(obj["backup_manifest"])
            self.assertEqual(original["ownership"], "created")

    def test_transition_does_not_upgrade_reused_or_unknown(self):
        obj = self.add(self.obj(ownership="reused"))
        previous = copy.deepcopy(self.data)
        obj["ownership"] = "created"
        with self.assertRaises(RegistryError):
            validate_ownership_transition(previous, self.data)

    def test_created_baseline_cannot_be_refreshed_over_drift(self):
        obj = self.add()
        previous = copy.deepcopy(self.data)
        obj["fingerprint"]["value"] = "0" * 64
        with self.assertRaises(RegistryError):
            validate_ownership_transition(previous, self.data)

    def test_commit_new_created_block_binds_actual_write_and_pending_manifest(self):
        output, registry = self.repo / "AGENTS.md", self.root / "registry.json"
        output.write_bytes(b"outside\r\n")
        tx = Transaction(lock_path=self.root / ".agm.lock", backup_root=self.root / "backups", allowed_roots=[self.root])
        obj = self.add()
        obj["backup_manifest"] = str(tx.manifest_path)
        change = Change.file(output, output.read_bytes() + BLOCK, expected=read_snapshot(output))
        result = commit_registry(registry, self.data, transaction=tx, expected=read_snapshot(registry), changes=[change])
        self.assertEqual(result["status"], "committed")
        self.assertEqual(load_registry(registry), self.data)
        self.assertEqual(output.read_bytes(), b"outside\r\n" + BLOCK)
        self.assertTrue(tx.manifest_path.is_file())

    def test_commit_cannot_claim_existing_block_as_created(self):
        output, registry = self.repo / "AGENTS.md", self.root / "registry.json"
        output.write_bytes(BLOCK)
        tx = Transaction(lock_path=self.root / ".agm.lock", backup_root=self.root / "backups", allowed_roots=[self.root])
        obj = self.add()
        obj["backup_manifest"] = str(tx.manifest_path)
        change = Change.file(output, BLOCK + b"outside", expected=read_snapshot(output))
        with self.assertRaises(RegistryError):
            commit_registry(registry, self.data, transaction=tx, expected=read_snapshot(registry), changes=[change])
        self.assertFalse(registry.exists())
        self.assertFalse((self.root / "backups").exists())

    def test_corrupt_registry_rebuild_requires_explicit_caller_authorization(self):
        registry = self.root / "registry.json"
        registry.write_bytes(b"corrupt original")
        tx = lambda: Transaction(lock_path=self.root / ".agm.lock", backup_root=self.root / "backups", allowed_roots=[self.root])
        with self.assertRaises(RegistryError):
            commit_registry(registry, self.data, transaction=tx(), expected=read_snapshot(registry))
        result = commit_registry(registry, self.data, transaction=tx(), expected=read_snapshot(registry), rebuild=True)
        manifest = Path(result["manifest"])
        entry = json.loads(manifest.read_bytes())["entries"][0]
        self.assertEqual((manifest.parent / entry["before"]["backup"]).read_bytes(), b"corrupt original")

    def test_commit_cannot_skip_existing_ownership_transition_check(self):
        obj = self.add(self.obj(ownership="reused"))
        registry = self.root / "registry.json"
        registry.write_bytes(serialize_registry(self.data))
        tx = Transaction(lock_path=self.root / ".agm.lock", backup_root=self.root / "backups", allowed_roots=[self.root])
        obj.update(ownership="created", original_existed=False, backup_manifest=str(tx.manifest_path))
        with self.assertRaises(RegistryError):
            commit_registry(registry, self.data, transaction=tx, expected=read_snapshot(registry))

    def test_registry_atomic_commit_preserves_mode_and_noop_mtime(self):
        path = self.root / "registry.json"
        path.write_bytes(serialize_registry(empty_registry()))
        path.chmod(0o640)
        tx = lambda: Transaction(lock_path=self.root / ".agm.lock", backup_root=self.root / "backups", allowed_roots=[self.root])
        result = commit_registry(path, self.data, transaction=tx(), expected=read_snapshot(path))
        self.assertEqual(result["status"], "committed")
        self.assertEqual(path.stat().st_mode & 0o777, 0o640)
        before = path.stat().st_mtime_ns
        result = commit_registry(path, self.data, transaction=tx(), expected=read_snapshot(path))
        self.assertEqual(result["status"], "unchanged")
        self.assertEqual(before, path.stat().st_mtime_ns)


if __name__ == "__main__":
    unittest.main()
