"""Exact-plan project rules and CK protocol assembly; never invokes CK."""
import copy
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from . import entries, paths, project, registry, layout, detect
from .transaction import Change, Snapshot, Transaction, TransactionError, read_snapshot, write_lock

LEGACY_KEEPER_MARKER = {"start": "<!-- context-keeper:start -->", "end": "<!-- context-keeper:end -->"}
KEEPER_MARKER = {"start": "<!-- mem-sharing:project-experience:start -->", "end": "<!-- mem-sharing:project-experience:end -->"}
BASE_MARKER = {"start": "<!-- mem-sharing:rules:start -->", "end": "<!-- mem-sharing:rules:end -->"}
LEGACY_WORKBUDDY_MARKER = {"start": "<!-- context-keeper:workbuddy:start -->", "end": "<!-- context-keeper:workbuddy:end -->"}
WORKBUDDY_MARKER = {"start": "<!-- mem-sharing:project-rules:start -->", "end": "<!-- mem-sharing:project-rules:end -->"}
DENIED_MARKER = {"start":"<!-- mem-sharing:memory-denied:start -->", "end":"<!-- mem-sharing:memory-denied:end -->"}
DENIED_TEXT = "本项目已撤销自动记忆授权。本段优先于本文件中的历史 context-keeper 桥接和 Skill 触发说明：不得自动记录本项目经历、初始化或建库，不得因残留 Skill/桥接恢复旧授权；Context Keeper 安装与已有记录库保留；手动 Context Keeper 操作仍按用户明确请求与 Context Keeper 自身流程执行。只有用户重新明确批准本项目 enable-memory --memory 后才可恢复自动记录。"

EXCEPTION_MARKER = {"start": "<!-- mem-sharing:keeper-exception:start -->", "end": "<!-- mem-sharing:keeper-exception:end -->"}


class EnableError(ValueError):
    def __init__(self, code, message, status="failed"):
        super().__init__(message)
        self.code, self.status = code, status


def _now():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _fact(status, evidence):
    return {"status": status, "observed_at": _now(), "evidence": str(evidence)}


def _block(marker, body):
    return (marker["start"] + "\n" + body + "\n" + marker["end"]).encode("utf-8")


def _marker_args(marker):
    return {"start": marker["start"], "end": marker["end"]}


EXPERIENCE_TEXT = ("位置：项目经历记录库由 Context Keeper 管理，默认位于 docs/context-keeper/。\n"
                   "入口：使用 /context-keeper，首次保存按 Context Keeper 流程确认位置并初始化。\n"
                   "职责：命令、记录格式、保存与查找流程由 Context Keeper 自行定义。")


