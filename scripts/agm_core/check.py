"""只读 check-memory 命令体(M2-05)。

职责:项目装配状态报告(四态现场观测)、入口块存在/漂移、@AGENTS.md 引用、
AGENTS.override.md 告警、registry 对照、非引用规则增长告警、执行器安装信号(hint)、
--all 巡检矩阵(已纳管项目 × 已接入执行器)。
接入集以 registry 各项目 agents 的并集为依据,不使用目录安装 hint 扩大目标。

零写入合同(D7 / architecture §5):不 mkdir、不建锁(write_lock 仅写操作使用)、
不修漂移/补入口、不更新 registry 时间戳、不调用可能写缓存的 Keeper 探针——
第四态无法用只读证据判定时一律 unknown,不假装 ready。registry 缺失/损坏时仅在内存
重建可观察事实;--all 失去索引只报告范围不完整,不扫描未知项目,不宣称已巡检全部。

request/build_request 合同见 agm.py;返回 dict 的 status 仅用 completed/gaps/failed,
changes 恒为空(候选修复放 next_action),projects[] 每项含本模块定义的缺口清单 gaps[]:
{"code","agent","path","detail","suggestion"},suggestion ∈ enable/manual/null。
"""

from __future__ import annotations

import os
from . import layout
import stat as stat_module
from datetime import datetime, timezone
from pathlib import Path

from . import paths as agm_paths
from .entries import EntryConflict, block_fingerprint, managed_span, sha256, verify_link, free_project_rules, reference_span
from .project import ProjectError, resolve_project
from .registry import RegistryError, load_registry, require_installed

# 两对桥接标记与上游 install.py / templates/workbuddy-bridge.md 一致,仅用于
# 未登记现场的只读观察;已登记现场的权威标记来自 registry 对象。
BRIDGE_MARKERS = {
    "context-keeper": ("<!-- context-keeper:start -->", "<!-- context-keeper:end -->"),
    "mem-sharing": ("<!-- context-keeper:workbuddy:start -->", "<!-- context-keeper:workbuddy:end -->"),
}
ALL_MARKER_PAIRS = tuple(BRIDGE_MARKERS.values())
IMPORT_REFERENCE_LINE = b"@AGENTS.md"
OVERRIDE_BASENAME = "AGENTS.override.md"
SKILL_NAME = "context-keeper"

STATUS_COMPLETED = "completed"
STATUS_GAPS = "gaps"
STATUS_FAILED = "failed"

FACT_UNKNOWN_NOTE_WORKTREE = "worktree 未纳管(O1 未决,M2 仅主 checkout),现场事实 unknown"
RECLONE_LIMIT = "v1 无法识别同路径重 clone(architecture §2.4)"


def _utc_now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _fact(status, evidence=None):
    """输出用 Fact:沿用登记结构;unknown 可附'本次无法判明'的证据,其余必附证据。"""
    if status == "unknown" and evidence is None:
        return {"status": "unknown", "observed_at": None, "evidence": None}
    return {"status": status, "observed_at": _utc_now(), "evidence": evidence}


def _gap(code, detail, *, agent=None, path=None, suggestion=None):
    return {"code": code, "agent": agent, "path": path, "detail": detail, "suggestion": suggestion}


def _observe_path(path):
    """只读识别落点类型:('file', bytes)|('symlink',None)|('other',None)|('absent',None)。"""
    try:
        mode = os.lstat(path).st_mode
    except OSError:
        return "absent", None
    if stat_module.S_ISLNK(mode):
        return "symlink", None
    if stat_module.S_ISREG(mode):
        try:
            return "file", Path(path).read_bytes()
        except OSError:
            return "other", None
    return "other", None


def _reference_line_present(data):
    return any(line.strip() == IMPORT_REFERENCE_LINE for line in data.split(b"\n"))


def _marker_spans(data):
    """返回文件中恰好出现一次的标记对区间;异常/缺失的对不计入并附说明。"""
    spans, notes = [], []
    for start, end in ALL_MARKER_PAIRS:
        try:
            span = managed_span(data, start, end)
        except EntryConflict as exc:
            notes.append("%s…%s: %s" % (start, end, exc))
            continue
        if span is not None:
            spans.append(span)
    return spans, notes


