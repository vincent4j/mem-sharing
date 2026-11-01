#!/usr/bin/env python3
"""memSharing project CLI: strict parsing and exact-policy approval envelopes.

Exit codes: 0 completed, 1 check gaps, 2 failed/recovery, 3 migration gate,
5 approval required. Project rules use schema3 follow_ck/disabled policy;
CK user installation is an independent installer operation.
"""

from __future__ import annotations

import argparse
import importlib
import json
import os
import re
import sys

# Installed release trees are manifest-closed; CLI use must not add cache files.
sys.dont_write_bytecode = True
from datetime import datetime
from pathlib import Path

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

# CLI 全程零写入(D7):在首次导入 agm_core 前禁用字节码缓存,冷启动不得产生 __pycache__。
sys.dont_write_bytecode = True

from agm_core import paths as agm_paths
from agm_core import layout as agm_layout

SCHEMA_VERSION = 1
KNOWN_COMMANDS = ("enable-memory", "enable-memory-batch", "remove-memory", "check-memory")
WRITE_COMMANDS = ("enable-memory", "enable-memory-batch", "remove-memory")
INSTALL_NEXT_ACTION = "先阅读 INSTALL.md，运行 python3 -B <已核验源>/scripts/install.py 预览机器安装；确认后用 --approval-file 执行。"

STATUS_COMPLETED = "completed"
STATUS_GAPS = "gaps"
STATUS_APPROVAL_REQUIRED = "approval_required"
STATUS_MIGRATION_REQUIRED = "migration_required"
STATUS_FAILED = "failed"
STATUS_RECOVERY_REQUIRED = "recovery_required"

EXIT_OK = 0
EXIT_GAPS = 1
EXIT_FAILED = 2
EXIT_MIGRATION = 3
EXIT_APPROVAL = 5

_STATUS_EXIT = {
    STATUS_COMPLETED: EXIT_OK,
    STATUS_GAPS: EXIT_GAPS,
    STATUS_FAILED: EXIT_FAILED,
    STATUS_RECOVERY_REQUIRED: EXIT_FAILED,
    STATUS_MIGRATION_REQUIRED: EXIT_MIGRATION,
    STATUS_APPROVAL_REQUIRED: EXIT_APPROVAL,
}
# 依裁定 D-M2-05:迁移门禁错误在场 → 3;但执行/恢复失败(status=failed/recovery_required)
# 仍压过迁移 → 2,envelope 完整保留全部错误。
_MIGRATION_ERROR_CODES = frozenset(("migration_required",))


class CliError(ValueError):
    """参数/路径表/批准文件错误;code 序列化进 errors[].code。"""

    def __init__(self, code, message, *, path=None, recovery=None, command=None):
        super().__init__(message)
        self.code = code
        self.path = path
        self.recovery = recovery
        self.command = command


def error_item(code, message, *, path=None, recovery=None):
    return {"code": code, "path": path, "message": message, "recovery": recovery}


def make_envelope(
    command,
    status,
    *,
    projects=None,
    changes=None,
    warnings=None,
    errors=None,
    approval_required=False,
    next_action=None,
    runtime_layout=None,
):
    """构造输出合同要求的唯一 JSON envelope(architecture §4)。"""
    return {
        "schema_version": SCHEMA_VERSION,
        "runtime_layout": runtime_layout,
        "command": command,
        "status": status,
        "projects": list(projects or []),
        "changes": list(changes or []),
        "warnings": list(warnings or []),
        "errors": list(errors or []),
        "approval_required": bool(approval_required),
        "next_action": next_action,
    }


def exit_for(status, errors=()):
    """状态/错误 → 进程退出码;优先级 2 > 3 > 5 > 1 > 0;未知状态保守归 2。"""
    if status in (STATUS_FAILED, STATUS_RECOVERY_REQUIRED):
        return EXIT_FAILED
    codes = {item.get("code") for item in errors if isinstance(item, dict)}
    if status == STATUS_MIGRATION_REQUIRED or codes & _MIGRATION_ERROR_CODES:
        return EXIT_MIGRATION
    if status == STATUS_APPROVAL_REQUIRED:
        return EXIT_APPROVAL
    if status == STATUS_GAPS:
        return EXIT_GAPS
    return _STATUS_EXIT.get(status, EXIT_FAILED)


class _StrictParser(argparse.ArgumentParser):
    """argparse 报错不直接退出进程,抛 CliError 以便仍输出统一 JSON envelope。"""

    def error(self, message):
        raise CliError("invalid_arguments", message)


