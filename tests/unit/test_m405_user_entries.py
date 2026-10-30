"""M4-05 regressions: user-entry planning/approved assembly on synthetic HOME."""
import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts"))
sys.path.insert(0, str(Path(__file__).parent))

from agm_core import layout, paths, registry, user_entries  # noqa: E402
from agm_core.entries import block_fingerprint, sha256  # noqa: E402
from agm_core.transaction import read_snapshot  # noqa: E402
from runtime_fixture import installed_registry, seed_runtime  # noqa: E402
from test_m405_detect import fake_codesign  # noqa: E402

BASE_MARKER = {"start": "<!-- mem-sharing:rules:start -->",
               "end": "<!-- mem-sharing:rules:end -->"}


class UserEntryFixture(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.area = Path(self.temp.name).resolve()
        self.home = self.area / "home"
        self.home.mkdir()
        self.runtime = layout.resolve_layout(self.home)
        self.config = paths.select_platform(paths.load_agents_table(), "darwin")
        self.apps = self.area / "Applications"
        self.apps.mkdir()
        self.bin_dir = self.area / "bin"
        self.bin_dir.mkdir()
        # Machine installed: complete ledger + product code source C.
        seed_runtime(self.home)
        code = self.runtime.code
        (code / "scripts").mkdir(parents=True)
        (code / "SKILL.md").write_text("# agent-group-memory fixture skill\n")
        self.memory_index = self.runtime.root / "memories" / "MEMORY.md"

    # ---- fixture helpers ---------------------------------------------------

    def seed_codex_package(self, name="@openai/codex"):
        package_dir = self.area / "lib" / "node_modules" / name
        (package_dir / "bin").mkdir(parents=True, exist_ok=True)
        script = package_dir / "bin" / "codex"
        script.write_text("#!/bin/sh\n")
        script.chmod(0o755)
        (package_dir / "package.json").write_text(json.dumps(
            {"name": name, "version": "0.162.0", "bin": {"codex": "bin/codex"}}))
        link = self.bin_dir / "codex"
        if link.is_symlink() or link.exists():
            link.unlink()
        link.symlink_to("../lib/node_modules/%s/bin/codex" % name)
        return package_dir

    def seed_workbuddy_bundle(self, *, version="1.4"):
        import plistlib
        bundle = self.apps / "WorkBuddy.app"
        (bundle / "Contents" / "MacOS").mkdir(parents=True)
        info = {"CFBundleName": "WorkBuddy", "CFBundleIdentifier": "com.fixture.workbuddy",
                "CFBundleExecutable": "WorkBuddy", "CFBundleShortVersionString": version}
        (bundle / "Contents" / "Info.plist").write_bytes(plistlib.dumps(info))
        exe = bundle / "Contents" / "MacOS" / "WorkBuddy"
        exe.write_text("#!/bin/sh\n")
        exe.chmod(0o755)
        return bundle

    def request(self, **overrides):
        request = {"home": str(self.home), "platform_config": self.config,
                   "agents": None, "search_paths": [str(self.bin_dir)],
                   "app_directories": [str(self.apps)]}
        request.update(overrides)
        return request

    def workbuddy_runner(self):
        return fake_codesign(identifier="com.fixture.workbuddy")

    def tree(self):
        return {str(p.relative_to(self.home)): (p.read_bytes(), p.stat().st_mtime_ns)
                if p.is_file() and not p.is_symlink() else (None, None)
                for p in self.home.rglob("*")}

    def approval_for(self, result):
        self.assertEqual(result["status"], "approval_required", result)
        plan = json.loads(result["next_action"])
        plan.update(confirmed_at="2026-10-30T00:00:00Z", reference="user confirmed fixture plan")
        return plan

    def preview(self, **overrides):
        return user_entries.run_user_entries(self.request(**overrides))

    def execute(self, preview=None, **overrides):
        result = preview if preview is not None else self.preview(**overrides)
        approval = self.approval_for(result)
        return user_entries.run_user_entries(self.request(approval=approval, **overrides))

    def load_ledger(self):
        allowed = paths.allowed_user_paths(self.config, None, home=str(self.home))
        return registry.load_registry(self.runtime.registry, allowed_user_paths=allowed)

    # ---- planning purity and target filtering ------------------------------

    def test_preview_is_read_only_and_requires_approval(self):
        self.seed_codex_package()
        before = self.tree()
        result = self.preview()
        self.assertEqual(result["status"], "approval_required", result)
        self.assertEqual(self.tree(), before)
        self.assertFalse(self.runtime.lock.exists())

    def test_only_codex_installed_plan_contains_no_other_agent_paths(self):
        self.seed_codex_package()
        result = self.preview()
        plan = json.loads(result["next_action"])
        written = [c["path"] for c in plan["changes"]] + plan["machine_objects"]
        self.assertTrue(written)
        for path in written:
            self.assertIn(".codex", path, path)
        self.assertEqual(plan["machine_agents"], ["codex"])
        self.assertEqual(plan["effective"], ["codex"])
        self.assertEqual(result["detection"]["agents"]["claude"]["status"], "absent")
        self.assertEqual(result["detection"]["agents"]["workbuddy"]["status"], "absent")

    def test_residual_claude_directory_is_unknown_and_never_written(self):
        self.seed_codex_package()
        (self.home / ".claude").mkdir()
        result = self.execute()
        self.assertEqual(result["status"], "completed", result)
        self.assertEqual(result["detection"]["agents"]["claude"]["status"], "unknown")
        self.assertFalse((self.home / ".claude" / "CLAUDE.md").exists())
        self.assertFalse((self.home / ".claude" / "skills").exists())
        self.assertTrue((self.home / ".codex" / "AGENTS.md").is_file())

    def test_explicit_not_installed_agent_stops_whole_request(self):
        self.seed_codex_package()
        before = self.tree()
        result = self.preview(agents=["codex", "claude"])
        self.assertEqual(result["status"], "failed", result)
        self.assertEqual(result["errors"][0]["code"], "agent_not_installed")
        self.assertEqual(self.tree(), before)

    def test_no_effective_agents_reports_without_faking_readiness(self):
        result = self.preview()
        self.assertEqual(result["status"], "completed", result)
        self.assertEqual(result["agents"]["effective"], [])
        self.assertEqual(result["agents"]["skipped"],
                         {"codex": "absent", "claude": "absent", "workbuddy": "absent"})

    # ---- approved execution -------------------------------------------------

    def test_execute_writes_entries_and_ledger_without_skill_projection(self):
        self.seed_codex_package()
        result = self.execute()
        self.assertEqual(result["status"], "completed", result)
        entry = self.home / ".codex" / "AGENTS.md"
        self.assertTrue(entry.is_file())
        data = entry.read_bytes()
        self.assertIn(BASE_MARKER["start"].encode(), data)
        self.assertIn(str(self.memory_index).encode(), data)
        # v1.11:入口文本携带治理条款与 /mem-sharing 菜单;无任何 Skill 投影落点。
        self.assertIn(user_entries.GOVERNANCE_RULES_TEXT.encode(), data)
        self.assertIn("/mem-sharing 菜单".encode(), data)
        self.assertIn("enable-memory".encode(), data)
        self.assertFalse((self.home / ".codex" / "skills").exists())
        ledger = self.load_ledger()
        self.assertEqual(ledger["machine"]["agents"]["codex"]["installation"]["status"], "installed")
        objects = ledger["machine"]["objects"]
        self.assertEqual(sorted(objects), [str(entry) + "#public-source"])
        for obj in objects.values():
            self.assertEqual(obj["scope"], "machine")
            self.assertEqual(obj["consumers"], [])
            self.assertEqual(obj["agents"], ["codex"])
        self.assertFalse(self.runtime.lock.exists())

    def test_second_assembly_is_idempotent_with_zero_writes(self):
        self.seed_codex_package()
        self.execute()
        before = self.tree()
        registry_bytes = self.runtime.registry.read_bytes()
        # execute 的事务备份按保留策略持续存在;幂等的判据是二次预览不再新增任何东西
        backups_before = sorted(str(p) for p in self.runtime.backups.rglob("*")) \
            if self.runtime.backups.exists() else []
        result = self.preview()
        self.assertEqual(result["status"], "completed", result)
        self.assertEqual(self.tree(), before)
        self.assertEqual(self.runtime.registry.read_bytes(), registry_bytes)
        backups_after = sorted(str(p) for p in self.runtime.backups.rglob("*")) \
            if self.runtime.backups.exists() else []
        self.assertEqual(backups_after, backups_before)

    def test_managed_block_drift_stops_all_writes(self):
        self.seed_codex_package()
        self.execute()
        entry = self.home / ".codex" / "AGENTS.md"
        registry_bytes = self.runtime.registry.read_bytes()
        drifted = entry.read_bytes().replace(
            b"mem-sharing:rules:start -->",
            b"mem-sharing:rules:start -- tampered", 1)
        entry.write_bytes(drifted)
        before = self.tree()
        result = self.preview()
        self.assertEqual(result["status"], "failed", result)
        self.assertEqual(result["errors"][0]["code"], "drift")
        self.assertEqual(self.tree(), before)
        self.assertEqual(self.runtime.registry.read_bytes(), registry_bytes)

    def test_projection_targets_are_never_touched_by_entry_planning(self):
        # v1.11:产品 Skill 投影取消——预置的投影位(链接/目录)不再是受管对象,
        # 规划与执行都不触碰它们,也不再因占用而整单停写。
        self.seed_codex_package()
        target = self.home / ".codex" / "skills" / "agent-group-memory"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.mkdir()
        (target / "foreign").write_bytes(b"keep me")

        def skills_tree():
            root = self.home / ".codex" / "skills"
            return {str(p.relative_to(root)): (p.read_bytes(), p.stat().st_mtime_ns)
                    if p.is_file() and not p.is_symlink() else (None, None)
                    for p in root.rglob("*")} if root.exists() else {}
        before = skills_tree()
        result = self.execute()
        self.assertEqual(result["status"], "completed", result)
        self.assertTrue((self.home / ".codex" / "AGENTS.md").is_file())
        self.assertTrue((target / "foreign").is_file())
        self.assertEqual(skills_tree(), before)
        ledger = self.load_ledger()
        self.assertFalse(any(obj["kind"] == "skill_symlink"
                             for obj in ledger["machine"]["objects"].values()))

    def test_symlinked_agent_dir_is_a_conflict(self):
        self.seed_codex_package()
        elsewhere = self.area / "elsewhere"
        elsewhere.mkdir()
        (self.home / ".codex").symlink_to(elsewhere, target_is_directory=True)
        result = self.preview()
        self.assertEqual(result["status"], "failed", result)
        self.assertEqual(result["errors"][0]["code"], "path_conflict")

    def test_approval_mismatch_is_rejected_without_writes(self):
        self.seed_codex_package()
        result = self.preview()
        approval = self.approval_for(result)
        approval["changes"] = []
        before = self.tree()
        outcome = user_entries.run_user_entries(self.request(approval=approval))
        self.assertEqual(outcome["status"], "approval_required", outcome)
        self.assertEqual(outcome["errors"][0]["code"], "approval_mismatch")
        self.assertEqual(self.tree(), before)

    def test_scene_change_between_preview_and_execute_stops(self):
        self.seed_codex_package()
        result = self.preview()
        approval = self.approval_for(result)
        # User edits the target entry after previewing: the exact plan no longer
        # matches the scene; execution must stop before any write.
        (self.home / ".codex").mkdir(exist_ok=True)
        (self.home / ".codex" / "AGENTS.md").write_bytes(b"my own rules\n")
        registry_bytes = self.runtime.registry.read_bytes()
        outcome = user_entries.run_user_entries(self.request(approval=approval))
        self.assertEqual(outcome["status"], "approval_required", outcome)
        self.assertEqual(outcome["errors"][0]["code"], "approval_mismatch")
        self.assertFalse((self.home / ".codex" / "skills").exists())
        self.assertEqual(self.runtime.registry.read_bytes(), registry_bytes)
        self.assertFalse(self.runtime.lock.exists())

    def test_execution_requires_installed_machine_ledger(self):
        self.runtime.registry.unlink()
        self.seed_codex_package()
        result = self.preview()
        self.assertEqual(result["status"], "approval_required", result)
        approval = self.approval_for(result)
        outcome = user_entries.run_user_entries(self.request(approval=approval))
        self.assertEqual(outcome["status"], "failed", outcome)
        self.assertEqual(outcome["errors"][0]["code"], "machine_not_installed")
        self.assertFalse(self.runtime.registry.exists())
        self.assertFalse(self.runtime.lock.exists())

    # ---- per-mode entry semantics -------------------------------------------

    def test_workbuddy_convention_uses_enable_template_text(self):
        enable_source = (REPO / "scripts" / "agm_core" / "enable.py").read_text(encoding="utf-8")
        self.assertIn(user_entries.WORKBUDDY_CONVENTION_TEXT, enable_source)

    def test_workbuddy_shared_convention_is_referenced_not_duplicated(self):
        self.seed_workbuddy_bundle()
        entry = self.home / ".workbuddy" / "MEMORY.md"
        entry.parent.mkdir(parents=True)
        block = (BASE_MARKER["start"] + "\n项目规则读取当前项目根 AGENTS.md。保留已有公共源与用户约定。\n"
                 + BASE_MARKER["end"]).encode("utf-8")
        entry.write_bytes(b"existing header\n" + block + b"\n")
        data = installed_registry()
        data["shared_objects"]["wb-convention"] = {
            "kind": "user_convention", "path": str(entry), "scope": "user",
            "agents": ["workbuddy"], "ownership": "reused", "marker": BASE_MARKER,
            "fingerprint": {"algorithm": "sha256", "basis": "block_bytes",
                            "value": block_fingerprint(entry.read_bytes(), BASE_MARKER["start"], BASE_MARKER["end"])},
            "original_existed": True, "link_target": None, "backup_manifest": None,
            "consumers": []}
        allowed = paths.allowed_user_paths(self.config, None, home=str(self.home))
        self.runtime.registry.write_bytes(registry.serialize_registry(data, allowed_user_paths=allowed))
        before = entry.read_bytes()
        request = self.request(detect_runner=self.workbuddy_runner())
        result = user_entries.run_user_entries(request)
        approval = self.approval_for(result)
        outcome = user_entries.run_user_entries(dict(request, approval=approval))
        self.assertEqual(outcome["status"], "completed", outcome)
        self.assertEqual(entry.read_bytes(), before)
        ledger = self.load_ledger()
        self.assertNotIn(str(entry) + "#convention", ledger["machine"]["objects"])
        self.assertEqual(ledger["machine"]["agents"]["workbuddy"]["installation"]["status"], "installed")
        self.assertFalse((self.home / ".workbuddy" / "skills").exists())

    def test_workbuddy_machine_convention_carries_governance_and_menu(self):
        self.seed_workbuddy_bundle()
        result = self.execute(detect_runner=self.workbuddy_runner())
        self.assertEqual(result["status"], "completed", result)
        entry = self.home / ".workbuddy" / "MEMORY.md"
        data = entry.read_bytes()
        self.assertIn(user_entries.WORKBUDDY_CONVENTION_TEXT.encode(), data)
        self.assertIn(user_entries.GOVERNANCE_RULES_TEXT.encode(), data)
        self.assertIn(user_entries.WORKBUDDY_FALLBACK_TEXT.encode(), data)
        self.assertIn("/mem-sharing 菜单".encode(), data)
        self.assertIn("批量启用记忆".encode(), data)

    def test_workbuddy_existing_entry_without_block_is_preserved(self):
        self.seed_workbuddy_bundle()
        entry = self.home / ".workbuddy" / "MEMORY.md"
        entry.parent.mkdir(parents=True)
        entry.write_bytes(b"my own workbuddy memory\n")
        before = entry.read_bytes()
        request = self.request(detect_runner=self.workbuddy_runner())
        result = user_entries.run_user_entries(request)
        approval = self.approval_for(result)
        outcome = user_entries.run_user_entries(dict(request, approval=approval))
        self.assertEqual(outcome["status"], "completed", outcome)
        self.assertEqual(entry.read_bytes(), before)
        ledger = self.load_ledger()
        self.assertFalse(any(obj["path"] == str(entry) for obj in ledger["machine"]["objects"].values()))

    def test_claude_receipt_import_line_references_common_source(self):
        exe = self.area / "native" / "claude"
        exe.parent.mkdir()
        exe.write_text("#!/bin/sh\n")
        exe.chmod(0o755)
        import hashlib
        receipt = {"schema_version": 1, "product": "Claude Code", "version": "2.1.0",
                   "executable": str(exe),
                   "files": [{"path": str(exe), "sha256": hashlib.sha256(exe.read_bytes()).hexdigest()}]}
        receipt_path = self.area / "native" / "receipt.json"
        receipt_path.write_text(json.dumps(receipt))
        request = self.request(user_candidates={
            "claude": [{"kind": "user_receipt", "path": str(receipt_path)}]})
        result = user_entries.run_user_entries(request)
        approval = self.approval_for(result)
        outcome = user_entries.run_user_entries(dict(request, approval=approval))
        self.assertEqual(outcome["status"], "completed", outcome)
        entry = self.home / ".claude" / "CLAUDE.md"
        self.assertEqual(entry.read_bytes(), ("@" + str(self.memory_index) + "\n").encode())
        ledger = self.load_ledger()
        obj = ledger["machine"]["objects"][str(entry) + "#import"]
        self.assertEqual(obj["kind"], "import")
        self.assertEqual(obj["ownership"], "reused")

    def test_claude_existing_content_keeps_reference_append_only(self):
        exe = self.area / "native" / "claude"
        exe.parent.mkdir()
        exe.write_text("#!/bin/sh\n")
        exe.chmod(0o755)
        import hashlib
        receipt = {"schema_version": 1, "product": "Claude Code", "executable": str(exe),
                   "files": [{"path": str(exe), "sha256": hashlib.sha256(exe.read_bytes()).hexdigest()}]}
        receipt_path = self.area / "native" / "receipt.json"
        receipt_path.write_text(json.dumps(receipt))
        entry = self.home / ".claude" / "CLAUDE.md"
        entry.parent.mkdir(parents=True, exist_ok=True)
        entry.write_bytes(b"# my claude rules\n")
        request = self.request(user_candidates={
            "claude": [{"kind": "user_receipt", "path": str(receipt_path)}]})
        result = user_entries.run_user_entries(request)
        approval = self.approval_for(result)
        outcome = user_entries.run_user_entries(dict(request, approval=approval))
        self.assertEqual(outcome["status"], "completed", outcome)
        data = entry.read_bytes()
        self.assertTrue(data.startswith(b"# my claude rules\n"))
        self.assertIn(("@" + str(self.memory_index)).encode(), data)

    def test_codex_existing_rules_get_block_appended(self):
        self.seed_codex_package()
        entry = self.home / ".codex" / "AGENTS.md"
        entry.parent.mkdir(parents=True, exist_ok=True)
        entry.write_bytes(b"# my codex rules\n")
        result = self.execute()
        self.assertEqual(result["status"], "completed", result)
        data = entry.read_bytes()
        self.assertTrue(data.startswith(b"# my codex rules\n"))
        self.assertIn(BASE_MARKER["start"].encode(), data)
        # 重复规划:同标记同模板不再追加第二个块;收敛后零差异,直接完成无需批准。
        fingerprint = block_fingerprint(data, BASE_MARKER["start"], BASE_MARKER["end"])
        repeat = self.preview()
        self.assertEqual(repeat["status"], "completed", repeat)
        data2 = entry.read_bytes()
        self.assertEqual(data2, data)
        self.assertEqual(block_fingerprint(data2, BASE_MARKER["start"], BASE_MARKER["end"]), fingerprint)

    def test_unknown_and_absent_mixed_order_only_writes_installed(self):
        self.seed_codex_package()
        (self.home / ".workbuddy").mkdir()  # residual hint -> unknown
        result = self.execute()
        self.assertEqual(result["status"], "completed", result)
        self.assertEqual(result["detection"]["agents"]["workbuddy"]["status"], "unknown")
        self.assertEqual(result["detection"]["agents"]["claude"]["status"], "absent")
        self.assertTrue((self.home / ".codex" / "AGENTS.md").is_file())
        self.assertFalse((self.home / ".workbuddy" / "MEMORY.md").exists())
        self.assertFalse((self.home / ".workbuddy" / "skills").exists())


if __name__ == "__main__":
    unittest.main()
