"""M2-04 contract tests; every mutable path and provider lives in TemporaryDirectory."""
import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
sys.path.insert(0, str(SCRIPTS))
from agm_core import enable, paths, registry
from agm_core.entries import sha256


class EnableFixture(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.area = Path(self.temp.name).resolve()
        self.root = self.area / "project with spaces"
        self.root.mkdir()
        subprocess.run(["git", "init", "-q", str(self.root)], check=True)
        self.install = self.area / "agm/scripts"
        self.install.mkdir(parents=True)
        self.home = self.area / "home"
        self.home.mkdir()
        self.source = self.area / "keeper"
        (self.source / "scripts").mkdir(parents=True)
        subprocess.run(["git", "init", "-q", str(self.source)], check=True)
        (self.source / "SKILL.md").write_text("name: context-keeper\n")
        (self.source / "scripts/install.py").write_text('''BRIDGE_START = "<!-- context-keeper:start -->"
BRIDGE_END = "<!-- context-keeper:end -->"
BRIDGE = f"{BRIDGE_START}\\nKeeper rules\\n{BRIDGE_END}\\n"
WORKBUDDY_BRIDGE_START = "<!-- context-keeper:workbuddy:start -->"
WORKBUDDY_BRIDGE_END = "<!-- context-keeper:workbuddy:end -->"
WORKBUDDY_BRIDGE = f"{WORKBUDDY_BRIDGE_START}\\nUpstream WorkBuddy rules\\n{WORKBUDDY_BRIDGE_END}\\n"
''')
        (self.source / "scripts/context_keeper_probe.py").write_text("# isolated stub\n")
        self.config = paths.select_platform(paths.load_agents_table(), "darwin")
        self.calls = []
        self.preview_extra = False
        self.install_preview_only = False
        self.bad_ensure = False
        self.init_rc = 0
        self.init_approved_rc = 0
        self.partial = False
        self.request = {"project": str(self.root), "agents": ["codex", "claude", "workbuddy"],
                        "memory_choice": "no", "approval": None, "interactive": False,
                        "home": str(self.home), "platform_config": self.config,
                        "install_dir": str(self.install), "runner": self.runner}

    def runner(self, argv, **kwargs):
        self.calls.append(argv)
        self.assertEqual(kwargs["env"]["HOME"], str(self.home))
        self.assertEqual(kwargs["env"]["PYTHONDONTWRITEBYTECODE"], "1")
        self.assertNotIn("--all", argv)
        rc, data = 0, {}
        if argv[1].endswith("install.py"):
            if "--ensure-bridge" in argv:
                name = ".workbuddy/memory/MEMORY.md" if "--workbuddy" in argv else "AGENTS.md" if "--codex" in argv else "CLAUDE.md"
                data = {"scope": "user" if self.bad_ensure else "project", "bridge": str(self.root / name), "action": "unchanged"}
            elif "--approved" not in argv:
                links, rules = [], []
                for a in self.request["agents"]:
                    links.extend(str(self.root / p.split("{project}/", 1)[1] / "context-keeper") for p in self.config[a]["project_skill_roots"])
                    rules.append(paths.expand_path(self.config[a]["project_bridge_entry"], home=str(self.home), project=str(self.root)))
                if self.preview_extra:
                    rules.append(str(self.root / "UNSELECTED.md"))
                data = {"approval_required": True, "skill_entries": links, "rule_files": rules}
            else:
                data = {"scope": "project", "project": str(self.root)}
                if self.install_preview_only:
                    data["approval_required"] = True
        else:
            rc = self.init_approved_rc if "--approved" in argv else self.init_rc
            if "--approved" in argv:
                store = Path(argv[argv.index("--store-dir") + 1])
                if not rc or self.partial:
                    store.mkdir(parents=True, exist_ok=True)
                    (store / "memory-keeper.md").write_text("# memory\n")
                    if not self.partial:
                        for name in ("plans", "worklogs", "evolution"):
                            (store / name).mkdir(exist_ok=True)
                    if store != self.root / "docs/context-keeper":
                        (self.root / "context-keeper.json").write_text(json.dumps({"directory": str(store)}))
        return subprocess.CompletedProcess(argv, rc, json.dumps(data), "")

    def preview(self, memory="no", source=False, store=None):
        self.request["memory_choice"] = memory
        if source:
            # The dispatch contract carries source/location in the approval envelope.
            self.request["approval"] = {"provider_source": str(self.source), "memory_authorization": memory,
                                        "store_path": str(store) if store else None}
            # First discover the plan without approving: same source exposed via existing project link.
            self.request["approval"] = None
            alias = self.root / ".agents/skills/context-keeper"
            alias.parent.mkdir(parents=True, exist_ok=True)
            if not alias.is_symlink():
                alias.symlink_to(self.source, target_is_directory=True)
        result = enable.run(self.request)
        self.assertEqual(result["status"], "approval_required", result)
        plan = json.loads(result["next_action"])
        if store:
            # Regenerate an exact custom-location plan through the same inspection path.
            approval = dict(plan, store_path=str(store), confirmed_at="2026-10-29T00:00:00Z", reference="test confirmation")
            self.request["approval"] = approval
            result = enable.run(self.request)
            # Location changes only affect store_path, so the exact config plan remains valid.
            return approval, result
        plan.update(confirmed_at="2026-10-29T00:00:00Z", reference="test user confirmation")
        return plan

    def apply(self, memory="no", source=False):
        approval = self.preview(memory, source)
        self.request["approval"] = approval
        result = enable.run(self.request)
        self.assertEqual(result["status"], "completed", result)
        return result

    def load(self):
        return registry.load_registry(self.install / "registry.json", allowed_user_paths=paths.allowed_user_paths(self.config, None, home=str(self.home)))


class EnableTests(EnableFixture):
    def seed_m1_user_entry(self, custom_exception=False, reused_exception=False):
        self.apply("yes", True)
        path = self.home / ".workbuddy/MEMORY.md"
        data = self.load()
        shared = data["shared_objects"]
        rules_id = str(path) + "#rules"
        rules = shared.pop(rules_id)
        content = path.read_bytes()
        span = enable.entries.managed_span(content, **enable._marker_args(enable.BASE_MARKER))
        content = b"# Existing user conventions\n" + content[:span[0]] + content[span[1]:]
        if custom_exception:
            block = enable._block(enable.EXCEPTION_MARKER, "Previously approved exception wording")
            content = enable.entries.render_block(content, block, **enable._marker_args(enable.EXCEPTION_MARKER),
                        expected_fingerprint=enable.entries.block_fingerprint(content, **enable._marker_args(enable.EXCEPTION_MARKER)))
            shared[str(path) + "#keeper-exception"]["fingerprint"]["value"] = sha256(block)
        if reused_exception:
            shared[str(path) + "#keeper-exception"].update(ownership="reused", original_existed=True)
        path.write_bytes(content)
        rules.update(kind="file", marker=None, ownership="reused", original_existed=True,
                     fingerprint={"algorithm": "sha256", "basis": "file_bytes", "value": sha256(content)})
        shared[str(path) + "#base"] = rules
        assembly = data["projects"][str(self.root)]["checkouts"][str(self.root)]
        assembly["shared_object_ids"].remove(rules_id)
        assembly["shared_object_ids"].append(str(path) + "#base")
        (self.install / "registry.json").write_bytes(registry.serialize_registry(data,
            allowed_user_paths=paths.allowed_user_paths(self.config, None, home=str(self.home))))
        self.request["approval"] = None
        self.calls.clear()
        return path

    def test_m1_shared_entry_unchanged_for_new_consumer_despite_new_template(self):
        path = self.seed_m1_user_entry(custom_exception=True)
        before = path.read_bytes(), path.stat().st_mtime_ns
        second = self.area / "second project"
        second.mkdir()
        subprocess.run(["git", "init", "-q", str(second)], check=True)
        self.request.update(project=str(second), approval={"provider_source": str(self.source),
                            "memory_authorization": "yes", "store_path": None})
        result = enable.run(self.request)
        self.assertEqual(result["status"], "approval_required", result)
        plan = json.loads(result["next_action"])
        self.assertNotIn(str(path), [c["path"] for c in plan["changes"]])
        self.assertEqual((path.read_bytes(), path.stat().st_mtime_ns), before)
        self.assertEqual(self.calls, [])

    def test_shared_exception_external_edit_requires_exact_update_review(self):
        path = self.seed_m1_user_entry(reused_exception=True)
        original = path.read_bytes()
        marker = enable.EXCEPTION_MARKER
        span = enable.entries.managed_span(original, **enable._marker_args(marker))
        foreign = enable._block(marker, "External edit")
        edited = original[:span[0]] + foreign + original[span[1]:]
        path.write_bytes(edited)
        result = enable.run(self.request)
        self.assertEqual(result["status"], "approval_required", result)
        plan = json.loads(result["next_action"])
        changes = [c for c in plan["changes"] if c["path"] == str(path)]
        self.assertEqual(changes, [{"path": str(path), "operation": "update",
                        "before_fingerprint": sha256(edited), "after_fingerprint": sha256(original)}])
        self.assertEqual(path.read_bytes(), edited)
        self.assertEqual(self.calls, [])
        plan.update(confirmed_at="2026-10-29T00:00:00Z", reference="review exact shared repair")
        self.request["approval"] = plan
        result = enable.run(self.request)
        self.assertEqual(result["status"], "completed", result)
        self.assertEqual(path.read_bytes(), original)
        self.assertEqual(self.load()["shared_objects"][str(path) + "#base"]["fingerprint"]["value"], sha256(original))

    def test_created_shared_drift_still_preserves_registry_ownership_guard(self):
        path = self.seed_m1_user_entry()
        edited = path.read_bytes().replace("项目记忆例外".encode(), b"External edit")
        path.write_bytes(edited)
        result = enable.run(self.request)
        self.assertEqual(result["status"], "approval_required", result)
        plan = json.loads(result["next_action"])
        self.assertIn(str(path), [c["path"] for c in plan["changes"]])
        plan.update(confirmed_at="2026-10-29T00:00:00Z", reference="review created drift")
        self.request["approval"] = plan
        result = enable.run(self.request)
        self.assertEqual(result["status"], "failed", result)
        self.assertEqual(result["errors"][0]["code"], "registry_invalid")
        self.assertIn("created unit drifted", result["errors"][0]["message"])
        self.assertIn("人工核对并还原", result["errors"][0]["recovery"])
        self.assertIn("remove", result["next_action"])
        self.assertEqual(path.read_bytes(), edited)

    def test_unknown_approved_shared_wording_cannot_be_repaired_with_new_template(self):
        path = self.seed_m1_user_entry(custom_exception=True, reused_exception=True)
        edited = path.read_bytes().replace(b"Previously approved", b"External edit")
        path.write_bytes(edited)
        result = enable.run(self.request)
        self.assertEqual(result["status"], "failed", result)
        self.assertEqual(result["errors"][0]["code"], "drift")
        self.assertEqual(path.read_bytes(), edited)
        self.assertEqual(self.calls, [])

    def test_m1_shared_entry_idempotent_without_template_migration(self):
        path = self.seed_m1_user_entry(custom_exception=True)
        before = path.read_bytes(), path.stat().st_mtime_ns
        result = enable.run(self.request)
        self.assertEqual(result["status"], "completed", result)
        self.assertEqual(result["changes"], [])
        self.assertEqual((path.read_bytes(), path.stat().st_mtime_ns), before)

    def test_preview_is_no_write_and_has_exact_changes(self):
        plan = self.preview()
        self.assertEqual(plan["memory_authorization"], "no")
        self.assertFalse((self.root / "AGENTS.md").exists())
        self.assertFalse((self.install / "registry.json").exists())
        self.assertFalse((self.install / "backups").exists())
        self.assertFalse((self.install / ".agm.lock").exists())
        self.assertEqual(self.calls, [])
        self.assertTrue(all(c["after_fingerprint"] for c in plan["changes"]))

    def test_base_only_and_existing_no_default_persists(self):
        self.apply()
        self.request.update(approval=None, memory_choice=None)
        result = enable.run(self.request)
        self.assertEqual(result["status"], "completed", result)
        self.assertEqual(result["changes"], [])
        self.assertEqual(self.calls, [])
        self.assertEqual(self.load()["projects"][str(self.root)]["memory_authorization"], "no")
        self.assertIn(b"@AGENTS.md", (self.root / "CLAUDE.md").read_bytes())

    def test_memory_four_states_and_pending_runtime(self):
        self.apply("yes", True)
        p = self.load()["projects"][str(self.root)]
        a = p["checkouts"][str(self.root)]
        self.assertEqual(p["memory_authorization"], "yes")
        self.assertEqual(a["states"]["source_available"]["status"], "ready")
        self.assertEqual(a["states"]["store_authorized_ready"]["status"], "ready")
        for state in ("skill_installed", "bridge_assembled"):
            self.assertTrue(all(f["status"] == "ready" for f in a["states"][state].values()))
        self.assertEqual(a["runtime_acceptance"]["status"], "pending")
        self.assertEqual(len([c for c in self.calls if "--ensure-bridge" in c]), 3)
        self.assertTrue(any("--workbuddy" in c for c in self.calls if "--ensure-bridge" in c))

    def test_idempotent_configs_not_rewritten_and_ownership_retained(self):
        self.apply("yes", True)
        p = self.root / "AGENTS.md"
        before = p.stat().st_mtime_ns
        ledger = self.load()
        self.request["approval"] = None
        result = enable.run(self.request)
        self.assertEqual(result["status"], "completed", result)
        self.assertEqual(result["changes"], [])
        self.assertEqual(p.stat().st_mtime_ns, before)
        old = ledger["projects"][str(self.root)]["checkouts"][str(self.root)]["objects"]
        new = self.load()["projects"][str(self.root)]["checkouts"][str(self.root)]["objects"]
        self.assertEqual({k: v["ownership"] for k, v in old.items()}, {k: v["ownership"] for k, v in new.items()})

    def test_exact_missing_created_bridge_repaired_without_new_approval(self):
        self.apply("yes", True)
        path = self.root / ".workbuddy/memory/MEMORY.md"
        original = path.read_bytes()
        path.unlink()
        self.request["approval"] = None
        result = enable.run(self.request)
        self.assertEqual(result["status"], "completed", result)
        self.assertEqual(path.read_bytes(), original)

    def test_missing_codex_and_claude_blocks_repair_despite_overlapping_base_snapshots(self):
        self.apply("yes", True)
        for name in ("AGENTS.md", "CLAUDE.md"):
            path = self.root / name
            data = path.read_bytes()
            span = enable.entries.managed_span(data, **enable._marker_args(enable.KEEPER_MARKER))
            path.write_bytes(data[:span[0]] + data[span[1]:] + b"\noutside user edit\n")
        self.request["approval"] = None
        result = enable.run(self.request)
        self.assertEqual(result["status"], "completed", result)
        for name in ("AGENTS.md", "CLAUDE.md"):
            self.assertIn(b"outside user edit", (self.root / name).read_bytes())
            self.assertIn(b"Keeper rules", (self.root / name).read_bytes())


    def test_new_agent_requires_approval(self):
        self.request["agents"] = ["codex"]
        self.apply()
        self.request.update(approval=None, agents=["codex", "claude"])
        self.assertEqual(enable.run(self.request)["status"], "approval_required")

    def test_drift_precedes_every_installer_call(self):
        self.apply("yes", True)
        self.calls.clear()
        path = self.root / "AGENTS.md"
        path.write_bytes(path.read_bytes().replace(b"Keeper rules", b"foreign edit"))
        self.request["approval"] = None
        result = enable.run(self.request)
        self.assertEqual(result["status"], "failed", result)
        self.assertEqual(result["errors"][0]["code"], "drift")
        self.assertEqual(self.calls, [])

    def test_approval_binds_every_field(self):
        plan = self.preview("yes", True)
        for field, value in (("main_checkout", str(self.area)), ("git_common_dir", str(self.area)),
                             ("provider_fingerprints", []), ("changes", []), ("agents", ["codex"])):
            with self.subTest(field=field):
                self.request["approval"] = dict(plan, **{field: value})
                result = enable.run(self.request)
                self.assertEqual(result["status"], "approval_required", result)
                self.assertEqual(result["errors"][0]["code"], "approval_mismatch")
                self.assertEqual(self.calls, [])

    def test_before_fingerprint_changed_since_approval(self):
        plan = self.preview()
        (self.root / "CLAUDE.md").write_bytes(b"external\n")
        self.request["approval"] = plan
        self.assertEqual(enable.run(self.request)["errors"][0]["code"], "approval_mismatch")
        self.assertFalse((self.root / "AGENTS.md").exists())

    def test_source_changed_since_approval(self):
        plan = self.preview("yes", True)
        (self.source / "SKILL.md").write_text("changed")
        self.request["approval"] = plan
        self.assertEqual(enable.run(self.request)["errors"][0]["code"], "approval_mismatch")
        self.assertEqual(self.calls, [])

    def test_copy_and_foreign_link_protected_before_installer(self):
        plan = self.preview("yes", True)
        path = self.root / ".codex/skills/context-keeper"
        path.mkdir(parents=True)
        self.request["approval"] = plan
        result = enable.run(self.request)
        self.assertEqual(result["status"], "failed")
        self.assertEqual(self.calls, [])
        self.assertTrue(path.is_dir())

    def test_preview_rc_zero_approval_required_is_not_completion(self):
        plan = self.preview("yes", True)
        self.request["approval"] = plan
        self.install_preview_only = True
        result = enable.run(self.request)
        self.assertEqual(result["status"], "approval_required", result)
        self.assertFalse((self.install / "registry.json").exists())
        self.assertFalse((self.root / "AGENTS.md").exists())

    def test_scope_mismatch_preview_stops_before_writes(self):
        plan = self.preview("yes", True)
        self.request["approval"] = plan
        self.preview_extra = True
        result = enable.run(self.request)
        self.assertEqual(result["errors"][0]["code"], "provider_scope_mismatch")
        self.assertFalse((self.root / "AGENTS.md").exists())

    def test_ensure_wrong_scope_rolls_config_back(self):
        plan = self.preview("yes", True)
        self.request["approval"] = plan
        self.bad_ensure = True
        result = enable.run(self.request)
        self.assertEqual(result["errors"][0]["code"], "provider_scope_mismatch")
        self.assertFalse((self.install / "registry.json").exists())
        self.assertFalse((self.root / "AGENTS.md").exists())

    def test_migration_preview_stops_immediately(self):
        plan = self.preview("yes", True)
        self.request["approval"] = plan
        self.init_rc = 3
        result = enable.run(self.request)
        self.assertEqual(result["status"], "migration_required", result)
        self.assertEqual(len(self.calls), 2)
        self.assertFalse((self.root / "AGENTS.md").exists())
        self.assertFalse((self.install / "registry.json").exists())

    def test_init_preview_five_then_approved_success(self):
        self.init_rc = 5
        self.apply("yes", True)

    def test_init_two_is_failure_not_migration(self):
        plan = self.preview("yes", True)
        self.request["approval"] = plan
        self.init_rc = 2
        result = enable.run(self.request)
        self.assertEqual(result["status"], "failed", result)
        self.assertEqual(result["errors"][0]["code"], "keeper_failed")

    def test_partial_init_assets_preserved_without_ready_registry(self):
        plan = self.preview("yes", True)
        self.request["approval"] = plan
        self.partial = True
        self.init_approved_rc = 2
        result = enable.run(self.request)
        self.assertEqual(result["status"], "failed", result)
        self.assertTrue((self.root / "docs/context-keeper/memory-keeper.md").exists())
        self.assertFalse((self.install / "registry.json").exists())
        self.assertFalse((self.root / "AGENTS.md").exists())

    def test_workbuddy_top_preserves_raw_native_bytes(self):
        path = self.root / ".workbuddy/memory/MEMORY.md"
        path.parent.mkdir(parents=True)
        native = b"native\r\n\xffdaily logs\r\n"
        path.write_bytes(native)
        self.apply("yes", True)
        self.assertTrue(path.read_bytes().startswith(b"<!-- context-keeper:workbuddy:start -->"))
        self.assertTrue(path.read_bytes().endswith(native))

    def test_worktree_rejected_without_writes(self):
        subprocess.run(["git", "-C", str(self.root), "-c", "user.name=Fixture", "-c", "user.email=f@example.invalid", "commit", "--allow-empty", "-qm", "fixture"], check=True)
        tree = self.area / "linked"
        subprocess.run(["git", "-C", str(self.root), "worktree", "add", "-qb", "fixture", str(tree)], check=True)
        self.request["project"] = str(tree)
        result = enable.run(self.request)
        self.assertEqual(result["errors"][0]["code"], "worktree_unsupported")
        self.assertFalse((self.install / "registry.json").exists())

    def test_lock_is_not_stolen(self):
        (self.install / ".agm.lock").mkdir()
        result = enable.run(self.request)
        self.assertEqual(result["errors"][0]["code"], "lock_conflict")
        self.assertTrue((self.install / ".agm.lock").exists())

    def test_corrupt_registry_requires_exact_approval_and_backup(self):
        (self.install / "registry.json").write_bytes(b"{broken")
        plan = self.preview()
        self.request["approval"] = plan
        result = enable.run(self.request)
        self.assertEqual(result["status"], "completed", result)
        self.assertTrue(any(p.read_bytes() == b"{broken" for p in (self.install / "backups").rglob("*.before")))

    def test_source_update_requires_new_approval_without_recorded_fingerprint_refresh(self):
        self.apply("yes", True)
        (self.source / "SKILL.md").write_text("new source version")
        self.request["approval"] = None
        self.calls.clear()
        result = enable.run(self.request)
        self.assertEqual(result["status"], "approval_required", result)
        self.assertEqual(self.calls, [])

    def test_new_shared_unit_cannot_inherit_prior_approval(self):
        self.apply()
        path = self.home / ".workbuddy/MEMORY.md"
        data = self.load()
        shared = data["shared_objects"]
        for oid in list(shared):
            shared.pop(oid)
        data["projects"][str(self.root)]["checkouts"][str(self.root)]["shared_object_ids"] = []
        (self.install / "registry.json").write_bytes(registry.serialize_registry(data))
        path.unlink()
        self.request["approval"] = None
        self.assertEqual(enable.run(self.request)["status"], "approval_required")

    def test_no_memory_after_yes_keeps_provider_assets(self):
        self.apply("yes", True)
        self.request.update(approval=None, memory_choice="no")
        result = enable.run(self.request)
        self.assertEqual(result["status"], "approval_required", result)
        approval = json.loads(result["next_action"])
        approval.update(confirmed_at="2026-10-29T00:00:00Z", reference="explicit decline")
        self.request["approval"] = approval
        result = enable.run(self.request)
        self.assertEqual(result["status"], "completed", result)
        self.assertEqual(self.load()["projects"][str(self.root)]["memory_authorization"], "no")
        self.assertTrue((self.root / "docs/context-keeper/memory-keeper.md").exists())

    def test_unknown_memory_choice_does_not_infer_yes_from_source(self):
        self.request["memory_choice"] = None
        self.assertEqual(enable.run(self.request)["status"], "approval_required")
        self.assertEqual(self.calls, [])

    def test_canonical_store_binding_rejects_config_redirect(self):
        plan = self.preview("yes", True)
        (self.root / "context-keeper.json").write_text(json.dumps({"directory": str(self.area / "other")}))
        self.request["approval"] = plan
        result = enable.run(self.request)
        self.assertEqual(result["errors"][0]["code"], "approval_mismatch")
        self.assertEqual(self.calls, [])

    def test_approved_init_five_never_marks_store_ready(self):
        plan = self.preview("yes", True)
        self.request["approval"] = plan
        self.init_approved_rc = 5
        result = enable.run(self.request)
        self.assertEqual(result["status"], "approval_required", result)
        self.assertFalse((self.install / "registry.json").exists())
        self.assertNotEqual(result["projects"][0]["states"]["store_authorized_ready"]["status"], "ready")

    def test_unknown_provider_failure_is_failure(self):
        plan = self.preview("yes", True)
        self.request["approval"] = plan
        self.init_rc = 99
        self.assertEqual(enable.run(self.request)["status"], "failed")

    def test_selected_agent_does_not_touch_other_executors(self):
        self.request["agents"] = ["codex"]
        self.apply("yes", True)
        self.assertFalse((self.root / "CLAUDE.md").exists())
        self.assertFalse((self.root / ".workbuddy").exists())
        self.assertFalse((self.home / ".workbuddy").exists())
        self.assertFalse(any("--claude" in c or "--workbuddy" in c for c in self.calls))


    def test_interactive_exact_plan_confirmation_and_decline(self):
        self.request.update(interactive=True, confirm=lambda prompt: False)
        result = enable.run(self.request)
        self.assertEqual(result["status"], "approval_required")
        self.assertFalse((self.root / "AGENTS.md").exists())
        prompts = []
        self.request["confirm"] = lambda prompt: prompts.append(prompt) or True
        result = enable.run(self.request)
        self.assertEqual(result["status"], "completed", result)
        self.assertIn(str(self.root), prompts[0])
        self.assertIn("after_fingerprint", prompts[0])

    def test_approved_init_migration_stops_before_store_metadata_readback(self):
        plan = self.preview("yes", True)
        self.request["approval"] = plan
        self.init_approved_rc = 3
        result = enable.run(self.request)
        self.assertEqual(result["status"], "migration_required", result)
        self.assertEqual(self.calls[-1][1], str(self.source / "scripts/context_keeper_probe.py"))
        self.assertIn("--approved", self.calls[-1])
        self.assertEqual(result["projects"][0]["states"]["store_authorized_ready"]["status"], "blocked")
        self.assertFalse((self.install / "registry.json").exists())
        self.assertFalse((self.root / "AGENTS.md").exists())


    def test_custom_store_location(self):
        plan, result = self.preview("yes", True, self.area / "custom-store")
        self.assertEqual(result["status"], "completed", result)
        self.assertEqual(self.load()["projects"][str(self.root)]["checkouts"][str(self.root)]["store"]["path"], str(self.area / "custom-store"))


if __name__ == "__main__":
    unittest.main()
