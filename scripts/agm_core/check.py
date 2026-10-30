"""Read-only project-entry inspection with ownership and byte-drift evidence.

CK availability, source code and record-store state belong to CK. A disabled
policy is an intentional state, never a health gap. No locks, caches or writes.
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
from .registry import RegistryError, RegistryMigrationRequired, load_registry, load_diagnostic_registry, require_installed

# Current memSharing protocol markers; registered objects remain authoritative.
BRIDGE_MARKERS = {
    "project-experience": ("<!-- mem-sharing:project-experience:start -->", "<!-- mem-sharing:project-experience:end -->"),
    "project-rules": ("<!-- mem-sharing:project-rules:start -->", "<!-- mem-sharing:project-rules:end -->"),
}
ALL_MARKER_PAIRS = tuple(BRIDGE_MARKERS.values())
IMPORT_REFERENCE_LINE = b"@AGENTS.md"
OVERRIDE_BASENAME = "AGENTS.override.md"

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
    except RegistryMigrationRequired:
        try:
            historical = load_diagnostic_registry(registry_path, allowed_user_paths=allowed_user_paths)
            return None, "schema=%s read-only diagnosis; preserve historical bytes and reinstall; pre-release migration unsupported" % historical["schema_version"]
        except RegistryError as exc:
            return None, "historical registry strict diagnosis failed: %s" % exc
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
                    warnings.append("workbuddy_convention_review: %s 含旧的唯一规则来源表述，请人工核对项目经历协议(不输出正文)" % user_path)
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
    return {'entries': {a: _fact('unknown', note) for a in agents}}


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

    report["memory_policy"] = project_entry["memory_policy"] if project_entry else None
    # CK availability and store contents belong to CK, never health gaps here.
    for agent in agents:
        agent_objects = _agent_objects(objects, shared_objects, checkout, agent)
        rule_path = agm_paths.expand_path(platform_config[agent]["project_rule_entry"], home=home, project=checkout)
        if agent == 'claude' and assembly is not None and not any(
                obj['kind'] == 'import' and obj['path'] == rule_path for obj in agent_objects.values()):
            continue  # Installed but not yet explicitly used/assembled in this project.
        if agent == 'workbuddy' and not (Path(checkout)/'.workbuddy/memory').exists():
            warnings.append('WorkBuddy pointer pending actual use; native directory is not created by memSharing')
            continue
        # disabled may be a deliberately removed project; only retained guard objects are checked.
        if report['memory_policy'] != 'disabled':
            kind, raw = _observe_path(rule_path)
            if kind != 'file':
                gaps.append(_gap('rule_entry_unavailable','Rule entry missing or conflicting',agent=agent,path=rule_path,suggestion='enable' if kind=='absent' else 'manual'))
            elif platform_config[agent]['rule_mode']=='import_agents' and not _reference_line_present(raw):
                gaps.append(_gap('import_reference_missing','Missing @AGENTS.md reference',agent=agent,path=rule_path,suggestion='enable'))
        warnings.extend(_import_rule_warnings(agent,platform_config,home=home,checkout=checkout,objects=agent_objects))
    report['states'] = {'entries': {item['path']:item['status'] for item in observations}}
    report['runtime_acceptance'] = _runtime_output(assembly,bool(gaps),warnings)
    warnings.extend(_override_warnings(checkout,home))
    warnings.extend(_entry_warnings(agents,platform_config,home=home,checkout=checkout))
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
