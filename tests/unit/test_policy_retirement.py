"""2026-11-01 经历开关退役合同:remove-memory/--memory/--no-memory 退出,disabled
降级为历史停用登记(schema3 保留可读),默认流程跳过不重建、零写入;核心命令前置
路由;用户文案统一「历史停用登记」不显示为 CK 停用。全部合成环境,零真实 HOME。
"""
import ast
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import agm
from agm_core import batch_enable, check, enable, paths, registry
from agm_core.project import resolve_project
from agm_core.registry import new_project, serialize_registry
from runtime_fixture import installed_registry, seed_project_executors, seed_runtime

NOW = "2026-10-30T00:00:00Z"


def snapshot(root):
    return {str(p.relative_to(root)): (p.lstat().st_mode, p.lstat().st_mtime_ns,
            os.readlink(p) if p.is_symlink() else p.read_bytes() if p.is_file() else None)
            for p in root.rglob("*")}


class RetirementFixture(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.area = Path(self.temp.name).resolve()
        self.root = self.area / "project"
        self.root.mkdir()
        subprocess.run(["git", "init", "-q", str(self.root)], check=True, capture_output=True)
        self.home = self.area / "home"
        self.home.mkdir()
        self.runtime = seed_runtime(self.home)
        self.config = paths.select_platform(paths.load_agents_table(), "darwin")
        self.request = {"project": str(self.root), "agents": ["codex"],
                        "approval": None, "interactive": False,
                        "home": str(self.home), "platform_config": self.config,
                        "runtime_layout": self.runtime}
        self.request.update(seed_project_executors(self.home))

    def load(self):
        return registry.load_registry(self.runtime.registry,
                                      allowed_user_paths=paths.allowed_user_paths(self.config, None, home=str(self.home)))

    def seed_tombstone(self):
        """按历史 remove/--no-memory 之后的现场登记一个 disabled 项目。"""
        identity = resolve_project(self.root)
        data = self.load()
        data["projects"][str(identity.main_checkout)] = new_project(identity, ["codex"])
        data["projects"][str(identity.main_checkout)]["memory_policy"] = "disabled"
        allowed = paths.allowed_user_paths(self.config, None, home=str(self.home))
        self.runtime.registry.write_bytes(serialize_registry(data, allowed_user_paths=allowed))


class RetiredOptionTests(RetirementFixture):
    def test_explicit_memory_choice_is_rejected_zero_write(self):
        for choice in ("disabled", "follow_ck"):
            with self.subTest(choice=choice):
                self.seed_tombstone() if choice == "disabled" else None
                before = snapshot(self.area)
                result = enable.run(dict(self.request, memory_choice=choice))
                self.assertEqual(result["status"], "failed", result)
                self.assertEqual(result["errors"][0]["code"], "retired_option", result)
                self.assertEqual(snapshot(self.area), before)
                self.assertFalse(self.runtime.lock.exists())
                self.assertFalse(self.runtime.backups.exists())

    def test_none_memory_choice_still_works_for_internal_fixtures(self):
        result = enable.run(dict(self.request, memory_choice=None, preview=True))
        self.assertEqual(result["status"], "approval_required", result)


class TombstoneSkipTests(RetirementFixture):
    def test_tombstone_project_skipped_zero_write_and_no_rebuild(self):
        self.seed_tombstone()
        entry = self.root / "AGENTS.md"
        # 历史 --no-memory 可能保留入口:现场保留经历块与用户正文,不得宣称已撤。
        entry.write_bytes(b"user rules\r\n" + enable._block(enable.KEEPER_MARKER, enable.EXPERIENCE_TEXT))
        store = self.root / "docs/context-keeper/memory-keeper.md"
        store.parent.mkdir(parents=True)
        store.write_bytes(b"private memory")
        before = snapshot(self.area)
        result = enable.run(self.request)
        self.assertEqual(result["status"], "gaps", result)
        self.assertIn("历史停用登记", result["next_action"])
        # 不得设计成「先 migrate-policy 即可恢复」的死循环提示。
        self.assertNotIn("先 migrate-policy", result["next_action"])
        self.assertIn("不重建", result["next_action"])
        self.assertEqual(self.load()["projects"][str(self.root)]["memory_policy"], "disabled")
        self.assertEqual(snapshot(self.area), before)
        self.assertEqual(store.read_bytes(), b"private memory")
        self.assertTrue(any("历史停用登记" in w for w in result["warnings"]))
        self.assertEqual(result["projects"][0]["memory_policy"], "disabled")

    def test_tombstone_without_entry_also_skipped_without_claim(self):
        # 不宣称所有 disabled 都已撤入口:入口缺失时同样只跳过。
        self.seed_tombstone()
        before = snapshot(self.area)
        result = enable.run(self.request)
        self.assertEqual(result["status"], "gaps", result)
        self.assertFalse((self.root / "AGENTS.md").exists())
        self.assertEqual(snapshot(self.area), before)


class FreshEnableTests(RetirementFixture):
    def apply(self):
        preview = enable.run(dict(self.request, preview=True))
        self.assertEqual(preview["status"], "approval_required", preview)
        plan = json.loads(preview["next_action"])
        plan.update(confirmed_at=NOW, reference="retirement fixture confirmation")
        result = enable.run(dict(self.request, approval=plan))
        self.assertEqual(result["status"], "completed", result)
        return result

    def test_fresh_enable_writes_no_denied_and_policy_is_follow_ck(self):
        self.apply()
        data = self.load()
        project = data["projects"][str(self.root)]
        self.assertEqual(project["memory_policy"], "follow_ck")
        body = (self.root / "AGENTS.md").read_bytes()
        self.assertIn(enable.KEEPER_MARKER["start"].encode(), body)
        self.assertNotIn(enable.DENIED_MARKER["start"].encode(), body)
        self.assertNotIn(enable.DENIED_TEXT.encode(), body)

    def test_preview_is_zero_write_and_carries_follow_ck(self):
        before = snapshot(self.area)
        preview = enable.run(dict(self.request, preview=True))
        self.assertEqual(preview["status"], "approval_required", preview)
        plan = json.loads(preview["next_action"])
        self.assertEqual(plan["memory_policy"], "follow_ck")
        self.assertNotIn("memory_transition", plan)
        self.assertEqual(snapshot(self.area), before)


class CliRetirementTests(unittest.TestCase):
    def run_cli(self, *argv, home="/tmp/retirement-fake-home"):
        out, err = io.StringIO(), io.StringIO()
        code = agm.main(list(argv), stdout=out, stderr=err, home=home)
        return code, json.loads(out.getvalue())

    def test_retired_flags_and_command_rejected(self):
        for argv in (("enable-memory", "--project", "/tmp/p", "--memory"),
                     ("enable-memory", "--project", "/tmp/p", "--no-memory"),
                     ("remove-memory", "--project", "/tmp/p"),
                     ("remove-memory", "--project", "/tmp/p", "--preview")):
            with self.subTest(argv=argv):
                code, envelope = self.run_cli(*argv)
                self.assertEqual(code, 2, envelope)
                self.assertEqual(envelope["errors"][0]["code"], "invalid_arguments", envelope)

    def test_help_lists_core_commands_without_retired_ones(self):
        text = agm.build_parser().format_help()
        for command in ("uninstall-machine", "recover-uninstall", "migrate-policy"):
            self.assertIn(command, text)
        self.assertNotIn("remove-memory", text)
        self.assertNotIn("--memory", text.replace("--no-memory", ""))

    def test_core_commands_route_before_project_parsing(self):
        # 核心 v2 已在 worktree:前置路由直达 agm_core.uninstall/policy_migration,
        # 由核心自行输出 JSON;合成 HOME 无安装 → 核心自身 failed(2),外壳不再拦截。
        home = str(Path(tempfile.mkdtemp(prefix="retirement-route-")).resolve())
        self.addCleanup(lambda: subprocess.run(["rm", "-rf", home], check=False))
        before = set(os.listdir(home))
        for argv in (("uninstall-machine", "--backup-dir", os.path.join(home, "backup")),
                     ("recover-uninstall", "--manifest", os.path.join(home, "backup/manifest.json")),
                     ("migrate-policy",),
                     ("migrate-policy", "--project", "/tmp/p")):
            with self.subTest(argv=argv):
                code, envelope = self.run_cli(*argv, home=home)
                self.assertEqual(code, 2, envelope)
                self.assertNotEqual(envelope["errors"][0]["code"], "kernel_unavailable", envelope)
        self.assertEqual(set(os.listdir(home)), before)

    def test_core_route_guard_when_module_missing(self):
        # 核心未交付环境(如旧安装树)仍保守 kernel_unavailable,不执行任何写入。
        import importlib
        saved = agm.CORE_COMMAND_ROUTES["migrate-policy"]
        agm.CORE_COMMAND_ROUTES["migrate-policy"] = "agm_core.__missing_core__"
        try:
            code, envelope = self.run_cli("migrate-policy")
            self.assertEqual(code, 2, envelope)
            self.assertEqual(envelope["errors"][0]["code"], "kernel_unavailable", envelope)
        finally:
            agm.CORE_COMMAND_ROUTES["migrate-policy"] = saved


class BatchTombstoneTests(RetirementFixture):
    def test_batch_rows_skip_tombstone_without_ck_disabled_claim(self):
        self.seed_tombstone()
        request = dict(self.request)
        request.pop("project", None)
        request["directory"] = str(self.area)
        result = batch_enable.run(request)
        rows = [row for row in result["projects"] if row["state"] == "disabled"]
        self.assertTrue(rows, result)
        self.assertIn("历史停用登记", rows[0]["action"])
        self.assertTrue(any("不代表 Context Keeper 停用" in note for note in rows[0]["notes"]), rows[0])


class CheckTombstoneTests(RetirementFixture):
    def test_check_reports_tombstone_not_ck_disabled_and_no_entry_claim(self):
        self.seed_tombstone()
        before = snapshot(self.area)
        result = check.run(self.request)
        self.assertEqual(result["status"], "completed", result)
        report = result["projects"][0]
        self.assertEqual(report["memory_policy"], "disabled")
        self.assertTrue(any("历史停用登记" in w for w in result["warnings"]), result)
        self.assertEqual(snapshot(self.area), before)


class TemplateSemanticsTests(unittest.TestCase):
    def test_user_copy_uses_historical_registration_wording(self):
        from agm_core import user_entries
        menu = user_entries.agent_group_menu_text("/tmp/C")
        self.assertIn("批量接入项目规则", menu)
        self.assertIn("接入项目规则", menu)
        for banned in ("remove-memory", "--memory", "--no-memory", "启用项目记忆", "停用记忆", "tombstone"):
            self.assertNotIn(banned, menu)
        self.assertIn("uninstall-machine", menu)
        governance = user_entries.GOVERNANCE_RULES_TEXT
        self.assertIn("历史停用登记", governance)
        self.assertNotIn("--memory", governance)
        self.assertNotIn("tombstone", governance)
        topic = user_entries.usage_convention_topic_text("/tmp/C")
        self.assertIn("历史停用登记", topic)
        self.assertNotIn("tombstone", topic)
        for text in user_entries.NATIVE_FALLBACK_TEXTS.values():
            self.assertNotIn("tombstone", text)
        self.assertNotIn("tombstone", user_entries.CLAUDE_FALLBACK_TEXT)
        self.assertNotIn("tombstone", user_entries.WORKBUDDY_FALLBACK_TEXT)

    def test_public_layout_frozen_literals_match_012_history_and_live_uses_new_wording(self):
        """历史模板识别冻结:旧字面量锚定固定历史 blob(0f690ef=0.1.2,与 0.1.1 相同),
        不随 HEAD 漂移;live 常量已按 2026-11-01 裁定改用新职责文案,与冻结旧值不同。
        证据核对:0f690ef、04c32e2(0.1.1)、d14a3c0d(0.1.4)三处 blob 的
        CLAUDE/WORKBUDDY_FALLBACK_TEXT 与本仓 public_layout._OLD_* 逐字节一致。"""
        repo = Path(__file__).resolve().parents[2]
        from agm_core import public_layout, user_entries
        blob = subprocess.run(["git", "show", "0f690ef7aabf747a23bacc7662c19bee34c4bf52:scripts/agm_core/user_entries.py"],
                              cwd=repo, capture_output=True, check=True).stdout
        namespace = {}
        tree = ast.parse(blob)
        wanted = {"CLAUDE_FALLBACK_TEXT", "WORKBUDDY_FALLBACK_TEXT"}
        keep = [node for node in tree.body
                if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name)
                and node.targets[0].id in wanted]
        exec(compile(ast.Module(body=keep, type_ignores=[]), "<012-blob>", "exec"), namespace)
        self.assertEqual(public_layout._OLD_CLAUDE_FALLBACK, namespace["CLAUDE_FALLBACK_TEXT"])
        self.assertEqual(public_layout._OLD_WORKBUDDY_FALLBACK, namespace["WORKBUDDY_FALLBACK_TEXT"])
        # live 语义独立断言:当前模板必须仍是退役后的新职责文案,而非历史旧句;
        # 冻结旧字面量与新文案共存,供迁移精确识别历史字节。
        for live in (user_entries.CLAUDE_FALLBACK_TEXT, user_entries.WORKBUDDY_FALLBACK_TEXT):
            self.assertIn("历史停用登记", live)
            self.assertNotIn("政策非 disabled", live)
        self.assertNotEqual(user_entries.CLAUDE_FALLBACK_TEXT, public_layout._OLD_CLAUDE_FALLBACK)
        self.assertNotEqual(user_entries.WORKBUDDY_FALLBACK_TEXT, public_layout._OLD_WORKBUDDY_FALLBACK)

    def test_denied_constants_frozen_for_migration(self):
        self.assertIn("--memory", enable.DENIED_TEXT)  # 历史原文保留,字节不改
        self.assertEqual(enable.DENIED_MARKER["start"], "<!-- mem-sharing:memory-denied:start -->")


if __name__ == "__main__":
    unittest.main()