_SINGLE_USE_FLAGS = ("--project", "--directory", "--agent", "--memory", "--no-memory", "--all", "--approval-file", "--preview")


def _prescan_single_use(argv):
    """argparse 对重复单值参数会静默取后者;合同要求重复使用必须拒绝,先扫描原始 argv。"""
    counts = {}
    for token in argv:
        if not isinstance(token, str):
            continue
        for flag in _SINGLE_USE_FLAGS:
            if token == flag or token.startswith(flag + "="):
                counts[flag] = counts.get(flag, 0) + 1
    duplicated = sorted(flag for flag, count in counts.items() if count > 1)
    if duplicated:
        raise CliError("invalid_arguments", "参数只能使用一次: %s" % ", ".join(duplicated))


def build_parser():
    parser = _StrictParser(
        prog="agm",
        description="memSharing CLI(合同: docs/architecture.md)",
    )
    sub = parser.add_subparsers(dest="command", metavar="command", required=True)

    enable = sub.add_parser("enable-memory", help="经授权装配规则基座与可选记忆档")
    enable.add_argument("--project", metavar="GIT_ROOT", help="显式项目 Git 根;缺省从 cwd 定位")
    enable.add_argument(
        "--agent",
        nargs="+",
        metavar="AGENT",
        help="目标执行器,一次多个唯一值(codex/claude/workbuddy/dsh/zcode);缺省 codex/claude/workbuddy 三家,dsh/zcode 需显式指定",
    )
    memory_group = enable.add_mutually_exclusive_group()
    memory_group.add_argument(
        "--memory", dest="memory_choice", action="store_const", const="follow_ck", help="显式解除项目经历停用政策"
    )
    memory_group.add_argument(
        "--no-memory", dest="memory_choice", action="store_const", const="disabled", help="禁止自动项目经历记录与初始化，保留 CK 与数据"
    )
    enable_action = enable.add_mutually_exclusive_group()
    enable_action.add_argument(
        "--approval-file", metavar="JSON", help="非交互批准文件(裁定 D-M2-04;仅写命令)"
    )
    enable_action.add_argument("--preview", action="store_true", help="只读生成精确批准模板；不确认、不修补、不获取写锁")

    batch = sub.add_parser("enable-memory-batch", help="扫描 Git 主 checkout，集中批准后批量启用记忆")
    batch.add_argument("--directory", required=True, metavar="DIR", help="只读递归扫描的目录(含自身)")
    batch.add_argument("--agent", nargs="+", metavar="AGENT", help="透传单项目启用的执行器选择；缺省按安装事实")
    batch.add_argument("--approval-file", metavar="JSON", help="绑定完整批量计划的一次批准文件")

    remove = sub.add_parser("remove-memory", help="仅撤销本工具所有权对象")
    remove.add_argument("--project", metavar="GIT_ROOT", help="显式项目 Git 根;缺省从 cwd 定位")
    remove_action = remove.add_mutually_exclusive_group()
    remove_action.add_argument(
        "--approval-file", metavar="JSON", help="非交互批准文件(裁定 D-M2-04;仅写命令)"
    )
    remove_action.add_argument("--preview", action="store_true", help="只读生成精确批准模板；不确认、不获取写锁")

    check = sub.add_parser("check-memory", help="只读报告现场状态与缺口")
    check_group = check.add_mutually_exclusive_group()
    check_group.add_argument("--project", metavar="GIT_ROOT", help="显式项目 Git 根;缺省仅当前目标")
    check_group.add_argument("--all", action="store_true", help="巡检全部已登记项目")
    return parser


def _guess_command(argv):
    """从原始 argv 尽力识别子命令,供解析失败的 envelope 归属;启发式,不影响执行。"""
    previous = None
    for token in argv:
        if not isinstance(token, str):
            continue
        if token in KNOWN_COMMANDS and previous not in ("--project", "--directory", "--approval-file"):
            return token
        previous = token if token.startswith("--") else None
    return None


_APPROVAL_FIELDS = (
    "schema_version",
    "command",
    "main_checkout",
    "checkout",
    "git_common_dir",
    "agents",
    "memory_policy",
    "changes",
    "confirmed_at",
    "reference",
)
_ENABLE_APPROVAL_FIELDS = frozenset(("installation", "native_pending", "memory_transition", "legacy_bridge_transition", "rebuild", "rebuild_confirmation"))
_APPROVAL_OPERATIONS = frozenset(("create", "update", "remove"))
_HEX64_RE = re.compile(r"^[0-9a-f]{64}$")
_UTC_ISO_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?Z$")