def _load_registry_state(registry_path, allowed_user_paths):
    """只读加载 registry;失败不落盘、不重建,返回 (data|None, 原因说明)。"""
    if not os.path.isfile(registry_path):
        return None, "registry 文件不存在: %s" % registry_path
    try:
        return require_installed(load_registry(registry_path, allowed_user_paths=allowed_user_paths)), None
    except RegistryError as exc:
        return None, "registry 校验失败(损坏或含越界对象): %s" % exc


def _verify_objects(objects, shared_objects, checkout):
    """逐对象只读核对登记指纹;返回 (状态表, 对象观察列表, 块索引)。

    状态 ∈ ok/missing/drifted/blocked/baseline_changed/unverified:
    baseline_changed 指受管块完好而整文件基线指纹不符(块外增长/编辑),仅告警不缺口;
    unverified 指登记无指纹(所有权未知),只确认可观察事实,不产生缺口。
    """
    relevant = dict(objects)
    for oid, obj in shared_objects.items():
        if checkout in obj["consumers"]:
            relevant[oid] = obj
    statuses, observations = {}, []
    block_ids = {}  # path -> [oid] 受管块对象,供整文件对象区分块外变化
    for oid, obj in relevant.items():
        if obj["kind"] in ("block", "user_convention") and not free_project_rules(obj):
            block_ids.setdefault(obj["path"], []).append(oid)

    def observe(oid, obj, status, detail):
        statuses[oid] = status
        observations.append(
            {
                "id": oid,
                "kind": obj["kind"],
                "path": obj["path"],
                "scope": obj["scope"],
                "agents": list(obj["agents"]),
                "ownership": obj["ownership"],
                "status": status,
                "detail": detail,
            }
        )

    # 先核对受管块,整文件/引用对象的判定依赖块状态。
    ordered = sorted(relevant.items(), key=lambda kv: (0 if kv[1]["kind"] in ("block", "user_convention") else 1, kv[0]))
    for oid, obj in ordered:
        kind = obj["kind"]
        on_disk, data = _observe_path(obj["path"])
        if free_project_rules(obj):
            observe(oid,obj,"unverified","历史 AGENTS 基座属于项目自由规则,不守护正文或授予删除权")
            continue
        if kind in ("block", "user_convention"):
            if on_disk == "absent":
                observe(oid, obj, "missing", "承载文件缺失")
                continue
            if on_disk != "file":
                observe(oid, obj, "blocked", "承载文件不是普通文件(%s)" % on_disk)
                continue
            marker = obj["marker"]
            try:
                actual = block_fingerprint(data, marker["start"], marker["end"])
            except EntryConflict as exc:
                observe(oid, obj, "blocked", "标记异常: %s" % exc)
                continue
            if actual is None:
                observe(oid, obj, "missing", "受管块不存在(marker 未找到)")
                continue
            expected = (obj.get("fingerprint") or {}).get("value")
            if expected is None:
                observe(oid, obj, "unverified", "登记无指纹,仅确认块存在(所有权未知)")
            elif actual == expected:
                observe(oid, obj, "ok", "块指纹相符")
            else:
                observe(oid, obj, "drifted", "块指纹漂移")
        elif kind == "skill_symlink":
            if not os.path.lexists(obj["path"]):
                observe(oid, obj, "missing", "Skill 链接不存在")
                continue
            try:
                verify_link(obj["path"], obj["link_target"])
                observe(oid, obj, "ok", "链接指向与登记目标相符")
            except EntryConflict as exc:
                if not os.path.islink(obj["path"]):
                    observe(oid, obj, "blocked", "落点被普通文件/目录占用: %s" % exc)
                else:
                    observe(oid, obj, "drifted", str(exc))
        elif kind == "file":
            if on_disk == "absent":
                observe(oid, obj, "missing", "文件缺失")
                continue
            if on_disk != "file":
                observe(oid, obj, "blocked", "落点不是普通文件(%s)" % on_disk)
                continue
            expected = (obj.get("fingerprint") or {}).get("value")
            if expected is None:
                observe(oid, obj, "unverified", "登记无指纹,仅确认文件存在(所有权未知)")
            elif sha256(data) == expected:
                observe(oid, obj, "ok", "整文件指纹相符")
            else:
                sibling_blocks = block_ids.get(obj["path"], [])
                blocks_ok = bool(sibling_blocks) and all(
                    statuses.get(b) in ("ok", "unverified") for b in sibling_blocks
                )
                if sibling_blocks and blocks_ok:
                    observe(oid, obj, "baseline_changed", "整文件基线指纹不符,但同文件受管块完好(块外内容已变化)")
                else:
                    observe(oid, obj, "drifted", "整文件指纹不符")
        elif kind == "import":
            if on_disk == "absent":
                observe(oid, obj, "missing", "承载文件缺失,@AGENTS.md 引用无从核对")
                continue
            if on_disk != "file":
                observe(oid, obj, "blocked", "落点不是普通文件(%s)" % on_disk)
                continue
            try:
                span=reference_span(data)
            except EntryConflict as exc:
                observe(oid,obj,"blocked",str(exc));continue
            if obj.get("lifecycle"):
                if span is None:observe(oid,obj,"missing","受管引用行缺失")
                elif sha256(data[span[0]:span[1]])!=obj["fingerprint"]["value"]:observe(oid,obj,"drifted","受管引用行被编辑")
                else:observe(oid,obj,"ok","独立引用单元指纹相符,正文自由编辑")
                continue
            if span is None:
                observe(oid, obj, "missing", "@AGENTS.md 引用行缺失")
                continue
            expected = (obj.get("fingerprint") or {}).get("value")
            if expected is None:
                observe(oid, obj, "unverified", "引用行存在;登记无指纹")
            elif sha256(data) == expected:
                observe(oid, obj, "ok", "引用行存在,整文件指纹相符")
            else:
                observe(oid, obj, "baseline_changed", "引用行存在;整文件基线指纹不符(非引用内容已增长)")
        else:  # pragma: no cover - registry 校验已限定 kind 枚举
            observe(oid, obj, "unverified", "未知对象类型")
    return statuses, observations, block_ids