class _Plan:
    def __init__(self, assembly, shared, root, tx):
        self.assembly, self.shared, self.root, self.tx = assembly, shared, root, tx
        self.before, self.after = {}, {}
        self.retired_ids = set()

    def snapshot(self, path):
        path = Path(path)
        if path not in self.before:
            self.before[path] = read_snapshot(path)
            self.after[path] = self.before[path]
        return self.after[path]

    def object(self, path, suffix, agents, kind, *, marker=None, block=None, target=None, scope="project", top=False):
        """Plan shared drift for review without granting ownership override.

        A created unit's external drift is still rejected by registry commit,
        even with exact-plan approval. Recovery requires manual inspection and
        restoration of the registered bytes, or a separately reviewed remove
        and re-enable; approval here never bypasses that ownership guard.
        """
        path = Path(path)
        objects = self.shared if scope == "user" else self.assembly["objects"]
        oid = str(path) + suffix
        if oid in self.retired_ids: oid += "-replacement"
        old = objects.get(oid)
        if old is not None and (old["kind"] != kind or old["marker"] != marker):
            oid = str(path) + suffix + "-unit"
            old = objects.get(oid)
            if old is not None and (old["kind"] != kind or old["marker"] != marker):
                raise EnableError("registry_invalid", "Object ID conflicts with a different managed unit")
        # Reuse existing ledger unit even when its historic ID has another suffix.
        matches = [(key, obj) for key, obj in objects.items() if obj["path"] == str(path)
                   and obj["kind"] == kind and obj["marker"] == marker]
        if old is None and matches:
            oid, old = matches[0]
        snap = self.snapshot(path)
        original = snap
        if kind == "skill_symlink":
            proposed = Change.symlink(path, target, expected=snap).after
            fp = entries.link_fingerprint(target)
            existed = snap.kind != "absent"
            basis = "link_target"
        else:
            if snap.kind not in ("absent", "file"):
                raise EnableError("path_conflict", "Entry is not a regular file: " + str(path))
            data = snap.data or b""
            if marker:
                actual = entries.block_fingerprint(data, **_marker_args(marker))
                desired = entries.block_fingerprint(block, **_marker_args(marker))
                trusted = old["fingerprint"]["value"] if old and old["fingerprint"] else desired
                shared_block = scope == "user" and old is not None and old["fingerprint"] is not None
                if shared_block and actual != trusted and desired != trusted:
                    raise EnableError("drift", "Registered shared block cannot be reconstructed from the install template: " + str(path))
                if actual is not None and actual != trusted and not (shared_block and desired == trusted):
                    raise EnableError("drift", "Managed block drifted: " + str(path))
                if shared_block and actual == trusted:
                    # Registered shared content is authoritative; templates are
                    # for installation, not implicit migrations of user rules.
                    new, desired = data, trusted
                else:
                    new = entries.render_block(data, block, **_marker_args(marker), expected_fingerprint=actual,
                                               position="top" if top else "append")
                fp, existed, basis = desired, actual is not None, "block_bytes"
            else:
                new, existed, basis = data, snap.kind != "absent", "file_bytes"
                fp = entries.sha256(new)
            proposed = Snapshot("file", new, snap.mode if snap.kind == "file" else 0o600)
        self.after[path] = proposed
        if old:
            obj = copy.deepcopy(old)
            if obj["ownership"] == "created" and obj["fingerprint"]["value"] != fp:
                raise EnableError("drift", "Created unit template changed; explicit review required: " + str(path))
            obj["agents"] = [a for a in registry.AGENTS if a in set(obj["agents"]) | set(agents)]
            obj["fingerprint"] = {"algorithm": "sha256", "basis": basis, "value": fp}
            if scope == "user" and str(self.root) not in obj["consumers"]:
                obj["consumers"].append(str(self.root))
        else:
            # Imports are protected under schema v1, even when the reference was appended here.
            created = not existed and kind != "import"
            obj = {"kind": kind, "path": str(path), "scope": scope, "agents": agents,
                   "ownership": "created" if created else "reused", "marker": marker,
                   "fingerprint": {"algorithm": "sha256", "basis": basis, "value": fp},
                   "original_existed": not created, "link_target": str(target) if target else None,
                   "backup_manifest": str(self.tx.manifest_path) if created else None,
                   "consumers": [str(self.root)]}
        if scope=="project" and marker in (KEEPER_MARKER,WORKBUDDY_MARKER,DENIED_MARKER) and obj["ownership"]=="created" and old is None:
            unit=proposed.data[entries.managed_span(proposed.data,**marker)[0]:entries.managed_span(proposed.data,**marker)[1]]
            obj["lifecycle"]={"version":1,"unit_hex":unit.hex(),
                "prefix_hex":(b"\n" if not top and original.kind=="file" and original.data and not original.data.endswith(b"\n") else b"").hex(),
                "suffix_hex":(b"\n" if top and original.data else b"").hex(),
                "file_created":self.before[path].kind=="absent", "operation_id":self.tx.directory.name,"container_units":[oid]}
        objects[oid] = obj
        if scope == "user" and oid not in self.assembly["shared_object_ids"]:
            self.assembly["shared_object_ids"].append(oid)
        return original

    def reference(self,path):
        path=Path(path);oid=str(path)+"#import";objects=self.assembly['objects']
        old=next((o for o in objects.values() if o['path']==str(path) and o['kind']=='import'),None)
        if old is not None:oid=next(k for k,v in objects.items() if v is old)
        snap=self.snapshot(path)
        if snap.kind not in ('absent','file'):raise EnableError('path_conflict','CLAUDE entry must be regular')
        body=snap.data or b'';span=entries.reference_span(body)
        if old and old.get('lifecycle'):
            entries.lifecycle_span(body,old)
            return
        if span is None:
            prefix=b'\n' if body and not body.endswith(b'\n') else b''
            unit=b'@AGENTS.md\n';self.after[path]=Snapshot('file',body+prefix+unit,snap.mode or 0o600)
        else:prefix=b'';unit=body[span[0]:span[1]]
        if old:
            old['fingerprint']={'algorithm':'sha256','basis':'file_bytes','value':entries.sha256(self.after[path].data)}
            return  # Legacy reused import never acquires creation/deletion rights.
        created=span is None
        obj={'kind':'import','path':str(path),'scope':'project','agents':['claude'],'ownership':'created' if created else 'reused',
             'marker':None,'fingerprint':{'algorithm':'sha256','basis':'reference_line' if created else 'file_bytes','value':entries.sha256(unit) if created else entries.sha256(body)},
             'original_existed':not created,'link_target':None,'backup_manifest':str(self.tx.manifest_path) if created else None,'consumers':[str(self.root)]}
        if created:
            obj['lifecycle']={'version':1,'unit_hex':unit.hex(),'prefix_hex':prefix.hex(),'suffix_hex':'','file_created':self.before[path].kind=='absent',
                              'operation_id':self.tx.directory.name,'container_units':[oid]}
        objects[oid]=obj

    def erase(self,oid):
        obj=self.assembly['objects'][oid];path=Path(obj['path']);snap=self.snapshot(path)
        actual=registry._unit_fingerprint(snap,obj)
        if not obj['fingerprint'] or actual!=obj['fingerprint']['value']:
            raise EnableError('drift','Cannot revoke edited/missing created unit: '+str(path))
        if obj['kind']=='skill_symlink':self.after[path]=Snapshot('absent')
        elif obj.get('lifecycle'):
            self.after[path]=Snapshot('file',entries.remove_lifecycle_unit(snap.data,obj),snap.mode)
        else:
            self.after[path]=Snapshot('file',entries.remove_block(snap.data,**obj['marker'],expected_fingerprint=actual),snap.mode)
        del self.assembly['objects'][oid]
        self.retired_ids.add(oid)

    def authorization(self, choice, *, transition=False):
        if choice == 'follow_ck':
            for oid, obj in list(self.assembly['objects'].items()):
                if obj.get('marker') == DENIED_MARKER:
                    if obj['ownership'] != 'created':
                        raise EnableError('authorization_conflict', 'User-owned denial cannot be lifted')
                    self.erase(oid)
        else:
            self.object(self.root / 'AGENTS.md', '#memory-denied', list(self.assembly['agents']),
                        'block', marker=DENIED_MARKER, block=_block(DENIED_MARKER, DENIED_TEXT))
        return []

    def legacy_bridges(self, *, claude_active, workbuddy_active):
        """Expose exact old bytes and provenance; changes require a new exact approval."""
        transitions = []
        pairs = [(self.root/'AGENTS.md', LEGACY_KEEPER_MARKER)]
        if claude_active:
            pairs.append((self.root/'CLAUDE.md', LEGACY_KEEPER_MARKER))
        if workbuddy_active:
            pairs.append((self.root/'.workbuddy/memory/MEMORY.md', LEGACY_WORKBUDDY_MARKER))
        for path, marker in pairs:
            snap = self.snapshot(path)
            if snap.kind == 'absent': continue
            if snap.kind != 'file': raise EnableError('path_conflict', 'Legacy entry must be a regular file')
            if b'agent-group-memory:' in snap.data:
                raise EnableError('drift', 'Retired product marker; preserve and reinstall')
            span = entries.managed_span(snap.data, **marker)
            old = [(oid,o) for oid,o in self.assembly['objects'].items() if o['path']==str(path) and o.get('marker')==marker]
            if span is None:
                if old: raise EnableError('drift','Registered legacy block missing: '+str(path))
                continue
            unit = snap.data[span[0]:span[1]]
            if old and any(not o['fingerprint'] or o['fingerprint']['value'] != entries.sha256(unit) for _,o in old):
                raise EnableError('drift','Legacy bridge drifted: '+str(path))
            owner = old[0][1]['ownership'] if old else 'reused'
            transitions.append({'path':str(path),'ownership':owner,'before_hex':unit.hex(),
                'fingerprint':entries.sha256(unit),'action':'retire created and rebuild' if owner=='created' else 'review exact bytes and replace'})
            if old and owner=='created':
                self.erase(old[0][0])
            else:
                self.after[path]=Snapshot('file',entries.remove_block(snap.data,**marker,expected_fingerprint=entries.sha256(unit)),snap.mode)
                for oid,_ in old: del self.assembly['objects'][oid]
        return transitions

    def finalize_lifecycle(self):
        objects=self.assembly['objects']
        for oid,obj in objects.items():
            if obj.get('lifecycle') and obj['backup_manifest']==str(self.tx.manifest_path):
                obj['lifecycle']['container_units']=sorted(k for k,v in objects.items() if v['path']==obj['path'] and v.get('lifecycle') and v['ownership']=='created')

    def changes(self):
        return [Change(path, self.after[path], snap) for path, snap in self.before.items() if self.after[path] != snap]

    def description(self):
        return [{"path": str(c.path), "operation": "remove" if c.after.kind == "absent" else "create" if c.expected.kind == "absent" else "update",
                 "before_fingerprint": c.expected.fingerprint,
                 "after_fingerprint": c.after.fingerprint} for c in sorted(self.changes(), key=lambda c: str(c.path))]