def _reject_approval_duplicate_keys(pairs):
    seen = set()
    for key, _ in pairs:
        if key in seen:
            raise CliError("approval_file_invalid", "批准文件 JSON 存在重复键: %s" % key)
        seen.add(key)
    return dict(pairs)


def _approval_fail(message, path=None):
    raise CliError("approval_file_invalid", message, path=path)


def _check_abs_path(value, label, path):
    if not isinstance(value, str) or not value or not os.path.isabs(value):
        _approval_fail("%s 必须是非空绝对路径" % label, path)


def _check_fingerprint(value, label, path):
    if value is None:
        return
    if not isinstance(value, str) or not _HEX64_RE.match(value):
        _approval_fail("%s 必须是 64 位小写十六进制 sha256 或 null" % label, path)


def load_approval(path):
    """读取批准文件;重复 JSON 键、非法 JSON、不可读均为 approval_file_invalid。"""
    if not os.path.isfile(path):
        raise CliError("approval_file_invalid", "批准文件不存在: %s" % path, path=path)
    try:
        with open(path, "r", encoding="utf-8") as handle:
            data = json.load(handle, object_pairs_hook=_reject_approval_duplicate_keys)
    except CliError:
        raise
    except json.JSONDecodeError as exc:
        raise CliError("approval_file_invalid", "批准文件不是合法 JSON: %s" % exc, path=path)
    except (OSError, UnicodeDecodeError) as exc:
        raise CliError("approval_file_invalid", "批准文件不可读: %s" % exc, path=path)
    if not isinstance(data, dict):
        _approval_fail("批准文件顶层必须是对象", path)
    return data



