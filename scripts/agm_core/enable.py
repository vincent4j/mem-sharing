"""M2-04: exact-plan enable orchestration, with a stdlib-only Keeper adapter.

AGM materializes the installer's declared links/bridge template in its recoverable
transaction, then invokes the approved installer on that already-current output.
This avoids letting an external writer escape AGM's before snapshots/manifests.
The installer and ensure-bridge must subsequently report the expected project
scope and leave those bytes unchanged. Store init remains Keeper-owned: on any
failure its assets are preserved, never rolled back or read as memory content.

run(request) is the CLI dispatch entry. Private request injection points
runtime_layout, runner, confirm and transaction_hook support isolated tests only;
they are not CLI options. No source download, fallback, or global installation.
"""
import ast
import copy
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from . import entries, paths, project, registry, layout, detect
from .transaction import Change, Snapshot, Transaction, TransactionError, read_snapshot, write_lock

KEEPER_MARKER = {"start": "<!-- context-keeper:start -->", "end": "<!-- context-keeper:end -->"}
BASE_MARKER = {"start": "<!-- agent-group-memory:rules:start -->", "end": "<!-- agent-group-memory:rules:end -->"}
WORKBUDDY_MARKER = {"start": "<!-- context-keeper:workbuddy:start -->", "end": "<!-- context-keeper:workbuddy:end -->"}
DENIED_MARKER = {"start":"<!-- agent-group-memory:memory-denied:start -->", "end":"<!-- agent-group-memory:memory-denied:end -->"}
DENIED_TEXT = "本项目已撤销自动记忆授权。本段优先于本文件中的历史 context-keeper 桥接和 Skill 触发说明：不得自动调用记忆写入、迁移、初始化或建库，不得因残留 Skill/桥接恢复旧授权；历史内容仅供只读参考。只有用户重新明确批准本项目 enable-memory --memory 后才可恢复自动记录。"

EXCEPTION_MARKER = {"start": "<!-- agent-group-memory:keeper-exception:start -->", "end": "<!-- agent-group-memory:keeper-exception:end -->"}


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


def _source_fingerprints(source):
    required = [source / "SKILL.md", source / "scripts/install.py",
                source / "scripts/context_keeper_probe.py"]
    if not (source / ".git").exists() or any(not p.is_file() or p.is_symlink() for p in required):
        raise EnableError("provider_source_invalid", "Keeper requires a verified local Git checkout with SKILL.md/install/probe")
    try:
        project.resolve_project(source, allow_worktree=True)
    except project.ProjectError as exc:
        raise EnableError("provider_source_invalid", "Keeper source is not a Git root: " + str(exc)) from exc
    files = set(required) | set((source / "scripts").rglob("*.py"))
    if any(not p.is_file() or p.is_symlink() or p.resolve() != p for p in files):
        raise EnableError("provider_source_invalid", "Keeper source scripts must not be symlinks")
    return [{"path": str(p), "sha256": entries.sha256(p.read_bytes())} for p in sorted(files)]


def _bridge_template(source, agent="codex"):
    """Read upstream literals without importing/executing provider Python."""
    prefix = "WORKBUDDY_" if agent == "workbuddy" else ""
    names = tuple(prefix + name for name in ("BRIDGE_START", "BRIDGE_END", "BRIDGE"))
    marker = WORKBUDDY_MARKER if agent == "workbuddy" else KEEPER_MARKER
    constants = {}
    tree = ast.parse((source / "scripts/install.py").read_text(encoding="utf-8"))
    for node in tree.body:
        if not isinstance(node, ast.Assign) or len(node.targets) != 1 or not isinstance(node.targets[0], ast.Name):
            continue
        name = node.targets[0].id
        if name not in names:
            continue
        value = node.value
        if isinstance(value, ast.Constant) and isinstance(value.value, str):
            constants[name] = value.value
        elif isinstance(value, ast.JoinedStr):
            parts = []
            for item in value.values:
                if isinstance(item, ast.Constant) and isinstance(item.value, str):
                    parts.append(item.value)
                elif (isinstance(item, ast.FormattedValue) and isinstance(item.value, ast.Name)
                      and item.value.id in constants and item.conversion == -1 and item.format_spec is None):
                    parts.append(constants[item.value.id])
                else:
                    raise EnableError("provider_protocol_invalid", "Unsupported Keeper bridge template expression")
            constants[name] = "".join(parts)
    value = constants.get(prefix + "BRIDGE", "").rstrip("\n").encode("utf-8")
    if entries.managed_span(value, **_marker_args(marker)) != (0, len(value)):
        raise EnableError("provider_protocol_invalid", "Keeper bridge template markers do not match")
    return value


