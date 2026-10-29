"""M2-03 CLI 外壳与路径表单元测试。

运行:仓库根目录 `python3 -m unittest tests.unit.test_cli`(或 pytest tests/unit/test_cli.py)。
仅标准库;不触真实入口/记录库;内核未接线,所有命令体止于 kernel_unavailable 桩,
天然无写入副作用(check 路径不会触发锁创建)。
"""

from __future__ import annotations

import io
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import types
import unittest
import unittest.mock

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SCRIPTS_DIR = os.path.join(REPO_ROOT, "scripts")
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)

import agm  # noqa: E402
from agm_core import paths  # noqa: E402

AGM_ENTRY = os.path.join(SCRIPTS_DIR, "agm.py")


def _agent_entry(**overrides):
    entry = {
        "user_entry": "{home}/.codex/AGENTS.md",
        "project_rule_entry": "{project}/AGENTS.md",
        "project_bridge_entry": "{project}/AGENTS.md",
        "project_skill_roots": ["{project}/.agents/skills"],
        "installation_signals": [
            {"kind": "directory_exists", "path": "{home}/.codex", "strength": "hint"}
        ],
        "rule_mode": "native",
        "bridge_owner": "context-keeper",
        "runtime_status": "upstream_verified_local_pending",
    }
    entry.update(overrides)
    return entry


def _valid_table():
    return {
        "schema_version": 1,
        "platforms": {
            "darwin": {
                "codex": _agent_entry(),
                "claude": _agent_entry(
                    user_entry="{home}/.claude/CLAUDE.md",
                    project_rule_entry="{project}/CLAUDE.md",
                    project_bridge_entry="{project}/CLAUDE.md",
                    project_skill_roots=["{project}/.claude/skills"],
                    installation_signals=[
                        {"kind": "directory_exists", "path": "{home}/.claude", "strength": "hint"}
                    ],
                    rule_mode="import_agents",
                ),
                "workbuddy": _agent_entry(
                    user_entry="{home}/.workbuddy/MEMORY.md",
                    project_bridge_entry="{project}/.workbuddy/memory/MEMORY.md",
                    project_skill_roots=["{project}/.workbuddy/skills"],
                    installation_signals=[
                        {"kind": "directory_exists", "path": "{home}/.workbuddy", "strength": "hint"}
                    ],
                    rule_mode="user_convention",
                    bridge_owner="agent-group-memory",
                    runtime_status="pending",
                ),
            }
        },
    }


def _write_json(data=None, raw=None, suffix=".json"):
    fd, path = tempfile.mkstemp(suffix=suffix)
    os.close(fd)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(raw if raw is not None else json.dumps(data, ensure_ascii=False))
    return path


def _approval_data(**overrides):
    data = {
        "schema_version": 1,
        "command": "enable-memory",
        "main_checkout": "/TestHome/src/demo",
        "checkout": "/TestHome/src/demo",
        "git_common_dir": "/TestHome/src/demo/.git",
        "agents": ["codex", "claude", "workbuddy"],
        "memory_authorization": "yes",
        "store_path": None,
        "provider_source": None,
        "provider_fingerprints": [],
        "changes": [],
        "confirmed_at": "2026-10-29T12:00:00Z",
        "reference": "用户 2026-10-29 会话确认",
    }
    data.update(overrides)
    return data


