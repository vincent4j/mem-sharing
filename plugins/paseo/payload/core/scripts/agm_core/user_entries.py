"""M4-05: machine-level user entry planning and approved assembly.

One planner serves both first install and later agent accession (决策单 §7.2):
only executors detected as installed get user entries; absent/unknown agents
are reported and never written; an explicitly requested agent that is not
installed stops the whole request before any write.

Templates reuse the existing M2/M3 semantics instead of a second dialect:
- 公共分层(2026-10-31 裁定):公共 MEMORY 只存读取契约、预算、公共治理与按需操作
  指南指针;六项菜单、绝对命令与 L0/L1/L2 维护规则由主题《使用约定》承载;
- 各 Agent 用户入口只含公共索引指针与自身专属规则,不复制公共治理或菜单;
- WorkBuddy 用户约定: enable.py 的既有 user_convention 文本与 BASE_MARKER(测试锁定
  两处文本一致),机器级块=指针+用户约定+WorkBuddy 专属 fallback;
- Codex 用户级公共源块(native): 同一 BASE_MARKER 机制,“开工先读公共记忆”指针块
  (DESIGN §4.8)指向本机公共源索引 R/memories/MEMORY.md,并携带 Codex 专属 fallback;
- Claude @import(import_agents): 复用 enable.py 的引用行语义,引用同一公共源索引,
  并以独立 CLAUDE_FALLBACK_MARKER 块携带 Claude 自身 fallback——Claude 不只依赖
  公共索引,公共侧移除 Claude 条款后仍保有本机兜底规则。

Managed-block semantics for registered machine units: on-disk bytes differing
from the registered fingerprint is drift and stops the whole order (no template
"repair" over registered content); a vanished block is recreated only when the
registered content is the template itself; unregistered existing blocks are
registered byte-preserving (reused) without rewriting only when they satisfy
the current WorkBuddy template. Fingerprint-intact machine WorkBuddy blocks
may be updated by an exact approved plan; shared user-scope blocks are never
rewritten by this machine operation.

Planning is pure read-only (no mkdir, no locks, no detection side effects).
Execution requires an approval envelope matching the exact plan (same semantics
as enable-memory) and re-verifies the scene under the machine writer lock:
detection re-runs and the plan is rebuilt inside the transaction before commit;
any difference stops the write. The registry commits last.
"""

from __future__ import annotations

import copy
import json
import shlex
import os
import sys
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime, timezone
from pathlib import Path

from . import detect as detect_module
from . import layout as layout_module
from . import paths as agm_paths
from . import registry as registry_module
from . import user_entry_layout
from .enable import BASE_MARKER
from .entries import EntryConflict, block_fingerprint, sha256, managed_span, render_block
from .transaction import (Change, Snapshot, Transaction, TransactionError,
                          read_snapshot, write_lock)

# Frozen pre-natural-language-uninstall templates from the integrated candidate.
# Exact UTF-8 bytes; never regenerate these by calling the current renderers.
PRE_UNINSTALL_ROUTE_TEMPLATES = {'pre_route_contract': '读取契约：L0 恒读本索引 → 需要该主题时读其 L1 概要段 → 仍不足才读 L2 全文；相对链接以本文件所在目录解析，指向的内容缺失时停止相关操作。\n预算：L0 一主题一行：主题名 + 一句话当前结论 + 链接；索引 ≤200 行 / 25KB；增加主题文件，不加长索引；摘要在记忆整理时手写，不自动生成。\n用户规则治理：公共内容只写公共指定文件（R/memories），Agent 独有内容保留于各自用户文件，永不并入公共或自动删除。进入 Git 主 checkout 时，未登记项目默认启用项目规则：创建缺失的 AGENTS.md 骨架并追加项目经历短协议，已有全文保留。默认启用不创建 Context Keeper 记录库、不调用 Context Keeper 安装或初始化；首次 /context-keeper 进入 Context Keeper 流程，首次保存按其流程确认位置。项目经历由 Context Keeper 独立管理，本工具不设经历开关，不撤销、不禁用也不否决 Context Keeper。历史停用登记（disabled）项目默认流程跳过、不重建，也不宣称入口已移除；该状态不代表 Context Keeper 停用，重新接入需用户明确的重新接入计划。各 Agent 只维护自身专属项目入口（Claude 的 CLAUDE.md、WorkBuddy 的原生 memory 指针），由各自实际使用时补齐，其他执行器不得预建；AGENTS.md 是共享项目规则基座，不依赖 Codex，无 Codex 的机器同样成立，其默认建立遵本治理条款；非 Git 目录和 linked worktree 不触发。\n按需操作指南：/mem-sharing 菜单、绝对命令与公共记忆维护规则由主题《使用约定》承载（[使用约定](topics/使用约定.md)）；仅在用户明确 /mem-sharing、提出同义自然语言操作或默认项目接入前读取；该指南不回指其他菜单。\n', 'pre_route_topic': '# 使用约定\n\n## L1 概要\n\n当前有效结论：公共记忆采用索引与主题文件，摘要由 Agent 手写，不自动生成。\n本主题即操作指南：/mem-sharing 菜单、绝对命令与公共记忆 L0/L1/L2 维护规则都在本文件正文，不回指其他菜单。\n待办：有新事实且获准记录时，更新对应主题结论与索引行。\n\n## L2 正文\n\n### /mem-sharing 菜单\n\n/mem-sharing 菜单:\n添加新的 Agent：接入已安装的执行器 → python3 __CODE__/scripts/install.py --agent <执行器名>\n批量接入项目规则：扫描给定目录，汇总预览后一次批准 → python3 __CODE__/scripts/agm.py enable-memory-batch --directory <目录绝对路径>\n整理用户记忆：公共与独有分开，逐条计划后一次批准 → 治理流程见 __CODE__/SKILL.md\n健康检查：只读检查已登记入口 → python3 __CODE__/scripts/agm.py check-memory --project <项目绝对路径>\n接入项目规则：为当前项目装配规则基座与桥接 → python3 __CODE__/scripts/agm.py enable-memory --project <项目绝对路径>；新 Git 主 checkout 默认启用，历史停用登记项目跳过、不自动重建\n整机卸载：外置备份并归还公共记忆后卸载本产品 → python3 __CODE__/scripts/agm.py uninstall-machine --backup-dir <外置备份绝对路径>（默认只读预览，批准后执行）\n\n### 公共记忆维护（L0/L1/L2）\n\nL0 索引一主题一行：主题名 + 一句话当前结论 + 链接，≤200 行 / 25KB；增加主题文件，不加长索引。\nL1 位于主题文件开头，简列当前有效结论与待办；L2 为全文及 references/ 手册，仅在概要不足时读取。\n摘要在记忆整理时手写，不自动生成。本指南内相对链接以本文件所在目录（topics/）解析；受管产品命令与 Skill 路径使用安装代码的绝对路径。\n\n### 项目接入约定\n\n规则驱动的默认接入由当前实际执行者发起：python3 __CODE__/scripts/agm.py enable-memory --project <项目绝对路径> --agent <当前执行器>；执行前先检查项目政策，历史停用登记（disabled）项目跳过、不由本路径恢复（历史停用登记不代表 Context Keeper 停用，也不宣称入口已移除；migrate-policy 仅清理产品自有的停用控制，不恢复接入；重新接入需用户明确的重新接入计划）；各 Agent 专属项目入口按当前执行器自身用户文件中的规则维护，公共指南不承载执行器专属细节。\n当前会话不得无参数顺带改动其他执行器的入口。用户显式授权的全体接入或批量启用沿用现有命令语义，本约定不改变任何命令默认。\n'}

COMMAND = "assemble-user-entries"
_INSTALLER_SOURCE = ContextVar("agm_installer_verified_source", default=None)
_PREVIEW_STATE = ContextVar("agm_user_entry_preview_state", default=None)


@contextmanager
def _preview_state(runtime, ledger, snapshots):
    """Installer-only in-memory post-migration view; never a request field.

    The migration planner has already validated this ledger, including its
    pending manifest. No writer may run while this view is active.
    """
    token = _PREVIEW_STATE.set((str(runtime.registry), copy.deepcopy(ledger), dict(snapshots)))
    try:
        yield
    finally:
        _PREVIEW_STATE.reset(token)


def _entry_snapshot(path):
    state = _PREVIEW_STATE.get()
    if state is not None and Path(path) in state[2]:
        return state[2][Path(path)]
    return read_snapshot(path)


@contextmanager
def _installer_source(code, fingerprint, *, preview):
    """Internal installer capability, never deserialized from an approval/CLI."""
    token = _INSTALLER_SOURCE.set((str(code), fingerprint, preview))
    try:
        yield
    finally:
        _INSTALLER_SOURCE.reset(token)
# enable.py 的既有 WorkBuddy 用户约定文本(读它复用,不另造第二份);测试锁定一致。
WORKBUDDY_CONVENTION_TEXT = "项目规则读取当前项目根 AGENTS.md。保留已有公共源与用户约定。"

