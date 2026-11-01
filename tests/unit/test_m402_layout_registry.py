"""M4-02 regressions using synthetic HOME and machine metadata only."""
import copy
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts"))
sys.path.insert(0, str(Path(__file__).parent))
import agm
from agm_core import check, enable, layout, paths, registry
from agm_core.transaction import Transaction, read_snapshot
from runtime_fixture import installed_registry, seed_runtime


class LayoutRegistryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.area = Path(self.temp.name).resolve()
        self.home = self.area / "home"
        self.home.mkdir()
        self.runtime = layout.resolve_layout(self.home)
        self.config = paths.select_platform(paths.load_agents_table(), "darwin")
        self.request = {"home": str(self.home), "platform_config": self.config,
                        "project": str(self.area / "no-project"), "all": True,
                        "agents": ["codex"], "approval": None,
                        "interactive": False}

    def tree(self):
        return {str(p.relative_to(self.area)): (p.read_bytes(), p.stat().st_mtime_ns)
                if p.is_file() else (None, None) for p in self.area.rglob("*")}

    def cli(self, args):
        output = io.StringIO()
        code = agm.main(args, home=str(self.home), platform="darwin", interactive=True,
                        stdin=io.StringIO(), stdout=output, stderr=io.StringIO())
        return code, json.loads(output.getvalue())

    def test_layout_resolution_has_no_side_effects(self):
        before = self.tree()
        self.assertEqual(layout.from_request(self.request), self.runtime)
        self.assertEqual(self.runtime.registry, self.home / ".mem-sharing/var/registry.json")
        self.assertEqual(self.runtime.transaction_lock, self.home / ".mem-sharing/var/.agm.lock/transaction")
        self.assertEqual(self.runtime.backups, self.home / ".mem-sharing/backups")
        self.assertEqual(self.tree(), before)

    def test_missing_request_home_never_falls_back_to_host(self):
        with self.assertRaises(layout.LayoutError):
            layout.from_request({})
        with self.assertRaises(layout.LayoutError):
            layout.from_request(dict(self.request, runtime_layout=layout.resolve_layout(self.area)))

    def test_symlink_runtime_parent_is_rejected_without_writes(self):
        other = self.area / "other"
        other.mkdir()
        self.runtime.root.symlink_to(other, target_is_directory=True)
        before = self.tree()
        with self.assertRaises(layout.LayoutError):
            layout.from_request(self.request)
        self.assertEqual(before, self.tree())

    def test_home_with_symlink_ancestor_checks_readonly_like_normal_home(self):
        # A relative directory alias models macOS mktemp's /var -> /private/var.
        alias = self.area / "home-parent-alias"
        alias.symlink_to(".", target_is_directory=True)
        aliased_home = alias / self.home.name
        before = self.tree()
        aliased = check.run(dict(self.request, home=str(aliased_home)))
        normal = check.run(self.request)
        self.assertEqual(aliased["status"], "gaps", aliased)
        self.assertEqual(aliased["errors"], [])
        self.assertEqual(normal["status"], aliased["status"])
        self.assertEqual(normal["errors"], [])
        self.assertEqual(aliased["runtime_layout"]["registry"],
                         str(aliased_home / ".mem-sharing/var/registry.json"))
        self.assertEqual(before, self.tree())

    def test_symlink_leaves_below_aliased_home_still_conflict_without_writes(self):
        alias = self.area / "home-parent-alias"
        alias.symlink_to(".", target_is_directory=True)
        target = self.area / "outside-managed-tree"
        target.mkdir()
        for name in ("root", "var", "registry", "lock", "transaction_lock", "backups"):
            with self.subTest(leaf=name):
                home = alias / ("home-" + name)
                home.mkdir()
                runtime = layout.resolve_layout(home)
                leaf = getattr(runtime, name)
                leaf.parent.mkdir(parents=True, exist_ok=True)
                leaf.symlink_to(target, target_is_directory=True)
                before = self.tree()
                result = check.run(dict(self.request, home=str(home)))
                self.assertEqual(result["status"], "failed", result)
                self.assertEqual(result["errors"][0]["code"], "runtime_path_conflict")
                self.assertEqual(before, self.tree())

    def test_empty_home_cli_entrypoints_import_help_check_never_write(self):
        before = self.tree()
        env = dict(os.environ, HOME=str(self.home), PYTHONDONTWRITEBYTECODE="1")
        for argv in (["--help"], ["enable-memory", "--help"], ["remove-memory", "--help"],
                     ["check-memory", "--help"], ["check-memory", "--all"],
                     ["enable-memory", "--project", str(self.area)],
                     ["remove-memory", "--project", str(self.area)]):
            result = subprocess.run([sys.executable, "-B", str(REPO / "scripts/agm.py"), *argv],
                                    cwd=self.area, env=env, capture_output=True, text=True)
            self.assertIn(result.returncode, (0, 1, 2, 5), result.stderr)
            self.assertEqual(before, self.tree(), argv)
        result = subprocess.run([sys.executable, "-B", "-c",
            "import sys; sys.path.insert(0, sys.argv[1]); import agm; "
            "from agm_core import layout, registry, enable, check",
            str(REPO / "scripts")], cwd=self.area, env=env, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(before, self.tree())

    def test_all_commands_report_same_new_layout(self):
        seed_runtime(self.home)
        for args in (["enable-memory","--project",str(self.area)],["check-memory","--all"]):
            _,result=self.cli(args)
            self.assertEqual(result["runtime_layout"],self.runtime.describe(),result)

    def test_agents_table_and_old_install_dir_cannot_relocate_active_registry(self):
        old = self.area / "old-code"
        old.mkdir()
        old_registry = old / "registry.json"
        old_registry.write_bytes(b'{"schema_version":1,"projects":{},"shared_objects":{}}')
        before = self.tree()
        result = check.run(dict(self.request, agents_table_path=str(old / "agents.json")))
        self.assertEqual(result["status"], "gaps")
        self.assertEqual(result["runtime_layout"]["registry"], str(self.runtime.registry))
        self.assertEqual(before, self.tree())

    def test_uninstalled_and_incomplete_product_models_reject_writers(self):
        self.runtime.var.mkdir(parents=True)
        repo = self.area / "project"
        repo.mkdir()
        subprocess.run(["git", "init", "-q", str(repo)], check=True, capture_output=True)
        request = dict(self.request, project=str(repo))
        for model in (registry.empty_registry(), installed_registry()):
            if model["product"]:
                model["product"]["installation_status"] = "installing"
            self.runtime.registry.write_bytes(registry.serialize_registry(model))
            before = self.tree()
            for command in (enable.run,):
                result = command(request)
                self.assertEqual(result["status"], "failed", result)
                self.assertEqual(before, self.tree())

    def test_legacy_v1_only_explicit_diagnostic_loader_accepts_it(self):
        self.runtime.var.mkdir(parents=True)
        old = {"schema_version": 1, "projects": {}, "shared_objects": {}}
        self.runtime.registry.write_text(json.dumps(old))
        self.assertEqual(registry.load_legacy_registry(self.runtime.registry), old)
        with self.assertRaises(registry.RegistryMigrationRequired):
            registry.load_registry(self.runtime.registry)
        with self.assertRaises(registry.RegistryError):
            registry.validate_registry_v1(dict(old, product=None))
        repo = self.area / "project"
        repo.mkdir()
        subprocess.run(["git", "init", "-q", str(repo)], check=True, capture_output=True)
        request = dict(self.request, project=str(repo))
        before = self.tree()
        for command in (enable.run,):
            result = command(request)
            self.assertEqual(result["errors"][0]["code"], "registry_migration_required", result)
            self.assertEqual(before, self.tree())
        result = check.run(request)
        self.assertEqual(result["status"], "gaps")
        self.assertTrue(any("read-only" in w for w in result["warnings"]))
        self.assertEqual(before, self.tree())

    def test_future_schema_and_structure_are_refused(self):
        for change in (lambda d: d.update(schema_version=4),
                       lambda d: d["product"].update(product_structure_version=2)):
            data = installed_registry()
            change(data)
            with self.assertRaises(registry.RegistryError):
                registry.validate_registry(data)

    def test_code_schema_and_structure_versions_are_separate(self):
        data = installed_registry()
        self.assertEqual(data["schema_version"], 3)
        self.assertEqual(data["product"]["product_structure_version"], 1)
        self.assertEqual(registry.validate_registry(data), data)
        data["product"]["product_code_version"] = "1.6.0"
        registry.validate_registry(data)
        data["product"]["product_code_version"] = "DESIGN v1.6"
        with self.assertRaises(registry.RegistryError):
            registry.validate_registry(data)

    def test_non_dict_product_type_is_registry_error_not_attribute_error(self):
        for bad in ([], "damaged", 7):
            with self.subTest(product=bad):
                data = registry.empty_registry()
                data["product"] = bad
                with self.assertRaises(registry.RegistryError):
                    registry.validate_registry(data)

    def test_all_required_nullable_fields_and_nested_unknown_fields_are_strict(self):
        base = installed_registry()
        for name in base:
            data = copy.deepcopy(base)
            del data[name]
            with self.subTest(field=name), self.assertRaises(registry.RegistryError):
                registry.validate_registry(data)
        for target in (lambda d: d, lambda d: d["product"], lambda d: d["product"]["source"],
                       lambda d: d["machine"]):
            data = copy.deepcopy(base)
            target(data)["extra"] = None
            with self.assertRaises(registry.RegistryError):
                registry.validate_registry(data)

    def machine_model(self):
        data = installed_registry()
        target = self.home / ".codex/AGENTS.md"
        data["machine"]["agents"]["codex"] = {
            "installation": {"status": "installed", "observed_at": "2026-10-30T00:00:00Z", "evidence": "fixture package"},
            "static": registry.unknown_fact(), "runtime_acceptance": {"status": "pending", "evidence_path": None}}
        data["machine"]["objects"]["codex-rules"] = {
            "kind": "file", "path": str(target), "scope": "machine", "agents": ["codex"],
            "ownership": "reused", "marker": None, "fingerprint": {"algorithm": "sha256", "basis": "file_bytes", "value": "b" * 64},
            "original_existed": True, "link_target": None, "backup_manifest": None, "consumers": []}
        return data, target

    def test_machine_installation_without_project_or_fake_consumer(self):
        data, target = self.machine_model()
        self.assertEqual(data["projects"], {})
        encoded = registry.serialize_registry(data, allowed_user_paths=[str(target)])
        self.assertEqual(json.loads(encoded), data)

    def test_machine_object_consumer_agent_scope_and_path_guards(self):
        base, target = self.machine_model()
        for mutation in (lambda d: d["machine"]["objects"]["codex-rules"].update(consumers=[str(self.area)]),
                         lambda d: d["machine"]["objects"]["codex-rules"].update(scope="user"),
                         lambda d: d["machine"]["objects"]["codex-rules"].update(agents=["claude"]),
                         lambda d: d["machine"]["objects"]["codex-rules"].update(path=str(self.area / "outside")),
                         lambda d: d["machine"]["agents"]["codex"]["installation"].update(status="ready")):
            data = copy.deepcopy(base)
            mutation(data)
            with self.assertRaises(registry.RegistryError):
                registry.validate_registry(data, allowed_user_paths=[str(target)])

    def test_machine_created_ownership_cannot_be_invented_by_a_project_commit(self):
        data, target = self.machine_model()
        target.parent.mkdir()
        target.write_bytes(b"existing")
        data["machine"]["objects"]["codex-rules"]["fingerprint"]["value"] = hashlib.sha256(b"existing").hexdigest()
        self.runtime.var.mkdir(parents=True)
        self.runtime.registry.write_bytes(registry.serialize_registry(data, allowed_user_paths=[str(target)]))
        tx = Transaction(lock_path=self.runtime.lock, backup_root=self.runtime.backups, allowed_roots=[self.home])
        forged = copy.deepcopy(data)
        forged["machine"]["objects"]["codex-rules"].update(
            ownership="created", original_existed=False, backup_manifest=str(tx.manifest_path))
        with self.assertRaises(registry.RegistryError):
            registry.commit_registry(self.runtime.registry, forged, transaction=tx,
                expected=read_snapshot(self.runtime.registry), previous=data, allowed_user_paths=[str(target)])
        self.assertFalse(self.runtime.backups.exists())

    def test_nullable_migration_and_import_models_do_not_grant_installation(self):
        data = installed_registry()
        data["legacy_import"] = {"operation_id": "op", "source_tree_sha256": "c" * 64,
                                 "manifest_path": str(self.area / "manifest.json"), "status": "applying"}
        registry.validate_registry(data)
        with self.assertRaises(registry.RegistryError):
            registry.require_installed(data)
        data["legacy_import"]["extra"] = False
        with self.assertRaises(registry.RegistryError):
            registry.validate_registry(data)


from test_m204_enable import EnableFixture


class MachinePreservationTests(EnableFixture):
    def additional_entry_request(self):
        self.request.update(agents=['codex','claude'],approval=None)
        result=enable.run(self.request)
        self.assertEqual(result['status'],'approval_required',result)
        self.request['approval']=json.loads(result['next_action'])
        self.request['approval'].update(confirmed_at='2026-10-30T00:00:00Z',reference='exact additional rule entry confirmation')
        return self.request

    def test_machine_metadata_and_shared_private_bytes_unchanged_through_repeated_enable(self):
        metadata = {key: copy.deepcopy(self.load()[key]) for key in
                    ("product", "machine", "migration", "legacy_import")}
        self.apply()
        # Historical shared user convention: synthetic reused bytes, no CK install.
        shared_path=self.home/'.workbuddy/MEMORY.md';shared_path.parent.mkdir(parents=True,exist_ok=True)
        shared_path.write_bytes(b'<!-- fixture:user:start -->\nuser convention\xff\r\n<!-- fixture:user:end -->')
        model=self.load();assembly=model['projects'][str(self.root)]['checkouts'][str(self.root)]
        model['shared_objects']['historical-user-rule']={
            'kind':'user_convention','path':str(shared_path),'scope':'user','agents':['workbuddy'],
            'ownership':'reused','marker':{'start':'<!-- fixture:user:start -->','end':'<!-- fixture:user:end -->'},
            'fingerprint':{'algorithm':'sha256','basis':'block_bytes','value':hashlib.sha256(shared_path.read_bytes()).hexdigest()},
            'original_existed':True,'link_target':None,'backup_manifest':None,'consumers':[str(self.root)]}
        assembly['shared_object_ids']=['historical-user-rule']
        self.runtime.registry.write_bytes(registry.serialize_registry(model,allowed_user_paths=paths.allowed_user_paths(self.config,None,home=str(self.home))))
        shared_before=shared_path.read_bytes()

        self.request['approval']=None
        result = enable.run(self.request)
        self.assertEqual(result["status"], "completed", result)
        current = self.load()
        self.assertEqual({key: current[key] for key in metadata}, metadata)
        self.assertEqual(current["projects"][str(self.root)]["memory_policy"], "follow_ck")
        self.assertTrue(current["shared_objects"])
        self.assertEqual(shared_path.read_bytes(),shared_before)
        self.assertTrue(all(obj["consumers"] == [str(self.root)] for obj in current["shared_objects"].values()))

    def test_additional_enable_holds_writer_and_transaction_locks(self):
        seen = []
        def observe(event, path):
            if event == "before_write":
                self.assertTrue(self.runtime.lock.is_dir())
                self.assertTrue(self.runtime.transaction_lock.is_dir())
                seen.append(path)
        self.request["transaction_hook"] = observe
        self.request['agents']=['codex']
        self.apply()
        self.assertTrue(seen)
        seen.clear()
        def transaction_factory(**kwargs):
            self.assertEqual(kwargs["lock_path"], self.runtime.transaction_lock)
            self.assertEqual(kwargs["backup_root"], self.runtime.backups)
            old_hook = kwargs.get("hook")
            def hook(event, path):
                observe(event, path)
                if old_hook:old_hook(event, path)
            kwargs["hook"] = hook
            return Transaction(**kwargs)
        request=self.additional_entry_request()
        from unittest.mock import patch
        with patch.object(enable,'Transaction',side_effect=transaction_factory):
            result=enable.run(request)
        self.assertEqual(result["status"], "completed", result)
        self.assertTrue(seen)
        self.assertFalse(self.runtime.lock.exists())

    def test_additional_enable_cannot_bypass_writer_lock(self):
        self.request['agents']=['codex']
        self.apply()
        request = self.additional_entry_request()
        before = self.runtime.registry.read_bytes()
        self.runtime.lock.mkdir()
        result = enable.run(request)
        self.assertEqual(result["errors"][0]["code"], "lock_conflict", result)
        self.assertEqual(self.runtime.registry.read_bytes(), before)
        self.assertTrue(self.runtime.lock.exists())


if __name__ == "__main__":
    unittest.main()
