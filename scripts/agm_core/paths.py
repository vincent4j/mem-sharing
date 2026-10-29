"""agents.json 路径表合同实现(M2-03)。

加载并严格校验 scripts/agents.json,展开 {home}/{project} 占位符,选择平台与执行器目标,
并把目标映射为用户级入口绝对路径(allowed_user_paths,交 M2-02 内核做 user 对象校验)。

安装信号(installation_signals)仅作 hint:目录存在只表示安装线索,可能是残留目录,
不证明已安装;目录缺失也不能证明未安装;任何信号都不授权写入、不改变目标选择。
合同:docs/plan/architecture.md v2 §3;错误码供 CLI 的 errors.code 序列化(§4)。
"""

from __future__ import annotations

import json
import os
import re
import sys

AGENT_ORDER = ("codex", "claude", "workbuddy")
AGENTS = frozenset(AGENT_ORDER)

AGENT_FIELDS = (
    "user_entry",
    "project_rule_entry",
    "project_bridge_entry",
    "project_skill_roots",
    "installation_signals",
    "rule_mode",
    "bridge_owner",
    "runtime_status",
)
RULE_MODES = frozenset(("native", "import_agents", "user_convention"))
BRIDGE_OWNERS = frozenset(("context-keeper", "agent-group-memory"))
RUNTIME_STATUSES = frozenset(("upstream_verified_local_pending", "pending"))
SIGNAL_KINDS = frozenset(("directory_exists",))
SIGNAL_STRENGTHS = frozenset(("hint",))
SIGNAL_FIELDS = ("kind", "path", "strength")

_PLACEHOLDER_RE = re.compile(r"\{([A-Za-z_][A-Za-z0-9_]*)\}")
_ALLOWED_PLACEHOLDERS = frozenset(("home", "project"))

# sys.platform → 路径表平台键。仅映射已知系统;未识别值原样返回,由 select_platform 拒绝,
# 不硬套 darwin。
_PLATFORM_ALIASES = {"darwin": "darwin", "win32": "windows", "cygwin": "windows"}


class PathsError(ValueError):
    """路径表/占位/目标错误;code 供 CLI 的 errors.code 序列化使用。"""

    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


def current_platform(raw=None):
    """把 sys.platform(或显式传入的 raw)映射为路径表平台键。"""
    value = sys.platform if raw is None else raw
    if isinstance(value, str) and value.startswith("linux"):
        return "linux"
    return _PLATFORM_ALIASES.get(value, value)


def default_table_path():
    # agents.json 在安装源 scripts/ 目录(agm_core 的上一级),不在包内。
    scripts_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(scripts_dir, "agents.json")


def _reject_duplicate_keys(pairs):
    seen = set()
    for key, _ in pairs:
        if key in seen:
            raise PathsError("agents_table_invalid", "路径表 JSON 存在重复键: %s" % key)
        seen.add(key)
    return dict(pairs)


def _fail(code, message):
    raise PathsError(code, message)


def _check_string(value, label):
    if not isinstance(value, str) or not value:
        _fail("agents_table_invalid", "%s 必须是非空字符串" % label)


def _check_placeholders(value, label):
    for name in _PLACEHOLDER_RE.findall(value):
        if name not in _ALLOWED_PLACEHOLDERS:
            _fail(
                "unknown_placeholder",
                "%s 使用未知占位符 {%s}(仅允许 {home}/{project})" % (label, name),
            )
    residue = _PLACEHOLDER_RE.sub("", value)
    if "{" in residue or "}" in residue:
        _fail("unknown_placeholder", "%s 含无法识别的占位语法: %s" % (label, value))


def _check_string_list(value, label):
    if not isinstance(value, list) or not value:
        _fail("agents_table_invalid", "%s 必须是非空数组" % label)
    seen = set()
    for item in value:
        _check_string(item, "%s 项" % label)
        if item in seen:
            _fail("agents_table_invalid", "%s 存在重复项: %s" % (label, item))
        seen.add(item)