# v1.11/v1.12/§16(2026-10-30 用户裁定)用户规则治理条款:公共治理留在公共源索引,
# 各 Agent 入口不复制。术语用“启用/停用”(用户裁定),命令名 enable-memory 等保持不变;
# 用户可见文案写 Context Keeper 完整名称,不改 API 标识或历史记录。
# 2026-11-01 经历开关退役:memSharing 只管公共记忆共享与项目规则接入;项目经历由
# Context Keeper 独立管理。disabled 降级为历史接入tombstone(默认跳过不重建、不否决
# CK);常量名/签名保持不变,agm_core.policy_migration 以冻结旧模板做精确旧→新迁移。
GOVERNANCE_RULES_TEXT = (
    "用户规则治理：公共内容只写公共指定文件（R/memories），Agent 独有内容保留于各自用户文件，永不并入公共或自动删除。"
    "进入 Git 主 checkout 时，未登记项目默认启用项目规则：创建缺失的 AGENTS.md 骨架并追加项目经历短协议，已有全文保留。"
    "默认启用不创建 Context Keeper 记录库、不调用 Context Keeper 安装或初始化；首次 /context-keeper 进入 Context Keeper 流程，首次保存按其流程确认位置。"
    "项目经历由 Context Keeper 独立管理，本工具不设经历开关，不撤销、不禁用也不否决 Context Keeper。"
    "历史停用登记（disabled）项目默认流程跳过、不重建，也不宣称入口已移除；该状态不代表 Context Keeper 停用，重新接入需用户明确的重新接入计划。"
    "各 Agent 只维护自身专属项目入口（Claude 的 CLAUDE.md、WorkBuddy 的原生 memory 指针），由各自实际使用时补齐，其他执行器不得预建；"
    "AGENTS.md 是共享项目规则基座，不依赖 Codex，无 Codex 的机器同样成立，其默认建立遵本治理条款；非 Git 目录和 linked worktree 不触发。"
)
CLAUDE_FALLBACK_TEXT = (
    "首次使用已接入项目时，先读取 mem-sharing Skill，再按其流程补齐项目 CLAUDE.md 对 AGENTS.md 的引用。"
)
WORKBUDDY_FALLBACK_TEXT = "仅 WorkBuddy 在本项目实际使用产生原生 .workbuddy/memory 目录，且项目已启用（历史停用登记项目跳过）时，补顶部 AGENTS.md 指针；保留已有正文字节，不预建原生目录。"
CODEX_FALLBACK_TEXT = ""
# 桌面双端(2026-10-31 冻结合同):dsh=DeepSeek Harness、zcode=ZCode 均原生读取
# 项目根 AGENTS.md(rule_mode=native),用户入口分别是 ~/.dsh/AGENTS.md 与
# ~/.zcode/AGENTS.md。兜底文本各写自身执行器称谓,不复用 CODEX_FALLBACK_TEXT,
# 迁移/连接校验按块内语义精确区分执行器。
DSH_FALLBACK_TEXT = ""
ZCODE_FALLBACK_TEXT = ""
# OpenCode v2(2026-11-01 接入):v2 只识别 AGENTS.md(不再回退 CLAUDE.md),默认
# 配置根 ~/.config/opencode。规则加载受 XDG_CONFIG_HOME/OPENCODE_CONFIG_DIR/
# OPENCODE_CONFIG 影响的完整语义未获源码证实,第一版 default-root-only:配置根
# 被重定向或覆盖时不接入(见 opencode_config_redirected)。
OPENCODE_FALLBACK_TEXT = ""

NATIVE_FALLBACK_TEXTS = {"codex": CODEX_FALLBACK_TEXT, "dsh": DSH_FALLBACK_TEXT,
                         "zcode": ZCODE_FALLBACK_TEXT, "opencode": OPENCODE_FALLBACK_TEXT}

# Claude 自身 fallback 的独立受管块标记:与公共指针 import 并存于 CLAUDE.md,
# 迁移/连接校验按此标记精确识别,不与 BASE_MARKER 公共源块混用。
CLAUDE_FALLBACK_MARKER = {"start": "<!-- mem-sharing:claude-fallback:start -->",
                          "end": "<!-- mem-sharing:claude-fallback:end -->"}


def agent_group_menu_text(code):
    """菜单文本;命令基路径为受管产品代码 C(layout.code),逐项映射既有 CLI。

    2026-11-01 退役:remove-memory/--memory/--no-memory 不再出现;停用记忆项由
    整机卸载项(uninstall-machine,默认只读预览)接替机器级退出路径。
    """
    cli = "python3 %s/scripts/agm.py" % code
    installer = "python3 %s/scripts/install.py" % code
    skill = "%s/SKILL.md" % code
    return (
        "/mem-sharing 菜单:\n"
        "添加新的 Agent：接入已安装的执行器 → %s --agent <执行器名>\n"
        "批量接入项目规则：扫描给定目录，汇总预览后一次批准 → %s enable-memory-batch --directory <目录绝对路径>\n"
        "整理用户记忆：公共与独有分开，逐条计划后一次批准 → 治理流程见 %s\n"
        "健康检查：只读检查已登记入口 → %s check-memory --project <项目绝对路径>\n"
        "接入项目规则：为当前项目装配规则基座与桥接 → %s enable-memory --project <项目绝对路径>；新 Git 主 checkout 默认启用，历史停用登记项目跳过、不自动重建\n"
        "整机卸载：外置备份并归还公共记忆后卸载本产品 → %s uninstall-machine --backup-dir <外置备份绝对路径>（默认只读预览，批准后执行）\n"
        % (installer, cli, skill, cli, cli, "python3 -B " + shlex.quote(str(Path(code)/"scripts/agm.py")))
    )


def public_memory_contract_text(code=None):
    """Standing reading, ownership and accession instructions; operations in Skill."""
    skill = str(Path(code) / 'SKILL.md') if code else '~/.local/share/mem-sharing/SKILL.md'
    return (
        "开始任务前读取并遵守本目录的 user-rules.md（存在时）；其他主题按需读取。相关文件无法读取时，说明并停止依赖该内容的操作。\n\n"
        "## 保存记忆\n\n"
        "保存用户记忆时，适用于所有 Agent 的规则、偏好和长期事实写入本目录的对应文件，不在各 Agent 的用户记忆中重复保存。仅适用于某个 Agent 的内容保留在它自己的用户记忆中。项目规则和项目经历留在对应项目。\n"
        "新增主题文件时，在本索引添加链接。归属不明确时先确认；不得自动将专属内容移入公共记忆或删除。\n\n"
        "## 自动项目接入\n\n"
        "首次进入未登记的 Git 主工作目录时，按 mem-sharing Skill 自动接入项目，创建缺失的 AGENTS.md 并追加项目经历协议，保留已有内容。已停用项目、非 Git 目录及 linked worktree 跳过。\n"
        "项目已接入后，当前 Agent 首次实际使用时，只补齐自身缺失的专属项目入口，不替其他 Agent 预建。\n"
        "不自动安装或初始化 Context Keeper；项目经历按其自身规则管理。\n\n"
        "## 操作入口\n\n"
        "自动接入项目，或用户通过 /mem-sharing、自然语言要求安装、接入、整理、检查或卸载 mem-sharing 时，先读取 %s。无法读取时说明并停止相关操作。\n" % skill
    )