def _validate_enable_extensions(data, requested, path):
    """Validate optional kernel plan facts; no field grants authority on its own."""
    def fields(value, names, label):
        if not isinstance(value, dict) or set(value) != set(names.split()):
            _approval_fail(label + " 字段不符", path)
    def digest(value, label):
        if not isinstance(value, str) or not _HEX64_RE.fullmatch(value):
            _approval_fail(label + " 必须是 sha256", path)
    def agent_list(value, label):
        if (not isinstance(value, list) or any(a not in agm_paths.AGENT_ORDER for a in value)
                or len(set(value)) != len(value)):
            _approval_fail(label + " 必须是无重复执行器数组", path)
    installation = data.get("installation")
    if "installation" in data:
        if not isinstance(installation, dict) or set(installation) != set(requested):
            _approval_fail("installation 必须逐项覆盖请求的执行器", path)
        for fact in installation.values():
            fields(fact, "status fingerprint", "installation 项")
            if fact["status"] not in ("installed", "absent", "unknown"):
                _approval_fail("installation status 非法", path)
            digest(fact["fingerprint"], "installation fingerprint")
        effective = [a for a in requested if installation[a]["status"] == "installed"]
        if data["agents"] != effective:
            _approval_fail("agents 与 installation 已验证安装范围不一致", path)
    if "native_pending" in data:
        pending = data["native_pending"]
        if pending not in ([], ["workbuddy"]) or any(a not in data["agents"] for a in pending):
            _approval_fail("native_pending 仅接受已选 WorkBuddy", path)
    if "memory_transition" in data:
        transition = data["memory_transition"]
        fields(transition, "before after scope affected_agents", "memory_transition")
        if (transition["before"] not in ("follow_ck", "disabled")
                or transition["after"] not in ("follow_ck", "disabled")
                or transition["after"] != data["memory_policy"]
                or transition["scope"] != "all registered project agents"):
            _approval_fail("memory_transition 政策范围不符", path)
        agent_list(transition["affected_agents"], "affected_agents")
    if "legacy_bridge_transition" in data:
        items = data["legacy_bridge_transition"]
        if not isinstance(items, list) or not items:
            _approval_fail("legacy bridge transitions must be a nonempty array", path)
        for item in items:
            fields(item, "path ownership before_hex fingerprint action", "legacy bridge transition")
            _check_abs_path(item["path"], "legacy bridge path", path)
            digest(item["fingerprint"], "legacy bridge fingerprint")
            if item["ownership"] not in ("created", "reused", "unknown"):
                _approval_fail("invalid legacy ownership", path)
            try:
                unit = bytes.fromhex(item["before_hex"])
            except (ValueError, TypeError):
                _approval_fail("invalid legacy bytes", path)
            import hashlib
            if not unit or unit.hex() != item["before_hex"] or hashlib.sha256(unit).hexdigest() != item["fingerprint"]:
                _approval_fail("legacy bytes fingerprint mismatch", path)
            expected_action = "retire created and rebuild" if item["ownership"] == "created" else "review exact bytes and replace"
            if item["action"] != expected_action:
                _approval_fail("invalid legacy action", path)
    if ("rebuild" in data) != ("rebuild_confirmation" in data):
        _approval_fail("rebuild 必须绑定独立 rebuild_confirmation", path)
    if "rebuild" in data:
        rebuild, confirmation = data["rebuild"], data["rebuild_confirmation"]
        fields(rebuild, "classification reason registry_sha256 registry_bytes project_count removed_projects removed_shared_objects scope", "rebuild")
        if rebuild["classification"] not in ("registry_project_corrupt", "registry_evidence_unavailable"):
            _approval_fail("rebuild classification 非法", path)
        digest(rebuild["registry_sha256"], "rebuild registry_sha256")
        for name in ("registry_bytes", "project_count"):
            if type(rebuild[name]) is not int or rebuild[name] < 0:
                _approval_fail("rebuild " + name + " 必须是非负整数", path)
        if (not isinstance(rebuild["reason"], str) or not rebuild["reason"]
                or rebuild["scope"] != "reset all project registrations and shared consumer indexes; preserve machine identity and all user files"
                or not isinstance(rebuild["removed_projects"], list)
                or len(rebuild["removed_projects"]) != rebuild["project_count"]):
            _approval_fail("rebuild 全局影响摘要非法", path)
        seen = set()
        for item in rebuild["removed_projects"]:
            fields(item, "main_checkout record_sha256", "removed_projects 项")
            _check_abs_path(item["main_checkout"], "removed_projects main_checkout", path)
            digest(item["record_sha256"], "removed_projects record_sha256")
            if item["main_checkout"] in seen:
                _approval_fail("removed_projects 重复", path)
            seen.add(item["main_checkout"])
        shared = rebuild["removed_shared_objects"]
        if not isinstance(shared, list) or any(not isinstance(v, str) or not v for v in shared) or len(set(shared)) != len(shared):
            _approval_fail("removed_shared_objects 必须是无重复字符串数组", path)
        fields(confirmation, "registry_sha256 confirmed_at reference", "rebuild_confirmation")
        digest(confirmation["registry_sha256"], "rebuild_confirmation registry_sha256")
        if confirmation["registry_sha256"] != rebuild["registry_sha256"]:
            _approval_fail("rebuild_confirmation 与计划旧账哈希不一致", path)
        # Reuse the base envelope's evidence validation, including calendar validity.
        evidence = dict(data)
        for name in _ENABLE_APPROVAL_FIELDS:
            evidence.pop(name, None)
        evidence.update(confirmed_at=confirmation["confirmed_at"], reference=confirmation["reference"])
        evidence["agents"] = list(requested)
        validate_approval(evidence, command="enable-memory", agents=requested, memory_choice=None, path=path)