def _validate_agent(platform_name, agent, entry):
    label = "platforms.%s.%s" % (platform_name, agent)
    if not isinstance(entry, dict):
        _fail("agents_table_invalid", "%s 必须是对象" % label)
    keys = set(entry)
    expected = set(AGENT_FIELDS)
    missing = sorted(expected - keys)
    unknown = sorted(keys - expected)
    if missing:
        _fail("agents_table_invalid", "%s 缺少字段: %s" % (label, ", ".join(missing)))
    if unknown:
        _fail("agents_table_invalid", "%s 含未知字段: %s" % (label, ", ".join(unknown)))
    for field in ("user_entry", "project_rule_entry", "project_bridge_entry"):
        _check_string(entry[field], "%s.%s" % (label, field))
        _check_placeholders(entry[field], "%s.%s" % (label, field))
    _check_string_list(entry["project_skill_roots"], "%s.project_skill_roots" % label)
    for root in entry["project_skill_roots"]:
        _check_placeholders(root, "%s.project_skill_roots 项" % label)
    signals = entry["installation_signals"]
    if not isinstance(signals, list) or not signals:
        _fail("agents_table_invalid", "%s.installation_signals 必须是非空数组" % label)
    seen_paths = set()
    for signal in signals:
        if not isinstance(signal, dict) or set(signal) != set(SIGNAL_FIELDS):
            _fail(
                "agents_table_invalid",
                "%s.installation_signals 项字段必须恰好是 %s" % (label, ", ".join(SIGNAL_FIELDS)),
            )
        if signal["kind"] not in SIGNAL_KINDS:
            _fail("agents_table_invalid", "%s 安装信号 kind 仅接受 directory_exists" % label)
        if signal["strength"] not in SIGNAL_STRENGTHS:
            _fail("agents_table_invalid", "%s 安装信号 strength 仅接受 hint" % label)
        _check_string(signal["path"], "%s 安装信号 path" % label)
        _check_placeholders(signal["path"], "%s 安装信号 path" % label)
        if signal["path"] in seen_paths:
            _fail("agents_table_invalid", "%s.installation_signals 存在重复项" % label)
        seen_paths.add(signal["path"])
    if entry["rule_mode"] not in RULE_MODES:
        _fail("agents_table_invalid", "%s.rule_mode 枚举非法" % label)
    if entry["bridge_owner"] not in BRIDGE_OWNERS:
        _fail("agents_table_invalid", "%s.bridge_owner 枚举非法" % label)
    if entry["runtime_status"] not in RUNTIME_STATUSES:
        _fail(
            "agents_table_invalid",
            "%s.runtime_status 枚举非法(静态表不接受 passed)" % label,
        )


def _validate_table(data):
    if not isinstance(data, dict):
        _fail("agents_table_invalid", "路径表顶层必须是对象")
    if set(data) != {"schema_version", "platforms"}:
        _fail("agents_table_invalid", "路径表顶层字段必须恰好是 schema_version、platforms")
    if type(data["schema_version"]) is not int or data["schema_version"] != 1:
        _fail("agents_table_invalid", "schema_version 必须是整数 1")
    platforms = data["platforms"]
    if not isinstance(platforms, dict) or not platforms:
        _fail("agents_table_invalid", "platforms 必须是至少一个平台的对象")
    for name, platform in platforms.items():
        _check_string(name, "平台名")
        if not isinstance(platform, dict):
            _fail("agents_table_invalid", "平台 %s 必须是对象" % name)
        missing = [agent for agent in AGENT_ORDER if agent not in platform]
        if missing:
            _fail(
                "agents_table_invalid",
                "平台 %s 缺少执行器: %s(不完整平台不能冒充已支持)" % (name, ", ".join(missing)),
            )
        unknown = [agent for agent in platform if agent not in AGENTS]
        if unknown:
            _fail(
                "agents_table_invalid",
                "平台 %s 含未知执行器: %s(仅 codex/claude/workbuddy)" % (name, ", ".join(unknown)),
            )
        for agent, entry in platform.items():
            _validate_agent(name, agent, entry)