def natural_language_uninstall_text(code):
    """Single generated natural-language route; loaded on demand via public L0."""
    code = Path(code)
    cli = "python3 -B " + shlex.quote(str(code / "scripts/agm.py"))
    return (
        "### 自然语言卸载 memSharing\n\n"
        "用户明确说“卸载 memSharing”“卸载 mem-sharing”或“不想用这个共享记忆工具了，帮我卸载”等本产品退出意图，直接进入以下只读预览，不重复展示菜单；无须 /mem-sharing，也无须位于源码目录。"
        "“卸载这个项目”“停用项目记忆”等目标含糊时，仅澄清是否指 memSharing；不得猜测当前 cwd，不得删除项目。自然语言请求不批准尚未展示的精确删除计划。\n\n"
        "先核验本机台账与安装代码目录 C 的来源/身份，读取已核验的安装操作说明 [%s](<%s>) 及其完整卸载合同 [%s](<%s>)；不是凭路径存在就信任代码。"
        "安装代码缺失或已卸载时，只报告状态或使用已核验的外置恢复入口，不自动重装，也不执行未知来源脚本。\n\n"
        "根据台账及已核验安装来源确定机器实际安装形态；不能因从 Codex、Claude 或其它 Agent 发起就省略 Paseo 宿主义务。"
        "Paseo 形态优先沿现有插件 RPC 预览；若经 CLI 发起，沿完整合同携带 --host-obligation paseo、真实 --host-plugin-id、--host-plugin-source 及已核验 --host-plugin-record-json（编译期清单指纹可用时一并绑定），不得猜安装别名或来源。"
        "宿主来源/目标不明时先补齐证据，不能默认 standalone、伪造 absent 或扫描全 HOME；明确独立 CLI 范围才使用 standalone_declared，不能据此声称所有宿主均无残留。\n\n"
        "提议一个全新外置备份绝对路径（在待删产品目录之外）；预览前不 mkdir、不安装、不改真实 HOME。"
        "使用已核验 C 的绝对命令（若有宿主义务须附以上真实参数）：\n\n"
        "```sh\n%s uninstall-machine --backup-dir <全新外置备份绝对路径> --json\n```\n\n"
        "先展示完整归还、保全、删除目标、宿主义务和独立恢复材料的精确计划；用户批准该计划后才以同一参数加 --approval-file <精确批准文件> 执行。"
        "未知来源、漂移或阻断先停止；不要替用户批准。归还当前完整公共记忆而非回滚安装前。"
        "结果分列 machine_assets、host_plugin、overall；机器清理成功但插件仍在时 overall=partial。"
        "Paseo 后续由外置入口按 bind→官方 remove→同一 daemon 的 status/serverId 与 full-list 缺席核验→CK 尾步执行；查询错误、disabled、换 daemon 均不解锁。"
        "只有声明范围全部成功后才单独征询是否卸载 Context Keeper，默认保留；另行预览、另行精确批准，不能复用主卸载批准，CK 失败不改写主产品结果。\n"
        % (str(code/"SKILL.md"), str(code/"SKILL.md"),
           str(code/"docs/uninstall-design.md"), str(code/"docs/uninstall-design.md"), cli)
    )


def usage_convention_topic_text(code):
    """On-demand operations route; preserve project and CK safety boundaries."""
    code = Path(code)
    return (
        "# 使用约定\n\n"
        "安装、添加 Agent、整理记忆、检查、接入项目或卸载 memSharing：先读本机已核验的 [Skill](<%s>)，按相应操作路由执行。机器共用一套公共记忆和安装；已接入者重复安装应零写返回，新增 Agent 只补入口，显式 --agent 限定范围。\n\n"
        "公共记忆只存获准共享的原文；独有与未选内容留原处。索引一主题一行，最多 200 行 / 25KB；概要由 Agent 按事实维护，原文按需读，不自动摘要替换。\n\n"
        "项目：仅 Git 主 checkout 的未登记项目默认接入，保留已有正文；非 Git 和 linked worktree 跳过。当前执行器带 --agent 接入，只补自身入口，不替其他 Agent 预建。历史 disabled 项目跳过且不重建；重新接入须用户明确计划，不把历史停用当作入口已移除。\n\n"
        "Context Keeper 独立管理项目经历。默认接入不创建记录库、不安装或初始化 Context Keeper；首次使用与保存按其 Skill 确认。memSharing 不设置或撤销其开关，disabled 不代表 Context Keeper 停用。\n\n"
        "卸载：用户说‘卸载 memSharing’即进入 [完整卸载合同](<%s>) 的只读预览；目标含糊先澄清。先核来源与宿主义务，完整展示归还、外置备份和删除计划，精确批准后再执行；未知、漂移或恢复未闭合则停止。公共记忆归还当前正文。机器、宿主和整体分别报告；宿主仍在则整体未完成。Context Keeper 默认保留，另行预览批准。\n"
        % (code / "SKILL.md", code / "docs/uninstall-design.md")
    )


class UserEntryError(ValueError):
    def __init__(self, code, message, status="failed"):
        super().__init__(message)
        self.code, self.status = code, status
        self.agents = None
        self.detection = None


def _now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _wrap_block(marker, body):
    return (marker["start"] + "\n" + body + "\n" + marker["end"]).encode("utf-8")


def _marker_args(marker):
    return {"start": marker["start"], "end": marker["end"]}


def _confirm(request, approval_plan):
    if not request.get("interactive"):
        return False
    prompt = "Approve this exact user-entry plan? [y/N]\n" + json.dumps(
        approval_plan, ensure_ascii=False, indent=2)
    confirm = request.get("confirm")
    if confirm:
        return bool(confirm(prompt))
    print(prompt, file=sys.stderr)
    return input().strip().lower() in ("y", "yes")


def _require_real_parents(path, home):
    # 与 layout.validate_paths 同口径,但只检查父目录链:叶子本身允许是普通文件,
    # 入口文件的叶子类型由 read_snapshot 的冲突检查把关。
    path = Path(path)
    component = Path(home)
    for part in path.relative_to(Path(home)).parts[:-1]:
        component = component / part
        if component.is_symlink():
            raise UserEntryError("path_conflict", "用户级落点位于符号链接之下: " + str(component))


def _ledger_units(ledger):
    """Map (path, marker_start|None) -> registered user/machine object."""
    units = {}
    if ledger is None:
        return units
    for obj in ledger["shared_objects"].values():
        units[(obj["path"], obj["marker"]["start"] if obj["marker"] else None)] = obj
    for obj in ledger["machine"]["objects"].values():
        units[(obj["path"], obj["marker"]["start"] if obj["marker"] else None)] = obj
    return units


def _preflight_machine_units(ledger):
    """Drift stop on registered machine units (whole order, any agent).

    Mirrors enable's preflight: absent units are check-reportable gaps and are
    skipped (the planner may legitimately recreate units in this request's
    scope); a drifted managed block stops everything.
    """
    problems = []
    for obj in ledger["machine"]["objects"].values():
        if obj["kind"] not in ("block", "user_convention"):
            continue
        snap = _entry_snapshot(obj["path"])
        if snap.kind == "absent":
            continue
        if snap.kind != "file":
            problems.append("%s: 承载文件不是普通文件" % obj["path"])
            continue
        try:
            actual = block_fingerprint(snap.data, **_marker_args(obj["marker"]))
        except EntryConflict as exc:
            problems.append("%s: 标记异常 %s" % (obj["path"], exc))
            continue
        if actual is None:
            continue
        expected = (obj.get("fingerprint") or {}).get("value")
        if expected is not None and actual != expected:
            problems.append("%s: 受管块指纹漂移" % obj["path"])
    if problems:
        raise UserEntryError("drift", "登记的机器级受管单元漂移,整单停写: " + "; ".join(problems))