def _preflight_objects(assembly, shared, review_user_units=()):
    for obj in list(assembly["objects"].values()) + [shared[key] for key in assembly["shared_object_ids"]]:
        if entries.free_project_rules(obj):continue
        snap = read_snapshot(obj["path"])
        if obj["kind"]=="import" and obj.get("lifecycle"):
            if snap.kind!="file" or registry._unit_fingerprint(snap,obj)!=obj["fingerprint"]["value"]:
                raise EnableError("drift","Managed reference missing or edited: "+obj["path"])
        if snap.kind == "absent":
            continue  # Only exact prior units may subsequently be repaired without a fresh approval.
        if obj["kind"] in ("block", "user_convention"):
            actual = registry._unit_fingerprint(snap, obj)
            if actual is not None and (not obj["fingerprint"] or actual != obj["fingerprint"]["value"]):
                if (obj["scope"] == "user" and obj["kind"] == "user_convention"
                        and (obj["path"], obj["marker"]["start"]) in review_user_units):
                    continue  # Planned below; only an exact approved repair may write it.
                raise EnableError("drift", "Registered managed block drifted: " + obj["path"])
        elif obj["kind"] == "skill_symlink":
            entries.verify_link(obj["path"], obj["link_target"])
        # file/import snapshots may overlap managed blocks; their hashes are not deletion rights.