def validate_approval(data, *, command, agents, memory_choice, path=None):
    """批准 envelope 的命令级结构校验(含内核版本化计划字段)。

    仅校验结构与本命令已知目标的匹配;与锁内现场(主键/指纹/库位置/源码身份)的一致性
    核对由内核在写锁内完成;CLI 校验 rebuild 独立确认与旧账哈希的绑定。
    """
    if command == "enable-memory-batch":
        from agm_core.batch_enable import validate_approval as validate_batch
        try:
            return validate_batch(data, agents=agents)
        except ValueError as exc:
            _approval_fail(str(exc), path)
    if command not in ("enable-memory", "remove-memory"):
        _approval_fail("该命令不接受批准", path)
    keys = set(data)
    expected = set(_APPROVAL_FIELDS)
    expected = expected | ({"registry_sha256"} if command == "remove-memory" else set())
    allowed = expected | (_ENABLE_APPROVAL_FIELDS if command == "enable-memory" else set())
    missing = sorted(expected - keys)
    unknown = sorted(keys - allowed)
    if missing:
        _approval_fail("批准文件缺少字段: %s" % ", ".join(missing), path)
    if unknown:
        _approval_fail("批准文件含未知字段: %s" % ", ".join(unknown), path)
    if type(data["schema_version"]) is not int or data["schema_version"] != 1:
        _approval_fail("批准文件 schema_version 必须是整数 1", path)
    if data["command"] != command:
        raise CliError(
            "approval_mismatch",
            "批准文件 command=%r 与实际命令 %r 不一致" % (data["command"], command),
            path=path,
        )
    for field in ("main_checkout", "checkout", "git_common_dir"):
        _check_abs_path(data[field], "批准文件 %s" % field, path)
    file_agents = data["agents"]
    revocation = data.get("memory_transition", {})
    empty_revocation = (isinstance(revocation, dict) and revocation.get("before") == "follow_ck"
                        and revocation.get("after") == "disabled" and "installation" in data)
    if not isinstance(file_agents, list) or (not file_agents and not empty_revocation):
        _approval_fail("批准文件 agents 必须是非空数组", path)
    try:
        canonical = agm_paths.resolve_agents(file_agents) if file_agents else []
    except agm_paths.PathsError as exc:
        raise CliError("approval_file_invalid", "批准文件 agents 非法: %s" % exc, path=path) from None
    if command != "remove-memory" and "installation" not in data and canonical != list(agents or []):
        raise CliError(
            "approval_mismatch",
            "批准范围(agents=%s)与命令目标(%s)不一致,须重新预览确认" % (canonical, list(agents or [])),
            path=path,
        )
    memory = data["memory_policy"]
    if memory not in ("follow_ck", "disabled"):
        _approval_fail("memory_policy only accepts follow_ck/disabled", path)
    if command == "remove-memory":
        _check_fingerprint(data["registry_sha256"], "registry_sha256", path)
        if data["registry_sha256"] is None: _approval_fail("registry_sha256 required", path)
    if command == "remove-memory" and memory != "disabled":
        _approval_fail("remove-memory must set disabled", path)
    if command == "enable-memory" and memory_choice is not None and memory != memory_choice:
        raise CliError("approval_mismatch", "Approved policy differs from explicit choice", path=path)
    changes = data["changes"]
    if not isinstance(changes, list):
        _approval_fail("批准文件 changes 必须是数组", path)
    for item in changes:
        if not isinstance(item, dict) or set(item) != {
            "path",
            "operation",
            "before_fingerprint",
            "after_fingerprint",
        }:
            _approval_fail(
                "changes 项字段必须恰好是 path、operation、before_fingerprint、after_fingerprint", path
            )
        _check_abs_path(item["path"], "changes 项 path", path)
        if item["operation"] not in _APPROVAL_OPERATIONS:
            _approval_fail("changes 项 operation 仅接受 create/update/remove", path)
        _check_fingerprint(item["before_fingerprint"], "changes 项 before_fingerprint", path)
        _check_fingerprint(item["after_fingerprint"], "changes 项 after_fingerprint", path)
    confirmed = data["confirmed_at"]
    if not isinstance(confirmed, str) or not _UTC_ISO_RE.match(confirmed):
        _approval_fail("confirmed_at 必须是 UTC ISO8601(YYYY-MM-DDTHH:MM:SS[.小数]Z)", path)
    else:
        for pattern in ("%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S.%fZ"):
            try:
                datetime.strptime(confirmed, pattern)
                break
            except ValueError:
                continue
        else:
            _approval_fail("confirmed_at 不是合法 UTC 时间: %s" % confirmed, path)
    if not isinstance(data["reference"], str) or not data["reference"]:
        _approval_fail("reference 必须是非空定位字符串(不保存对话正文)", path)
    if command == "enable-memory":
        _validate_enable_extensions(data, list(agents or []), path)
    return data


_COMMAND_MODULES = {
    "enable-memory": ("agm_core.enable", "run"),
    "enable-memory-batch": ("agm_core.batch_enable", "run"),
    "remove-memory": ("agm_core.remove", "run"),
    "check-memory": ("agm_core.check", "run"),
}


def _normalize_errors(errors):
    """命令模块 errors[] 规范化;缺 code 即整体拒绝(错误序列化必须含 code)。"""
    normalized = []
    for item in errors or []:
        if not isinstance(item, dict) or not isinstance(item.get("code"), str) or not item["code"]:
            return None
        normalized.append(
            error_item(
                item["code"],
                str(item.get("message", "")),
                path=item.get("path"),
                recovery=item.get("recovery"),
            )
        )
    return normalized