class _Planner:
    def __init__(self, *, config, runtime, ledger, detection, effective, transaction):
        self.config, self.runtime = config, runtime
        self.ledger, self.detection, self.effective = ledger, detection, effective
        self.transaction = transaction
        self.before, self.after = {}, {}
        self.objects = {}  # oid -> planned machine object (upsert)
        self.notes = []
        self.units = _ledger_units(ledger)
        self.memory_index = runtime.root / "memories" / "MEMORY.md"

    # ---- shared machinery -------------------------------------------------

    def snapshot(self, path):
        path = Path(path)
        if path not in self.before:
            self.before[path] = _entry_snapshot(path)
            self.after[path] = self.before[path]
        return self.after[path]

    def _new_object(self, oid, kind, path, agent, ownership, *, marker=None, value=None,
                    original_existed=None):
        basis = "block_bytes" if kind in ("block", "user_convention") else "file_bytes"
        created = ownership == "created"
        if original_existed is None:
            original_existed = not created
        return {
            "kind": kind, "path": str(path), "scope": "machine", "agents": [agent],
            "ownership": ownership, "marker": marker,
            "fingerprint": None if value is None else
                {"algorithm": "sha256", "basis": basis, "value": value},
            "original_existed": original_existed,
            "link_target": None,
            "backup_manifest": str(self.transaction.manifest_path) if (created and self.transaction) else None,
            "consumers": [],
        }

    @staticmethod
    def _merge_agents(existing, agent):
        return sorted(set(existing["agents"]) | {agent}, key=agm_paths.AGENT_ORDER.index)

    def _adopt_existing(self, oid, existing, *, agent, fingerprint=None):
        obj = copy.deepcopy(existing)
        obj["agents"] = self._merge_agents(existing, agent)
        if fingerprint is not None:
            obj["fingerprint"] = fingerprint
        self.objects[oid] = obj

    def _block_actual(self, data):
        try:
            return block_fingerprint(data, **_marker_args(BASE_MARKER)), None
        except EntryConflict as exc:
            return None, UserEntryError("entry_conflict", "公共源/约定块标记异常: %s" % exc)

    # ---- per-mode entry planning ------------------------------------------

    def native_skill(self, agent):
        path = agm_paths.native_skill_path(agent, home=self.runtime.home)
        _require_real_parents(path, self.runtime.home)
        snap = self.snapshot(path)
        raw = ("---\nname: mem-sharing\ndescription: 多 Agent 记忆共享与融合，给你的每一个 AI Agent 同一份记忆。\n---\n\n"
               "先读取并遵守 <%s>，按用户意图进入对应流程；读不到则停止并说明。\n" % (self.runtime.code / 'SKILL.md')).encode()
        oid = str(path) + '#native-skill'
        existing = self.units.get((str(path), None))
        if existing:
            if existing['kind'] != 'file' or snap.kind != 'file' or snap.fingerprint != existing['fingerprint']['value'] or snap.data != raw:
                raise UserEntryError('entry_conflict', '原生 Skill 入口漂移，保留并停止：' + str(path))
            self._adopt_existing(oid, existing, agent=agent)
            return
        if snap.kind != 'absent':
            raise UserEntryError('entry_conflict', 'Unregistered user unit: 已有未登记 Skill，保留并停止：' + str(path))
        self.after[path] = Snapshot('file', raw, 0o600)
        self.objects[oid] = self._new_object(oid, 'file', path, agent, 'created', value=sha256(raw))

    def marker_block(self, agent, path, block, oid_suffix, *, append_to_unblocked, note_label, update_registered=False):
        """Plan one BASE_MARKER managed block (codex public-source / workbuddy convention)."""
        existing = self.units.get((str(path), BASE_MARKER["start"]))
        if existing is not None and existing["scope"] == "user":
            self._verify_shared_unit(existing, path)
            if update_registered and not _public_block_intact(self.snapshot(path).data, existing, self.memory_index, agent):
                raise UserEntryError("entry_semantics_missing", "共享用户约定缺少公共读取入口，需所属项目精确治理，不由机器接入改写: " + str(path))
            self.notes.append("referenced shared %s: %s" % (note_label, path))
            return
        snap = self.snapshot(path)
        if snap.kind not in ("absent", "file"):
            raise UserEntryError("path_conflict", "用户级入口不是普通文件/缺失: " + str(path))
        actual, error = self._block_actual(snap.data or b"")
        if error is not None:
            raise error
        desired = sha256(block)
        oid = str(path) + oid_suffix
        if existing is not None:  # machine unit already registered
            trusted = (existing.get("fingerprint") or {}).get("value")
            if actual is not None and trusted is not None and actual != trusted:
                raise UserEntryError("drift", "受管块被改(漂移),整单停写: " + str(path))
            if actual is None:
                if trusted is not None and trusted != desired:
                    raise UserEntryError(
                        "drift",
                        "受管块缺失且登记内容非模板,需人工恢复,不以模板覆盖: " + str(path))
                new = render_append(snap.data or b"", block)
                self.after[Path(path)] = Snapshot("file", new, snap.mode if snap.kind == "file" else 0o600)
                self._adopt_existing(oid, existing, agent=agent,
                                     fingerprint={"algorithm": "sha256", "basis": "block_bytes", "value": desired})
                return
            if update_registered and actual != desired:
                known_old = _wrap_block(BASE_MARKER, "\n".join(
                    [WORKBUDDY_CONVENTION_TEXT, WORKBUDDY_FALLBACK_TEXT]))
                from . import policy_migration
                old_span = managed_span(snap.data, **BASE_MARKER)
                old_unit = snap.data[slice(*old_span)] if old_span is not None else b""
                if old_unit not in (known_old, policy_migration.legacy('old_workbuddy', self.runtime),
                                    policy_migration.legacy('workbuddy', self.runtime)):
                    raise UserEntryError("entry_layout_conflict", "Unknown registered user block template")
                if trusted is None:
                    raise UserEntryError("entry_semantics_missing", "旧受管块无可信指纹，不自动更新: " + str(path))
                self.after[Path(path)] = Snapshot("file", render_block(
                    snap.data, block, **_marker_args(BASE_MARKER), expected_fingerprint=trusted), snap.mode)
                self._adopt_existing(oid, existing, agent=agent,
                                     fingerprint={"algorithm": "sha256", "basis": "block_bytes", "value": desired})
                self.notes.append("approved managed block update: %s %s -> %s" % (path, trusted, desired))
                return
            self._adopt_existing(oid, existing, agent=agent,
                                 fingerprint=None if trusted is not None else
                                 {"algorithm": "sha256", "basis": "block_bytes", "value": actual})
            return
        if actual is not None:
            if update_registered and actual != desired:
                raise UserEntryError("entry_semantics_missing", "未登记旧约定块不自动收编或覆盖，需先精确治理: " + str(path))
            # Unregistered current block: register its actual bytes, zero write.
            self.objects[oid] = self._new_object(oid, "user_convention", path, agent, "reused",
                                                 marker=BASE_MARKER, value=actual)
            return
        if snap.kind == "file" and not append_to_unblocked:
            # enable.py M1 语义:已有无块用户入口是整文件基线,不追加第二份约定。
            self.notes.append("preserved existing %s without managed block: %s" % (note_label, path))
            return
        new = render_append(snap.data or b"", block)
        self.after[Path(path)] = Snapshot("file", new, snap.mode if snap.kind == "file" else 0o600)
        self.objects[oid] = self._new_object(oid, "user_convention", path, agent, "created",
                                             marker=BASE_MARKER, value=desired)

    def claude_fallback_block(self, agent, path, block):
        """Plan Claude's own fallback managed block (CLAUDE_FALLBACK_MARKER).

        与公共指针 import 行共存于 CLAUDE.md;块内容即模板本身。shared 归属的
        文件只引用不迁移:语义/哈希一致时零写引用并保留 pending,缺语义零写拒绝;
        machine 已登记分支同样校验块内语义,哈希一致不等于语义就位。
        """
        marker = CLAUDE_FALLBACK_MARKER
        existing = self.units.get((str(path), marker["start"]))
        shared_whole_file = self._shared_whole_file_owners(path)
        snap = self.snapshot(path)
        if snap.kind not in ("absent", "file"):
            raise UserEntryError("path_conflict", "用户级入口不是普通文件/缺失: " + str(path))
        try:
            actual = block_fingerprint(snap.data or b"", **_marker_args(marker))
        except EntryConflict as exc:
            raise UserEntryError("entry_conflict", "Claude 兜底块标记异常: %s" % exc)
        desired = sha256(block)
        if existing is not None and existing["scope"] == "user":
            self._verify_shared_unit(existing, path)
            if not _claude_fallback_block_intact(snap.data, (existing.get("fingerprint") or {}).get("value")):
                raise UserEntryError("entry_semantics_missing",
                                     "共享 Claude 兜底块缺少专属语义，需专用精确治理: " + str(path))
            self.notes.append("referenced shared claude fallback: %s" % path)
            return
        oid = str(path) + "#claude-fallback"
        if existing is not None:  # machine unit already registered
            trusted = (existing.get("fingerprint") or {}).get("value")
            if actual is not None and trusted is not None and actual != trusted:
                raise UserEntryError("drift", "受管块被改(漂移),整单停写: " + str(path))
            if actual is not None and actual != desired:
                raise UserEntryError("entry_semantics_missing",
                                     "已登记 Claude 兜底块内容非模板，需先精确治理: " + str(path))
            if actual is None:
                if trusted is not None and trusted != desired:
                    raise UserEntryError(
                        "drift",
                        "受管块缺失且登记内容非模板,需人工恢复,不以模板覆盖: " + str(path))
                new = render_append(snap.data or b"", block)
                self.after[Path(path)] = Snapshot("file", new, snap.mode if snap.kind == "file" else 0o600)
                self._adopt_existing(oid, existing, agent=agent,
                                     fingerprint={"algorithm": "sha256", "basis": "block_bytes", "value": desired})
                return
            self._adopt_existing(oid, existing, agent=agent,
                                 fingerprint=None if trusted is not None else
                                 {"algorithm": "sha256", "basis": "block_bytes", "value": actual})
            return
        if actual is not None:
            if actual != desired:
                raise UserEntryError("entry_semantics_missing",
                                     "未登记 Claude 兜底块内容非模板，需先精确治理: " + str(path))
            if shared_whole_file:
                # shared 整文件承载的入口:兜底字节已就位也只引用,不登记机器
                # 对象假冒连接,保留 pending 交专用迁移收编。
                self.notes.append("referenced shared claude fallback bytes: %s" % path)
                return
            self.objects[oid] = self._new_object(oid, "block", path, agent, "reused",
                                                 marker=marker, value=actual)
            return
        if shared_whole_file:
            # 追加即改写 shared 整文件:普通接入零写拒绝,交专用精确迁移。
            raise UserEntryError("ownership_conflict",
                                 "共享整文件单元(%s)承载该入口，补 Claude 兜底块需专用精确迁移: %s"
                                 % (",".join(shared_whole_file), path))
        new = render_append(snap.data or b"", block)
        self.after[Path(path)] = Snapshot("file", new, snap.mode if snap.kind == "file" else 0o600)
        self.objects[oid] = self._new_object(oid, "block", path, agent, "created",
                                             marker=marker, value=desired)

    def _shared_whole_file_owners(self, path):
        """同路径 shared(user scope)整文件单元登记 ID(kind import/file, marker=None)。"""
        if self.ledger is None:
            return []
        return sorted(oid for oid, obj in self.ledger["shared_objects"].items()
                      if obj["path"] == str(path) and obj["marker"] is None
                      and obj["kind"] in ("import", "file"))

    def protect_shared_whole_files(self):
        """普通接入不得改写 shared 整文件单元:定稿前终局保护,零写拒绝。

        需要改动这类承载文件(如为 Claude 补兜底块)属专用精确迁移;
        不扩大 rebind 更新 shared,也不把 shared 复制收编为 machine。
        """
        if self.ledger is None:
            return
        for path, snap in self.after.items():
            if snap == self.before.get(path):
                continue
            owners = self._shared_whole_file_owners(path)
            if owners:
                raise UserEntryError(
                    "ownership_conflict",
                    "共享整文件单元(%s)承载该入口，普通接入不得隐式迁移；需专用精确迁移后再接入: %s"
                    % (",".join(owners), path))

    def top_layout(self, agent, path):
        original = self.before[Path(path)]
        raw = original.data or b""
        # A shared user-owned carrier may be referenced without claiming or
        # relocating it. Static connection remains pending in that case.
        if (self.after[Path(path)] == original and self._shared_whole_file_owners(path)
                and not any(o['path'] == str(path) for o in self.objects.values())):
            self.notes.append("shared user layout retained; no machine relocation")
            return
        marker = CLAUDE_FALLBACK_MARKER if agent == "claude" else BASE_MARKER
        staged = self.after[Path(path)].data
        span = managed_span(staged, **marker)
        if span is None:
            raise UserEntryError("entry_layout_conflict", "Entry has no managed public unit")
        desired = staged[slice(*span)]
        if agent in NATIVE_FALLBACK_TEXTS and desired != native_public_source_block(agent, self.memory_index):
            raise UserEntryError("entry_layout_conflict", "Unknown registered native block template")
        units = [(marker, desired, self.units.get((str(path), marker["start"])))]
        if agent == "claude":
            units.insert(0, (None, ("@" + str(self.memory_index)).encode(),
                             self.units.get((str(path), None))))
        try:
            final = user_entry_layout.arrange(raw, units)
        except EntryConflict as exc:
            raise UserEntryError("entry_layout_conflict", str(exc)) from exc
        self.after[Path(path)] = Snapshot("file", final, original.mode if original.kind == "file" else 0o600)

    def rebind_import_fingerprints(self):
        """同一文件随后追加其他受管单元时,把 import 指纹重绑到最终整文件字节。

        import 的 basis 是整文件哈希,不构成正文删除权;重绑只改指纹,
        不改变 ownership/agents 等登记语义,且只作用于本次规划的 machine 对象。
        """
        for oid, obj in list(self.objects.items()):
            if obj["kind"] != "import":
                continue
            path = Path(obj["path"])
            if path in self.after:
                obj["fingerprint"] = {"algorithm": "sha256", "basis": "file_bytes",
                                      "value": self.after[path].fingerprint}

    def import_line(self, agent, path, line):
        """Plan the Claude-style @import reference (kind import, whole-file hash)."""
        oid = str(path) + "#import"
        existing = self.units.get((str(path), None))
        if existing is not None and (existing["kind"] != "import" or existing["marker"] is not None):
            # 旧 file 整文件记录不得被当成引用记录收编:不换 kind、不刷新基线。
            raise UserEntryError(
                "ownership_conflict",
                "同路径登记不是 import 引用单元(kind=%s,marker=%r)，拒绝收编，需精确治理: %s"
                % (existing["kind"], existing["marker"], path))
        if existing is not None and existing["scope"] == "user":
            snap = self.snapshot(path)
            if snap.kind == "absent" or (snap.kind == "file" and not any(
                    l.strip() == line for l in (snap.data or b"").split(b"\n"))):
                raise UserEntryError(
                    "drift", "已登记共享引用单元缺失引用行: %s;修复属项目层,机器启用不代写" % path)
            self.notes.append("referenced shared import unit: " + str(path))
            return
        snap = self.snapshot(path)
        if snap.kind not in ("absent", "file"):
            raise UserEntryError("path_conflict", "用户级入口不是普通文件/缺失: " + str(path))
        data = snap.data or b""
        present = any(l.strip() == line for l in data.split(b"\n"))
        new = data if present else data + (b"\n" if data and not data.endswith(b"\n") else b"") + line + b"\n"
        self.after[Path(path)] = Snapshot("file", new, snap.mode if snap.kind == "file" else 0o600)
        fingerprint = {"algorithm": "sha256", "basis": "file_bytes", "value": sha256(new)}
        if existing is not None:
            self._adopt_existing(oid, existing, agent=agent, fingerprint=fingerprint)
        else:
            # enable.py 语义:import 永不取得 created 所有权(整文件哈希不是删除凭证)。
            self.objects[oid] = self._new_object(oid, "import", path, agent, "reused",
                                                 value=fingerprint["value"], original_existed=True)

    def _verify_shared_unit(self, obj, path):
        """Shared (project-owned) units are referenced, never rewritten here."""
        snap = self.snapshot(path)
        try:
            actual = block_fingerprint(snap.data or b"", **_marker_args(obj["marker"]))
        except EntryConflict as exc:
            raise UserEntryError("drift", "共享受管块标记异常,整单停写: %s (%s)" % (path, exc)) from exc
        if snap.kind == "absent" or actual is None:
            raise UserEntryError(
                "drift", "已登记共享用户约定缺失: %s;修复属项目 enable/check,机器启用不代写" % path)
        trusted = (obj.get("fingerprint") or {}).get("value")
        if trusted is not None and actual != trusted:
            raise UserEntryError("drift", "共享受管块漂移,整单停写: " + str(path))

    # ---- outputs -----------------------------------------------------------

    def changes(self):
        result = []
        for path, snap in sorted(self.before.items(), key=lambda kv: str(kv[0])):
            after = self.after[path]
            if after == snap:
                continue
            result.append(Change.file(path, after.data, expected=snap))
        return result

    @staticmethod
    def describe(changes):
        return [{"path": str(change.path),
                 "operation": "create" if change.expected.kind == "absent" else "update",
                 "before_fingerprint": change.expected.fingerprint,
                 "after_fingerprint": change.after.fingerprint,
                 "before_mode": change.expected.mode,
                 "after_mode": change.after.mode}
                for change in changes]

    def machine_agent_records(self):
        records = {}
        existing = {} if self.ledger is None else self.ledger["machine"]["agents"]
        for agent in self.effective:
            detection = self.detection["agents"][agent]
            current = existing.get(agent)
            if current is not None and current["installation"]["status"] == detection["status"]:
                records[agent] = None  # unchanged: never refresh a stable fact's timestamp
                continue
            records[agent] = {
                "installation": {
                    "status": detection["status"],
                    "observed_at": detection["observed_at"],
                    "evidence": "detect %s: %s" % (detection["rules_version"], detection["summary"]),
                },
                "static": registry_module.unknown_fact(),
                "runtime_acceptance": {"status": "pending", "evidence_path": None},
            }
        return records

    def machine_object_updates(self):
        if self.ledger is None:
            return sorted(self.objects)
        return sorted(oid for oid, obj in self.objects.items()
                      if oid not in self.ledger["machine"]["objects"]
                      or self.ledger["machine"]["objects"][oid] != obj)