def _object_gaps(observations):
    gaps = []
    for item in observations:
        status, kind = item["status"], item["kind"]
        if status == "missing" and kind == "import":
            gaps.append(_gap("import_reference_missing", item["detail"], path=item["path"], suggestion="enable"))
        elif status == "missing":
            gaps.append(_gap("object_missing", item["detail"], path=item["path"], suggestion="enable"))
        elif status == "drifted":
            gaps.append(_gap("object_drifted", item["detail"], path=item["path"], suggestion="manual"))
        elif status == "blocked":
            gaps.append(_gap("object_conflict", item["detail"], path=item["path"], suggestion="manual"))
    return gaps


def _agent_objects(objects, shared_objects, checkout, agent):
    result = {}
    for oid, obj in objects.items():
        if agent in obj["agents"]:
            result[oid] = obj
    for oid, obj in shared_objects.items():
        if checkout in obj["consumers"] and agent in obj["agents"]:
            result[oid] = obj
    return result


def _bridge_fact(agent, platform_config, *, home, checkout, objects, statuses):
    entry = platform_config[agent]
    bridge_path = agm_paths.expand_path(entry["project_bridge_entry"], home=home, project=checkout)
    related = [
        (oid, obj)
        for oid, obj in objects.items()
        if obj["kind"] in ("block", "user_convention") and obj["path"] == bridge_path
        and obj.get("marker")==dict(zip(("start","end"),BRIDGE_MARKERS[entry["bridge_owner"]]))
    ]
    if related:
        states = [statuses.get(oid, "unverified") for oid, _ in related]
        if any(s in ("blocked",) for s in states):
            return _fact("blocked", "%s 标记/落点冲突: %s" % (agent, bridge_path)), bridge_path
        if any(s == "drifted" for s in states):
            return _fact("blocked", "%s 受管块指纹漂移: %s" % (agent, bridge_path)), bridge_path
        if any(s == "missing" for s in states):
            return _fact("missing", "%s 受管块缺失: %s" % (agent, bridge_path)), bridge_path
        return _fact("ready", "%s 桥接块就绪: %s" % (agent, bridge_path)), bridge_path
    on_disk, data = _observe_path(bridge_path)
    if on_disk == "absent":
        return _fact("missing", "%s 桥接入口文件不存在: %s" % (agent, bridge_path)), bridge_path
    if on_disk != "file":
        return _fact("blocked", "%s 桥接入口不是普通文件: %s" % (agent, bridge_path)), bridge_path
    start, end = BRIDGE_MARKERS[entry["bridge_owner"]]
    try:
        span = managed_span(data, start, end)
    except EntryConflict as exc:
        return _fact("blocked", "%s 桥接标记异常(%s): %s" % (agent, exc, bridge_path)), bridge_path
    if span is None:
        return _fact("missing", "%s 桥接块未找到(未登记现场仅观察标记): %s" % (agent, bridge_path)), bridge_path
    return _fact("ready", "%s 桥接标记存在(未登记,无登记指纹可核对): %s" % (agent, bridge_path)), bridge_path