class PathTableValidationTests(unittest.TestCase):
    def test_repo_table_is_valid(self):
        table = paths.load_agents_table()
        self.assertEqual(table["schema_version"], 1)
        self.assertEqual(set(table["platforms"]["darwin"]), set(paths.AGENT_ORDER))

    def test_default_table_path_points_to_scripts(self):
        self.assertTrue(paths.default_table_path().endswith("agents.json"))

    def test_missing_table(self):
        with self.assertRaises(paths.PathsError) as ctx:
            paths.load_agents_table("/nonexistent/agents.json")
        self.assertEqual(ctx.exception.code, "agents_table_missing")

    def _assert_invalid(self, mutate=None, code="agents_table_invalid", raw=None):
        data = _valid_table()
        if mutate is not None:
            mutate(data)
        path = _write_json(data, raw=raw)
        try:
            with self.assertRaises(paths.PathsError) as ctx:
                paths.load_agents_table(path)
            self.assertEqual(ctx.exception.code, code)
        finally:
            os.unlink(path)

    def test_duplicate_json_keys_rejected(self):
        self._assert_invalid(
            raw='{"schema_version": 1, "schema_version": 2, "platforms": {}}'
        )

    def test_bool_schema_version_rejected(self):
        self._assert_invalid(lambda data: data.update(schema_version=True))

    def test_wrong_schema_version_rejected(self):
        self._assert_invalid(lambda data: data.update(schema_version=2))

    def test_unknown_top_field_rejected(self):
        self._assert_invalid(lambda data: data.update(extra=1))

    def test_empty_platforms_rejected(self):
        self._assert_invalid(lambda data: data.update(platforms={}))

    def test_incomplete_platform_rejected(self):
        self._assert_invalid(lambda data: data["platforms"]["darwin"].pop("workbuddy"))

    def test_unknown_agent_rejected(self):
        self._assert_invalid(
            lambda data: data["platforms"]["darwin"].update(cursor=_agent_entry())
        )

    def test_missing_agent_field_rejected(self):
        self._assert_invalid(lambda data: data["platforms"]["darwin"]["codex"].pop("rule_mode"))

    def test_unknown_agent_field_rejected(self):
        self._assert_invalid(
            lambda data: data["platforms"]["darwin"]["codex"].update(extra=1)
        )

    def test_bad_rule_mode_rejected(self):
        self._assert_invalid(
            lambda data: data["platforms"]["darwin"]["codex"].update(rule_mode="magic")
        )

    def test_static_passed_runtime_status_rejected(self):
        self._assert_invalid(
            lambda data: data["platforms"]["darwin"]["codex"].update(runtime_status="passed")
        )

    def test_empty_skill_roots_rejected(self):
        self._assert_invalid(
            lambda data: data["platforms"]["darwin"]["codex"].update(project_skill_roots=[])
        )

    def test_duplicate_skill_roots_rejected(self):
        self._assert_invalid(
            lambda data: data["platforms"]["darwin"]["codex"].update(
                project_skill_roots=["{project}/.agents/skills", "{project}/.agents/skills"]
            )
        )

    def test_signal_extra_field_rejected(self):
        def mutate(data):
            data["platforms"]["darwin"]["codex"]["installation_signals"][0]["ttl"] = 1

        self._assert_invalid(mutate)

    def test_signal_command_kind_rejected(self):
        def mutate(data):
            data["platforms"]["darwin"]["codex"]["installation_signals"][0]["kind"] = "command_exists"

        self._assert_invalid(mutate)

    def test_signal_non_hint_strength_rejected(self):
        def mutate(data):
            data["platforms"]["darwin"]["codex"]["installation_signals"][0]["strength"] = "proof"

        self._assert_invalid(mutate)

    def test_unknown_placeholder_rejected(self):
        self._assert_invalid(
            lambda data: data["platforms"]["darwin"]["codex"].update(
                user_entry="{home}/.codex/{env}/AGENTS.md"
            ),
            code="unknown_placeholder",
        )

    def test_unclosed_brace_rejected(self):
        self._assert_invalid(
            lambda data: data["platforms"]["darwin"]["codex"].update(
                user_entry="{home}/.codex/AGENTS.md {"
            ),
            code="unknown_placeholder",
        )