def public_read_text(memory_index):
    return "开始任务前读取并遵守 %s;读不到就说明。" % memory_index


def native_public_source_block(agent, memory_index):
    """native 执行器的用户级公共源受管块(公共指针 + 执行器专属兜底)。

    codex 分支与既有内联构造字节一致(公共布局迁移幂等依赖该字节);dsh/zcode
    是 2026-10-31 新增桌面端,首版即新模板,无历史旧模板。
    """
    return _wrap_block(BASE_MARKER, "\n".join(filter(None,
        [public_read_text(memory_index), NATIVE_FALLBACK_TEXTS[agent]])))


def dsh_home_redirected(home):
    """DSH_HOME 是否把 DeepSeek Harness 用户根重定向到非默认位置(纯布尔)。

    上游语义(冻结合同):先按 strip 判空,空白视为未设置;非空则保留原文作为
    根,~/ 或波浪号加反斜杠前缀按本函数收到的 home 展开(不用进程 HOME),
    仅转换此前缀的分隔符,再做绝对路径规范化;
    规范化后等于 <home>/.dsh 不算重定向。只返回布尔,原始环境值不得进入错误
    信息或报告(可能含用户私有路径)。
    """
    value = os.environ.get("DSH_HOME")
    if value is None or not value.strip():
        return False
    root = value
    if root.startswith("~"):
        rest = root[1:]
        if not rest:
            root = str(home)
        elif rest.startswith(("/", "\\")):
            root = str(home) + "/" + rest[1:]
    return os.path.abspath(root) != os.path.abspath(os.path.join(str(home), ".dsh"))


