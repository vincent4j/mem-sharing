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
from .enable import BASE_MARKER
from .entries import EntryConflict, block_fingerprint, sha256, managed_span, render_block
from .transaction import (Change, Snapshot, Transaction, TransactionError,
                          read_snapshot, write_lock)

COMMAND = "assemble-user-entries"
_INSTALLER_SOURCE = ContextVar("agm_installer_verified_source", default=None)


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
GOVERNANCE_RULES_TEXT = (
    "用户规则治理：公共内容只写公共指定文件（R/memories），Agent 独有内容保留于各自用户文件，永不并入公共或自动删除。"
    "进入 Git 主 checkout 时，未登记项目默认启用项目规则：创建缺失的 AGENTS.md 骨架并追加项目经历短协议，已有全文保留。"
    "默认启用不创建 Context Keeper 记录库、不调用 Context Keeper 安装或初始化；首次 /context-keeper 进入 Context Keeper 流程，首次保存按其流程确认位置。"
    "项目政策已为 disabled 时，默认流程不得重新启用入口、自动记录经历或初始化；已有 Context Keeper 自动规则也不能覆盖此政策。"
    "重新启用须用户显式执行 enable-memory；解除 disabled 须显式 enable-memory --memory 并批准精确计划。"
    "各 Agent 只维护自身专属项目入口（Claude 的 CLAUDE.md、WorkBuddy 的原生 memory 指针），由各自实际使用时补齐，其他执行器不得预建；"
    "AGENTS.md 是共享项目规则基座，不依赖 Codex，无 Codex 的机器同样成立，其默认建立遵本治理条款；非 Git 目录和 linked worktree 不触发。"
)
CLAUDE_FALLBACK_TEXT = (
    "仅 Claude Code 在本项目实际使用且项目已启用、政策非 disabled 时补引用：CLAUDE.md 不存在才创建仅含 @AGENTS.md 的文件；"
    "已有正文必须完整保留，仅追加缺失的 @AGENTS.md 引用行，重复执行不改字节。"
)
WORKBUDDY_FALLBACK_TEXT = "仅 WorkBuddy 在本项目实际使用产生原生 .workbuddy/memory 目录，且项目已启用、政策非 disabled 时，补顶部 AGENTS.md 指针；保留已有正文字节，不预建原生目录。"
CODEX_FALLBACK_TEXT = "Codex 原生读取共享项目规则基座 AGENTS.md，自身无额外专属项目入口；该基座默认建立遵公共治理条款，已 disabled 项目不自动恢复。"
# 桌面双端(2026-10-31 冻结合同):dsh=DeepSeek Harness、zcode=ZCode 均原生读取
# 项目根 AGENTS.md(rule_mode=native),用户入口分别是 ~/.dsh/AGENTS.md 与
# ~/.zcode/AGENTS.md。兜底文本各写自身执行器称谓,不复用 CODEX_FALLBACK_TEXT,
# 迁移/连接校验按块内语义精确区分执行器。
DSH_FALLBACK_TEXT = ("DeepSeek Harness 原生读取共享项目规则基座 AGENTS.md，自身无额外专属项目入口；"
                     "该基座默认建立遵公共治理条款，已 disabled 项目不自动恢复。"
                     "用户入口仅支持默认根 ~/.dsh/AGENTS.md，DSH_HOME 重定向时不接入。")
ZCODE_FALLBACK_TEXT = ("ZCode 原生读取共享项目规则基座 AGENTS.md 与用户级 ~/.zcode/AGENTS.md，自身无额外专属项目入口；"
                       "该基座默认建立遵公共治理条款，已 disabled 项目不自动恢复。")
NATIVE_FALLBACK_TEXTS = {"codex": CODEX_FALLBACK_TEXT, "dsh": DSH_FALLBACK_TEXT, "zcode": ZCODE_FALLBACK_TEXT}

# Claude 自身 fallback 的独立受管块标记:与公共指针 import 并存于 CLAUDE.md,
# 迁移/连接校验按此标记精确识别,不与 BASE_MARKER 公共源块混用。
CLAUDE_FALLBACK_MARKER = {"start": "<!-- mem-sharing:claude-fallback:start -->",
                          "end": "<!-- mem-sharing:claude-fallback:end -->"}


def agent_group_menu_text(code):
    """菜单文本;命令基路径为受管产品代码 C(layout.code),逐项映射既有 CLI。"""
    cli = "python3 %s/scripts/agm.py" % code
    installer = "python3 %s/scripts/install.py" % code
    skill = "%s/SKILL.md" % code
    return (
        "/mem-sharing 菜单:\n"
        "添加新的 Agent：接入已安装的执行器 → %s --agent <执行器名>\n"
        "批量启用项目记忆：扫描给定目录，汇总预览后一次批准 → %s enable-memory-batch --directory <目录绝对路径>\n"
        "整理用户记忆：公共与独有分开，逐条计划后一次批准 → 治理流程见 %s\n"
        "健康检查：只读检查已登记入口 → %s check-memory --project <项目绝对路径>\n"
        "给项目停用记忆：撤项目记忆入口并保留数据 → %s remove-memory --project <项目绝对路径>；仅禁自动项目经历记录、保留入口用 enable-memory --no-memory\n"
        "给项目启用记忆：显式恢复已停用项目或手动启用项目记忆 → %s enable-memory --project <项目绝对路径> --memory；新 Git 主 checkout 默认启用、disabled 不自动恢复语义不变\n"
        % (installer, cli, skill, cli, cli, cli)
    )