def _skill_fact(agent, platform_config, *, home, checkout, objects, statuses):
    entry = platform_config[agent]
    roots = [agm_paths.expand_path(r, home=home, project=checkout) for r in entry["project_skill_roots"]]
    candidates = [Path(r) / SKILL_NAME for r in roots]
    found = [str(p) for p in candidates if p.is_dir() and (p / "SKILL.md").is_file()]
    broken = [str(p) for p in candidates if os.path.lexists(p) and str(p) not in found]
    related_bad = [
        oid
        for oid, obj in objects.items()
        if obj["kind"] == "skill_symlink" and statuses.get(oid) in ("drifted", "blocked")
    ]
    if related_bad:
        return _fact("blocked", "%s Skill 链接漂移/冲突: %s" % (agent, ", ".join(sorted(related_bad))))
    if broken:
        return _fact("blocked", "%s Skill 落点不可用(断链/非目录/缺 SKILL.md): %s" % (agent, "; ".join(broken)))
    if found:
        return _fact("ready", "%s Skill 已安装: %s" % (agent, "; ".join(found)))
    return _fact("missing", "%s Skill 根下未见 %s(检查根: %s)" % (agent, SKILL_NAME, "; ".join(roots)))


def _import_rule_warnings(agent, platform_config, *, home, checkout, objects):
    """import 模式入口文件的非引用规则增长告警(DESIGN §4.2 瘦身终态)。

    只读计算:受管块(登记对象或已知标记对)与裸 @AGENTS.md 引用行之外仍有
    非空白内容即告警;不修改任何字节。
    """
    entry = platform_config[agent]
    if entry["rule_mode"] != "import_agents":
        return []
    rule_path = agm_paths.expand_path(entry["project_rule_entry"], home=home, project=checkout)
    on_disk, data = _observe_path(rule_path)
    if on_disk != "file" or data is None:
        return []
    spans = []
    for oid, obj in objects.items():
        if obj["path"] == rule_path and obj["kind"] in ("block", "user_convention"):
            try:
                span = managed_span(data, obj["marker"]["start"], obj["marker"]["end"])
            except EntryConflict:
                span = None
            if span is not None:
                spans.append(span)
    if not spans:
        spans, _notes = _marker_spans(data)
    remainder = bytearray(data)
    for left, right in sorted(spans, reverse=True):
        del remainder[left:right]
    kept = [line for line in bytes(remainder).split(b"\n") if line.strip() != IMPORT_REFERENCE_LINE]
    if b"".join(kept).strip():
        return [
            "rule_growth: %s 在受管块与 @AGENTS.md 引用行之外仍有 %d 字节非引用内容,请人工核对"
            % (rule_path, len(b"\n".join(kept).strip()))
        ]
    return []


def _override_warnings(project_root, home):
    warnings = []
    candidates = [
        ("项目根", os.path.join(project_root, OVERRIDE_BASENAME)),
        ("用户级 Codex", os.path.join(home, ".codex", OVERRIDE_BASENAME)),
    ]
    for label, path in candidates:
        if os.path.lexists(path):
            warnings.append(
                "override_present: %s 存在 %s,可能劫持执行器规则链,请人工核对(AGM 不代改)" % (label, path)
            )
    return warnings


def _entry_warnings(agents, platform_config, *, home, checkout):
    """只检查表列根入口,不遍历私有记忆或子目录;预算是风险提示而非运行验收。"""
    warnings = []
    for agent in agents:
        entry = platform_config[agent]
        path = agm_paths.expand_path(entry["project_rule_entry"], home=home, project=checkout)
        kind, data = _observe_path(path)
        if kind == "file":
            if agent == "codex" and len(data) >= 32 * 1024:
                warnings.append("entry_budget: %s 已达 32KiB;仅根入口即达到默认规则预算,祖先/子目录链未统计" % path)
            if agent == "claude" and len(data.splitlines()) >= 200:
                warnings.append("entry_budget: %s 已达 200 行建议预算,请人工精简" % path)
        if entry["rule_mode"] == "user_convention":
            user_path = agm_paths.expand_path(entry["user_entry"], home=home)
            user_kind, user_data = _observe_path(user_path)
            if user_kind == "file":
                text = user_data.decode("utf-8", "replace")
                if "AGENTS.md" in text and "唯一" in text and "context-keeper" not in text:
                    warnings.append("workbuddy_convention_review: %s 含旧的唯一规则来源表述且未见 context-keeper 例外,请人工核对桥接冲突(不输出正文)" % user_path)
    return warnings


