"""M4-05: machine-level user entry planning and approved assembly.

One planner serves both first install and later agent accession (决策单 §7.2):
only executors detected as installed get user entries and the product Skill
projection; absent/unknown agents are reported and never written; an explicitly
requested agent that is not installed stops the whole request before any write.

Templates reuse the existing M2/M3 semantics instead of a second dialect:
- WorkBuddy 用户约定: enable.py 的既有 user_convention 文本与 BASE_MARKER(测试锁定
  两处文本一致);
- Codex 用户级公共源块(native): 同一 BASE_MARKER 机制,追加“开工先读公共记忆”指针块
  (DESIGN §4.8),指向本机公共源索引 R/memories/MEMORY.md;
- Claude @import(import_agents): 复用 enable.py 的引用行语义,引用同一公共源索引;
- 产品自身 Skill 投影: H/<agent>/skills/agent-group-memory → C(layout.code),
  已有同目标链接复用,异目标链接/复制目录冲突整单停写,不 repoint。

Managed-block semantics for registered machine units: on-disk bytes differing
from the registered fingerprint is drift and stops the whole order (no template
"repair" over registered content); a vanished block is recreated only when the
registered content is the template itself; unregistered existing blocks are
registered byte-preserving (reused) without rewriting.

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
from datetime import datetime, timezone
from pathlib import Path

from . import detect as detect_module
from . import layout as layout_module
from . import paths as agm_paths
from . import registry as registry_module
from .enable import BASE_MARKER
from .entries import (EntryConflict, block_fingerprint, link_fingerprint,
                      sha256, verify_link)
from .transaction import (Change, Snapshot, Transaction, TransactionError,
                          read_snapshot, write_lock)

COMMAND = "assemble-user-entries"
# enable.py 的既有 WorkBuddy 用户约定文本(读它复用,不另造第二份);测试锁定一致。
WORKBUDDY_CONVENTION_TEXT = "项目规则读取当前项目根 AGENTS.md。保留已有公共源与用户约定。"


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
    # 与 layout.validate_paths 同口径,但只检查父目录链:叶子本身允许是受管符号链接
    # (Skill 投影)或普通文件;入口文件的叶子类型由 read_snapshot 的冲突检查把关。
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
    scope); a drifted managed block or a foreign Skill link stops everything.
    """
    problems = []
    for obj in ledger["machine"]["objects"].values():
        snap = read_snapshot(obj["path"])
        if obj["kind"] in ("block", "user_convention"):
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
        elif obj["kind"] == "skill_symlink":
            if not Path(obj["path"]).exists() and not Path(obj["path"]).is_symlink():
                continue
            try:
                verify_link(obj["path"], obj["link_target"])
            except EntryConflict as exc:
                problems.append("%s: %s" % (obj["path"], exc))
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
                    target=None, original_existed=None):
        if kind == "skill_symlink":
            basis = "link_target"
        elif kind in ("block", "user_convention"):
            basis = "block_bytes"
        else:
            basis = "file_bytes"
        created = ownership == "created"
        if original_existed is None:
            original_existed = not created
        return {
            "kind": kind, "path": str(path), "scope": "machine", "agents": [agent],
            "ownership": ownership, "marker": marker,
            "fingerprint": None if value is None else
                {"algorithm": "sha256", "basis": basis, "value": value},
            "original_existed": original_existed,
            "link_target": str(target) if target else None,
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

    def marker_block(self, agent, path, block, oid_suffix, *, append_to_unblocked, note_label):
        """Plan one BASE_MARKER managed block (codex public-source / workbuddy convention)."""
        existing = self.units.get((str(path), BASE_MARKER["start"]))
        if existing is not None and existing["scope"] == "user":
            self._verify_shared_unit(existing, path)
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
            self._adopt_existing(oid, existing, agent=agent,
                                 fingerprint=None if trusted is not None else
                                 {"algorithm": "sha256", "basis": "block_bytes", "value": actual})
            return
        if actual is not None:
            # Unregistered existing block: register its actual bytes, zero write.
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
                    "drift", "已登记共享引用单元缺失引用行: %s;修复属项目层,机器装配不代写" % path)
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
                "drift", "已登记共享用户约定缺失: %s;修复属项目 enable/check,机器装配不代写" % path)
        trusted = (obj.get("fingerprint") or {}).get("value")
        if trusted is not None and actual != trusted:
            raise UserEntryError("drift", "共享受管块漂移,整单停写: " + str(path))

    def skill_projection(self, agent):
        code = self.runtime.code
        if not (code / "SKILL.md").is_file():
            raise UserEntryError(
                "product_code_missing",
                "产品代码源缺失,无法投影 Skill: %s;先完成/修复机器安装" % code)
        for raw in agm_paths.user_skill_paths(self.config, [agent], home=str(self.runtime.home)):
            path = Path(raw)
            _require_real_parents(path, self.runtime.home)
            oid = str(path) + "#skill"
            registered = None
            for obj in self.units.values():
                if obj["kind"] == "skill_symlink" and obj["path"] == str(path):
                    registered = obj
                    break
            # read_snapshot 对目录抛 path_conflict,先给出投影位专属的明确冲突语义
            if path.is_dir() and not path.is_symlink():
                raise UserEntryError(
                    "entry_conflict",
                    "Skill 投影位被复制目录/文件占用: " + str(path) + ";整单停写")
            snap = self.snapshot(path)
            if registered is not None and registered["scope"] == "user":
                self._verify_shared_link(registered, path)
                continue
            if registered is not None:
                self._verify_shared_link(registered, path)  # machine unit: same strictness
                self._adopt_existing(oid, registered, agent=agent)
                continue
            if snap.kind == "symlink":
                resolved = str(path.resolve())
                if resolved != str(code.resolve()):
                    raise UserEntryError(
                        "entry_conflict",
                        "Skill 投影位已有异目标链接: %s -> %s(预期 %s);整单停写"
                        % (path, resolved, code))
                self.objects[oid] = self._new_object(oid, "skill_symlink", path, agent, "reused",
                                                     target=code.resolve(),
                                                     value=link_fingerprint(code.resolve()))
                self.notes.append("reused existing same-target skill link: " + str(path))
                continue
            if snap.kind != "absent":
                raise UserEntryError(
                    "entry_conflict",
                    "Skill 投影位被复制目录/文件占用: " + str(path) + ";整单停写")
            self.after[path] = Change.symlink(path, code, expected=snap).after
            self.objects[oid] = self._new_object(oid, "skill_symlink", path, agent, "created",
                                                 target=code.resolve(),
                                                 value=link_fingerprint(code.resolve()))

    @staticmethod
    def _verify_shared_link(obj, path):
        try:
            verify_link(path, obj["link_target"])
        except EntryConflict as exc:
            raise UserEntryError("drift", "已登记 Skill 链接漂移/冲突,整单停写: %s (%s)" % (path, exc)) from exc

    # ---- outputs -----------------------------------------------------------

    def changes(self):
        result = []
        for path, snap in sorted(self.before.items(), key=lambda kv: str(kv[0])):
            after = self.after[path]
            if after == snap:
                continue
            if after.kind == "symlink":
                result.append(Change.symlink(path, after.target, expected=snap))
            else:
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
    ledger, registry_snap = _load_ledger(runtime, allowed)
    if ledger is not None:
        _preflight_machine_units(ledger)
    planner = _Planner(config=config, runtime=runtime, ledger=ledger,
                       detection=detection, effective=effective, transaction=transaction)
    for agent in effective:
        entry = config[agent]
        user_path = Path(agm_paths.expand_path(entry["user_entry"], home=home))
        _require_real_parents(user_path, runtime.home)
        if entry["rule_mode"] == "user_convention":
            planner.marker_block(agent, user_path,
                                 _wrap_block(BASE_MARKER, WORKBUDDY_CONVENTION_TEXT),
                                 "#convention", append_to_unblocked=False, note_label="user convention")
        elif entry["rule_mode"] == "native":
            body = "开始任务前读取并遵守 %s;读不到就说明。" % planner.memory_index
            planner.marker_block(agent, user_path, _wrap_block(BASE_MARKER, body),
                                 "#public-source", append_to_unblocked=True, note_label="public-source block")
        elif entry["rule_mode"] == "import_agents":
            planner.import_line(agent, user_path, ("@" + str(planner.memory_index)).encode("utf-8"))
        else:  # pragma: no cover - 路径表枚举已限定 rule_mode
            raise UserEntryError("agents_table_invalid", "未知 rule_mode: %r" % entry["rule_mode"])
        planner.skill_projection(agent)
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
            "机器台账缺失: %s;用户级装配由安装器在机器安装完成后执行" % runtime.registry)
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
                           "无待装配差异:请求的 installed 执行器均已接入,零写入"])
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
    result["warnings"].append("runtime acceptance pending: 用户级指针/Skill 是否被新会话读取未验证")
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