class PlatformAndTargetTests(unittest.TestCase):
    def setUp(self):
        self.table = _valid_table()

    def test_select_platform_known(self):
        config = paths.select_platform(self.table, "darwin")
        self.assertEqual(set(config), set(paths.AGENT_ORDER))

    def test_select_platform_unknown_rejected(self):
        with self.assertRaises(paths.PathsError) as ctx:
            paths.select_platform(self.table, "windows")
        self.assertEqual(ctx.exception.code, "unknown_platform")

    def test_current_platform_mapping(self):
        self.assertEqual(paths.current_platform("darwin"), "darwin")
        self.assertEqual(paths.current_platform("linux-gnu"), "linux")
        self.assertEqual(paths.current_platform("win32"), "windows")

    def test_resolve_agents_default_three(self):
        self.assertEqual(paths.resolve_agents(None), ["codex", "claude", "workbuddy"])

    def test_resolve_agents_canonical_order(self):
        self.assertEqual(
            paths.resolve_agents(["workbuddy", "codex"]), ["codex", "workbuddy"]
        )

    def test_resolve_agents_invalid_name(self):
        with self.assertRaises(paths.PathsError) as ctx:
            paths.resolve_agents(["cursor"])
        self.assertEqual(ctx.exception.code, "invalid_agent")

    def test_resolve_agents_duplicate_value(self):
        with self.assertRaises(paths.PathsError) as ctx:
            paths.resolve_agents(["codex", "codex"])
        self.assertEqual(ctx.exception.code, "invalid_agent")

    def test_resolve_agents_bare_string_rejected(self):
        with self.assertRaises(paths.PathsError) as ctx:
            paths.resolve_agents("codex")
        self.assertEqual(ctx.exception.code, "invalid_agent")

    def test_expand_path(self):
        self.assertEqual(
            paths.expand_path("{project}/AGENTS.md", home="/TestHome", project="/repo"),
            "/repo/AGENTS.md",
        )

    def test_expand_path_home_only_allows_null_project(self):
        self.assertEqual(
            paths.expand_path("{home}/.codex/AGENTS.md", home="/TestHome", project=None),
            "/TestHome/.codex/AGENTS.md",
        )

    def test_expand_path_relative_value_rejected(self):
        with self.assertRaises(paths.PathsError) as ctx:
            paths.expand_path("{project}/AGENTS.md", home="/TestHome", project="repo")
        self.assertEqual(ctx.exception.code, "path_invalid")

    def test_expand_path_relative_result_rejected(self):
        with self.assertRaises(paths.PathsError) as ctx:
            paths.expand_path("skills/context-keeper", home="/TestHome", project="/repo")
        self.assertEqual(ctx.exception.code, "path_invalid")

    def test_expand_path_unknown_placeholder(self):
        with self.assertRaises(paths.PathsError) as ctx:
            paths.expand_path("{env}/x", home="/TestHome", project="/repo")
        self.assertEqual(ctx.exception.code, "unknown_placeholder")


class InstallationHintTests(unittest.TestCase):
    def setUp(self):
        self.home = tempfile.mkdtemp(prefix="agm-hints-")
        self.addCleanup(shutil.rmtree, self.home)
        self.config = _valid_table()["platforms"]["darwin"]

    def test_hints_report_existence_with_hint_strength(self):
        os.makedirs(os.path.join(self.home, ".codex"))
        hints = paths.installation_hints(self.config, home=self.home)
        self.assertEqual(len(hints), 3)
        by_agent = {hint["agent"]: hint for hint in hints}
        self.assertTrue(by_agent["codex"]["exists"])
        self.assertFalse(by_agent["workbuddy"]["exists"])
        for hint in hints:
            self.assertEqual(hint["strength"], "hint")
            self.assertEqual(hint["kind"], "directory_exists")

    def test_hints_never_change_targets(self):
        # 目录信号仅 hint:workbuddy 目录缺失也不缩减缺省三家目标
        hints = paths.installation_hints(self.config, home=self.home)
        self.assertFalse(any(hint["exists"] for hint in hints))
        self.assertEqual(paths.resolve_agents(None), ["codex", "claude", "workbuddy"])

    def test_allowed_user_paths_expands_selected_agents(self):
        allowed = paths.allowed_user_paths(
            self.config, ["claude", "codex"], home="/TestHome"
        )
        self.assertEqual(
            allowed, ["/TestHome/.codex/AGENTS.md", "/TestHome/.claude/CLAUDE.md"]
        )

    def test_allowed_user_paths_single_agent(self):
        allowed = paths.allowed_user_paths(self.config, ["workbuddy"], home="/TestHome")
        self.assertEqual(allowed, ["/TestHome/.workbuddy/MEMORY.md"])