def public_memory_contract_text():
    """公共 MEMORY 头部契约:读取契约、预算、公共治理与按需操作指南指针。

    公共治理全文留在此处;菜单/绝对命令/L0L1L2 维护规则由《使用约定》主题承载,
    指南不回指菜单;相对链接以 MEMORY 所在目录解析,指南缺失时停止相关操作。
    """
    return (
        "读取契约：L0 恒读本索引 → 需要该主题时读其 L1 概要段 → 仍不足才读 L2 全文；"
        "相对链接以本文件所在目录解析，指向的内容缺失时停止相关操作。\n"
        "预算：L0 一主题一行：主题名 + 一句话当前结论 + 链接；索引 ≤200 行 / 25KB；"
        "增加主题文件，不加长索引；摘要在记忆整理时手写，不自动生成。\n"
        + GOVERNANCE_RULES_TEXT + "\n"
        "按需操作指南：/mem-sharing 菜单、绝对命令与公共记忆维护规则由主题《使用约定》承载"
        "（[使用约定](topics/使用约定.md)）；仅在用户明确 /mem-sharing、提出同义自然语言操作"
        "或默认项目接入前读取；该指南不回指其他菜单。\n"
    )


def usage_convention_topic_text(code):
    """新装主题《使用约定》:操作指南本体,承接六项菜单、绝对命令与 L0/L1/L2 维护。

    指南不循环回指菜单;本指南内相对链接以指南自身目录(topics/)解析,
    受管产品命令与 Skill 路径用安装代码 C 的绝对路径。规则驱动的默认项目
    接入由当前实际执行器带 --agent 发起(不带 --memory,先查 disabled 并跳过),
    不让当前会话无参数顺带改动其他执行器入口;显式菜单启用保留 --memory。
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
        "规则驱动的默认接入由当前实际执行器发起：%s enable-memory --project <项目绝对路径> --agent <当前执行器>；"
        "执行前先检查项目政策，已 disabled 的项目跳过、不由本路径恢复（解除 disabled 须用户显式 --memory 并批准精确计划）；"
        "各 Agent 专属项目入口按当前执行器自身用户文件中的规则维护，公共指南不承载执行器专属细节。\n"
        "当前会话不得无参数顺带改动其他执行器的入口。"
        "用户显式授权的全体接入或批量启用沿用现有命令语义，本约定不改变任何命令默认。\n" % cli
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
        snap = read_snapshot(obj["path"])
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
            self.before[path] = read_snapshot(path)
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
                 "after_fingerprint": change.after.fingerprint}
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
    return _wrap_block(BASE_MARKER, "\n".join(
        [public_read_text(memory_index), NATIVE_FALLBACK_TEXTS[agent]]))


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


def _public_block_intact(raw, obj, memory_index, agent):
    span = managed_span(raw, **_marker_args(obj["marker"]))
    if span is None:
        return False
    block = raw[span[0]:span[1]]
    trusted = (obj.get("fingerprint") or {}).get("value")
    return (trusted == sha256(block) and public_read_text(memory_index).encode() in block.splitlines()
            and (agent != "workbuddy" or WORKBUDDY_CONVENTION_TEXT.encode() in block.splitlines()))


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
    snap = read_snapshot(runtime.registry)
    if snap.kind == "absent":
        return None, snap
    ledger = registry_module.require_installed(
        registry_module.load_registry(runtime.registry, allowed_user_paths=allowed))
    return ledger, snap


def _plan(request, runtime, detection, effective, *, transaction):
    config = request["platform_config"]
    home = request["home"]
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
    if ledger is not None:
        _preflight_machine_units(ledger)
    planner = _Planner(config=config, runtime=runtime, ledger=ledger,
                       detection=detection, effective=effective, transaction=transaction)
    if "dsh" in effective and dsh_home_redirected(home):
        # 冻结合同:DSH_HOME 重定向时默认入口不被读取;fail closed,不写无效文件。
        # 只说明变量名与默认根支持范围,不回传 DSH_HOME 原始值(隐私)。
        raise UserEntryError(
            "dsh_home_redirected",
            "DSH_HOME 已把 DeepSeek Harness 用户根重定向到非默认位置,默认入口不会被该应用读取;"
            "本产品仅支持默认根 ~/.dsh(即 <home>/.dsh),请清除该重定向后重试;"
            "整单停止,零写入。")
    for agent in effective:
        entry = config[agent]
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
        # Claude 兜底块在 import 行之后追加:同文件 import 登记按最终字节重绑。
        planner.rebind_import_fingerprints()
        # 终局保护:shared 整文件单元承载的入口不允许被普通接入改写(零写拒绝)。
        planner.protect_shared_whole_files()
    requested = agm_paths.resolve_agents(request.get("agents"))
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
    config, home = request["platform_config"], request["home"]
    requested = agm_paths.resolve_agents(request.get("agents"))
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
