"""Strict versioned registry validation; reads never create state or locks.

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
    """An explicit uninstalled schema-v2 model, never an on-disk initializer."""
    return {"schema_version": 2, "projects": {}, "shared_objects": {},
            "product": None, "machine": {"agents": {}, "objects": {}},
            "migration": None, "legacy_import": None}


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


def validate_registry_v1(data, *, allowed_user_paths=None, _pending_manifest=None):
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



def _digest(value):
    if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value):
        _fail("expected SHA-256 digest")


def _runtime(value):
    _keys(value, "status evidence_path", "runtime")
    if value["status"] not in ("pending", "passed", "failed"):
        _fail("unknown runtime status")
    if value["evidence_path"] is not None:
        _path(value["evidence_path"])
    if value["status"] != "pending" and (value["evidence_path"] is None or not Path(value["evidence_path"]).is_file()):
        _fail("runtime evidence unavailable")


def validate_registry(data, *, allowed_user_paths=None, _pending_manifest=None):
    """Active v2 only. Legacy v1 is available solely via explicit diagnostic APIs."""
    if isinstance(data, dict) and type(data.get("schema_version")) is int and data["schema_version"] == 1:
        raise RegistryMigrationRequired("schema=1 requires explicit machine migration; no fallback/rebuild")
    _keys(data, "schema_version projects shared_objects product machine migration legacy_import", "registry")
    if type(data["schema_version"]) is not int or data["schema_version"] != 2:
        _fail("unsupported registry schema")
    validate_registry_v1({"schema_version": 1, "projects": data["projects"],
                          "shared_objects": data["shared_objects"]},
                         allowed_user_paths=allowed_user_paths, _pending_manifest=_pending_manifest)
    product = data["product"]
    if product is not None:
        _keys(product, "product_id installation_id product_structure_version product_code_version source installation_status last_operation_id", "product")
        if product["product_id"] != "agent-group-memory":
            _fail("product identity mismatch")
        _text(product["installation_id"])
        if type(product["product_structure_version"]) is not int or product["product_structure_version"] != 1:
            _fail("unsupported product structure version")
        if not isinstance(product["product_code_version"], str) or not re.fullmatch(
                r"(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?", product["product_code_version"]):
            _fail("invalid product code SemVer")
        _keys(product["source"], "url commit tree_sha256", "product source")
        _text(product["source"]["url"])
        if not isinstance(product["source"]["commit"], str) or not re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", product["source"]["commit"]):
            _fail("invalid source commit")
        _digest(product["source"]["tree_sha256"])
        if product["installation_status"] not in ("complete", "installing", "recovery_required"):
            _fail("unknown installation status")
        _text(product["last_operation_id"])
    machine = data["machine"]
    _keys(machine, "agents objects", "machine")
    if not isinstance(machine["agents"], dict) or not set(machine["agents"]) <= set(AGENTS):
        _fail("invalid machine agents")
    for record in machine["agents"].values():
        _keys(record, "installation static runtime_acceptance", "machine agent")
        installation = record["installation"]
        _keys(installation, "status observed_at evidence", "agent installation")
        if installation["status"] not in ("installed", "absent", "unknown"):
            _fail("invalid installation fact")
        _fact(dict(installation, status={"installed": "ready", "absent": "missing", "unknown": "unknown"}[installation["status"]]))
        _fact(record["static"])
        _runtime(record["runtime_acceptance"])
    if not isinstance(machine["objects"], dict):
        _fail("invalid machine objects")
    existing = _objects(dict(data, machine={"objects": {}}))
    units = {(o["path"], json.dumps(o["marker"], sort_keys=True)) for o in existing.values()}
    for oid, obj in machine["objects"].items():
        _text(oid)
        if oid in existing or not isinstance(obj, dict) or obj.get("scope") != "machine":
            _fail("machine object identity collision/scope mismatch")
        _object(dict(obj, scope="user"), "user", None,
                None if allowed_user_paths is None else set(allowed_user_paths), _pending_manifest)
        if obj["consumers"] != []:
            _fail("machine objects cannot use project consumers")
        if not set(obj["agents"]) <= set(machine["agents"]):
            _fail("machine object has no agent installation record")
        unit = (obj["path"], json.dumps(obj["marker"], sort_keys=True))
        if unit in units:
            _fail("duplicate machine unit; reference existing shared object instead")
        units.add(unit)
    migration = data["migration"]
    if migration is not None:
        _keys(migration, "operation_id source_registry source_sha256 archive_root reference_map tombstones status", "migration")
        _text(migration["operation_id"])
        _path(migration["source_registry"])
        _digest(migration["source_sha256"])
        _path(migration["archive_root"])
        if migration["status"] not in ("prepared", "committed", "recovery_required", "rolled_back"):
            _fail("unknown migration status")
        if not isinstance(migration["reference_map"], dict):
            _fail("invalid reference map")
        for old, target in migration["reference_map"].items():
            _path(old)
            _keys(target, "path sha256 kind", "archived reference")
            _path(target["path"])
            _digest(target["sha256"])
            if target["kind"] != "file":
                _fail("unsupported archived evidence kind")
        if not isinstance(migration["tombstones"], dict):
            _fail("invalid tombstones")
        for path, digest in migration["tombstones"].items():
            _path(path)
            _digest(digest)
    imported = data["legacy_import"]
    if imported is not None:
        _keys(imported, "operation_id source_tree_sha256 manifest_path status", "legacy import")
        _text(imported["operation_id"])
        _digest(imported["source_tree_sha256"])
        _path(imported["manifest_path"])
        if imported["status"] not in ("prepared", "snapshot_complete", "applying", "outputs_verified", "committed", "recovery_required", "rolled_back"):
            _fail("unknown legacy import status")
    return data


class RegistryMigrationRequired(RegistryError):
    code = "registry_migration_required"


def require_installed(data):
    """Project writers cannot initialize or repair the machine installation."""
    if data["product"] is None:
        raise RegistryError("Machine product missing; use INSTALL.md and scripts/install.py")
    if data["product"]["installation_status"] != "complete":
        raise RegistryError("Machine installation incomplete; explicit recovery required")
    for name in ("migration", "legacy_import"):
        state = data[name]
        if state is not None and state["status"] not in ("committed", "rolled_back"):
            raise RegistryError("Machine operation incomplete; explicit recovery required")
    return data

def _no_duplicates(pairs):
    obj = {}
    for key, value in pairs:
        if key in obj:
            _fail("duplicate JSON key: " + key)
        obj[key] = value
    return obj


def _load_registry(path, *, allowed_user_paths=None, legacy=False):
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
    validator = validate_registry_v1 if legacy else validate_registry
    return validator(data, allowed_user_paths=allowed_user_paths)


def load_registry(path, *, allowed_user_paths=None):
    return _load_registry(path, allowed_user_paths=allowed_user_paths)


def load_legacy_registry(path, *, allowed_user_paths=None):
    """Explicit strict v1 diagnostic/migration input; never used by project writers."""
    return _load_registry(path, allowed_user_paths=allowed_user_paths, legacy=True)


def serialize_registry(data, *, allowed_user_paths=None, _pending_manifest=None):
    validate_registry(data, allowed_user_paths=allowed_user_paths, _pending_manifest=_pending_manifest)
    result = copy.deepcopy(data)
    for project in result["projects"].values():
        for assembly in project["checkouts"].values():
            assembly["agents"].sort(key=AGENTS.index)
            for obj in assembly["objects"].values():
                obj["agents"].sort(key=AGENTS.index)
    for obj in list(result["shared_objects"].values()) + list(result["machine"]["objects"].values()):
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
    result.update(data.get("machine", {}).get("objects", {}))
    for project in data["projects"].values():
        for assembly in project["checkouts"].values():
            result.update(assembly["objects"])
    return result


def commit_registry(path, data, *, transaction, expected, changes=(),
                    allowed_user_paths=None, previous=None, rebuild=False):
    """Validate and commit registry last, including evidence for new created units.

    expected is the exact registry snapshot read by the caller. Existing valid
    ownership cannot be promoted by omitting previous. Corrupt/legacy active
    state is never rebuilt, including when an old caller passes rebuild=True.
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
            raise RegistryError("Active registry invalid; explicit machine recovery required") from exc
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