def _consistent_repair(previous, current, plan, choice, old_shared):
    if previous is None or previous["memory_policy"] != choice:
        return False
    old = previous["checkouts"][str(plan.root)]
    if old["git_common_dir"] != current["git_common_dir"] or not set(current["agents"]) <= set(old["agents"]):
        return False
    units = list(old["objects"].values()) + list(old_shared.values())
    for change in plan.changes():
        matching = [obj for obj in units if obj["path"] == str(change.path)]
        if not matching:
            return False
        # Every new/repaired unit must already have a trusted fingerprint in the old ledger.
        for obj in list(current["objects"].values()) + [plan.shared[k] for k in current["shared_object_ids"]]:
            if obj["path"] != str(change.path):
                continue
            prior = next((p for p in matching if p["kind"] == obj["kind"] and p["marker"] == obj["marker"]), None)
            if prior is None:
                return False
            # Reused whole-file/import snapshots overlap separately managed blocks.
            # They grant no deletion rights and must not prevent an exact bridge repair.
            if obj["kind"] in ("file", "import") and prior["ownership"] != "created":
                continue
            if prior["fingerprint"] != obj["fingerprint"]:
                return False
            if obj["scope"] == "user" and obj["marker"] and change.expected.kind == "file":
                actual = registry._unit_fingerprint(change.expected, prior)
                if actual is not None and actual != prior["fingerprint"]["value"]:
                    return False  # External edits require a fresh exact-plan review.
    return True