class CliTestCase(unittest.TestCase):
    def run_cli(self, *argv, interactive=False, platform="darwin", table_path=None, home="/TestHome"):
        out = io.StringIO()
        err = io.StringIO()
        code = agm.main(
            list(argv),
            stdin=io.StringIO(),
            stdout=out,
            stderr=err,
            interactive=interactive,
            platform=platform,
            table_path=table_path,
            home=home,
        )
        return code, json.loads(out.getvalue()), err.getvalue()


class CliParseTests(CliTestCase):
    def test_envelope_contract_on_error(self):
        code, envelope, _ = self.run_cli("enable-memory", "--memory", "--no-memory")
        self.assertEqual(code, 2)
        self.assertEqual(
            sorted(envelope),
            [
                "approval_required",
                "changes",
                "command",
                "errors",
                "next_action",
                "projects",
                "schema_version",
                "status",
                "warnings",
            ],
        )
        self.assertEqual(envelope["schema_version"], 1)
        self.assertEqual(envelope["status"], "failed")
        item = envelope["errors"][0]
        self.assertEqual(sorted(item), ["code", "message", "path", "recovery"])
        self.assertTrue(item["code"])

    def test_memory_mutex_rejected(self):
        code, envelope, _ = self.run_cli("enable-memory", "--memory", "--no-memory")
        self.assertEqual(code, 2)
        self.assertEqual(envelope["errors"][0]["code"], "invalid_arguments")

    def test_unknown_command_rejected(self):
        code, envelope, _ = self.run_cli("bogus-memory")
        self.assertEqual(code, 2)
        self.assertIsNone(envelope["command"])
        self.assertEqual(envelope["errors"][0]["code"], "invalid_arguments")

    def test_no_fourth_repair_command(self):
        for name in ("fix-memory", "repair-memory"):
            code, envelope, _ = self.run_cli(name)
            self.assertEqual(code, 2, name)
            self.assertIn("invalid choice", envelope["errors"][0]["message"], name)

    def test_missing_command_rejected(self):
        code, envelope, _ = self.run_cli()
        self.assertEqual(code, 2)
        self.assertEqual(envelope["errors"][0]["code"], "invalid_arguments")

    def test_unknown_flag_rejected(self):
        for extra in ("--force", "--yes", "--approved"):
            code, envelope, _ = self.run_cli("enable-memory", extra)
            self.assertEqual(code, 2, extra)
            self.assertEqual(envelope["errors"][0]["code"], "invalid_arguments", extra)

    def test_invalid_agent_name_rejected(self):
        code, envelope, _ = self.run_cli("enable-memory", "--agent", "cursor")
        self.assertEqual(code, 2)
        self.assertEqual(envelope["errors"][0]["code"], "invalid_agent")
        self.assertEqual(envelope["command"], "enable-memory")

    def test_duplicate_agent_values_rejected(self):
        code, envelope, _ = self.run_cli("enable-memory", "--agent", "codex", "codex")
        self.assertEqual(code, 2)
        self.assertEqual(envelope["errors"][0]["code"], "invalid_agent")

    def test_repeated_agent_flag_rejected(self):
        code, envelope, _ = self.run_cli(
            "enable-memory", "--agent", "codex", "--agent", "claude"
        )
        self.assertEqual(code, 2)
        self.assertEqual(envelope["errors"][0]["code"], "invalid_arguments")

    def test_repeated_project_flag_rejected(self):
        code, envelope, _ = self.run_cli(
            "check-memory", "--project", "/a", "--project", "/b"
        )
        self.assertEqual(code, 2)
        self.assertEqual(envelope["errors"][0]["code"], "invalid_arguments")

    def test_repeated_project_equals_form_rejected(self):
        code, envelope, _ = self.run_cli(
            "check-memory", "--project=/a", "--project=/b"
        )
        self.assertEqual(code, 2)
        self.assertEqual(envelope["errors"][0]["code"], "invalid_arguments")

    def test_empty_agent_flag_rejected(self):
        code, envelope, _ = self.run_cli("enable-memory", "--agent")
        self.assertEqual(code, 2)
        self.assertEqual(envelope["errors"][0]["code"], "invalid_arguments")

    def test_check_all_with_project_rejected(self):
        code, envelope, _ = self.run_cli("check-memory", "--all", "--project", "/repo")
        self.assertEqual(code, 2)
        self.assertEqual(envelope["errors"][0]["code"], "invalid_arguments")

    def test_remove_rejects_agent(self):
        code, envelope, _ = self.run_cli("remove-memory", "--agent", "codex")
        self.assertEqual(code, 2)

    def test_remove_rejects_memory(self):
        code, envelope, _ = self.run_cli("remove-memory", "--memory")
        self.assertEqual(code, 2)

    def test_remove_rejects_all(self):
        code, envelope, _ = self.run_cli("remove-memory", "--all")
        self.assertEqual(code, 2)

    def test_check_rejects_memory(self):
        code, envelope, _ = self.run_cli("check-memory", "--memory")
        self.assertEqual(code, 2)

    def test_check_rejects_agent(self):
        code, envelope, _ = self.run_cli("check-memory", "--agent", "codex")
        self.assertEqual(code, 2)

    def test_check_rejects_approval_file(self):
        code, envelope, _ = self.run_cli("check-memory", "--approval-file", "/tmp/a.json")
        self.assertEqual(code, 2)

    def test_enable_rejects_all(self):
        code, envelope, _ = self.run_cli("enable-memory", "--all")
        self.assertEqual(code, 2)

    def test_positional_garbage_rejected(self):
        code, envelope, _ = self.run_cli("enable-memory", "extra")
        self.assertEqual(code, 2)

    def test_valid_parse_reaches_routing(self):
        # 合法参数不会死在解析层:非交互 enable 停在批准门(5),证明解析通过
        code, envelope, _ = self.run_cli(
            "enable-memory", "--project", "/repo", "--agent", "codex", "claude", "--memory"
        )
        self.assertEqual(code, 5)
        self.assertEqual(envelope["command"], "enable-memory")
        self.assertEqual(envelope["status"], "approval_required")