def opencode_config_redirected(home):
    """OpenCode 配置根是否被环境变量重定向/覆盖到非默认位置(纯布尔)。

    第一版 default-root-only:默认配置根是 <home>/.config/opencode。官方文档已
    证实 XDG_CONFIG_HOME 改变 config 目录位置;OPENCODE_CONFIG_DIR 与
    OPENCODE_CONFIG 是否影响 AGENTS.md 入口加载未获 v2.2.5 源码/实验证实
    (指定额外 config 并非必然入口重定向,不臆断;XDG 通用标准不能当应用已
    实现证据)。无证据即拒绝:对每个非空变量,仅当取值是明确等于默认落点的
    绝对路径(或变量未设置/空白)才放行;相对路径、字面 ~ 前缀及其他一切
    未确认写法(应用是否忽略/如何解析均未知)一律视为重定向,fail closed:
    - XDG_CONFIG_HOME:绝对且规范化后 == <home>/.config 才放行;
    - OPENCODE_CONFIG_DIR:绝对且规范化后 == <home>/.config/opencode 才放行;
    - OPENCODE_CONFIG:值域与语义均未证实,任何非空取值即视为重定向。
    只返回布尔,原始环境值不得进入错误信息或报告(可能含用户私有路径)。
    """
    for name, default in (("XDG_CONFIG_HOME", ".config"),
                          ("OPENCODE_CONFIG_DIR", os.path.join(".config", "opencode"))):
        value = os.environ.get(name)
        if value is None or not value.strip():
            continue
        if not os.path.isabs(value) or os.path.abspath(value) != os.path.abspath(os.path.join(str(home), default)):
            return True
    override = os.environ.get("OPENCODE_CONFIG")
    if override is not None and override.strip():
        return True
    return False


def _public_block_intact(raw, obj, memory_index, agent):
    span = managed_span(raw, **_marker_args(obj["marker"]))
    if span is None:
        return False
    block = raw[span[0]:span[1]]
    trusted = (obj.get("fingerprint") or {}).get("value")
    return (trusted == sha256(block) and public_read_text(memory_index).encode() in block.splitlines()
            and (agent != "workbuddy" or WORKBUDDY_CONVENTION_TEXT.encode() in block.splitlines()))


def top_layout_intact(raw, agent, memory_index):
    bom = user_entry_layout.BOM if raw.startswith(user_entry_layout.BOM) else b""
    if agent == "claude":
        top = ("@" + str(memory_index)).encode() + b"\n" + _wrap_block(CLAUDE_FALLBACK_MARKER, CLAUDE_FALLBACK_TEXT)
    elif agent == "workbuddy":
        top = _wrap_block(BASE_MARKER, "\n".join([public_read_text(memory_index), WORKBUDDY_CONVENTION_TEXT, WORKBUDDY_FALLBACK_TEXT]))
    else:
        top = native_public_source_block(agent, memory_index)
    return raw.startswith(bom + top)


def connection_status(runtime, config, ledger, agents):
    """Read-only entry proof; detection and runtime acceptance are separate facts."""
    result = {}
    objects = list(ledger["machine"]["objects"].values())
    for agent in agents:
        path = Path(agm_paths.expand_path(config[agent]["user_entry"], home=str(runtime.home)))
        record = ledger["machine"]["agents"].get(agent)
        if record is None or record["installation"]["status"] != "installed":
            result[agent] = {"status": "pending", "reason": "agent_not_registered_installed", "runtime_acceptance": "pending"}
            continue
        candidates = [o for o in objects if o["path"] == str(path) and agent in o["agents"]]
        shared = any(o["path"] == str(path) and agent in o["agents"] for o in ledger["shared_objects"].values())
        reason = "machine_entry_not_registered_shared_reference" if shared and not candidates else "entry_not_registered"
        if candidates:
            # 连接证据要求该入口的全部登记机器单元就位且语义匹配;Claude(import_agents)
            # 必须同时具备公共指针 import 与自身 fallback 块两类证据,旧 import-only
            # 登记(迁移前台账)不算已接入。
            reasons = []
            passed = set()
            for obj in candidates:
                try:
                    _require_real_parents(path, runtime.home)
                    snap = read_snapshot(path)
                    if snap.kind != "file":
                        reasons.append("entry_missing_or_not_file")
                        continue
                    if obj["kind"] == "import" and config[agent]["rule_mode"] == "import_agents":
                        line = ("@" + str(runtime.root / "memories/MEMORY.md")).encode()
                        intact = sum(p.strip() == line for p in snap.data.splitlines()) == 1
                        evidence = "public_import"
                    elif obj["kind"] in ("block", "user_convention") and config[agent]["rule_mode"] != "import_agents":
                        intact = _public_block_intact(snap.data, obj, runtime.root / "memories/MEMORY.md", agent)
                        evidence = "public_pointer"
                    elif (obj["kind"] == "block" and obj.get("marker") == CLAUDE_FALLBACK_MARKER
                            and config[agent]["rule_mode"] == "import_agents"):
                        trusted = (obj.get("fingerprint") or {}).get("value")
                        intact = (_claude_fallback_block_intact(snap.data, trusted))
                        evidence = "claude_fallback"
                    else:
                        intact, evidence = False, None
                    if intact and evidence is not None:
                        passed.add(evidence)
                    elif not intact:
                        reasons.append("entry_drift_or_semantics_missing")
                except (ValueError, OSError):
                    reasons.append("entry_unreadable_or_conflict")
            required = ({"public_import", "claude_fallback"}
                        if config[agent]["rule_mode"] == "import_agents" else {"public_pointer"})
            if not required <= passed:
                reasons.append("entry_evidence_incomplete")
            if not reasons and not top_layout_intact(snap.data, agent, runtime.root / "memories/MEMORY.md"):
                reasons.append("entry_layout_not_top")
            reason = None if not reasons else reasons[0]
        result[agent] = {"status": "connected" if reason is None else "pending", "reason": reason,
                         "runtime_acceptance": "pending"}
    return result


def _claude_fallback_block_intact(raw, trusted):
    """核验 Claude 兜底块:登记哈希一致且块内语义就是 fallback 模板。

    语义以标记内内容为准(不搜文件内任意位置的同名文本,不审核自由私人正文);
    已登记哈希只能证明与登记一致,不能证明块承载了专属兜底语义。
    """
    try:
        span = managed_span(raw, **_marker_args(CLAUDE_FALLBACK_MARKER))
    except EntryConflict:
        return False
    if span is None:
        return False
    block = raw[span[0]:span[1]]
    if block != _wrap_block(CLAUDE_FALLBACK_MARKER, CLAUDE_FALLBACK_TEXT):
        return False
    if trusted is None:
        return True
    return sha256(block) == trusted


def render_append(data, block):
    return data + (b"\n" if data and not data.endswith(b"\n") else b"") + block


def _load_ledger(runtime, allowed):
    """Read-only ledger load; absent registry is fine for preview (installer owns creation)."""
    state = _PREVIEW_STATE.get()
    if state is not None:
        if state[0] != str(runtime.registry):
            raise UserEntryError("installer_context_required", "Preview runtime differs from migration")
        return copy.deepcopy(state[1]), _entry_snapshot(runtime.registry)
    snap = read_snapshot(runtime.registry)
    if snap.kind == "absent":
        return None, snap
    ledger = registry_module.require_installed(
        registry_module.load_registry(runtime.registry, allowed_user_paths=allowed))
    return ledger, snap