def _discovery(platform_config, *, home, checkout):
    hints = agm_paths.installation_hints(platform_config, home=home, project=checkout)
    by_agent = {}
    for hint in hints:
        by_agent.setdefault(hint["agent"], []).append(
            {"kind": hint["kind"], "path": hint["path"], "strength": hint["strength"], "exists": hint["exists"]}
        )
    return [
        {"agent": agent, "signals": by_agent.get(agent, [])} for agent in agm_paths.AGENT_ORDER if agent in by_agent
    ]


def _empty_states(agents, note):
    return {
        "source_available": _fact("unknown", note),
        "skill_installed": {agent: _fact("unknown", note) for agent in agents},
        "bridge_assembled": {agent: _fact("unknown", note) for agent in agents},
        "store_authorized_ready": _fact("unknown", note),
    }


def _store_fact_and_gaps(project_entry, assembly):
    """第四态只读判定:不调用 Keeper 探针,证据不足一律 unknown(architecture §2.3)。"""
    if project_entry is None:
        return _fact("unknown", "项目未登记,记忆授权与库状态未知"), []
    auth = project_entry["memory_authorization"]
    store = assembly["store"] if assembly else None
    if auth is None:
        return _fact("unknown", "项目记忆授权未登记(null)"), []
    if auth == "no":
        return (
            _fact("blocked", "memory_authorization=no(登记):check 以缺口说明记忆未启用"),
            [_gap("memory_not_enabled", "用户已选择 no,记忆档未启用;如需启用须用户明确授权 --memory", suggestion="manual")],
        )
    if store is None or not store["location_approved"] or store["path"] is None:
        return (
            _fact("blocked", "记忆位置未获批(location_approved=false 或 path=null)"),
            [_gap("store_location_unapproved", "授权 yes 但记录库位置未获批", suggestion="manual")],
        )
    path = store["path"]
    if not os.path.isdir(path):
        return (
            _fact("missing", "获批记录库位置不存在: %s" % path),
            [_gap("store_missing", "获批记录库位置不存在: %s" % path, path=path, suggestion="manual")],
        )
    return (
        _fact("unknown", "库目录存在: %s;只读检查不调用可能写缓存的 Keeper 探针,无法判定库可用/迁移状态" % path),
        [],
    )


def _runtime_output(assembly, object_gaps, warnings):
    runtime = dict(assembly["runtime_acceptance"]) if assembly else {"status": "pending", "evidence_path": None}
    if assembly and object_gaps and runtime["status"] != "pending":
        warnings.append(
            "runtime_invalidated: 登记 runtime_acceptance=%s,但现场检查存在缺口,输出降为 pending(不改登记)"
            % runtime["status"]
        )
        return {"status": "pending", "evidence_path": None}
    return runtime