def _marker_args(marker):
    return {"start": marker["start"], "end": marker["end"]}


def _call(request, source, argv, *, allow_preview=False, fingerprints=None):
    if fingerprints is not None and _source_fingerprints(source) != fingerprints:
        raise EnableError("approval_mismatch", "Keeper source changed before subprocess", "approval_required")
    command = [sys.executable, str(source / "scripts" / argv[0])] + argv[1:]
    env = dict(os.environ, HOME=request["home"], PYTHONDONTWRITEBYTECODE="1")
    # Do not emit provider stdout: it may include local record text/paths outside the plan.
    result = request.get("runner", subprocess.run)(command, stdout=subprocess.PIPE,
                stderr=subprocess.PIPE, text=True, env=env, cwd=str(source))
    if result.returncode == 3:
        raise EnableError("migration_required", "Keeper migration gate: stop and run its migrate preview", "migration_required")
    if fingerprints is not None and _source_fingerprints(source) != fingerprints:
        raise EnableError("approval_mismatch", "Keeper source changed during subprocess", "approval_required")
    if result.returncode == 5:
        if allow_preview:
            return {"approval_required": True}
        raise EnableError("approval_required", "Keeper requires location approval", "approval_required")
    if result.returncode:
        raise EnableError("keeper_failed", "Keeper subprocess failed (rc=%s); preserve any partial store assets" % result.returncode)
    try:
        data = json.loads(result.stdout)
    except (ValueError, TypeError):
        if argv[0] == "context_keeper_probe.py":
            return {}
        raise EnableError("provider_protocol_invalid", "Keeper installer did not return JSON")
    if not isinstance(data, dict):
        raise EnableError("provider_protocol_invalid", "Keeper result must be an object")
    if data.get("approval_required"):
        if allow_preview:
            return data
        raise EnableError("approval_required", "Keeper preview is not completed installation", "approval_required")
    return data


def _candidate_store(root):
    found = []
    for candidate in (root / "docs/context-keeper", root / "context-keeper"):
        if candidate.is_dir() and any((candidate / name).exists() for name in
                ("memory-keeper.md", "worklogs", "plans", "evolution", "migration-manifest.json")):
            found.append(candidate.resolve())
    if len(found) > 1:
        raise EnableError("store_ambiguous", "Multiple Keeper stores; do not select or delete one automatically")
    if found:
        return found[0]
    config = root / "context-keeper.json"
    if config.exists():
        data = json.loads(config.read_text(encoding="utf-8"))
        if not isinstance(data, dict) or not isinstance(data.get("directory"), str) or not data["directory"].strip():
            raise EnableError("store_config_invalid", "Invalid Keeper directory configuration")
        value = Path(data["directory"])
        return (value if value.is_absolute() else root / value).resolve()
    return (root / "docs/context-keeper").resolve()


