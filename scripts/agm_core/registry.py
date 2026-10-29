"""Strict schema-v1 registry validation; reads never create state or locks.

User paths are supplied by the validated platform path table, not inferred here.
Atomic writes are delegated to transaction.Transaction; a registry must be its
last change. Missing/corrupt registries are never silently defaulted on load.
"""
import copy
import json
import os
import re
from datetime import datetime
from pathlib import Path

AGENTS = ("codex", "claude", "workbuddy")
OWNERSHIP = ("created", "reused", "unknown")


class RegistryError(ValueError):
    code = "registry_invalid"


def _fail(message):
    raise RegistryError(message)


def _keys(value, names, label):
    if not isinstance(value, dict) or set(value) != set(names.split()):
        _fail(label + ": missing or unknown fields")


def _text(value):
    if not isinstance(value, str) or not value.strip():
        _fail("expected nonempty text")


def _path(value, *, resolve=False):
    _text(value)
    p = Path(value)
    if not p.is_absolute() or os.path.normpath(value) != value or "~" in p.parts or "\x00" in value:
        _fail("expected normalized absolute path: " + repr(value))
    if resolve and str(p.resolve()) != value:
        _fail("path is not canonical: " + value)
    return p


def _time(value):
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d+)?Z", value):
        _fail("expected UTC timestamp")
    try:
        datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError:
        _fail("invalid UTC timestamp")


def _evidence(value):
    _keys(value, "confirmed_at reference", "evidence")
    _time(value["confirmed_at"])
    _text(value["reference"])


def _unique(value, allowed=None, *, nonempty=False):
    if not isinstance(value, list) or (nonempty and not value):
        _fail("expected array")
    for item in value:
        _text(item)
    if len(set(value)) != len(value) or (allowed is not None and not set(value) <= set(allowed)):
        _fail("duplicate or unknown array member")


def _fact(value):
    _keys(value, "status observed_at evidence", "fact")
    if value["status"] not in ("ready", "missing", "blocked", "unknown"):
        _fail("unknown fact status")
    if value["observed_at"] is not None:
        _time(value["observed_at"])
    if value["evidence"] is not None:
        _text(value["evidence"])
    if value["status"] != "unknown" and (value["observed_at"] is None or value["evidence"] is None):
        _fail("observed fact requires timestamp and evidence")
    if (value["observed_at"] is None) != (value["evidence"] is None):
        _fail("fact timestamp/evidence must be paired")


def _within(path, root):
    try:
        path.relative_to(root)
        return path != root
    except ValueError:
        return False


def _object(obj, scope, checkout, allowed_user_paths, pending_manifest=None):
    _keys(obj, "kind path scope agents ownership marker fingerprint original_existed link_target backup_manifest consumers", "object")
    kind = obj["kind"]
    if kind not in ("file", "block", "import", "skill_symlink", "user_convention") or obj["scope"] != scope:
        _fail("invalid object kind/scope")
    p = _path(obj["path"])
    # A symlink leaf is legal only for skill_symlink. Parents must be real paths.
    if str(p.parent.resolve() / p.name) != str(p):
        _fail("object output has a symlink parent")
    if scope == "project" and not _within(p, Path(checkout)):
        _fail("project object outside checkout")
    if scope == "user" and (allowed_user_paths is None or str(p) not in allowed_user_paths):
        _fail("user object is not in the verified path table")
    _unique(obj["agents"], AGENTS, nonempty=True)
    if obj["ownership"] not in OWNERSHIP:
        _fail("unknown ownership")
    if obj["original_existed"] is not None and type(obj["original_existed"]) is not bool:
        _fail("invalid original_existed")
    marker, fp = obj["marker"], obj["fingerprint"]
    if marker is not None:
        _keys(marker, "start end", "marker")
        _text(marker["start"])
        _text(marker["end"])
        if marker["start"] == marker["end"] or marker["start"] in marker["end"] or marker["end"] in marker["start"]:
            _fail("ambiguous marker")
    if kind in ("block", "user_convention"):
        if marker is None:
            _fail("block requires markers")
        basis = "block_bytes"
    elif kind == "skill_symlink":
        if marker is not None or obj["link_target"] is None:
            _fail("link requires target and no marker")
        _path(obj["link_target"], resolve=True)
        basis = "link_target"
    else:
        if marker is not None:
            _fail("file/import cannot have markers")
        basis = "file_bytes"
    if kind != "skill_symlink" and obj["link_target"] is not None:
        _fail("nonlink has link target")
    if fp is not None:
        _keys(fp, "algorithm basis value", "fingerprint")
        if fp["algorithm"] != "sha256" or fp["basis"] != basis or not isinstance(fp["value"], str) or not re.fullmatch("[0-9a-f]{64}", fp["value"]):
            _fail("invalid fingerprint")
    if obj["backup_manifest"] is not None:
        _path(obj["backup_manifest"])
    ownership = obj["ownership"]
    if ownership == "created":
        if obj["original_existed"] is not False or fp is None or obj["backup_manifest"] is None:
            _fail("created lacks creation evidence")
        if obj["backup_manifest"] != pending_manifest and not Path(obj["backup_manifest"]).is_file():
            _fail("created backup manifest is unavailable")
    if ownership == "reused" and (obj["original_existed"] is not True or fp is None):
        _fail("reused lacks verification evidence")
    if kind == "import" and ownership == "created":
        _fail("schema v1 cannot own import deletion")
    _unique(obj["consumers"])
    for consumer in obj["consumers"]:
        _path(consumer, resolve=True)
    if scope == "project" and obj["consumers"] != [checkout]:
        _fail("project consumers must equal checkout")