def _envelope_from_result(command, result):
    """把命令模块返回 dict 规范化为输出 envelope(字段合同固定,status 必填)。"""
    if not isinstance(result, dict) or result.get("status") not in _STATUS_EXIT:
        return make_envelope(
            command,
            STATUS_FAILED,
            errors=[
                error_item("command_result_invalid", "命令模块返回无法识别的结果(status 缺失或非法)")
            ],
        )
    errors = _normalize_errors(result.get("errors"))
    if errors is None:
        return make_envelope(
            command,
            STATUS_FAILED,
            errors=[error_item("command_result_invalid", "命令模块 errors[] 项缺少 code")],
        )
    next_action=result.get("next_action")
    if any(item.get("code") == "machine_not_installed" for item in errors):
        next_action=INSTALL_NEXT_ACTION
    return make_envelope(
        command,
        result["status"],
        projects=result.get("projects"),
        changes=result.get("changes"),
        warnings=result.get("warnings"),
        errors=errors,
        approval_required=result.get("approval_required", False),
        next_action=next_action,
        runtime_layout=result.get("runtime_layout"),
    )


def dispatch(command, request):
    """路由到命令模块;模块未交付时返回 kernel_unavailable(合同桩,见模块 docstring 清单)。"""
    module_name, entry_name = _COMMAND_MODULES[command]
    try:
        module = importlib.import_module(module_name)
    except ImportError:
        return make_envelope(
            command,
            STATUS_FAILED,
            warnings=[
                "命令体 %s.%s 尚未接线(分别由 M2-04/M2-05/M2-06 交付)" % (module_name, entry_name),
                "M2-02 内核模块(agm_core project/registry/entries/transaction)合并后随命令体一并接线",
            ],
            errors=[
                error_item(
                    "kernel_unavailable",
                    "命令体尚未实现: 未找到 %s;本次未执行任何写入" % module_name,
                    recovery="等待对应任务合并接线后重试;本次参数解析、路径表与批准结构校验已通过",
                )
            ],
            next_action="等待 %s 命令模块交付后重试" % command,
        )
    entry = getattr(module, entry_name, None)
    if not callable(entry):
        return make_envelope(
            command,
            STATUS_FAILED,
            errors=[
                error_item(
                    "kernel_unavailable",
                    "命令体 %s 缺少入口 %s;本次未执行任何写入" % (module_name, entry_name),
                    recovery="等待对应任务合并接线后重试",
                )
            ],
        )
    return _envelope_from_result(command, entry(request))


def build_request(
    command,
    namespace,
    *,
    agents,
    approval,
    table,
    platform_key,
    platform_config,
    table_path,
    interactive,
    home,
):
    """构造传给命令模块的 request(dict);接线合同见模块 docstring。

    allowed_user_paths 仅 enable-memory 提供(--agent 目标已知,经路径表展开);remove/check
    的目标由内核依登记与路径表现场推导,CLI 不放宽用户级路径校验(M2-02 合同)。
    """
    allowed = (
        agm_paths.allowed_user_paths(platform_config, agents, home=home)
        if command == "enable-memory"
        else []
    )
    return {
        "command": command,
        "project": getattr(namespace, "project", None),
        "directory": getattr(namespace, "directory", None),
        "agents": None if command in ("enable-memory", "enable-memory-batch") and getattr(namespace, "agent", None) is None else agents,
        "memory_choice": getattr(namespace, "memory_choice", None),
        "all": bool(getattr(namespace, "all", False)),
        "approval": approval,
        "interactive": False if getattr(namespace, "preview", False) else interactive,
        "preview": bool(getattr(namespace, "preview", False)),
        "platform": platform_key,
        "agents_table": table,
        "platform_config": platform_config,
        "agents_table_path": table_path,
        "home": home,
        "runtime_layout": agm_layout.resolve_layout(home),
        "allowed_user_paths": allowed,
    }