def _confirm(request, approval_plan):
    if not request.get("interactive"):
        return False
    prompt = "Approve this exact enable plan? [y/N]\n" + json.dumps(approval_plan, ensure_ascii=False, indent=2)
    confirm = request.get("confirm")
    if confirm:
        return bool(confirm(prompt))
    print(prompt, file=sys.stderr)
    return input().strip().lower() in ("y", "yes")


def _change_ownership(plan, path):
    objects = list(plan.assembly["objects"].values()) + list(plan.shared.values())
    values = {o["ownership"] for o in objects if o["path"] == path}
    return "created" if values == {"created"} else "reused" if values == {"reused"} else "unknown"


def run(request):
    """Return CLI result; all project decisions and writes share .agm.lock."""
    result = {"status": "failed", "projects": [], "changes": [], "warnings": [], "errors": [],
              "approval_required": False, "next_action": None}
    try:
        runtime = layout.from_request(request)
        result["runtime_layout"] = runtime.describe()
        if runtime.lock.exists():
            raise TransactionError("writer lock exists; do not steal a stale lock", code="lock_conflict")
        return _run_locked(request, runtime, result, locked=False)
    except (ValueError, OSError, EOFError, SyntaxError) as exc:
        result["status"] = getattr(exc, "status", "recovery_required" if getattr(exc, "code", None) == "recovery_required" else "failed")
        result["approval_required"] = result["status"] == "approval_required"
        recovery = getattr(exc, "manifest", None)
        result["next_action"] = "Inspect preserved evidence; re-preview before retrying. No store assets are deleted."
        if getattr(exc, "code", None) == "registry_invalid" and "created unit drifted" in str(exc):
            recovery = ("人工核对并还原登记内容，或另行审查 remove 后重新 enable 的恢复方案；"
                        "精确计划批准不能覆盖 created 对象的漂移保护。")
            result["next_action"] = recovery
        result["errors"].append({"code": getattr(exc, "code", "enable_failed"), "path": None,
                                "message": str(exc), "recovery": recovery})
        return result