def empty_registry():
    return {"schema_version": 1, "projects": {}, "shared_objects": {}}


def unknown_fact():
    return {"status": "unknown", "observed_at": None, "evidence": None}


def new_project(identity, agents):
    _unique(agents, AGENTS, nonempty=True)
    selected = [a for a in AGENTS if a in agents]
    if not identity.is_main:
        _fail("M2 supports only the main checkout")
    assembly = {"git_common_dir": str(identity.git_common_dir), "agents": selected,
                "states": {"source_available": unknown_fact(),
                           "skill_installed": {a: unknown_fact() for a in selected},
                           "bridge_assembled": {a: unknown_fact() for a in selected},
                           "store_authorized_ready": unknown_fact()},
                "store": {"path": None, "location_approved": False, "approval_evidence": None},
                "objects": {}, "shared_object_ids": [],
                "runtime_acceptance": {"status": "pending", "evidence_path": None}}
    return {"main_checkout": str(identity.main_checkout), "memory_authorization": None,
            "authorization_evidence": None, "provider_source": None,
            "checkouts": {str(identity.checkout): assembly}}


def validate_registry(data, *, allowed_user_paths=None, _pending_manifest=None):
    """Validate exact schema and cross-references, without changing data or disk.

    allowed_user_paths must be provided when user-scoped objects exist.
    Runtime acceptance evidence and created manifests must remain locatable.
    """
    allowed = None if allowed_user_paths is None else {str(_path(str(p))) for p in allowed_user_paths}
    _keys(data, "schema_version projects shared_objects", "registry")
    if type(data["schema_version"]) is not int or data["schema_version"] != 1:
        _fail("unsupported registry schema")
    if not isinstance(data["projects"], dict) or not isinstance(data["shared_objects"], dict):
        _fail("invalid registry maps")
    ids, units, checkouts = set(), set(), {}

    def register(oid, obj, scope, checkout=None):
        _text(oid)
        if oid in ids:
            _fail("duplicate object ID")
        ids.add(oid)
        _object(obj, scope, checkout, allowed, _pending_manifest)
        if obj["marker"] is not None:
            unit = (obj["path"], obj["marker"]["start"], obj["marker"]["end"])
            if unit in units:
                _fail("duplicate managed block")
            units.add(unit)

    for main, project in data["projects"].items():
        _path(main, resolve=True)
        _keys(project, "main_checkout memory_authorization authorization_evidence provider_source checkouts", "project")
        if project["main_checkout"] != main:
            _fail("project key mismatch")
        auth, evidence = project["memory_authorization"], project["authorization_evidence"]
        if auth is not None and auth not in ("yes", "no"):
            _fail("invalid memory authorization")
        if (auth is None) != (evidence is None):
            _fail("authorization/evidence mismatch")
        if evidence is not None:
            _evidence(evidence)
        if project["provider_source"] is not None:
            _path(project["provider_source"], resolve=True)
        if not isinstance(project["checkouts"], dict) or set(project["checkouts"]) != {main}:
            _fail("M2 registry supports only one main checkout")
        for checkout, assembly in project["checkouts"].items():
            _keys(assembly, "git_common_dir agents states store objects shared_object_ids runtime_acceptance", "assembly")
            _path(assembly["git_common_dir"], resolve=True)
            _unique(assembly["agents"], AGENTS, nonempty=True)
            states = assembly["states"]
            _keys(states, "source_available skill_installed bridge_assembled store_authorized_ready", "states")
            _fact(states["source_available"])
            _fact(states["store_authorized_ready"])
            for name in ("skill_installed", "bridge_assembled"):
                if not isinstance(states[name], dict) or set(states[name]) != set(assembly["agents"]):
                    _fail("fact agents mismatch")
                for fact in states[name].values():
                    _fact(fact)
            store = assembly["store"]
            _keys(store, "path location_approved approval_evidence", "store")
            if type(store["location_approved"]) is not bool:
                _fail("invalid location approval")
            if store["path"] is not None:
                _path(store["path"], resolve=True)
            if store["location_approved"]:
                if store["path"] is None or store["approval_evidence"] is None:
                    _fail("store approval lacks path/evidence")
                _evidence(store["approval_evidence"])
            elif store["approval_evidence"] is not None:
                _fail("unapproved store has approval evidence")
            if states["store_authorized_ready"]["status"] == "ready" and (auth != "yes" or not store["location_approved"]):
                _fail("ready store is not authorized")
            runtime = assembly["runtime_acceptance"]
            _keys(runtime, "status evidence_path", "runtime")
            if runtime["status"] not in ("pending", "passed", "failed"):
                _fail("unknown runtime status")
            if runtime["evidence_path"] is not None:
                _path(runtime["evidence_path"])
            if runtime["status"] != "pending" and (runtime["evidence_path"] is None or not Path(runtime["evidence_path"]).exists()):
                _fail("runtime evidence unavailable")
            if not isinstance(assembly["objects"], dict):
                _fail("invalid object map")
            for oid, obj in assembly["objects"].items():
                register(oid, obj, "project", checkout)
                if not set(obj["agents"]) <= set(assembly["agents"]):
                    _fail("object uses unselected agent")
            _unique(assembly["shared_object_ids"])
            checkouts[checkout] = assembly
    for oid, obj in data["shared_objects"].items():
        register(oid, obj, "user")
        if not set(obj["consumers"]) <= set(checkouts):
            _fail("unknown shared consumer")
    for checkout, assembly in checkouts.items():
        referenced = set(assembly["shared_object_ids"])
        if not referenced <= set(data["shared_objects"]):
            _fail("unknown shared reference")
        for oid, obj in data["shared_objects"].items():
            if (oid in referenced) != (checkout in obj["consumers"]):
                _fail("shared consumer/reference mismatch")
    return data