def _plan(request, runtime, detection, effective, *, transaction):
    config = request["platform_config"]
    home = request["home"]
    # 与 _run 同源的机器安装器缺省:未显式指定时目标=全量支持清单(AGENT_ORDER),
    # 仅 installed 者生效;request["agents"] 保持 None,不转为显式列表。
    requested = agm_paths.resolve_agents(request.get("agents"), default=agm_paths.AGENT_ORDER)
    allowed = agm_paths.allowed_user_paths(config, None, home=home)
    context = _INSTALLER_SOURCE.get()
    verified = request.get("verified_product_source")
    if verified is not None:
        if context is None or context[0] != str(runtime.code):
            raise UserEntryError("installer_context_required", "verified_product_source is installer-only")
        source_skill = Path(verified) / "SKILL.md"
        if source_skill.is_symlink() or not source_skill.is_file() or sha256(source_skill.read_bytes()) != context[1]:
            raise UserEntryError("product_code_drift", "Verified product source fingerprint changed")
        code_skill = runtime.code / "SKILL.md"
        if code_skill.is_file() and not code_skill.is_symlink():
            if sha256(code_skill.read_bytes()) != context[1]:
                raise UserEntryError("product_code_drift", "C differs from the approved product source")
        elif not context[2] or code_skill.is_symlink():
            raise UserEntryError("product_code_missing", "Installer execution requires verified code at C")
    ledger, registry_snap = _load_ledger(runtime, allowed)
    try:
        if context is not None:
            candidate = verified or (request.get("source") or {}).get("root")
            if candidate is None:
                raise EntryConflict("Installer candidate source is required")
            user_entry_layout.require_source(candidate)
        elif ledger is not None:
            user_entry_layout.require_kernel(runtime)
    except (ValueError, OSError) as exc:
        raise UserEntryError("entry_layout_code_incompatible", str(exc)) from exc
    if ledger is not None:
        _preflight_machine_units(ledger)
    planner = _Planner(config=config, runtime=runtime, ledger=ledger,
                       detection=detection, effective=effective, transaction=transaction)
    if 'workbuddy' in effective:
        default = Path(home)/'.workbuddy'
        redirected = any(value and (not Path(value).is_absolute() or Path(value).resolve()!=default)
                         for key in ('WORKBUDDY_CONFIG_DIR', 'CODEBUDDY_CONFIG_DIR')
                         for value in [os.environ.get(key, '').strip()])
        redirected = redirected or os.environ.get('WORKBUDDY_DATA_FOLDER_NAME', '.workbuddy').strip() not in ('', '.workbuddy')
        if redirected or os.environ.get('WORKBUDDY_INSTANCE_NUMBER', '').strip():
            raise UserEntryError('workbuddy_config_redirected',
                                 'WorkBuddy 用户配置根重定向；只支持默认根，整单停止，零写入。')
    if "dsh" in effective and dsh_home_redirected(home):
        # 冻结合同:DSH_HOME 重定向时默认入口不被读取;fail closed,不写无效文件。
        # 只说明变量名与默认根支持范围,不回传 DSH_HOME 原始值(隐私)。
        raise UserEntryError(
            "dsh_home_redirected",
            "DSH_HOME 已把 DeepSeek Harness 用户根重定向到非默认位置,默认入口不会被该应用读取;"
            "本产品仅支持默认根 ~/.dsh(即 <home>/.dsh),请清除该重定向后重试;"
            "整单停止,零写入。")
    if "opencode" in effective and opencode_config_redirected(home):
        # 第一版 default-root-only:配置根受环境变量影响时默认入口是否被读取
        # 无法确定;fail closed,不写无效文件。只说明变量名与默认根支持范围,
        # 不回传任何原始环境值(隐私)。
        raise UserEntryError(
            "opencode_config_redirected",
            "OpenCode 配置根被环境变量重定向或覆盖(XDG_CONFIG_HOME/OPENCODE_CONFIG_DIR/OPENCODE_CONFIG),"
            "默认入口 <home>/.config/opencode/AGENTS.md 是否被读取无法确定;"
            "本产品仅支持默认配置根(清除相关变量或使其指向默认值后重试);"
            "整单停止,零写入。")
    for agent in effective:
        entry = config[agent]
        planner.native_skill(agent)
        user_path = Path(agm_paths.expand_path(entry["user_entry"], home=home))
        _require_real_parents(user_path, runtime.home)
        if entry["rule_mode"] == "user_convention":
            # 入口只含公共索引指针与自身专属规则;公共治理/菜单由公共源承载。
            planner.marker_block(agent, user_path,
                                 _wrap_block(BASE_MARKER, "\n".join(
                                     [public_read_text(planner.memory_index), WORKBUDDY_CONVENTION_TEXT,
                                      WORKBUDDY_FALLBACK_TEXT])),
                                 "#convention", append_to_unblocked=True, note_label="user convention", update_registered=True)
        elif entry["rule_mode"] == "native":
            planner.marker_block(agent, user_path,
                                 native_public_source_block(agent, planner.memory_index),
                                 "#public-source", append_to_unblocked=True, note_label="public-source block")
        elif entry["rule_mode"] == "import_agents":
            # Claude 经 @import 读公共源;自身 fallback 以独立受管块随入口落盘,
            # 不依赖公共索引承载 Claude 专属条款。
            planner.import_line(agent, user_path, ("@" + str(planner.memory_index)).encode("utf-8"))
            planner.claude_fallback_block(agent, user_path,
                                          _wrap_block(CLAUDE_FALLBACK_MARKER, CLAUDE_FALLBACK_TEXT))
        else:  # pragma: no cover - 路径表枚举已限定 rule_mode
            raise UserEntryError("agents_table_invalid", "未知 rule_mode: %r" % entry["rule_mode"])
        planner.top_layout(agent, user_path)
        # Claude 兜底块在 import 行之后追加:同文件 import 登记按最终字节重绑。
        planner.rebind_import_fingerprints()
        # 终局保护:shared 整文件单元承载的入口不允许被普通接入改写(零写拒绝)。
        planner.protect_shared_whole_files()
    agent_records = planner.machine_agent_records()
    machine_agents = sorted(a for a, record in agent_records.items() if record is not None)
    approval_plan = {
        "schema_version": 1,
        "command": COMMAND,
        "requested": requested,
        "effective": list(effective),
        "detection": {
            agent: {"status": detection["agents"][agent]["status"],
                    "fingerprint": detect_module.detection_fingerprint(detection["agents"][agent])}
            for agent in requested
        },
        "changes": _Planner.describe(planner.changes()),
        "machine_objects": planner.machine_object_updates(),
        "machine_agents": machine_agents,
        "registry_before_fingerprint": (None if verified is not None and
            (ledger is None or not ledger["machine"]["objects"]) else registry_snap.fingerprint),
        "registry_before_mode": (None if verified is not None and
            (ledger is None or not ledger["machine"]["objects"]) else registry_snap.mode),
        "entry_layout": "owned-top-v1",
        "machine_object_projection": {oid: {k: v for k, v in obj.items() if k != "backup_manifest"}
                                      for oid, obj in sorted(planner.objects.items())},
    }
    if verified is not None:
        approval_plan["verified_product_source"] = {"skill_sha256": context[1], "target": str(runtime.code)}
    return {
        "approval_plan": approval_plan,
        "planner": planner,
        "agent_records": agent_records,
        "ledger": ledger,
        "registry_snap": registry_snap,
        "notes": planner.notes,
    }


def _apply_registry(plan, runtime):
    """Merge planned machine agents/objects into registry data for commit."""
    if plan["ledger"] is None:
        raise UserEntryError(
            "machine_not_installed",
            "机器台账缺失: %s;用户级启用由安装器在机器安装完成后执行" % runtime.registry)
    data = copy.deepcopy(plan["ledger"])
    for agent, record in plan["agent_records"].items():
        if record is not None:
            data["machine"]["agents"][agent] = record
    for oid, obj in plan["planner"].objects.items():
        data["machine"]["objects"][oid] = obj
    return data


def _result(**fields):
    result = {"status": "failed", "command": COMMAND, "agents": None, "detection": None,
              "changes": [], "warnings": [], "errors": [], "approval_required": False,
              "next_action": None}
    result.update(fields)
    return result


def _agent_report(requested, effective, detection):
    return {
        "requested": requested,
        "effective": list(effective),
        "skipped": {agent: detection["agents"][agent]["status"]
                    for agent in requested if agent not in effective},
    }