class _Plan:
    def __init__(self, assembly, shared, root, tx):
        self.assembly, self.shared, self.root, self.tx = assembly, shared, root, tx
        self.before, self.after = {}, {}

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

    def authorization(self,choice,*,transition):
        conflicts=[]
        if choice=='yes':
            for oid,obj in list(self.assembly['objects'].items()):
                if obj.get('marker')==DENIED_MARKER:
                    if obj['ownership']!='created':raise EnableError('authorization_conflict','User-owned denial cannot be lifted')
                    self.erase(oid)
            return conflicts
        if choice!='no':return conflicts
        targets={self.root/'AGENTS.md'}
        for oid,obj in list(self.assembly['objects'].items()):
            trigger=(obj['kind']=='block' and obj.get('marker') in (KEEPER_MARKER,WORKBUDDY_MARKER)) or (obj['kind']=='skill_symlink' and Path(obj['path']).name=='context-keeper')
            if not trigger:continue
            if obj['ownership']=='created':self.erase(oid)
            else:
                conflicts.append({'path':obj['path'],'ownership':obj['ownership'],'action':'preserve bytes; explicit denial guard'})
                if obj['kind']=='block':targets.add(Path(obj['path']))
        # A pre-registry historical bridge is not deletion authority either.
        for path,marker in ((self.root/'AGENTS.md',KEEPER_MARKER),(self.root/'CLAUDE.md',KEEPER_MARKER),(self.root/'.workbuddy/memory/MEMORY.md',WORKBUDDY_MARKER)):
            snap=self.snapshot(path)
            if snap.kind=='file' and entries.managed_span(snap.data,**marker) is not None:
                targets.add(path)
                if not any(c['path']==str(path) for c in conflicts):conflicts.append({'path':str(path),'ownership':'unregistered','action':'preserve bytes; explicit denial guard'})
        existing_guard=any(o.get('marker')==DENIED_MARKER for o in self.assembly['objects'].values())
        if transition or conflicts or existing_guard:
            for path in sorted(targets):
                self.object(path,'#memory-denied',list(self.assembly['agents']),'block',marker=DENIED_MARKER,block=_block(DENIED_MARKER,DENIED_TEXT))
        return conflicts

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


def _consistent_repair(previous, current, plan, choice, source, store, old_shared, fingerprints):
    if previous is None or previous["memory_authorization"] != choice or (choice == "yes" and previous["provider_source"] != source):
        return False
    old = previous["checkouts"][str(plan.root)]
    if old["git_common_dir"] != current["git_common_dir"] or not set(current["agents"]) <= set(old["agents"]):
        return False
    if choice == "yes" and (not old["store"]["location_approved"] or old["store"]["path"] != store):
        return False
    if choice == "yes" and old["states"]["source_available"]["evidence"] != _source_evidence(fingerprints):
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