def load_agents_table(path=None):
    """读取并严格校验 agents.json;失败抛 PathsError(code 区分缺失/非法)。"""
    resolved = default_table_path() if path is None else path
    if not os.path.isfile(resolved):
        raise PathsError("agents_table_missing", "路径表不存在: %s" % resolved)
    try:
        with open(resolved, "r", encoding="utf-8") as handle:
            data = json.load(handle, object_pairs_hook=_reject_duplicate_keys)
    except PathsError:
        raise
    except json.JSONDecodeError as exc:
        raise PathsError("agents_table_invalid", "路径表不是合法 JSON: %s" % exc)
    except (OSError, UnicodeDecodeError) as exc:
        raise PathsError("agents_table_invalid", "路径表不可读: %s" % exc)
    _validate_table(data)
    return data


def select_platform(table, platform):
    """取出平台配置;未知平台拒绝,不硬套其他 OS(如 darwin)。"""
    platforms = table.get("platforms") if isinstance(table, dict) else None
    if not isinstance(platforms, dict) or platform not in platforms:
        raise PathsError("unknown_platform", "路径表未定义平台 %s;未知 OS 一律拒绝" % platform)
    return platforms[platform]


def resolve_agents(requested=None):
    """执行器目标选择:None → 缺省三家;非法名/重复值拒绝;输出按 AGENT_ORDER 排序。

    目标只由显式 --agent 与缺省规则决定;安装目录信号(hint)不参与本函数,
    残留目录不得缩减或扩大目标(裁定:--agent 缺省固定三家)。
    """
    if requested is None:
        return list(AGENT_ORDER)
    if isinstance(requested, str) or not isinstance(requested, (list, tuple)):
        raise PathsError("invalid_agent", "--agent 需要执行器列表(仅 codex/claude/workbuddy)")
    seen = set()
    for name in requested:
        if name not in AGENTS:
            raise PathsError("invalid_agent", "未知执行器: %r(仅 codex/claude/workbuddy)" % (name,))
        if name in seen:
            raise PathsError("invalid_agent", "重复执行器: %s(--agent 值必须唯一)" % name)
        seen.add(name)
    return [agent for agent in AGENT_ORDER if agent in seen]


def expand_path(template, *, home, project=None):
    """展开 {home}/{project} 占位符;展开结果必须是绝对路径。

    home/project 仅在模板实际引用时要求为非空绝对路径字符串;不 resolve 符号链接、
    不做规范化,保留落点原样(registry 记录落点,链接目标另记)。
    """
    values = {"home": home, "project": project}

    def _substitute(match):
        name = match.group(1)
        if name not in values:
            raise PathsError("unknown_placeholder", "未知占位符 {%s}(仅允许 {home}/{project})" % name)
        value = values[name]
        if not isinstance(value, str) or not os.path.isabs(value):
            raise PathsError("path_invalid", "占位符 {%s} 的值必须是绝对路径: %r" % (name, value))
        return value

    expanded = _PLACEHOLDER_RE.sub(_substitute, template)
    if "{" in expanded or "}" in expanded:
        raise PathsError("unknown_placeholder", "路径含未展开占位符: %s" % expanded)
    if not os.path.isabs(expanded):
        raise PathsError("path_invalid", "展开后不是绝对路径: %s" % expanded)
    return expanded


def installation_hints(platform_config, agents=None, *, home, project=None):
    """只读收集目录安装信号;strength 恒为 hint。

    目录存在只表示安装线索(可能为残留),目录缺失不能证明未安装;
    本函数结果不得用于改变目标选择或授权任何写入。
    """
    hints = []
    for agent in resolve_agents(agents):
        entry = platform_config[agent]
        for signal in entry["installation_signals"]:
            path = expand_path(signal["path"], home=home, project=project)
            hints.append(
                {
                    "agent": agent,
                    "kind": signal["kind"],
                    "path": path,
                    "strength": "hint",
                    "exists": os.path.isdir(path),
                }
            )
    return hints


def allowed_user_paths(platform_config, agents, *, home):
    """把目标执行器映射为用户级入口绝对路径(唯一、按 AGENT_ORDER 排序)。

    M2-02 内核合同:凡涉及 user 对象的 registry load/validate/serialize/commit 必须传该
    列表,不在表内的用户级路径一律拒绝;CLI 层不得自行放宽。
    """
    collected = []
    for agent in resolve_agents(agents):
        expanded = expand_path(platform_config[agent]["user_entry"], home=home)
        if expanded not in collected:
            collected.append(expanded)
    return collected