def _observe_project(
    *,
    identity,
    main,
    project_entry,
    assembly,
    shared_objects,
    registered,
    platform_config,
    home,
    matrix_agents=None,
):
    """单个项目的只读巡检;identity 为 None 表示现场目录已不可用(移动/重 clone)。"""
    checkout = str(identity.checkout) if identity is not None else main
    if assembly is not None:
        agents = list(assembly["agents"])
    elif identity is None and project_entry is not None:
        agents = list(project_entry["checkouts"][main]["agents"])
    else:
        agents = list(agm_paths.AGENT_ORDER)
    registered_agents = list(agents)
    if matrix_agents is not None:
        agents = list(matrix_agents)
    gaps, warnings, evidence = [], [], []
    objects = dict(assembly["objects"]) if assembly else {}
    report = {
        "main_checkout": main,
        "checkout": checkout,
        "registered": registered,
        "worktree": bool(identity is not None and not identity.is_main),
        "agents": agents,
        "states": {},
        "runtime_acceptance": {"status": "pending", "evidence_path": None},
        "objects": [],
        "agent_discovery": _discovery(platform_config, home=home, checkout=checkout or None),
        "gaps": gaps,
        "warnings": warnings,
        "evidence": evidence,
    }
    if identity is None:
        report["states"] = _empty_states(agents, "现场 Git 仓库不可用,无法观测")
        gaps.append(
            _gap(
                "checkout_missing",
                "登记 main_checkout 不是可用 Git 仓库(可能被移动/重 clone);%s" % RECLONE_LIMIT,
                path=main,
                suggestion="manual",
            )
        )
        return report
    if report["worktree"]:
        report["states"] = _empty_states(agents, FACT_UNKNOWN_NOTE_WORKTREE)
        gaps.append(
            _gap(
                "worktree_unsupported",
                "当前检出是 linked worktree,主 checkout 为 %s;M2 仅支持主 checkout(O1 未决)" % main,
                path=checkout,
                suggestion="manual",
            )
        )
        return report
    if not registered:
        gaps.append(
            _gap("project_unregistered", "项目未登记于 registry;现场观察仅含未纳管事实,所有权未知", path=main, suggestion="enable")
        )
    if assembly is not None:
        for agent in agents:
            if agent not in registered_agents:
                gaps.append(_gap("agent_not_assembled", "执行器已在其他纳管项目接入,本项目尚未登记装配", agent=agent, suggestion="enable"))
    if assembly is not None and str(identity.git_common_dir) != assembly["git_common_dir"]:
        gaps.append(
            _gap(
                "identity_mismatch",
                "现场 git common-dir(%s)与登记(%s)不符,可能被移动/重 clone;%s"
                % (identity.git_common_dir, assembly["git_common_dir"], RECLONE_LIMIT),
                path=main,
                suggestion="manual",
            )
        )
    warnings.append("identity_limit: %s;已知更换实例需重新核对授权" % RECLONE_LIMIT)

    statuses, observations, _block_ids = _verify_objects(
        objects, shared_objects, checkout
    )
    report["objects"] = observations
    obj_gaps = _object_gaps(observations)
    gaps.extend(obj_gaps)

    # 四态现场观测(不信任登记时间戳,逐项重新只读核实)。
    if project_entry is not None and project_entry.get("provider_source"):
        provider = project_entry["provider_source"]
        required=[Path(provider)/'SKILL.md',Path(provider)/'scripts/install.py',Path(provider)/'scripts/context_keeper_probe.py']
        absent=[p for p in required if _observe_path(str(p))[0]=='absent']
        invalid=[p for p in required if _observe_path(str(p))[0] not in ('absent','file') or p.is_symlink() or p.resolve()!=p]
        if absent:
            source_fact=_fact('missing','provider 必需文件缺失: '+', '.join(map(str,absent)))
            for p in absent:gaps.append(_gap('source_missing','provider 必需文件缺失',path=str(p),suggestion='manual'))
        elif invalid:
            source_fact=_fact('blocked','provider 必需文件类型/链接异常: '+', '.join(map(str,invalid)))
            for p in invalid:gaps.append(_gap('source_invalid','provider 必需文件不是可信普通文件',path=str(p),suggestion='manual'))
        else:
            try:
                from .enable import _source_fingerprints,_source_evidence
                fingerprints=_source_fingerprints(Path(provider))
                expected=assembly['states']['source_available']['evidence'] if assembly else None
                if expected and expected.startswith('Keeper source sha256:') and expected!=_source_evidence(fingerprints):
                    raise ValueError('provider 与已批准源码指纹不同')
                source_fact=_fact('ready','provider 最低文件集、Git 身份与可用批准指纹只读核验: '+provider)
            except (ValueError,OSError) as exc:
                source_fact=_fact('blocked',str(exc));gaps.append(_gap('source_invalid',str(exc),path=provider,suggestion='manual'))
    else:
        source_fact = _fact("unknown", "未登记 provider 源码位置" if project_entry is not None else "项目未登记,源码位置未知")

    skill_facts, bridge_facts = {}, {}
    for agent in agents:
        agent_objects = _agent_objects(objects, shared_objects, checkout, agent)
        skill_facts[agent] = _skill_fact(agent, platform_config, home=home, checkout=checkout, objects=agent_objects, statuses=statuses)
        bridge_fact, bridge_path = _bridge_fact(agent, platform_config, home=home, checkout=checkout, objects=agent_objects, statuses=statuses)
        memory_denied=project_entry is not None and project_entry.get("memory_authorization")=="no"
        if memory_denied:bridge_fact=_fact("blocked","本项目自动记忆授权为 no;历史桥接/Skill 不授予自动写入权限")
        bridge_facts[agent] = bridge_fact
        # 对象级缺口已定位到路径时不重复报事实级缺口;未登记现场没有对象可依,才报事实级。
        agent_gap_paths = {
            item["path"]
            for item in observations
            if agent in item["agents"] and item["status"] in ("missing", "drifted", "blocked")
        }
        skill_object_gap = any(
            agent in item["agents"] and item["kind"] == "skill_symlink"
            and item["status"] in ("missing", "drifted", "blocked") for item in observations
        )
        if not memory_denied and skill_facts[agent]["status"] in ("missing", "blocked") and not skill_object_gap:
            blocked = skill_facts[agent]["status"] == "blocked"
            gaps.append(_gap("skill_conflict" if blocked else "skill_missing", skill_facts[agent]["evidence"], agent=agent, suggestion="manual" if blocked else "enable"))
        if not memory_denied and bridge_fact["status"] == "missing" and bridge_path not in agent_gap_paths:
            gaps.append(_gap("bridge_missing", bridge_fact["evidence"], agent=agent, path=bridge_path, suggestion="enable"))
        elif not memory_denied and bridge_fact["status"] == "blocked" and bridge_path not in agent_gap_paths:
            gaps.append(_gap("bridge_conflict", bridge_fact["evidence"], agent=agent, path=bridge_path, suggestion="manual"))
        entry = platform_config[agent]
        rule_path = agm_paths.expand_path(entry["project_rule_entry"], home=home, project=checkout)
        rule_kind, _ = _observe_path(rule_path)
        if rule_kind != "file" and rule_path not in agent_gap_paths and not any(
            g["code"] == "rule_entry_unavailable" and g["path"] == rule_path for g in gaps
        ):
            gaps.append(_gap("rule_entry_unavailable", "规则入口缺失或不是普通文件", agent=agent, path=rule_path, suggestion="enable" if rule_kind == "absent" else "manual"))
        if entry["rule_mode"] == "import_agents":
            kind, data = _observe_path(rule_path)
            if (kind != "file" or not _reference_line_present(data)) and not any(
                g["code"] == "import_reference_missing" and g["path"] == rule_path for g in gaps
            ):
                gaps.append(_gap("import_reference_missing", "入口缺少可核对的 @AGENTS.md 引用行", agent=agent, path=rule_path, suggestion="enable" if kind in ("file", "absent") else "manual"))
        warnings.extend(_import_rule_warnings(agent, platform_config, home=home, checkout=checkout, objects=agent_objects))

    store_fact, store_gaps = _store_fact_and_gaps(project_entry, assembly)
    if any(g["code"] == "identity_mismatch" for g in gaps):
        store_fact = _fact("blocked", "Git 身份失配,登记授权不适用于当前 checkout;须人工核对")
    gaps.extend(store_gaps)
    report["states"] = {
        "source_available": source_fact,
        "skill_installed": skill_facts,
        "bridge_assembled": bridge_facts,
        "store_authorized_ready": store_fact,
    }
    report["runtime_acceptance"] = _runtime_output(assembly, bool(gaps), warnings)
    warnings.extend(_override_warnings(checkout, home))
    warnings.extend(_entry_warnings(agents, platform_config, home=home, checkout=checkout))
    evidence.extend(
        [
            fact["evidence"]
            for fact in [source_fact, store_fact]
            + list(skill_facts.values())
            + list(bridge_facts.values())
            if fact.get("evidence")
        ]
    )
    return report