def _source_evidence(fingerprints):
    return "Keeper source sha256: " + entries.sha256(json.dumps(fingerprints, sort_keys=True).encode("utf-8"))


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
    """Return CLI result; all decisions, provider calls and writes share .agm.lock."""
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
        for item in result["projects"]:
            if getattr(exc, "code", None) in ("migration_required", "keeper_failed", "store_unavailable", "approval_required"):
                item["states"]["store_authorized_ready"] = _fact("blocked", getattr(exc, "code", "provider failure"))
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
    agents = paths.resolve_agents(request.get("agents"))
    config, home = request["platform_config"], request["home"]
    allowed = paths.allowed_user_paths(config, None, home=home)
    registry_path = runtime.registry
    expected_registry = read_snapshot(registry_path)
    if expected_registry.kind == "absent":
        raise EnableError("machine_not_installed", "Machine registry missing: " + str(registry_path) + "; use INSTALL.md and scripts/install.py")
    rebuild = False
    try:
        previous_registry = registry.load_registry(registry_path, allowed_user_paths=allowed)
    except registry.RegistryError:
        previous_registry, rebuild = registry.plan_registry_rebuild(expected_registry, allowed_user_paths=allowed)
    previous_registry = registry.require_installed(previous_registry)
    detection=detect.detect_agents(config,agents,home=str(home),search_paths=request.get('search_paths'),
        app_directories=request.get('app_directories'),user_candidates=request.get('user_candidates'),runner=request.get('detect_runner'))
    requested_agents=list(agents)
    effective=[a for a in agents if detection['agents'][a]['status']=='installed']
    prior=previous_registry['projects'].get(key)
    revoking=(request.get('memory_choice') or (request.get('approval') or {}).get('memory_authorization'))=='no' and prior is not None and prior['memory_authorization']=='yes'
    result['installation']={'requested':requested_agents,'effective':effective,'skipped':{a:detection['agents'][a]['status'] for a in requested_agents if a not in effective}}
    if request.get('agents') is not None and len(effective)!=len(agents) and not revoking:
        raise EnableError('agent_not_installed','Explicit agent is not verified installed: '+json.dumps(result['installation']['skipped']))
    agents=effective
    if not agents and not revoking:
        result.update(status='gaps',next_action='Verify/install an executor before creating project entries')
        result['warnings'].append('No verified installed executor; project/entry state unchanged')
        return result
    data = copy.deepcopy(previous_registry)
    previous = copy.deepcopy(data["projects"].get(key))
    if key not in data["projects"]:data["projects"][key]=registry.new_project(identity,agents)
    p = data["projects"][key]
    assembly = p["checkouts"][key]
    if assembly["git_common_dir"] != str(identity.git_common_dir):
        raise EnableError("project_identity_mismatch", "Git common-dir changed; do not inherit authorization")
    for a in agents:
        if a not in assembly["agents"]:
            assembly["agents"].append(a)
            for phase in ("skill_installed", "bridge_assembled"):
                assembly["states"][phase][a] = registry.unknown_fact()
    assembly["agents"] = [a for a in registry.AGENTS if a in assembly["agents"]]
    approval = request.get("approval")
    choice = request.get("memory_choice")
    if approval and choice is not None and approval.get("memory_authorization") != choice:
        raise EnableError("approval_mismatch", "Approval conflicts with explicit memory choice", "approval_required")
    if choice is None:
        choice = approval["memory_authorization"] if approval else p["memory_authorization"]
    if choice is None and request.get("interactive"):
        print("Context Keeper provides project memory across agents. Enable memory? [y/N]", file=sys.stderr)
        choice = "yes" if input().strip().lower() in ("y", "yes") else "no"
    if choice not in ("yes", "no", None):
        raise EnableError("approval_mismatch", "Invalid memory choice")
    review_user_units = []
    if "workbuddy" in agents:
        user_path = paths.expand_path(config["workbuddy"]["user_entry"], home=home)
        review_user_units.append((user_path, BASE_MARKER["start"]))
        if choice == "yes":
            review_user_units.append((user_path, EXCEPTION_MARKER["start"]))
    _preflight_objects(assembly, data["shared_objects"], review_user_units)
    source = (approval.get("provider_source") if approval else p["provider_source"]) if choice == "yes" else None
    if choice == "yes" and source is None:
        candidates = set()
        for a in agents:
            for template in config[a]["project_skill_roots"]:
                path = Path(paths.expand_path(template, home=home, project=key)) / "context-keeper"
                if path.is_symlink():
                    candidates.add(path.resolve())
        if len(candidates) == 1:
            source = str(candidates.pop())
    native=root/'.workbuddy/memory'
    native_pending='workbuddy' in agents and not native.exists()
    if 'workbuddy' in agents and (native.is_symlink() or native.exists() and not native.is_dir()):
        raise EnableError('path_conflict','WorkBuddy native memory directory must be real')
    memory_agents=[a for a in agents if a!='workbuddy' or not native_pending]
    fingerprints, bridge, store = [], None, None
    if choice == "yes" and source:
        if str(Path(source).resolve()) != source:
            raise EnableError("provider_source_invalid", "Source must be a canonical absolute path")
        source = Path(source)
        fingerprints, bridge = _source_fingerprints(source), _bridge_template(source)
        store = _candidate_store(root)
        initial_store = store
        if approval and approval.get("store_path") is not None:
            approved_store = Path(approval["store_path"])
            if not approved_store.is_absolute() or approved_store.resolve() != approved_store:
                raise EnableError("approval_mismatch", "Store path must be canonical")
            # A previously configured/discovered store cannot silently be redirected.
            if (root / "context-keeper.json").exists() or store.exists():
                if approved_store != store:
                    raise EnableError("approval_mismatch", "Approved store differs from actual Keeper location")
            store = approved_store
        if previous and assembly["store"]["location_approved"] and str(store) != assembly["store"]["path"]:
            raise EnableError("approval_mismatch", "Keeper store location changed; re-confirm location explicitly")
    tx = Transaction(lock_path=runtime.transaction_lock, backup_root=runtime.backups,
                     allowed_roots=[root, registry_path] + [Path(v) for v in allowed])
    plan = _Plan(assembly, data["shared_objects"], root, tx)
    base=root/'AGENTS.md'
    snap=plan.snapshot(base)
    if snap.kind=='absent':plan.after[base]=Snapshot('file',('# '+root.name+'\n\n## 项目规则\n').encode(),0o600)
    elif snap.kind!='file':raise EnableError('path_conflict','AGENTS must be a regular file')
    revoke_conflicts=plan.authorization(choice,transition=previous is not None and previous['memory_authorization']=='yes' and choice=='no')
    if 'claude' in agents:plan.reference(root/'CLAUDE.md')
    if "workbuddy" in agents:
        path = Path(paths.expand_path(config["workbuddy"]["user_entry"], home=home))
        snap = plan.snapshot(path)
        registered_rules = any(o["path"] == str(path) and o["marker"] == BASE_MARKER
                               for o in data["shared_objects"].values())
        machine_rules=[o for o in data['machine']['objects'].values() if o['path']==str(path) and o['marker']==BASE_MARKER]
        if machine_rules:
            obj=machine_rules[0]
            if registry._unit_fingerprint(snap,obj)!=(obj.get('fingerprint') or {}).get('value'):
                raise EnableError('drift','Machine convention drift; project does not rewrite it')
        elif (snap.kind == "file" and not registered_rules
                and entries.block_fingerprint(snap.data, **_marker_args(BASE_MARKER)) is None):
            # M1 reuses the existing user entry as a whole-file baseline.
            # Do not append a second rule convention to that shared entry.
            plan.object(path, "#base", ["workbuddy"], "file", scope="user")
        else:
            plan.object(path, "#rules", ["workbuddy"], "user_convention", scope="user", marker=BASE_MARKER,
                        block=_block(BASE_MARKER, "项目规则读取当前项目根 AGENTS.md。保留已有公共源与用户约定。"))
    if choice == "yes" and source:
        for a in memory_agents:
            for template in config[a]["project_skill_roots"]:
                path = Path(paths.expand_path(template, home=home, project=key)) / "context-keeper"
                plan.object(path, "", [a], "skill_symlink", target=source)
            target = Path(paths.expand_path(config[a]["project_bridge_entry"], home=home, project=key))
            if a == "workbuddy":
                raw = _bridge_template(source, "workbuddy")
                marker = WORKBUDDY_MARKER
                plan.object(target, "#keeper", [a], "block", marker=marker, block=raw, top=True)
                user = Path(paths.expand_path(config[a]["user_entry"], home=home))
                plan.object(user, "#keeper-exception", [a], "user_convention", scope="user", marker=EXCEPTION_MARKER,
                            block=_block(EXCEPTION_MARKER, "## Context Keeper 项目记忆例外\n\n项目记忆用 context-keeper 记录库，由项目桥接块驱动。项目规则唯一来源仍为 AGENTS.md；已启用 context-keeper 的项目，其进度、事实与经验写入已获授权的记录库，项目 .workbuddy/memory/MEMORY.md 可在顶部包含受控桥接块。此条款作为既有\u201c事实归 AGENTS.md、项目 MEMORY 只放指针\u201d约定的记忆例外；其余原文约定保留。"))
            else:
                plan.object(target, "#keeper", [a], "block", marker=KEEPER_MARKER, block=bridge)
    plan.finalize_lifecycle()
    actual_plan = {"schema_version": 1, "command": "enable-memory", "main_checkout": key,
                   "checkout": str(root), "git_common_dir": str(identity.git_common_dir), "agents": agents,
                   "memory_authorization": choice, "store_path": str(store) if store else None,
                   "provider_source": str(source) if source else None, "provider_fingerprints": fingerprints,
                   "changes": plan.description(),
                   "installation":{a:{"status":detection["agents"][a]["status"],"fingerprint":detect.detection_fingerprint(detection["agents"][a])} for a in requested_agents},
                   "native_pending":["workbuddy"] if native_pending else []}
    if revoke_conflicts or previous and choice is not None and previous["memory_authorization"]!=choice:
        actual_plan["memory_transition"]={"before":previous["memory_authorization"] if previous else None,"after":choice,"scope":"all registered project agents", "affected_agents":assembly["agents"],"reused_conflicts":revoke_conflicts}
    if rebuild:
        actual_plan["rebuild"] = rebuild
    def approval_template():
        template = dict(actual_plan, confirmed_at="<UTC timestamp>", reference="<user confirmation reference>")
        if rebuild:
            template["rebuild_confirmation"] = {"registry_sha256": rebuild["registry_sha256"],
                "confirmed_at": "<separate UTC timestamp>", "reference": "<separate global registry rebuild confirmation>"}
        return json.dumps(template, ensure_ascii=False)
    observed = copy.deepcopy(assembly["states"])
    if choice == "yes":
        observed["source_available"] = _fact("ready" if source else "missing", str(source) if source else "No confirmed Keeper checkout")
        for a in agents:
            links = [o for o in assembly["objects"].values() if o["kind"] == "skill_symlink" and a in o["agents"]]
            link_ready = bool(links) and all(plan.before.get(Path(o["path"]), Snapshot("absent")).kind == "symlink" for o in links)
            observed["skill_installed"][a] = _fact("ready" if link_ready else "missing", "project link preflight")
            bridges = [o for o in assembly["objects"].values() if o["kind"] == "block" and a in o["agents"] and o["marker"] in
                       (KEEPER_MARKER, {"start": "<!-- context-keeper:workbuddy:start -->", "end": "<!-- context-keeper:workbuddy:end -->"})]
            bridge_ready = bool(bridges) and all(entries.block_fingerprint(plan.before[Path(o["path"])].data or b"", **_marker_args(o["marker"])) == o["fingerprint"]["value"] for o in bridges)
            observed["bridge_assembled"][a] = _fact("ready" if bridge_ready else "missing", "project bridge preflight")
    if native_pending and choice=="yes":
        for phase in ("skill_installed","bridge_assembled"):
            observed[phase]["workbuddy"]=_fact("blocked","WorkBuddy native memory directory must already exist")
    result["projects"] = [{"main_checkout": key, "checkout": str(root), "states": observed,
                           "agents": assembly["agents"], "evidence": [str(registry_path)],
                           "runtime_acceptance": {"status": "pending", "evidence_path": None}}]
    # No registry fingerprint in changes: it contains fresh evidence timestamps and a new manifest.
    # Its exact before Snapshot is independently checked by commit_registry under this same lock.
    consistent = _consistent_repair(previous, assembly, plan, choice, str(source) if source else None, str(store) if store else None, previous_registry["shared_objects"], fingerprints)
    if approval:
        if (set(approval) != set(actual_plan) | {"confirmed_at", "reference"} | ({"rebuild_confirmation"} if rebuild else set())
                or any(approval.get(k) != value for k, value in actual_plan.items())):
            result.update(status="approval_required", approval_required=True,
                          next_action=approval_template())
            result["errors"].append({"code": "approval_mismatch", "path": None,
                                    "message": "Approved plan differs from locked identity/source/store/write fingerprints", "recovery": "Review and confirm the new exact plan"})
            return result
        evidence = {"confirmed_at": approval["confirmed_at"], "reference": approval["reference"]}
        registry._evidence(evidence)
        if rebuild:
            confirmation = approval["rebuild_confirmation"]
            registry._keys(confirmation, "registry_sha256 confirmed_at reference", "rebuild confirmation")
            if confirmation["registry_sha256"] != rebuild["registry_sha256"]:
                raise EnableError("approval_mismatch", "Separate rebuild confirmation binds a different registry")
            registry._evidence({k: confirmation[k] for k in ("confirmed_at", "reference")})
    elif consistent and not rebuild:
        evidence = p["authorization_evidence"]
    elif choice is not None and _confirm(request, actual_plan):
        evidence = {"confirmed_at": _now(), "reference": "interactive exact enable plan confirmation"}
        if rebuild:
            if not _confirm(request, {"command": "rebuild-global-registry", "rebuild": rebuild}):
                result.update(status="approval_required", approval_required=True, next_action=approval_template())
                return result
            confirmation = dict(evidence, registry_sha256=rebuild["registry_sha256"],
                                reference="interactive separate global registry rebuild confirmation")
    else:
        result.update(status="approval_required", approval_required=True,
                      next_action=approval_template())
        return result
    if choice == "yes" and memory_agents and source is None:
        raise EnableError("provider_source_missing", "Confirm an existing Keeper checkout; no source download/fallback is permitted")
    if not locked:
        # Inspection is write-free; only an authorized execution takes the shared lock.
        # Replan under that lock so approval and machine state cannot race.
        approved_request = dict(request, approval=dict(actual_plan, **evidence))
        if rebuild:
            approved_request["approval"]["rebuild_confirmation"] = confirmation
        with write_lock(runtime.lock):
            return _run_locked(approved_request, runtime, result, locked=True)
    p["memory_authorization"], p["authorization_evidence"] = choice, evidence
    if choice == "yes" and memory_agents:
        p["provider_source"] = str(source)
        assembly["store"] = {"path": str(store), "location_approved": True, "approval_evidence": evidence}
        assembly["states"]["source_available"] = _fact("ready", _source_evidence(fingerprints))
        # All relevant outputs have already been drift-checked. Preview never counts as ready.
        argv = ["install.py", "--project", str(root)] + ["--" + a for a in memory_agents]
        preview = _call(request, source, argv, allow_preview=True, fingerprints=fingerprints)
        all_links = {o["path"] for o in assembly["objects"].values() if o["kind"] == "skill_symlink" and set(o["agents"]) & set(memory_agents)}
        expected_rules = {paths.expand_path(config[a]["project_bridge_entry"], home=home, project=key) for a in memory_agents}
        if (set(preview.get("skill_entries", [])) != all_links or set(preview.get("rule_files", [])) != expected_rules):
            raise EnableError("provider_scope_mismatch", "Keeper preview declared unexpected project outputs")
        init_argv = ["context_keeper_probe.py", "init", "--root", str(root), "--store-dir", str(store)]
        _call(request, source, init_argv, allow_preview=True, fingerprints=fingerprints)
        for a in memory_agents:
            assembly["states"]["skill_installed"][a] = _fact("ready", "verified project links: " + str(source))
            assembly["states"]["bridge_assembled"][a] = _fact("ready", config[a]["project_bridge_entry"])
        assembly["states"]["store_authorized_ready"] = _fact("ready", "Keeper init + metadata readback: " + str(store))
    else:
        assembly["states"]["store_authorized_ready"] = _fact("blocked", "memory authorization is no" if choice=='no' else 'WorkBuddy must create its native memory directory first')
    if choice=='no':
        for a in assembly['agents']:
            assembly['states']['bridge_assembled'][a]=_fact('blocked','Automatic project memory authorization revoked; historical assets retained')
            assembly['states']['skill_installed'][a]=_fact('unknown','Created trigger links removed; reused links confer no authorization')
    if native_pending and choice=='yes':
        for phase in ('skill_installed','bridge_assembled'):
            assembly['states'][phase]['workbuddy']=_fact('blocked','Open the project in WorkBuddy first; AGM does not create native .workbuddy/memory')

    assembly["runtime_acceptance"] = {"status": "pending", "evidence_path": None}
    # Normalize file/import reuse hashes after all overlapping block edits.
    for obj in list(assembly["objects"].values()) + [data["shared_objects"][oid] for oid in assembly["shared_object_ids"]]:
        if obj["kind"] in ("file", "import") and obj["ownership"] != "created" and not entries.free_project_rules(obj) and Path(obj["path"]) in plan.after:
            obj["fingerprint"]["value"] = plan.after[Path(obj["path"])].fingerprint
    called = []
    def hook(event, path):
        if event == "before_write" and not called:
            if project.resolve_project(root).git_common_dir != identity.git_common_dir:
                raise EnableError("project_identity_mismatch", "Git identity changed after approval")
            if source and _source_fingerprints(source) != fingerprints:
                raise EnableError("approval_mismatch", "Keeper source changed after approval")
            if source and _candidate_store(root) != initial_store:
                raise EnableError("approval_mismatch", "Keeper store configuration changed after approval")
            for output, snap in plan.before.items():
                if read_snapshot(output) != snap:
                    raise EnableError("drift", "Output changed after approval: " + str(output))
            called.append(True)
        if event == "before_write" and path == registry_path and choice == "yes" and memory_agents:
            # Before the registry commit the config is current; provider calls must be no-op.
            installed = _call(request, source, argv + ["--approved"], fingerprints=fingerprints)
            if installed.get("scope") != "project" or installed.get("project") != str(root):
                raise EnableError("provider_scope_mismatch", "Keeper installation is not for this project")
            for a in memory_agents:
                alias = Path(paths.expand_path(config[a]["project_skill_roots"][0], home=home, project=key)) / "context-keeper"
                ensured = _call(request, source, ["install.py", "--ensure-bridge", "--skill-dir", str(alias),
                                "--root", str(root), "--" + a, "--approved"], fingerprints=fingerprints)
                if (ensured.get("scope") != "project" or ensured.get("bridge") != paths.expand_path(config[a]["project_bridge_entry"], home=home, project=key)
                        or ensured.get("action") != "unchanged"):
                    raise EnableError("provider_scope_mismatch", "ensure-bridge did not verify an unchanged project bridge")
            for output, snap in plan.after.items():
                if read_snapshot(output) != snap:
                    raise EnableError("provider_protocol_invalid", "Keeper unexpectedly changed staged config")
            _call(request, source, init_argv + ["--approved"], fingerprints=fingerprints)
            # After rc=3 _call raises before any record metadata readback.
            if _candidate_store(root) != store or not all((store / name).is_dir() for name in ("plans", "worklogs", "evolution")) or not (store / "memory-keeper.md").is_file():
                raise EnableError("store_unavailable", "Keeper init did not produce the approved usable store; preserve partial assets")
        external = request.get("transaction_hook")
        if external:
            external(event, path)
    tx.hook = hook
    try:
        committed = registry.commit_registry(registry_path, data, transaction=tx, expected=expected_registry,
                          changes=plan.changes(), allowed_user_paths=allowed,
                          previous=previous_registry, rebuild=rebuild,
                          rebuild_confirmation=confirmation if rebuild else None)
    except TransactionError as exc:
        # Preserve semantic provider error across the shared transaction's rollback wrapper.
        cause = exc.__cause__
        if isinstance(cause, EnableError) and exc.code != "recovery_required":
            result["warnings"].append("Configuration rolled back; any Keeper store/config assets are preserved.")
            raise cause
        raise
    result["status"] = "gaps" if native_pending and choice=="yes" else "completed"
    result["changes"] = [dict(item, ownership=_change_ownership(plan, item["path"]), applied=True) for item in plan.description()]
    result["projects"] = [{"main_checkout": key, "checkout": str(root), "states": assembly["states"],
                           "agents": assembly["agents"], "evidence": [str(registry_path)],
                           "runtime_acceptance": assembly["runtime_acceptance"]}]
    if revoke_conflicts:result["warnings"].append("Historical reused triggers preserved; explicit project memory denial guards installed")
    if native_pending:result["warnings"].append("WorkBuddy native .workbuddy/memory must be created by WorkBuddy; no AGM mkdir")
    result["warnings"].append("Runtime acceptance pending; same-path replacement of .git cannot be reliably detected by schema v1.")
    if rebuild:
        result["warnings"].append("Corrupt registry backed up; prior authorization/created ownership was not recovered.")
    return result