class CliRoutingTests(CliTestCase):
    def test_noninteractive_enable_returns_5(self):
        code, envelope, err = self.run_cli("enable-memory", interactive=False)
        self.assertEqual(code, 5)
        self.assertEqual(envelope["status"], "approval_required")
        self.assertTrue(envelope["approval_required"])
        self.assertIn("--approval-file", envelope["next_action"])
        self.assertEqual(envelope["errors"], [])
        self.assertIn("待授权", err)

    def test_noninteractive_remove_returns_5(self):
        code, envelope, _ = self.run_cli("remove-memory", interactive=False)
        self.assertEqual(code, 5)
        self.assertEqual(envelope["status"], "approval_required")

    def test_unknown_platform_beats_approval_gate(self):
        code, envelope, _ = self.run_cli("enable-memory", interactive=False, platform="windows")
        self.assertEqual(code, 2)
        self.assertEqual(envelope["errors"][0]["code"], "unknown_platform")

    def test_unknown_platform_check_rejected(self):
        code, envelope, _ = self.run_cli("check-memory", interactive=False, platform="windows")
        self.assertEqual(code, 2)
        self.assertEqual(envelope["errors"][0]["code"], "unknown_platform")

    def test_broken_table_rejected_before_gate(self):
        path = _write_json({"schema_version": 2, "platforms": {}})
        try:
            code, envelope, _ = self.run_cli(
                "enable-memory", interactive=False, table_path=path
            )
            self.assertEqual(code, 2)
            self.assertEqual(envelope["errors"][0]["code"], "agents_table_invalid")
        finally:
            os.unlink(path)

    def test_check_has_no_approval_gate(self):
        code, envelope, _ = self.run_cli("check-memory", interactive=False)
        self.assertEqual(code, 2)
        self.assertEqual(envelope["errors"][0]["code"], "kernel_unavailable")
        self.assertNotEqual(envelope["status"], "approval_required")

    def test_kernel_stub_reports_no_writes(self):
        code, envelope, _ = self.run_cli("check-memory", "--all", interactive=False)
        self.assertEqual(code, 2)
        self.assertEqual(envelope["status"], "failed")
        self.assertEqual(envelope["changes"], [])
        self.assertTrue(envelope["warnings"])
        self.assertIn("未执行任何写入", envelope["errors"][0]["message"])

    @unittest.skipUnless(
        importlib.util.find_spec("agm_core.enable"),
        "enable 命令体(M2-04)交付后本用例生效",
    )
    def test_interactive_enable_reaches_enable_kernel(self):
        captured = {}

        def fake_run(request):
            captured["request"] = request
            return {
                "status": "completed",
                "projects": [],
                "changes": [],
                "warnings": [],
                "errors": [],
            }

        with unittest.mock.patch("agm_core.enable.run", side_effect=fake_run):
            code, envelope, _ = self.run_cli("enable-memory", interactive=True)
        self.assertEqual(code, 0)
        self.assertEqual(envelope["status"], "completed")
        self.assertEqual(captured["request"]["command"], "enable-memory")

    @unittest.skipUnless(
        importlib.util.find_spec("agm_core.enable"),
        "enable 命令体(M2-04)交付后本用例生效",
    )
    def test_enable_with_approval_file_reaches_enable_kernel(self):
        path = _write_json(_approval_data())
        captured = {}

        def fake_run(request):
            captured["request"] = request
            return {
                "status": "completed",
                "projects": [],
                "changes": [],
                "warnings": [],
                "errors": [],
            }

        try:
            with unittest.mock.patch("agm_core.enable.run", side_effect=fake_run):
                code, envelope, _ = self.run_cli(
                    "enable-memory",
                    "--memory",
                    "--approval-file",
                    path,
                    interactive=False,
                )
            self.assertEqual(code, 0)
            self.assertEqual(envelope["status"], "completed")
            self.assertEqual(envelope["command"], "enable-memory")
            self.assertEqual(captured["request"]["command"], "enable-memory")
        finally:
            os.unlink(path)

    def test_remove_with_approval_file_reaches_remove_kernel(self):
        data = _approval_data(
            command="remove-memory", agents=["codex"], memory_authorization=None
        )
        path = _write_json(data)
        captured = {}

        def fake_run(request):
            captured["request"] = request
            return {
                "status": "completed",
                "projects": [],
                "changes": [],
                "warnings": [],
                "errors": [],
            }

        try:
            with unittest.mock.patch("agm_core.remove.run", side_effect=fake_run):
                code, envelope, _ = self.run_cli(
                    "remove-memory", "--approval-file", path, interactive=False
                )
            self.assertEqual(code, 0)
            self.assertEqual(envelope["status"], "completed")
            self.assertEqual(captured["request"]["command"], "remove-memory")
            self.assertEqual(captured["request"]["approval"]["command"], "remove-memory")
        finally:
            os.unlink(path)