def _no_duplicates(pairs):
    obj = {}
    for key, value in pairs:
        if key in obj:
            _fail("duplicate JSON key: " + key)
        obj[key] = value
    return obj


def load_registry(path, *, allowed_user_paths=None):
    path = Path(path)
    if path.is_symlink() or str(path.parent.resolve() / path.name) != str(path.absolute()):
        _fail("registry path is a symlink or has a symlink parent")
    try:
        data = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_no_duplicates,
                          parse_constant=lambda x: _fail("nonfinite JSON value"))
    except (OSError, UnicodeError, ValueError) as exc:
        if isinstance(exc, RegistryError):
            raise
        raise RegistryError("cannot read registry: " + str(exc)) from exc
    return validate_registry(data, allowed_user_paths=allowed_user_paths)


def serialize_registry(data, *, allowed_user_paths=None, _pending_manifest=None):
    validate_registry(data, allowed_user_paths=allowed_user_paths, _pending_manifest=_pending_manifest)
    result = copy.deepcopy(data)
    for project in result["projects"].values():
        for assembly in project["checkouts"].values():
            assembly["agents"].sort(key=AGENTS.index)
            for obj in assembly["objects"].values():
                obj["agents"].sort(key=AGENTS.index)
    for obj in result["shared_objects"].values():
        obj["agents"].sort(key=AGENTS.index)
    return (json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def recovered_object(obj, *, verified=False):
    """O7: reconstruct observable units without recovering deletion rights."""
    result = copy.deepcopy(obj)
    result["ownership"] = "reused" if verified else "unknown"
    result["original_existed"] = True if verified else None
    result["backup_manifest"] = None
    return result


def _unit_fingerprint(snapshot, obj):
    from .entries import block_fingerprint, link_fingerprint, sha256
    if snapshot.kind == "absent":
        return None
    kind = obj["kind"]
    if kind in ("block", "user_convention") and snapshot.kind == "file":
        return block_fingerprint(snapshot.data, obj["marker"]["start"], obj["marker"]["end"])
    if kind in ("file", "import") and snapshot.kind == "file":
        return sha256(snapshot.data)
    if kind == "skill_symlink" and snapshot.kind == "symlink":
        # Resolve relative targets against the link's location, not cwd.
        return link_fingerprint(Path(obj["path"]).parent / snapshot.target)
    _fail("object and output type conflict")


def validate_ownership_transition(previous, current, *, changes=()):
    """No ownership escalation or refreshing a created baseline over drift."""
    before, after = _objects(previous), _objects(current)
    writes = {str(c.path): c for c in changes}
    for oid in before.keys() & after.keys():
        old, new = before[oid], after[oid]
        if old["ownership"] != "created" and new["ownership"] == "created":
            _fail("cannot recover created ownership: " + oid)
        if old["ownership"] == "created":
            if new["ownership"] != "created":
                _fail("cannot silently discard created ownership")
            for name in ("kind", "path", "scope", "marker", "original_existed", "link_target"):
                if old[name] != new[name]:
                    _fail("cannot change identity of a created unit")
            change = writes.get(old["path"])
            if change is not None:
                actual = _unit_fingerprint(change.expected, old)
                if actual is not None and actual != old["fingerprint"]["value"]:
                    _fail("created unit drifted; preserve its expected fingerprint")
                if _unit_fingerprint(change.after, new) != new["fingerprint"]["value"]:
                    _fail("created unit after fingerprint does not match write")
            elif old["fingerprint"] != new["fingerprint"] or old["backup_manifest"] != new["backup_manifest"]:
                _fail("cannot refresh created evidence without a verified change")


def _objects(data):
    result = dict(data["shared_objects"])
    for project in data["projects"].values():
        for assembly in project["checkouts"].values():
            result.update(assembly["objects"])
    return result


def commit_registry(path, data, *, transaction, expected, changes=(),
                    allowed_user_paths=None, previous=None, rebuild=False):
    """Validate and commit registry last, including evidence for new created units.

    expected is the exact registry snapshot read by the caller. Existing valid
    ownership cannot be promoted by omitting previous. Explicit rebuild=True is
    required for corrupt/missing history; its old objects cannot become created.
    New created records must bind to an absent unit in this transaction's write
    set and to its actual manifest path, including when the manifest is pending.
    """
    from .entries import block_fingerprint, link_fingerprint, sha256
    from .transaction import Change
    changes = list(changes)
    validate_registry(data, allowed_user_paths=allowed_user_paths,
                      _pending_manifest=str(transaction.manifest_path))
    if expected.kind == "file":
        try:
            observed = json.loads(expected.data.decode("utf-8"), object_pairs_hook=_no_duplicates)
            validate_registry(observed, allowed_user_paths=allowed_user_paths)
        except (ValueError, UnicodeError) as exc:
            if not rebuild:
                raise RegistryError("corrupt registry requires explicit authorized rebuild") from exc
            observed = empty_registry()
    elif expected.kind == "absent":
        observed = empty_registry()
    else:
        _fail("registry is not a regular file")
    if previous is not None and previous != observed:
        _fail("previous registry does not match the expected snapshot")
    validate_ownership_transition(observed, data, changes=changes)
    before_objects = _objects(observed)
    by_path = {str(change.path): change for change in changes}
    for oid, obj in _objects(data).items():
        if obj["ownership"] != "created" or oid in before_objects:
            continue
        change = by_path.get(obj["path"])
        if change is None or obj["backup_manifest"] != str(transaction.manifest_path):
            _fail("new created unit must bind to this transaction's write/manifest")
        before, after = change.expected, change.after
        if obj["kind"] in ("block", "user_convention"):
            marker = obj["marker"]
            if before.kind not in ("absent", "file") or after.kind != "file":
                _fail("block creation is not a file change")
            if block_fingerprint(before.data or b"", marker["start"], marker["end"]) is not None:
                _fail("cannot claim an existing block as created")
            actual = block_fingerprint(after.data, marker["start"], marker["end"])
        elif obj["kind"] == "file":
            if before.kind != "absent" or after.kind != "file":
                _fail("cannot claim an existing file as created")
            actual = sha256(after.data)
        elif obj["kind"] == "skill_symlink":
            if before.kind != "absent" or after.kind != "symlink" or str(Path(after.target).resolve()) != obj["link_target"]:
                _fail("cannot claim an existing link as created")
            actual = link_fingerprint(after.target)
        else:
            _fail("unsupported created unit")
        if obj["fingerprint"] is None or actual != obj["fingerprint"]["value"]:
            _fail("creation fingerprint does not match actual write")
    content = serialize_registry(data, allowed_user_paths=allowed_user_paths,
                                 _pending_manifest=str(transaction.manifest_path))
    return transaction.run(changes, registry_change=Change.file(path, content, expected=expected))
