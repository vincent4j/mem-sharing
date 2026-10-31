"""M4-05: machine-level user entry planning and approved assembly.

One planner serves both first install and later agent accession (决策单 §7.2):
only executors detected as installed get user entries; absent/unknown agents
are reported and never written; an explicitly requested agent that is not
installed stops the whole request before any write.

Templates reuse the existing M2/M3 semantics instead of a second dialect:
- WorkBuddy 用户约定: enable.py 的既有 user_convention 文本与 BASE_MARKER(测试锁定
  两处文本一致),机器级块在其后追加 v1.11 治理条款与 /mem-sharing 菜单;
- Codex 用户级公共源块(native): 同一 BASE_MARKER 机制,追加“开工先读公共记忆”指针块
  (DESIGN §4.8),指向本机公共源索引 R/memories/MEMORY.md,并携带治理条款与菜单;
- Claude @import(import_agents): 复用 enable.py 的引用行语义,引用同一公共源索引;
  治理条款与菜单由公共源文本承载(v1.11:产品自身 Skill 投影取消,无任何 Skill 落点)。

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

# v1.11/v1.12/§16(2026-10-30 用户裁定)用户规则治理条款与 /mem-sharing 会话菜单:
# 写入用户级入口文本与公共源模板;菜单逐项映射既有命令与安装器参数,零新机制。
# 术语用“启用/停用”(用户裁定,装配不好理解),命令名 enable-memory 等保持不变。
GOVERNANCE_RULES_TEXT = (
    "用户规则治理:公共内容只写公共指定文件(R/memories)，Agent 独有内容保留于各自用户文件，永不并入公共或自动删除。"
    "进入 Git 主 checkout 时，未登记项目默认启用项目规则：创建缺失的 AGENTS.md 骨架并追加项目经历短协议，已有全文保留。"
    "默认启用不创建 CK 记录库、不调用 CK 安装或初始化；首次 /context-keeper 进入 CK 流程，首次保存按其流程确认位置。"
    "项目政策已为 disabled 时，默认流程不得重新启用入口、自动记录经历或初始化；已有 CK 自动规则也不能覆盖此政策。"
    "重新启用须用户显式执行 enable-memory；解除 disabled 须显式 enable-memory --memory 并批准精确计划。"
    "Claude 和 WorkBuddy 项目入口只由各自实际使用时补齐，其他执行器不得预建；非 Git 目录和 linked worktree 不触发。"
)
CLAUDE_FALLBACK_TEXT = (
    "仅 Claude Code 在本项目实际使用且项目已启用、政策非 disabled 时补引用：CLAUDE.md 不存在才创建仅含 @AGENTS.md 的文件；"
    "已有正文必须完整保留，仅追加缺失的 @AGENTS.md 引用行，重复执行不改字节。"
)
WORKBUDDY_FALLBACK_TEXT = "仅 WorkBuddy 在本项目实际使用产生原生 .workbuddy/memory 目录，且项目已启用、政策非 disabled 时，补顶部 AGENTS.md 指针；保留已有正文字节，不预建原生目录。"
CODEX_FALLBACK_TEXT = "仅 Codex 首次实际使用时，按默认启用条款补缺失 AGENTS.md；已 disabled 项目不自动恢复。"


def agent_group_menu_text(code):
    """菜单文本;命令基路径为受管产品代码 C(layout.code),逐项映射既有 CLI。"""
    cli = "python3 %s/scripts/agm.py" % code
    installer = "python3 %s/scripts/install.py" % code
    return (
        "/mem-sharing 菜单:\n"
        "给项目启用记忆：为当前项目建立共享规则入口 → %s enable-memory --project <项目绝对路径> --memory\n"
        "添加新的 Agent：接入已安装的执行器 → %s --agent <执行器名>\n"
        "健康检查：只读检查已登记入口 → %s check-memory --project <项目绝对路径>\n"
        "停用记忆：撤入口并保留数据 → %s remove-memory --project <项目绝对路径>；仅禁自动项目经历记录、保留入口用 enable-memory --no-memory\n"
        "整理用户规则：公共与独有分开，逐条计划后一次批准 → 按 SKILL.md 治理流程执行\n"
        "批量启用记忆：扫描给定目录，汇总预览后一次批准 → %s enable-memory-batch --directory <目录绝对路径>\n"
        % (cli, installer, cli, cli, cli)
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

    def import_line(self, agent, path, line):
        """Plan the Claude-style @import reference (kind import, whole-file hash)."""
        oid = str(path) + "#import"
        existing = self.units.get((str(path), None))
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
        for obj in candidates:
            try:
                _require_real_parents(path, runtime.home)
                snap = read_snapshot(path)
                if snap.kind != "file":
                    reason = "entry_missing_or_not_file"
                    continue
                if obj["kind"] == "import" and config[agent]["rule_mode"] == "import_agents":
                    line = ("@" + str(runtime.root / "memories/MEMORY.md")).encode()
                    intact = sum(p.strip() == line for p in snap.data.splitlines()) == 1
                elif obj["kind"] in ("block", "user_convention") and config[agent]["rule_mode"] != "import_agents":
                    intact = _public_block_intact(snap.data, obj, runtime.root / "memories/MEMORY.md", agent)
                else:
                    intact = False
                if intact:
                    reason = None
                    break
                reason = "entry_drift_or_semantics_missing"
            except (ValueError, OSError):
                reason = "entry_unreadable_or_conflict"
        result[agent] = {"status": "connected" if reason is None else "pending", "reason": reason,
                         "runtime_acceptance": "pending"}
    return result


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
    governance = GOVERNANCE_RULES_TEXT
    menu = agent_group_menu_text(runtime.code)
    for agent in effective:
        entry = config[agent]
        user_path = Path(agm_paths.expand_path(entry["user_entry"], home=home))
        _require_real_parents(user_path, runtime.home)
        if entry["rule_mode"] == "user_convention":
            planner.marker_block(agent, user_path,
                                 _wrap_block(BASE_MARKER, "\n".join(
                                     [public_read_text(planner.memory_index), WORKBUDDY_CONVENTION_TEXT, governance,
                                      WORKBUDDY_FALLBACK_TEXT, menu])),
                                 "#convention", append_to_unblocked=True, note_label="user convention", update_registered=True)
        elif entry["rule_mode"] == "native":
            body = "\n".join([
                "开始任务前读取并遵守 %s;读不到就说明。" % planner.memory_index,
                governance, CODEX_FALLBACK_TEXT, menu])
            planner.marker_block(agent, user_path, _wrap_block(BASE_MARKER, body),
                                 "#public-source", append_to_unblocked=True, note_label="public-source block")
        elif entry["rule_mode"] == "import_agents":
            # Claude 经 @import 读公共源;治理条款与菜单由公共源文本承载。
            planner.import_line(agent, user_path, ("@" + str(planner.memory_index)).encode("utf-8"))
        else:  # pragma: no cover - 路径表枚举已限定 rule_mode
            raise UserEntryError("agents_table_invalid", "未知 rule_mode: %r" % entry["rule_mode"])
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