class ExitCodeMappingTests(unittest.TestCase):
    def test_completed(self):
        self.assertEqual(agm.exit_for("completed", []), 0)

    def test_gaps(self):
        self.assertEqual(agm.exit_for("gaps", []), 1)

    def test_failed(self):
        self.assertEqual(agm.exit_for("failed", []), 2)

    def test_recovery_required_is_execution_failure(self):
        self.assertEqual(agm.exit_for("recovery_required", []), 2)

    def test_migration_required(self):
        self.assertEqual(agm.exit_for("migration_required", []), 3)

    def test_approval_required(self):
        self.assertEqual(agm.exit_for("approval_required", []), 5)

    def test_migration_error_code_yields_3(self):
        self.assertEqual(agm.exit_for("gaps", [{"code": "migration_required"}]), 3)

    def test_failure_beats_migration(self):
        self.assertEqual(
            agm.exit_for("failed", [{"code": "migration_required"}]), 2
        )

    def test_migration_beats_approval(self):
        self.assertEqual(
            agm.exit_for("approval_required", [{"code": "migration_required"}]), 3
        )

    def test_unknown_status_conservative(self):
        self.assertEqual(agm.exit_for("weird", []), 2)


class ApprovalFileTests(unittest.TestCase):
    def _validate(self, data, *, command="enable-memory", agents=None, memory_choice=None, raw=None):
        path = _write_json(data if raw is None else {}, raw=raw)
        try:
            loaded = agm.load_approval(path)
            return agm.validate_approval(
                loaded,
                command=command,
                agents=agents if agents is not None else ["codex", "claude", "workbuddy"],
                memory_choice=memory_choice,
                path=path,
            )
        finally:
            os.unlink(path)

    def test_valid_enable_approval(self):
        data = self._validate(_approval_data())
        self.assertEqual(data["command"], "enable-memory")

    def test_missing_file(self):
        with self.assertRaises(agm.CliError) as ctx:
            agm.load_approval("/nonexistent/approval.json")
        self.assertEqual(ctx.exception.code, "approval_file_invalid")
        self.assertEqual(ctx.exception.path, "/nonexistent/approval.json")

    def test_duplicate_json_keys_rejected(self):
        with self.assertRaises(agm.CliError) as ctx:
            self._validate(None, raw='{"schema_version": 1, "schema_version": 1}')
        self.assertEqual(ctx.exception.code, "approval_file_invalid")

    def test_missing_field_rejected(self):
        data = _approval_data()
        del data["reference"]
        with self.assertRaises(agm.CliError) as ctx:
            self._validate(data)
        self.assertEqual(ctx.exception.code, "approval_file_invalid")

    def test_unknown_field_rejected(self):
        data = _approval_data()
        data["extra"] = 1
        with self.assertRaises(agm.CliError) as ctx:
            self._validate(data)
        self.assertEqual(ctx.exception.code, "approval_file_invalid")

    def test_bool_schema_version_rejected(self):
        data = _approval_data()
        data["schema_version"] = True
        with self.assertRaises(agm.CliError) as ctx:
            self._validate(data)
        self.assertEqual(ctx.exception.code, "approval_file_invalid")

    def test_command_mismatch_rejected(self):
        data = _approval_data()
        data["command"] = "remove-memory"
        with self.assertRaises(agm.CliError) as ctx:
            self._validate(data, command="enable-memory")
        self.assertEqual(ctx.exception.code, "approval_mismatch")

    def test_agents_mismatch_rejected(self):
        with self.assertRaises(agm.CliError) as ctx:
            self._validate(_approval_data(), agents=["codex"])
        self.assertEqual(ctx.exception.code, "approval_mismatch")

    def test_agents_invalid_name_rejected(self):
        data = _approval_data()
        data["agents"] = ["cursor"]
        with self.assertRaises(agm.CliError) as ctx:
            self._validate(data)
        self.assertEqual(ctx.exception.code, "approval_file_invalid")

    def test_remove_requires_null_memory_authorization(self):
        data = _approval_data(command="remove-memory", memory_authorization="yes")
        with self.assertRaises(agm.CliError) as ctx:
            self._validate(data, command="remove-memory", agents=None)
        self.assertEqual(ctx.exception.code, "approval_mismatch")

    def test_memory_choice_conflict_rejected(self):
        data = _approval_data()
        data["memory_authorization"] = "no"
        with self.assertRaises(agm.CliError) as ctx:
            self._validate(data, memory_choice="yes")
        self.assertEqual(ctx.exception.code, "approval_mismatch")

    def test_bad_sha256_rejected(self):
        data = _approval_data()
        data["provider_fingerprints"] = [
            {"path": "/TestHome/src/keeper", "sha256": "XYZ"}
        ]
        with self.assertRaises(agm.CliError) as ctx:
            self._validate(data)
        self.assertEqual(ctx.exception.code, "approval_file_invalid")

    def test_valid_fingerprint_accepted(self):
        data = _approval_data()
        data["provider_source"] = "/TestHome/src/context-keeper"
        data["provider_fingerprints"] = [
            {"path": "/TestHome/src/context-keeper", "sha256": "a" * 64}
        ]
        self.assertIsNotNone(self._validate(data))

    def test_bad_operation_rejected(self):
        data = _approval_data()
        data["changes"] = [
            {
                "path": "/repo/AGENTS.md",
                "operation": "repair",
                "before_fingerprint": None,
                "after_fingerprint": "b" * 64,
            }
        ]
        with self.assertRaises(agm.CliError) as ctx:
            self._validate(data)
        self.assertEqual(ctx.exception.code, "approval_file_invalid")

    def test_bad_confirmed_at_rejected(self):
        data = _approval_data()
        data["confirmed_at"] = "2026-10-29 12:00:00"
        with self.assertRaises(agm.CliError) as ctx:
            self._validate(data)
        self.assertEqual(ctx.exception.code, "approval_file_invalid")

    def test_impossible_date_rejected(self):
        data = _approval_data()
        data["confirmed_at"] = "2026-13-40T99:99:99Z"
        with self.assertRaises(agm.CliError) as ctx:
            self._validate(data)
        self.assertEqual(ctx.exception.code, "approval_file_invalid")

    def test_empty_reference_rejected(self):
        data = _approval_data()
        data["reference"] = ""
        with self.assertRaises(agm.CliError) as ctx:
            self._validate(data)
        self.assertEqual(ctx.exception.code, "approval_file_invalid")

    def test_relative_store_path_rejected(self):
        data = _approval_data()
        data["store_path"] = "relative/store"
        with self.assertRaises(agm.CliError) as ctx:
            self._validate(data)
        self.assertEqual(ctx.exception.code, "approval_file_invalid")