def _execute(argv, *, platform, interactive, table_path, home):
    argv = list(argv)
    try:
        _prescan_single_use(argv)
        namespace = build_parser().parse_args(argv)
    except CliError as exc:
        if exc.command is None:
            exc.command = _guess_command(argv)
        raise

    command = namespace.command
    try:
        agents = agm_paths.resolve_agents(namespace.agent) if command in ("enable-memory", "enable-memory-batch") else None
        table = agm_paths.load_agents_table(table_path)
        platform_key = agm_paths.current_platform(platform)
        platform_config = agm_paths.select_platform(table, platform_key)
        approval = None
        if getattr(namespace, "approval_file", None) is not None:
            approval = load_approval(namespace.approval_file)
            approval = validate_approval(
                approval,
                command=command,
                agents=agents,
                memory_choice=getattr(namespace, "memory_choice", None),
                path=namespace.approval_file,
            )
    except CliError as exc:
        if exc.command is None:
            exc.command = command
        raise
    except agm_paths.PathsError as exc:
        raise CliError(exc.code, str(exc), command=command) from None

    # 写命令批准门(裁定 D-M2-04 方案 A):remove 保守前置门保留(非交互且未绑定批准 → 5);
    # enable 的免批准判定(幂等补装)由内核在写锁内依 registry 现场裁决(M2-04 已实现),
    # 本外壳不前置截断,内核返回 approval_required 时同样映射为 5。TTY 只影响能否提问。
    if command == "remove-memory" and approval is None and not interactive and not getattr(namespace, "preview", False):
        return make_envelope(
            command,
            STATUS_APPROVAL_REQUIRED,
            approval_required=True,
            runtime_layout=agm_layout.resolve_layout(home).describe(),
            warnings=["非交互环境(非 TTY)无法提问;不从 stdin 猜测 yes,不因环境变量自动批准"],
            next_action=INSTALL_NEXT_ACTION if not os.path.lexists(agm_layout.resolve_layout(home).registry) else (
                "非交互写命令需 --approval-file <JSON> 绑定用户已确认的执行计划"
                "(裁定 D-M2-04),或在交互终端运行"
            ),
        )

    request = build_request(
        command,
        namespace,
        agents=agents,
        approval=approval,
        table=table,
        platform_key=platform_key,
        platform_config=platform_config,
        table_path=table_path or agm_paths.default_table_path(),
        interactive=interactive,
        home=home or str(Path.home()),
    )
    result = dispatch(command, request)
    if not os.path.lexists(agm_layout.resolve_layout(request['home']).registry):
        result['next_action'] = INSTALL_NEXT_ACTION
    return result


def _detect_interactive(stdin, stdout):
    try:
        return bool(stdin.isatty() and stdout.isatty())
    except Exception:
        return False


def main(
    argv=None,
    *,
    stdin=None,
    stdout=None,
    stderr=None,
    platform=None,
    interactive=None,
    table_path=None,
    home=None,
):
    """执行 CLI 并返回进程退出码;stdin/stdout/platform 等注入点供测试使用。

    stdout 恒输出单个 JSON envelope;stderr 输出人读诊断。帮助文本(-h)由 argparse
    直接输出,不属于执行结果。
    """
    in_stream = stdin if stdin is not None else sys.stdin
    out_stream = stdout if stdout is not None else sys.stdout
    err_stream = stderr if stderr is not None else sys.stderr
    if interactive is None:
        interactive = _detect_interactive(in_stream, out_stream)
    try:
        envelope = _execute(
            argv if argv is not None else sys.argv[1:],
            platform=platform,
            interactive=interactive,
            table_path=table_path,
            home=home,
        )
    except CliError as exc:
        recovery = exc.recovery
        if recovery is None and exc.code == "invalid_arguments":
            recovery = "核对参数后重试;核对当前命令 --help 与 docs/operations.md"
        envelope = make_envelope(
            exc.command,
            STATUS_FAILED,
            errors=[error_item(exc.code, str(exc), path=exc.path, recovery=recovery)],
        )
    except Exception as exc:  # 未预期内部失败保守报告,不猜测成功
        envelope = make_envelope(
            None,
            STATUS_FAILED,
            errors=[
                error_item(
                    "internal_error",
                    "未预期的内部错误: %s" % exc,
                    recovery="请把上述信息交给维护者;本次未执行任何写入",
                )
            ],
        )
    print(json.dumps(envelope, ensure_ascii=False, indent=2), file=out_stream)
    if envelope["errors"]:
        first = envelope["errors"][0]
        print("[agm] %s: %s" % (first.get("code"), first.get("message")), file=err_stream)
    elif envelope["approval_required"]:
        print("[agm] 待授权: %s" % (envelope.get("next_action") or ""), file=err_stream)
    return exit_for(envelope["status"], envelope["errors"])


if __name__ == "__main__":
    sys.exit(main())