def _shared_objects_for(registry, main):
    if registry is None:
        return {}
    return {
        oid: obj
        for oid, obj in registry["shared_objects"].items()
        if main in obj["consumers"]
    }


def _inspect_single(identity, registry, platform_config, home):
    main = str(identity.main_checkout)
    registered = None if registry is None else (main in registry["projects"])
    project_entry = registry["projects"].get(main) if registry is not None else None
    assembly = project_entry["checkouts"][main] if project_entry is not None else None
    return _observe_project(
        identity=identity,
        main=main,
        project_entry=project_entry,
        assembly=assembly,
        shared_objects=_shared_objects_for(registry, main),
        registered=registered,
        platform_config=platform_config,
        home=home,
    )


def _inspect_registered_entry(main, registry, platform_config, home, matrix_agents=None):
    project_entry = registry["projects"][main]
    try:
        identity = resolve_project(Path(main), allow_worktree=True)
    except ProjectError:
        identity = None
    assembly = None
    if identity is not None and identity.is_main:
        assembly = project_entry["checkouts"][main]
    return _observe_project(
        identity=identity,
        main=main,
        project_entry=project_entry,
        assembly=assembly,
        shared_objects=_shared_objects_for(registry, main),
        registered=True,
        platform_config=platform_config,
        home=home,
        matrix_agents=matrix_agents,
    )