class RequestBuildingTests(unittest.TestCase):
    def test_enable_request_contains_allowed_user_paths(self):
        table = _valid_table()
        config = table["platforms"]["darwin"]
        namespace = types.SimpleNamespace(
            command="enable-memory",
            project="/repo",
            agent=["codex", "claude"],
            memory_choice=None,
            approval_file=None,
        )
        request = agm.build_request(
            "enable-memory",
            namespace,
            agents=["codex", "claude"],
            approval=None,
            table=table,
            platform_key="darwin",
            platform_config=config,
            table_path="/t/agents.json",
            interactive=True,
            home="/TestHome",
        )
        self.assertEqual(
            request["allowed_user_paths"],
            ["/TestHome/.codex/AGENTS.md", "/TestHome/.claude/CLAUDE.md"],
        )
        self.assertEqual(request["agents"], ["codex", "claude"])
        self.assertTrue(request["interactive"])

    def test_check_request_has_no_allowed_user_paths(self):
        table = _valid_table()
        namespace = types.SimpleNamespace(command="check-memory", project=None, all=True)
        request = agm.build_request(
            "check-memory",
            namespace,
            agents=None,
            approval=None,
            table=table,
            platform_key="darwin",
            platform_config=table["platforms"]["darwin"],
            table_path="/t/agents.json",
            interactive=False,
            home="/TestHome",
        )
        self.assertEqual(request["allowed_user_paths"], [])
        self.assertTrue(request["all"])