def _run_locked(request, runtime, result, *, locked=True):
    identity = project.resolve_project(request.get("project"))
    root, key = identity.checkout, str(identity.main_checkout)
    requested_agents = paths.resolve_agents(request.get("agents"))
    config, home = request["platform_config"], request["home"]
    allowed = paths.allowed_user_paths(config, None, home=home)
    registry_path = runtime.registry
    expected_registry = read_snapshot(registry_path)
    if expected_registry.kind == "absent":
        raise EnableError("machine_not_installed", "Machine registry missing; use scripts/install.py")
    rebuild = False
    try:
        previous_registry = registry.load_registry(registry_path, allowed_user_paths=allowed)
    except registry.RegistryMigrationRequired:
        raise
    except registry.RegistryError:
        previous_registry, rebuild = registry.plan_registry_rebuild(expected_registry, allowed_user_paths=allowed)
    registry.require_installed(previous_registry)
    detection = detect.detect_agents(config, requested_agents, home=str(home), search_paths=request.get('search_paths'),
        app_directories=request.get('app_directories'), user_candidates=request.get('user_candidates'), runner=request.get('detect_runner'))
    agents = [a for a in requested_agents if detection['agents'][a]['status']=='installed']
    explicit = request.get('memory_choice')
    if explicit not in (None, 'follow_ck', 'disabled'):
        raise EnableError('approval_mismatch','Invalid memory policy')
    prior = previous_registry['projects'].get(key)
    revoking = explicit == 'disabled' and prior is not None
    result['installation'] = {'requested':requested_agents,'effective':agents,
        'skipped':{a:detection['agents'][a]['status'] for a in requested_agents if a not in agents}}
    if request.get('agents') is not None and agents != requested_agents and not revoking:
        raise EnableError('agent_not_installed','Explicit agent is not verified installed')
    if not agents and not revoking:
        result.update(status='gaps',next_action='Verify/install an executor before creating project entries')
        return result
    data = copy.deepcopy(previous_registry)
    previous = copy.deepcopy(prior)
    if key not in data['projects']: data['projects'][key] = registry.new_project(identity, agents)
    p = data['projects'][key]
    assembly = p['checkouts'][key]
    if assembly['git_common_dir'] != str(identity.git_common_dir):
        raise EnableError('project_identity_mismatch','Git common-dir changed; do not inherit policy')
    assembly['agents'] = [a for a in registry.AGENTS if a in set(assembly['agents']) | set(agents)]
    choice = explicit or p['memory_policy']
    approval = request.get('approval')
    # An envelope cannot silently lift disabled without an explicit --memory request.
    if previous and previous['memory_policy']=='disabled' and choice=='follow_ck' and explicit!='follow_ck':
        raise EnableError('approval_mismatch','Lifting disabled requires explicit --memory')
    _preflight_objects(assembly,data['shared_objects'])
    native = root/'.workbuddy/memory'
    if 'workbuddy' in agents and (native.is_symlink() or native.exists() and not native.is_dir()):
        raise EnableError('path_conflict','WorkBuddy native memory directory must be real')
    native_pending = 'workbuddy' in agents and not native.exists()
    tx = Transaction(lock_path=runtime.transaction_lock,backup_root=runtime.backups,
                     allowed_roots=[root,registry_path]+[Path(v) for v in allowed])
    plan = _Plan(assembly,data['shared_objects'],root,tx)
    base = root/'AGENTS.md'
    snap = plan.snapshot(base)
    if snap.kind=='absent': plan.after[base]=Snapshot('file',('# '+root.name+'\n\n## 项目规则\n').encode(),0o600)
    elif snap.kind!='file': raise EnableError('path_conflict','AGENTS must be a regular file')
    if b'agent-group-memory:' in (snap.data or b''):
        raise EnableError('drift','Retired product marker; preserve and reinstall')
    # Machine installation alone does not authorize prebuilding Claude's project entry.
    claude_active = request.get('agents') is not None and 'claude' in agents
    workbuddy_active = 'workbuddy' in agents and not native_pending
    transitions = plan.legacy_bridges(claude_active=claude_active, workbuddy_active=workbuddy_active)
    plan.authorization(choice)
    plan.object(base,'#experience',assembly['agents'],'block',marker=KEEPER_MARKER,block=_block(KEEPER_MARKER,EXPERIENCE_TEXT))
    if claude_active: plan.reference(root/'CLAUDE.md')
    if workbuddy_active:
        plan.object(native/'MEMORY.md','#project-rules',['workbuddy'],'block',marker=WORKBUDDY_MARKER,
                    block=_block(WORKBUDDY_MARKER,'项目规则读取当前项目根 AGENTS.md。'),top=True)
    plan.finalize_lifecycle()
    actual_plan = {'schema_version':1,'command':'enable-memory','main_checkout':key,'checkout':str(root),
        'git_common_dir':str(identity.git_common_dir),'agents':agents,'memory_policy':choice,'changes':plan.description(),
        'installation':{a:{'status':detection['agents'][a]['status'],'fingerprint':detect.detection_fingerprint(detection['agents'][a])} for a in requested_agents},
        'native_pending':['workbuddy'] if native_pending else []}
    if previous and previous['memory_policy'] != choice:
        actual_plan['memory_transition']={'before':previous['memory_policy'],'after':choice,'scope':'all registered project agents',
            'affected_agents':assembly['agents']}
    if transitions: actual_plan['legacy_bridge_transition']=transitions
    if rebuild: actual_plan['rebuild']=rebuild
    def approval_template():
        template = dict(actual_plan,confirmed_at='<UTC timestamp>',reference='<user confirmation reference>')
        if rebuild: template['rebuild_confirmation']={'registry_sha256':rebuild['registry_sha256'], 'confirmed_at':'<UTC timestamp>', 'reference':'<separate global rebuild confirmation>'}
        return json.dumps(template,ensure_ascii=False)
    result['projects']=[{'main_checkout':key,'checkout':str(root),'memory_policy':choice,'agents':assembly['agents'],
        'runtime_acceptance':assembly['runtime_acceptance'],'evidence':[str(registry_path)]}]
    consistent = not transitions and _consistent_repair(previous,assembly,plan,choice,previous_registry['shared_objects'])
    if request.get('preview'):
        # Reuse the actual plan before implicit consistent repairs, confirmation
        # callbacks or any writer lock. Preview never supplies its own approval.
        if consistent and not rebuild and not plan.changes() and data==previous_registry:
            result['status']='completed'
        else:
            result.update(status='approval_required',approval_required=True,next_action=approval_template())
        return result
    confirmation = None
    if approval:
        if set(approval) != set(actual_plan)|{'confirmed_at','reference'}|({'rebuild_confirmation'} if rebuild else set()) or any(approval.get(k)!=v for k,v in actual_plan.items()):
            result.update(status='approval_required',approval_required=True,next_action=approval_template())
            result['errors'].append({'code':'approval_mismatch','path':None,'message':'Approved plan differs from locked policy/identity/write fingerprints','recovery':'Review the new exact plan'})
            return result
        registry._evidence({k:approval[k] for k in ('confirmed_at','reference')})
        if rebuild:
            confirmation=approval['rebuild_confirmation']
            if confirmation['registry_sha256']!=rebuild['registry_sha256']: raise EnableError('approval_mismatch','Rebuild hash changed')
            registry._evidence({k:confirmation[k] for k in ('confirmed_at','reference')})
    elif consistent and not rebuild:
        if not plan.changes() and data==previous_registry:
            result['status']='completed'; return result
    elif _confirm(request,actual_plan):
        approval=dict(actual_plan,confirmed_at=_now(),reference='interactive exact enable plan confirmation')
        if rebuild:
            if not _confirm(request,{'command':'rebuild-global-registry','rebuild':rebuild}):
                result.update(status='approval_required',approval_required=True,next_action=approval_template()); return result
            confirmation={'registry_sha256':rebuild['registry_sha256'],'confirmed_at':_now(),'reference':'interactive separate rebuild confirmation'}
            approval['rebuild_confirmation']=confirmation
    else:
        result.update(status='approval_required',approval_required=True,next_action=approval_template()); return result
    if not locked:
        locked_approval=approval or dict(actual_plan,confirmed_at=_now(),reference='exact prior registered repair')
        with write_lock(runtime.lock):
            return _run_locked(dict(request,approval=locked_approval),runtime,result,locked=True)
    p['memory_policy']=choice
    assembly['runtime_acceptance']={'status':'pending','evidence_path':None}
    for obj in list(assembly['objects'].values())+[data['shared_objects'][oid] for oid in assembly['shared_object_ids']]:
        if obj['kind'] in ('file','import') and obj['ownership']!='created' and not entries.free_project_rules(obj) and Path(obj['path']) in plan.after:
            obj['fingerprint']['value']=plan.after[Path(obj['path'])].fingerprint
    called=[]
    def hook(event,path):
        if event=='before_write' and not called:
            if project.resolve_project(root).git_common_dir!=identity.git_common_dir:
                raise EnableError('project_identity_mismatch','Git identity changed after approval')
            for output,snapshot in plan.before.items():
                if read_snapshot(output)!=snapshot: raise EnableError('drift','Output changed after approval: '+str(output))
            called.append(True)
        if request.get('transaction_hook'): request['transaction_hook'](event,path)
    tx.hook=hook
    registry.commit_registry(registry_path,data,transaction=tx,expected=expected_registry,changes=plan.changes(),
        allowed_user_paths=allowed,previous=previous_registry,rebuild=rebuild,rebuild_confirmation=confirmation)
    result['status']='completed'
    result['changes']=[dict(item,ownership=_change_ownership(plan,item['path']),applied=True) for item in plan.description()]
    result['warnings'].append('Runtime acceptance pending; CK installation and record data are retained and not inspected.')
    if native_pending: result['warnings'].append('WorkBuddy native directory absent; pointer waits for actual use.')
    return result