def _run(request, runtime, *, locked):
    if _PREVIEW_STATE.get() is not None and (locked or request.get("approval") is not None
                                           or request.get("interactive")):
        raise UserEntryError("installer_context_required", "Predicted entry state is preview-only")
    config, home = request["platform_config"], request["home"]
    # 机器安装器缺省(2026-11-01 裁定):未显式指定 --agent 时目标=全量支持清单,
    # 仅检测 installed 者自动装配;request["agents"] 保持 None,显式判定不变。
    # 显式指定且未核验 installed 仍整单拒绝(下方 agent_not_installed)。
    requested = agm_paths.resolve_agents(request.get("agents"), default=agm_paths.AGENT_ORDER)
    detection = detect_module.detect_agents(
        config, requested, home=home, search_paths=request.get("search_paths"),
        user_candidates=request.get("user_candidates"), runner=request.get("detect_runner"),
        app_directories=request.get("app_directories"))
    effective = [a for a in requested if detection["agents"][a]["status"] == "installed"]
    agents = _agent_report(requested, effective, detection)

    def annotated(exc):
        exc.agents, exc.detection = agents, detection
        return exc

    if request.get("agents") is not None and len(effective) != len(requested):
        missing = {a: detection["agents"][a]["status"] for a in requested if a not in effective}
        raise annotated(UserEntryError(
            "agent_not_installed",
            "显式指定的执行器未核验为 installed(%s);整单停止,零写入。"
            "下一步:安装该执行器或提供可核验安装证据后重试" % json.dumps(missing, ensure_ascii=False)))
    try:
        plan = _plan(request, runtime, detection, effective, transaction=None)
    except UserEntryError as exc:
        raise annotated(exc) from None
    approval = request.get("approval")
    if approval is not None:
        expected = set(plan["approval_plan"]) | {"confirmed_at", "reference"}
        if (set(approval) != expected
                or any(approval.get(key) != value for key, value in plan["approval_plan"].items())):
            raise annotated(UserEntryError(
                "approval_mismatch",
                "批准计划与现场不一致,须重新预览确认: " + json.dumps(
                    plan["approval_plan"], ensure_ascii=False, sort_keys=True),
                status="approval_required"))
        evidence = {"confirmed_at": approval["confirmed_at"], "reference": approval["reference"]}
    elif not plan["approval_plan"]["changes"] and not plan["approval_plan"]["machine_objects"] \
            and not plan["approval_plan"]["machine_agents"]:
        return _result(status="completed", agents=agents, detection=detection,
                       changes=[], warnings=list(plan["notes"]) + [
                           "无待装配差异，零写入；接入状态须另查机器登记及入口，运行时仍待新会话验收"])
    elif _confirm(request, plan["approval_plan"]):
        evidence = {"confirmed_at": _now(), "reference": "interactive exact user-entry plan confirmation"}
    else:
        preview = dict(plan["approval_plan"],
                       confirmed_at="<UTC timestamp>", reference="<user confirmation reference>")
        return _result(status="approval_required", agents=agents, detection=detection,
                       changes=plan["approval_plan"]["changes"], warnings=list(plan["notes"]),
                       approval_required=True,
                       next_action=json.dumps(preview, ensure_ascii=False))
    if not locked:
        # Preview never takes a lock; execution re-plans under the machine writer
        # lock so approval and machine state cannot race.
        approved_request = dict(request, approval=dict(plan["approval_plan"], **evidence))
        with write_lock(runtime.lock):
            return _run(approved_request, runtime, locked=True)
    transaction = Transaction(
        lock_path=runtime.transaction_lock, backup_root=runtime.backups,
        allowed_roots=[Path(p) for p in agm_paths.allowed_user_paths(config, effective, home=home)]
        + [runtime.registry],
        operation=COMMAND)
    fresh = _plan(request, runtime, detection, effective, transaction=transaction)
    if fresh["approval_plan"] != plan["approval_plan"]:
        raise annotated(UserEntryError(
            "approval_mismatch",
            "预览与执行之间现场已变化,已停止写入;请重新预览确认",
            status="approval_required"))
    allowed = agm_paths.allowed_user_paths(config, None, home=home)
    data = _apply_registry(fresh, runtime)
    registry_module.commit_registry(
        runtime.registry, data, transaction=transaction,
        expected=fresh["registry_snap"], changes=fresh["planner"].changes(),
        allowed_user_paths=allowed, previous=fresh["ledger"])
    result = _result(status="completed", agents=agents, detection=detection,
                     changes=fresh["approval_plan"]["changes"], warnings=list(fresh["notes"]))
    result["warnings"].append("runtime acceptance pending: 用户级入口是否被新会话读取未验证")
    return result


def run_user_entries(request):
    """Entry point mirroring the command-module contract (request dict → result dict)."""
    try:
        runtime = layout_module.from_request(request)
        if runtime.lock.exists():
            raise TransactionError("writer lock exists; do not steal a stale lock", code="lock_conflict")
        return _run(request, runtime, locked=False)
    except UserEntryError as exc:
        result = _result(status=exc.status, approval_required=exc.status == "approval_required",
                         agents=exc.agents, detection=exc.detection)
        if exc.status == "approval_required":
            result["next_action"] = str(exc)
        result["errors"].append({
            "code": exc.code, "path": None, "message": str(exc),
            "recovery": "重新预览并确认新计划" if exc.status == "approval_required"
                        else "保持现场零写入;按错误码处理后重新预览"})
        return result
    except TransactionError as exc:
        status = "recovery_required" if exc.code == "recovery_required" else "failed"
        result = _result(status=status)
        result["errors"].append({
            "code": exc.code, "path": None, "message": str(exc),
            "recovery": ("核对 manifest 后显式恢复: " + exc.manifest) if exc.manifest
                        else "保留现场;核对事务材料后重试或显式恢复"})
        return result
    except (ValueError, OSError, EOFError) as exc:
        result = _result()
        result["errors"].append({"code": getattr(exc, "code", "user_entries_failed"), "path": None,
                                 "message": str(exc), "recovery": None})
        return result


# Frozen shipped templates: recognition only; never generated for fresh installs.
LEGACY_RUNTIME_CONTRACT = '读取契约：L0 恒读本索引 → 需要该主题时读其 L1 概要段 → 仍不足才读 L2 全文；相对链接以本文件所在目录解析，指向的内容缺失时停止相关操作。\n预算：L0 一主题一行：主题名 + 一句话当前结论 + 链接；索引 ≤200 行 / 25KB；增加主题文件，不加长索引；摘要在记忆整理时手写，不自动生成。\n用户规则治理：公共内容只写公共指定文件（R/memories），Agent 独有内容保留于各自用户文件，永不并入公共或自动删除。进入 Git 主 checkout 时，未登记项目默认启用项目规则：创建缺失的 AGENTS.md 骨架并追加项目经历短协议，已有全文保留。默认启用不创建 Context Keeper 记录库、不调用 Context Keeper 安装或初始化；首次 /context-keeper 进入 Context Keeper 流程，首次保存按其流程确认位置。项目经历由 Context Keeper 独立管理，本工具不设经历开关，不撤销、不禁用也不否决 Context Keeper。历史停用登记（disabled）项目默认流程跳过、不重建，也不宣称入口已移除；该状态不代表 Context Keeper 停用，重新接入需用户明确的重新接入计划。各 Agent 只维护自身专属项目入口（Claude 的 CLAUDE.md、WorkBuddy 的原生 memory 指针），由各自实际使用时补齐，其他执行器不得预建；AGENTS.md 是共享项目规则基座，不依赖 Codex，无 Codex 的机器同样成立，其默认建立遵本治理条款；非 Git 目录和 linked worktree 不触发。\n按需操作指南：/mem-sharing 菜单、绝对命令与公共记忆维护规则由主题《使用约定》承载（[使用约定](topics/使用约定.md)）；仅在用户明确 /mem-sharing、提出同义自然语言操作或默认项目接入前读取；用户明确说“卸载 memSharing / 卸载 mem-sharing”或“不想用这个共享记忆工具了，帮我卸载”时，立即按需读取该主题完整卸载路由，无须斜杠命令或源码目录；目标含糊先澄清；该指南不回指其他菜单。\n'

def legacy_usage_convention_topic_text(code):
    """新装主题《使用约定》:操作指南本体,承接六项菜单、绝对命令与 L0/L1/L2 维护。

    指南不循环回指菜单;本指南内相对链接以指南自身目录(topics/)解析,
    受管产品命令与 Skill 路径用安装代码 C 的绝对路径。规则驱动的默认项目
    接入由当前实际执行器带 --agent 发起(先查历史停用登记并跳过),
    不让当前会话无参数顺带改动其他执行器入口;经历开关已退役,恢复接入
    不经由任何迁移命令自动完成。
    """
    cli = "python3 %s/scripts/agm.py" % code
    return (
        "# 使用约定\n\n"
        "## L1 概要\n\n"
        "当前有效结论：公共记忆采用索引与主题文件，摘要由 Agent 手写，不自动生成。\n"
        "本主题即操作指南：/mem-sharing 菜单、绝对命令与公共记忆 L0/L1/L2 维护规则都在本文件正文，不回指其他菜单。\n"
        "待办：有新事实且获准记录时，更新对应主题结论与索引行。\n\n"
        "## L2 正文\n\n"
        "### /mem-sharing 菜单\n\n"
        + agent_group_menu_text(code) + "\n"
        "### 公共记忆维护（L0/L1/L2）\n\n"
        "L0 索引一主题一行：主题名 + 一句话当前结论 + 链接，≤200 行 / 25KB；增加主题文件，不加长索引。\n"
        "L1 位于主题文件开头，简列当前有效结论与待办；L2 为全文及 references/ 手册，仅在概要不足时读取。\n"
        "摘要在记忆整理时手写，不自动生成。本指南内相对链接以本文件所在目录（topics/）解析；"
        "受管产品命令与 Skill 路径使用安装代码的绝对路径。\n\n"
        "### 项目接入约定\n\n"
        "规则驱动的默认接入由当前实际执行者发起：%s enable-memory --project <项目绝对路径> --agent <当前执行器>；"
        "执行前先检查项目政策，历史停用登记（disabled）项目跳过、不由本路径恢复"
        "（历史停用登记不代表 Context Keeper 停用，也不宣称入口已移除；migrate-policy 仅清理产品自有的停用控制，不恢复接入；重新接入需用户明确的重新接入计划）；"
        "各 Agent 专属项目入口按当前执行器自身用户文件中的规则维护，公共指南不承载执行器专属细节。\n"
        "当前会话不得无参数顺带改动其他执行器的入口。"
        "用户显式授权的全体接入或批量启用沿用现有命令语义，本约定不改变任何命令默认。\n" % cli
        + "\n" + natural_language_uninstall_text(code)
    )