def run(request):
    """check-memory 命令体入口;合同与零写入边界见模块 docstring。"""
    platform_config = request["platform_config"]
    home = request["home"]
    try:
        runtime = layout.from_request(request)
    except ValueError as exc:
        return {"status": STATUS_FAILED, "projects": [], "changes": [], "warnings": [],
                "errors": [{"code": getattr(exc, "code", "runtime_layout_invalid"), "path": None,
                            "message": str(exc), "recovery": None}], "approval_required": False, "next_action": None}
    registry_path = runtime.registry
    allowed = agm_paths.allowed_user_paths(platform_config, None, home=home)
    registry, registry_problem = _load_registry_state(registry_path, allowed)

    projects, warnings, errors = [], [], []
    coverage_gap = False

    if request.get("all"):
        if registry is None:
            coverage_gap = True
            warnings.append(
                "check_scope_incomplete: registry 不可用(%s);--all 失去项目索引,不扫描未知项目,不能宣称已巡检全部"
                % registry_problem
            )
        else:
            # 接入依据为 registry 中明确的目标集,目录安装 hint 不扩大矩阵。
            connected = {a for p in registry["projects"].values() for c in p["checkouts"].values() for a in c["agents"]}
            matrix_agents = [a for a in agm_paths.AGENT_ORDER if a in connected]
            if not registry["projects"]:
                warnings.append("registry 无已登记项目,--all 巡检范围为空")
            for main in sorted(registry["projects"]):
                projects.append(_inspect_registered_entry(main, registry, platform_config, home, matrix_agents))
    else:
        raw_project = request.get("project")
        try:
            identity = resolve_project(Path(raw_project) if raw_project else None, allow_worktree=True)
        except ProjectError as exc:
            return {
                "runtime_layout": runtime.describe(),
                "status": STATUS_FAILED,
                "projects": [],
                "changes": [],
                "warnings": [],
                "errors": [
                    {
                        "code": getattr(exc, "code", "project_invalid"),
                        "path": raw_project,
                        "message": "无法定位项目 Git 根(只读检查未执行): %s" % exc,
                        "recovery": "确认 --project 指向 Git 根,或在仓库目录内运行",
                    }
                ],
                "approval_required": False,
                "next_action": "修正项目路径后重试",
            }
        report = _inspect_single(identity, registry, platform_config, home)
        if registry is None:
            warnings.append(
                "registry_unavailable: %s;仅输出内存现场观察,所有权未知,不落盘不重建" % registry_problem
            )
            report["gaps"].append(
                _gap("registry_unavailable", "%s;仅输出内存现场观察,所有权未知,不落盘不重建" % registry_problem,
                     path=str(registry_path), suggestion="manual")
            )
        projects.append(report)

    for report in projects:
        prefix = Path(report["main_checkout"]).name or report["main_checkout"]
        for note in report["warnings"]:
            warnings.append("%s: %s" % (prefix, note))
    any_gap = coverage_gap or any(report["gaps"] for report in projects)
    next_action = None
    if any_gap:
        next_action = (
            "check 发现缺口:suggestion=enable 的缺失项可运行 enable-memory 修复(写命令需授权/批准文件),"
            "drifted/conflict/manual 项先人工核对;缺口清单见 projects[].gaps"
        )
    return {
        "runtime_layout": runtime.describe(),
        "status": STATUS_GAPS if any_gap else STATUS_COMPLETED,
        "projects": projects,
        "changes": [],
        "warnings": warnings,
        "errors": errors,
        "approval_required": False,
        "next_action": next_action,
    }