class RealEntrySubprocessTests(unittest.TestCase):
    """真实入口(python3 scripts/agm.py)冒烟:子进程捕获环境下 stdin 非 TTY。"""

    def _run(self, *argv):
        return subprocess.run(
            [sys.executable, AGM_ENTRY] + list(argv),
            capture_output=True,
            text=True,
            cwd=REPO_ROOT,
        )

    def test_enable_memory_noninteractive_exit_5(self):
        proc = self._run("enable-memory")
        self.assertEqual(proc.returncode, 5)
        envelope = json.loads(proc.stdout)
        self.assertEqual(envelope["status"], "approval_required")
        self.assertTrue(envelope["approval_required"])

    def test_check_memory_kernel_unavailable_exit_2(self):
        proc = self._run("check-memory")
        self.assertEqual(proc.returncode, 2)
        envelope = json.loads(proc.stdout)
        self.assertEqual(envelope["errors"][0]["code"], "kernel_unavailable")

    def test_fourth_command_exit_2(self):
        proc = self._run("fix-memory")
        self.assertEqual(proc.returncode, 2)
        envelope = json.loads(proc.stdout)
        self.assertEqual(envelope["errors"][0]["code"], "invalid_arguments")

    def test_invalid_agent_exit_2(self):
        proc = self._run("enable-memory", "--agent", "cursor")
        self.assertEqual(proc.returncode, 2)
        envelope = json.loads(proc.stdout)
        self.assertEqual(envelope["errors"][0]["code"], "invalid_agent")


if __name__ == "__main__":
    unittest.main()
