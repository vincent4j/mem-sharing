"""Explicit M2/M3 ledger handoff, for the machine installer to call.

No import-time work, default HOME, source search, project command, network access
or implicit migration. plan_migration/inspect_migration/plan_recovery are read-only.
The caller must present their exact plans to the user before passing approval.
Target product metadata is installer input; this module does not install code or
claim a new-session/runtime acceptance. Free-text evidence is retained verbatim;
additional file evidence can be enumerated explicitly with evidence_files.
"""
import copy
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import uuid
from contextlib import ExitStack, contextmanager
from datetime import datetime, timezone

from . import registry
from .layout import RuntimeLayout
from .transaction import Snapshot, TransactionError, _atomic_file, _safe_path, read_snapshot, write_lock


class MigrationError(ValueError):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


def _fail(message, code="migration_conflict"):
    raise MigrationError(code, message)


def _bytes(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _json(path):
    snap = read_snapshot(Path(path))
    if snap.kind != "file":
        _fail("Expected ordinary JSON file: " + str(path))
    return json.loads(snap.data.decode("utf-8"), object_pairs_hook=registry._no_duplicates,
                      parse_constant=lambda value: _fail("nonfinite JSON"))


def _op(value):
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,127}", value):
        _fail("Invalid operation ID")
    return value


def _canonical(path):
    path = Path(path)
    if not path.is_absolute() or path != path.resolve():
        _fail("Canonical absolute path required: " + str(path))
    return _safe_path(path)


def _layout(runtime):
    if not isinstance(runtime, RuntimeLayout):
        _fail("Explicit RuntimeLayout required")
    runtime.validate_paths()
    # Existing transaction primitives require canonical write paths. A caller can
    # resolve an environment alias before planning; we never change a bound plan.
    _canonical(runtime.home)
    if not runtime.home.is_dir():
        _fail("Explicit HOME directory must already exist")
    return runtime


def _archive_target(archive, source):
    return archive / "files" / _sha(str(source.parent).encode("utf-8")) / source.name


def _code_inventory(source, commit):
    root = source.parent.parent
    if source.name != "registry.json" or source.parent.name != "scripts":
        _fail("Legacy input must be an explicit product scripts/registry.json")
    if not isinstance(commit, str) or not re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", commit):
        _fail("Pinned legacy commit required")
    required = [root / "SKILL.md", root / "scripts/agm.py", root / "scripts/agents.json",
                root / "scripts/agm_core/registry.py", root / "scripts/agm_core/transaction.py",
                root / "scripts/agm_core/enable.py"]
    candidates = set(required)
    core = root / "scripts/agm_core"
    for parent, dirs, files in os.walk(core, followlinks=False):
        if any((Path(parent) / name).is_symlink() for name in dirs):
            _fail("Legacy code contains symlink directories")
        candidates.update(Path(parent) / name for name in files if name.endswith(".py"))
    inventory = {}
    for path in sorted(candidates):
        _canonical(path)
        snap = read_snapshot(path)
        if snap.kind != "file":
            _fail("Missing legacy product code: " + str(path))
        inventory[str(path)] = {"sha256": snap.fingerprint, "mode": snap.mode}
    if b"agent-group-memory" not in (root / "SKILL.md").read_bytes():
        _fail("Legacy source product identity missing")
    if (root / ".git").exists():
        result = subprocess.run(["git", "-C", str(root), "rev-parse", "--verify", "HEAD"],
                                env=dict(os.environ, GIT_OPTIONAL_LOCKS="0"),
                                capture_output=True, text=True)
        if result.returncode or result.stdout.strip() != commit:
            _fail("Legacy checkout commit changed")
        status = subprocess.run(["git", "-c", "core.fsmonitor=false", "-c", "core.untrackedCache=false",
            "-C", str(root), "status", "--porcelain=v1", "--untracked-files=all", "--",
            "SKILL.md", "scripts/agm.py", "scripts/agents.json", "scripts/agm_core"],
            env=dict(os.environ, GIT_OPTIONAL_LOCKS="0"), capture_output=True, text=True)
        if status.returncode or status.stdout:
            _fail("Legacy managed code is dirty or contains untracked code; preserve source")
    return {"registry": str(source), "code_root": str(root), "commit": commit,
            "files": inventory, "tree_sha256": _sha(_bytes(inventory))}


def _materialize_inputs(sources, commits, evidence_files, allowed, archive):
    """Read a transitive recovery closure; never execute a legacy script."""
    files, manifests, ledgers = {}, set(), set()
    original_backup_manifests = {}
    source_infos = [_code_inventory(path, commits[str(path)]) for path in sources]
    first_raw = None

    def add(path):
        path = _canonical(path)
        raw = read_snapshot(path)
        if raw.kind != "file":
            _fail("Required recovery material missing/not a file: " + str(path))
        key = str(path)
        record = {"source": key, "target": str(_archive_target(archive, path)),
                  "sha256": raw.fingerprint, "mode": raw.mode, "size": len(raw.data)}
        if key in files and files[key] != record:
            _fail("Source changed during inspection: " + key, "source_drift")
        files[key] = record
        return raw.data

    def ledger(data):
        # Strict v1 stays strict. In particular, missing created evidence is fatal.
        registry.validate_registry_v1(data, allowed_user_paths=allowed)
        for oid, obj in registry._objects(data).items():
            if obj["backup_manifest"] is not None:
                original_backup_manifests.setdefault(oid, obj["backup_manifest"])
                manifest(Path(obj["backup_manifest"]))
        for project in data["projects"].values():
            for assembly in project["checkouts"].values():
                path = assembly["runtime_acceptance"]["evidence_path"]
                if path is not None:
                    add(Path(path))
        # An exact file locator is archiveable. Human references and composite
        # evidence strings stay unchanged; explicit evidence_files cover their
        # caller-reviewed file dependencies without guessing/tokenizing prose.
        def evidence(value):
            if isinstance(value, dict):
                for key, item in value.items():
                    if key in ("reference", "evidence") and isinstance(item, str):
                        candidate = Path(item)
                        if candidate.is_absolute() and candidate.is_file():
                            add(candidate)
                    elif isinstance(item, (dict, list)):
                        evidence(item)
            elif isinstance(value, list):
                for item in value:
                    evidence(item)
        evidence(data)

    def manifest(path):
        key = str(path)
        if key in manifests:
            return
        manifests.add(key)
        raw = add(path)
        data = json.loads(raw.decode("utf-8"), object_pairs_hook=registry._no_duplicates)
        registry._keys(data, "schema_version operation status registry_path created_directories entries error", "legacy transaction")
        if type(data["schema_version"]) is not int or data["schema_version"] != 1:
            _fail("Unsupported legacy transaction schema")
        if data["status"] not in ("committed", "rolled_back"):
            _fail("Unfinished legacy transaction requires legacy recovery first")
        if not isinstance(data["entries"], list) or not isinstance(data["created_directories"], list):
            _fail("Invalid legacy recovery lists")
        seen = set()
        for entry in data["entries"]:
            registry._keys(entry, "path before after attempted restoration", "legacy transaction entry")
            output = registry._path(entry["path"])
            if str(output) in seen or type(entry["attempted"]) is not bool:
                _fail("Duplicate/invalid legacy recovery entry")
            seen.add(str(output))
            for name in ("before", "after"):
                meta = entry[name]
                registry._keys(meta, "existed kind mode link_target fingerprint backup", "legacy snapshot")
                if (meta["kind"] not in ("file", "symlink", "absent") or type(meta["existed"]) is not bool
                        or meta["existed"] != (meta["kind"] != "absent")):
                    _fail("Invalid legacy snapshot")
                Snapshot(meta["kind"], b"" if meta["kind"] == "file" else None, meta["mode"], meta["link_target"])
                if meta["kind"] == "absent":
                    if meta["fingerprint"] is not None or meta["backup"] is not None:
                        _fail("Absent snapshot contains data/evidence")
                else:
                    registry._digest(meta["fingerprint"])
                if (name == "after" or meta["kind"] != "file") and meta["backup"] is not None:
                    _fail("Unexpected legacy snapshot backup reference")
            before = entry["before"]
            if before["kind"] == "file":
                filename = before["backup"]
                if not isinstance(filename, str) or filename in (".", "..") or Path(filename).name != filename:
                    _fail("Unsafe legacy before-file name")
                contents = add(path.parent / filename)
                if _sha(contents) != before["fingerprint"]:
                    _fail("Legacy before-file hash mismatch")
                if str(output) in {str(source) for source in sources} and _sha(contents) not in ledgers:
                    ledgers.add(_sha(contents))
                    try:
                        previous = json.loads(contents.decode("utf-8"), object_pairs_hook=registry._no_duplicates)
                    except (UnicodeError, ValueError):
                        previous = None  # Preserve corrupt historical before bytes; never activate them.
                    if isinstance(previous, dict) and previous.get("schema_version") == 1:
                        ledger(previous)
        for directory in data["created_directories"]:
            registry._path(directory)

    for info in source_infos:
        source = Path(info["registry"])
        raw = add(source)
        if first_raw is not None and raw != first_raw:
            _fail("Multiple legacy ledgers differ; never merge or choose by mtime")
        first_raw = raw
        for path in info["files"]:
            add(Path(path))
    original = json.loads(first_raw.decode("utf-8"), object_pairs_hook=registry._no_duplicates)
    ledgers.add(_sha(first_raw))
    ledger(original)
    for path in evidence_files:
        add(Path(path))
    return original, sorted(files.values(), key=lambda entry: entry["source"]), source_infos, original_backup_manifests


def _redirect(plan, source):
    return _bytes({"product_id": "mem-sharing", "operation_id": plan["operation_id"],
                   "source_registry": source, "source_sha256": plan["source_sha256"],
                   "target_registry": plan["layout"]["registry"], "status": "handoff"})


def _source_state(plan, source):
    path = Path(source)
    if path.is_dir() and not path.is_symlink():
        children = set(child.name for child in path.iterdir())
        if children == {"redirect.json"}:
            snap = read_snapshot(path / "redirect.json")
            if snap.kind == "file" and snap.data == _redirect(plan, source):
                return "tombstone"
        if not children:
            return "empty_tombstone"
        _fail("Foreign/modified tombstone: " + source)
    snap = read_snapshot(path)
    if snap.kind == "absent":
        return "absent"
    if snap.kind == "file" and snap.fingerprint == plan["source_sha256"]:
        expected = next(item for item in plan["files"] if item["source"] == source)
        if snap.mode == expected["mode"]:
            return "before"
    _fail("Legacy registry drifted: " + source, "source_drift")


def _target_state(plan):
    snap = read_snapshot(Path(plan["layout"]["registry"]))
    if snap.kind == "absent":
        return "before"
    if snap.kind == "file" and snap.data == _bytes(plan["after_registry"]) and snap.mode == 0o600:
        return "after"
    _fail("Target ledger differs from this operation; preserve both ledgers")


def _journal_path(runtime, op):
    return runtime.home / (".mem-sharing-install-" + _op(op)) / "journal.json"


def inspect_migration(runtime, source_registries=(), *, allowed_user_paths=()):
    """Read-only scene classification, including all six decision-table rows.

    No legacy fallback is returned as an active registry. Explicit legacy paths
    are needed when V does not exist; no search of arbitrary source checkouts.
    """
    try:
        runtime = _layout(runtime)
        sources = [_canonical(path) for path in source_registries]
        target_exists = os.path.lexists(runtime.registry)
        pending = []
        for bootstrap in sorted(runtime.home.glob(".mem-sharing-install-*")):
            if bootstrap.is_symlink():
                _fail("Bootstrap symlink conflict")
            journal = bootstrap / "journal.json"
            if journal.is_file():
                observed = _json(journal)
                if observed.get("product_id") == "mem-sharing" and observed.get("status") not in ("committed", "rolled_back"):
                    validated, _ = _load_journal(journal)
                    _recovery_scene(validated)
                    pending.append(str(journal))
        if pending:
            return {"scene": "interrupted", "channel": "stop", "journals": pending, "message": "Explicit recovery required"}
        old_files = [path for path in sources if path.is_file() and not path.is_symlink()]
        if target_exists and old_files:
            return {"scene": "dual_conflict", "channel": "stop", "journals": [], "message": "Both ledgers exist; no mtime winner"}
        if target_exists:
            active = registry.load_registry(runtime.registry, allowed_user_paths=allowed_user_paths)
            registry.require_installed(active)
            migration = active["migration"]
            if migration:
                expected = set(migration["tombstones"])
                if sources and set(map(str, sources)) != expected:
                    _fail("Legacy source set differs from migration record")
                for source in expected:
                    marker = Path(source) / "redirect.json"
                    if not Path(source).is_dir() or Path(source).is_symlink() or set(p.name for p in Path(source).iterdir()) != {"redirect.json"}:
                        _fail("Missing/invalid tombstone")
                    if read_snapshot(marker).fingerprint != migration["tombstones"][source]:
                        _fail("Tombstone fingerprint mismatch")
                return {"scene": "migrated", "channel": "installed", "journals": [], "message": "V with matching tombstones"}
            if any(os.path.lexists(path) for path in sources):
                _fail("Unaccounted legacy path with V")
            return {"scene": "installed_only", "channel": "installed", "journals": [], "message": "Only completed V"}
        if not sources:
            return {"scene": "no_ledger", "channel": "stop", "journals": [], "message": "No explicit legacy source; no initialization"}
        if len(old_files) != len(sources):
            _fail("Missing/partial legacy ledger without a recovery journal")
        raw = [read_snapshot(path).data for path in sources]
        if any(value != raw[0] for value in raw[1:]):
            _fail("Legacy ledgers differ")
        for path in sources:
            registry.load_legacy_registry(path, allowed_user_paths=allowed_user_paths)
        return {"scene": "legacy_only", "channel": "upgrade", "journals": [], "message": "Explicit strict migration planning required"}
    except (ValueError, OSError, KeyError, TypeError) as exc:
        scene = "interrupted" if "migration_scene=interrupted" in str(exc) else "conflict"
        return {"scene": scene, "channel": "stop", "journals": [], "message": str(exc)}


def plan_migration(runtime, source_registries, *, source_commits, product,
                   allowed_user_paths=(), evidence_files=(), operation_id=None):
    """Return an exact approval plan without creating directories or locks."""
    runtime = _layout(runtime)
    sources = sorted({_canonical(path) for path in source_registries})
    if not sources:
        _fail("Explicit legacy source required")
    scene = inspect_migration(runtime, sources, allowed_user_paths=allowed_user_paths)
    if scene["scene"] != "legacy_only":
        _fail("Cannot start migration: " + scene["scene"] + ": " + scene["message"])
    if set(source_commits) != set(map(str, sources)):
        _fail("Every legacy source needs its pinned code identity")
    locks = [runtime.home / ".mem-sharing-install.lock", runtime.lock, runtime.transaction_lock]
    locks += [path.parent / ".agm.lock" for path in sources]
    if any(os.path.lexists(path) for path in locks):
        _fail("Existing writer lock; no metadata or locks will be created", "lock_conflict")
    op = _op(operation_id or (datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex))
    archive = runtime.backups / ("m2-migration-" + op)
    bootstrap = _journal_path(runtime, op).parent
    if os.path.lexists(archive) or os.path.lexists(bootstrap):
        _fail("Operation path already exists; use explicit recovery")
    allowed = sorted(set(map(str, allowed_user_paths)))
    original, files, identities, original_manifests = _materialize_inputs(
        sources, source_commits, evidence_files, allowed, archive)
    source_sha = next(item["sha256"] for item in files if item["source"] == str(sources[0]))
    target = registry.empty_registry()
    target.update(projects=copy.deepcopy(original["projects"]), shared_objects=copy.deepcopy(original["shared_objects"]), product=copy.deepcopy(product))
    target["product"]["last_operation_id"] = op
    registry.validate_registry(target, allowed_user_paths=allowed)
    references = {item["source"]: {"path": item["target"], "sha256": item["sha256"], "kind": "file"} for item in files}
    for obj in registry._objects(target).values():
        if obj["backup_manifest"]:
            obj["backup_manifest"] = references[obj["backup_manifest"]]["path"]
    plan = {"schema_version": 1, "command": "migrate-machine", "operation_id": op,
            "channel": "upgrade", "source_version": "m2-schema1", "layout": runtime.describe(),
            "archive_root": str(archive), "bootstrap": str(bootstrap), "journal": str(bootstrap / "journal.json"),
            "sources": identities, "source_commits": dict(source_commits), "source_sha256": source_sha,
            "files": files, "reference_map": references, "original_backup_manifests": original_manifests,
            "allowed_user_paths": allowed, "evidence_files": sorted(set(map(str, evidence_files))),
            "requested_agents": [], "effective_agents": [], "legacy_identity": None,
            "versions": {"before": {"schema": 1, "structure": None, "code": "m2-schema1"},
                         "after": {"schema": 2, "structure": product["product_structure_version"], "code": product["product_code_version"]}}}
    target["migration"] = {"operation_id": op, "source_registry": str(sources[0]), "source_sha256": source_sha,
                           "archive_root": str(archive), "reference_map": references,
                           "tombstones": {str(source): _sha(_redirect(plan, str(source))) for source in sources}, "status": "committed"}
    plan["after_registry"] = target
    plan["after_registry_sha256"] = _sha(_bytes(target))
    plan["source_tree_sha256"] = _sha(_bytes(files))
    plan["lock_paths"] = [str(path) for path in _lock_paths(runtime, plan)]
    directories = set()
    for parent in [runtime.var, archive, bootstrap] + [Path(item["target"]).parent for item in files]:
        while not parent.exists():
            directories.add(str(parent))
            parent = parent.parent
    plan["directories"] = sorted(directories, key=lambda path: (len(Path(path).parts), path))
    plan["changes"] = ([{"path": item["target"], "operation": "copy", "before": None, "after": item["sha256"]} for item in files]
                       + [{"path": str(path), "operation": "tombstone", "before": source_sha,
                           "after": target["migration"]["tombstones"][str(path)]} for path in sources]
                       + [{"path": str(runtime.registry), "operation": "create", "before": None, "after": plan["after_registry_sha256"]},
                          {"path": str(bootstrap / "journal.json"), "operation": "journal_metadata", "before": None, "after": None},
                          {"path": str(archive / "source-identity.json"), "operation": "create_identity", "before": None, "after": _sha(_identity_bytes(plan))}]
                       + [{"path": directory, "operation": "mkdir", "before": None, "after": None} for directory in plan["directories"]]
                       + [{"path": path, "operation": "lock", "before": None, "after": None} for path in plan["lock_paths"]]
                       + [{"path": str(Path(path) / "migration-owner.json"), "operation": "lock_metadata", "before": None, "after": None} for path in plan["lock_paths"]]
                       + [{"path": str(path / "redirect.json"), "operation": "create", "before": None,
                           "after": target["migration"]["tombstones"][str(path)]} for path in sources])
    plan["plan_sha256"] = _sha(_bytes(plan))
    return plan


def _validate_plan(plan):
    if not isinstance(plan, dict) or "plan_sha256" not in plan:
        _fail("Missing bound migration plan")
    registry._keys(plan, "schema_version command operation_id channel source_version layout archive_root bootstrap journal sources source_commits source_sha256 files reference_map original_backup_manifests allowed_user_paths evidence_files requested_agents effective_agents legacy_identity versions after_registry after_registry_sha256 source_tree_sha256 directories lock_paths changes plan_sha256", "migration plan")
    body = dict(plan)
    digest = body.pop("plan_sha256")
    if _sha(_bytes(body)) != digest:
        _fail("Migration plan fingerprint mismatch")
    runtime = _layout(RuntimeLayout(Path(plan["layout"]["root"]).parent))
    op = _op(plan["operation_id"])
    if plan["command"] != "migrate-machine" or plan["source_version"] != "m2-schema1" or plan["schema_version"] != 1:
        _fail("Unsupported migration plan")
    if plan["layout"] != runtime.describe() or Path(plan["journal"]) != _journal_path(runtime, op):
        _fail("Migration layout mismatch")
    archive = runtime.backups / ("m2-migration-" + op)
    if plan["archive_root"] != str(archive) or plan["bootstrap"] != str(_journal_path(runtime, op).parent):
        _fail("Migration metadata scope mismatch")
    for item in plan["files"]:
        source = _canonical(item["source"])
        if Path(item["target"]) != _archive_target(archive, source):
            _fail("Archive target outside approved scope")
    if plan["after_registry_sha256"] != _sha(_bytes(plan["after_registry"])):
        _fail("Target model changed")
    return runtime


def _approval(plan, approval):
    if not isinstance(approval, dict) or set(approval) != set(plan) | {"confirmed_at", "reference"}:
        _fail("Exact user approval required", "approval_required")
    if any(approval[key] != value for key, value in plan.items()):
        _fail("Approval does not match inspected plan", "approval_required")
    registry._evidence({"confirmed_at": approval["confirmed_at"], "reference": approval["reference"]})



def _sync_directory(path):
    descriptor = os.open(str(path), os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _put(path, data, mode):
    _atomic_file(path, data, mode)
    _sync_directory(path.parent)

def _save(path, journal):
    _put(path, _bytes(journal), 0o600)
    if _json(path) != journal:
        _fail("Journal readback mismatch", "recovery_required")


def _intent(journal, kind, path, hook):
    journal["intent"] = {"kind": kind, "path": str(path)}
    _save(Path(journal["plan"]["journal"]), journal)
    hook("before_" + kind, Path(path))


def _mkdir(path, journal, hook):
    path = _safe_path(path)
    if path.exists():
        if not path.is_dir() or path.is_symlink():
            _fail("Directory conflict: " + str(path))
        return
    if str(path) not in journal["plan"]["directories"]:
        _fail("Unapproved/newly missing runtime directory: " + str(path))
    _mkdir(path.parent, journal, hook)
    if str(path) not in journal["created_directories"]:
        journal["created_directories"].append(str(path))
    _intent(journal, "mkdir", path, hook)
    path.mkdir(mode=0o700)
    _sync_directory(path.parent)
    hook("after_mkdir", path)


def _identity_bytes(plan):
    return _bytes({"source_version": "m2-schema1", "sources": plan["sources"],
                   "source_tree_sha256": plan["source_tree_sha256"],
                   "original_backup_manifests": plan["original_backup_manifests"]})


def _copy_materials(journal, hook):
    plan = journal["plan"]
    for item in plan["files"]:
        target = Path(item["target"])
        snapshot = read_snapshot(target)
        if snapshot.kind == "file" and snapshot.fingerprint == item["sha256"]:
            continue
        if snapshot.kind != "absent":
            _fail("Archive material changed: " + str(target))
        source = read_snapshot(Path(item["source"]))
        if source.kind != "file" or source.fingerprint != item["sha256"] or source.mode != item["mode"]:
            _fail("Source changed before archive: " + item["source"], "source_drift")
        _mkdir(target.parent, journal, hook)
        _intent(journal, "copy", target, hook)
        _put(target, source.data, 0o600)
        if read_snapshot(target).fingerprint != item["sha256"]:
            _fail("Archive copy readback mismatch")
        hook("after_copy", target)
    identity = Path(plan["archive_root"]) / "source-identity.json"
    contents = _identity_bytes(plan)
    snapshot = read_snapshot(identity)
    if snapshot.kind != "absent" and snapshot.data != contents:
        _fail("Archived code identity changed")
    if snapshot.kind == "absent":
        _intent(journal, "identity", identity, hook)
        _put(identity, contents, 0o600)


def _verify_sources(plan, journal=None):
    for info in plan["sources"]:
        if _code_inventory(Path(info["registry"]), info["commit"]) != info:
            _fail("Legacy code/source identity changed", "source_drift")
    sources = {info["registry"] for info in plan["sources"]}
    for item in plan["files"]:
        if item["source"] in sources:
            state = _source_state(plan, item["source"])
            if state != "before" and (journal is None or item["source"] not in journal["switch_started"]):
                _fail("Unplanned legacy path transition", "source_drift")
            continue
        observed = read_snapshot(Path(item["source"]))
        if observed.kind != "file" or observed.fingerprint != item["sha256"] or observed.mode != item["mode"]:
            _fail("Legacy recovery source changed: " + item["source"], "source_drift")


@contextmanager
def _lock(path, plan):
    """Use the existing lock primitive, adding a removable recovery owner record."""
    with write_lock(path):
        owner = path / "migration-owner.json"
        _put(owner, _bytes({"product_id": "mem-sharing", "operation_id": plan["operation_id"],
                                   "pid": os.getpid(), "plan_sha256": plan["plan_sha256"]}), 0o600)
        try:
            yield
        finally:
            owner.unlink()  # A hard crash retains this record for explicit stale-lock review.


def _finish(journal, hook):
    plan = journal["plan"]
    runtime = _validate_plan(plan)
    _copy_materials(journal, hook)
    _verify_sources(plan, journal)
    for source in sorted(info["registry"] for info in plan["sources"]):
        path = Path(source)
        state = _source_state(plan, source)
        if state == "before":
            if source not in journal["switch_started"]:
                journal["switch_started"].append(source)
            _intent(journal, "old_unlink", path, hook)
            # Recheck after the observer/fault boundary, immediately before mutation.
            if _source_state(plan, source) != "before":
                _fail("Legacy ledger changed before tombstone", "source_drift")
            path.unlink()
            _sync_directory(path.parent)
            hook("after_old_unlink", path)
            state = "absent"
        if state == "absent":
            _intent(journal, "tombstone_mkdir", path, hook)
            path.mkdir(mode=0o700)
            _sync_directory(path.parent)
            hook("after_tombstone_mkdir", path)
            state = "empty_tombstone"
        if state == "empty_tombstone":
            marker = path / "redirect.json"
            _intent(journal, "redirect", marker, hook)
            _put(marker, _redirect(plan, source), 0o400)
            hook("after_redirect", marker)
        if _source_state(plan, source) != "tombstone":
            _fail("Tombstone readback mismatch")
    # No source/ledger may change between freezing old writers and the last commit.
    _intent(journal, "commit", runtime.registry, hook)
    _verify_sources(plan, journal)
    registry.verify_archived_references(plan["after_registry"]["migration"])
    registry.validate_registry(plan["after_registry"], allowed_user_paths=plan["allowed_user_paths"])
    target_state = _target_state(plan)
    if target_state == "before":
        _put(runtime.registry, _bytes(plan["after_registry"]), 0o600)
        hook("after_commit", runtime.registry)
    if _target_state(plan) != "after":
        _fail("Target registry readback mismatch")
    _intent(journal, "finish", Path(plan["journal"]), hook)
    final_scene = _recovery_scene(journal)
    if final_scene["target"] != "after" or set(final_scene["sources"].values()) != {"tombstone"}:
        _fail("Output drift before completion marker")
    journal["status"] = "committed"
    journal["intent"] = None
    _save(Path(plan["journal"]), journal)
    hook("after_finish", Path(plan["journal"]))
    return {"status": "committed", "registry": str(runtime.registry), "journal": plan["journal"],
            "source_version": "m2-schema1", "operation_id": plan["operation_id"]}


def execute_migration(plan, approval, *, hook=None):
    """Execute an approved plan; exceptions preserve a resumable journal/scene."""
    runtime = _validate_plan(plan)
    _approval(plan, approval)
    # Rebuild the same pure plan before any locks/metadata are written.
    observed = plan_migration(runtime, [info["registry"] for info in plan["sources"]],
        source_commits=plan["source_commits"], product=plan["after_registry"]["product"],
        allowed_user_paths=plan["allowed_user_paths"], evidence_files=plan["evidence_files"], operation_id=plan["operation_id"])
    if observed != plan:
        _fail("Source/plan drift before execution", "source_drift")
    hook = hook or (lambda event, path: None)
    with ExitStack() as stack:
        stack.enter_context(_lock(runtime.home / ".mem-sharing-install.lock", plan))
        for info in sorted(plan["sources"], key=lambda item: item["registry"]):
            stack.enter_context(_lock(Path(info["registry"]).parent / ".agm.lock", plan))
        _verify_sources(plan)
        if os.path.lexists(runtime.registry):
            _fail("New registry appeared while acquiring legacy locks")
        bootstrap = Path(plan["bootstrap"])
        bootstrap.mkdir(mode=0o700)
        _sync_directory(bootstrap.parent)
        journal = {"schema_version": 1, "product_id": "mem-sharing", "plan": plan, "approval": approval,
                   "operation_id": plan["operation_id"], "status": "prepared", "intent": None,
                   "created_directories": [], "switch_started": []}
        _save(Path(plan["journal"]), journal)
        try:
            _mkdir(runtime.var, journal, hook)
            _mkdir(Path(plan["archive_root"]), journal, hook)
            stack.enter_context(_lock(runtime.lock, plan))
            stack.enter_context(_lock(runtime.transaction_lock, plan))
            journal["status"] = "applying"
            _save(Path(plan["journal"]), journal)
            return _finish(journal, hook)
        except Exception:
            journal["status"] = "recovery_required"
            _save(Path(plan["journal"]), journal)
            raise


def _load_journal(path):
    journal = _json(path)
    registry._keys(journal, "schema_version product_id plan approval operation_id status intent created_directories switch_started", "migration journal")
    runtime = _validate_plan(journal["plan"])
    if (journal["schema_version"] != 1 or type(journal["schema_version"]) is not int
            or journal["product_id"] != "mem-sharing" or journal["operation_id"] != journal["plan"]["operation_id"]
            or Path(path) != Path(journal["plan"]["journal"])):
        _fail("Invalid migration journal identity")
    if journal["status"] not in ("prepared", "applying", "recovery_required", "committed", "rolled_back"):
        _fail("Unknown migration journal status")
    _approval(journal["plan"], journal["approval"])
    if not isinstance(journal["created_directories"], list) or not isinstance(journal["switch_started"], list):
        _fail("Invalid migration journal lists")
    for path in journal["created_directories"]:
        path = _canonical(path)
        if path != runtime.root and runtime.root not in path.parents:
            _fail("Created-directory journal escapes runtime root")
    if not set(journal["switch_started"]) <= {item["registry"] for item in journal["plan"]["sources"]}:
        _fail("Unexpected legacy transition in journal")
    return journal, runtime


def _lock_paths(runtime, plan):
    return ([runtime.home / ".mem-sharing-install.lock"]
            + [Path(item["registry"]).parent / ".agm.lock" for item in sorted(plan["sources"], key=lambda entry: entry["registry"])]
            + [runtime.lock, runtime.transaction_lock])


def _stale_observation(path, plan):
    if not os.path.lexists(path):
        return None
    if path.is_symlink() or not path.is_dir():
        _fail("Lock is not a real directory")
    entries = {child.name for child in path.iterdir()}
    allowed = {"migration-owner.json"}
    if path == Path(plan["layout"]["lock"]):
        allowed.add("transaction")
    if not entries <= allowed or "migration-owner.json" not in entries:
        _fail("Unknown lock owner; inspect manually without deleting it", "lock_conflict")
    owner = _json(path / "migration-owner.json")
    registry._keys(owner, "product_id operation_id pid plan_sha256", "lock owner")
    if (owner["product_id"] != "mem-sharing" or owner["operation_id"] != plan["operation_id"]
            or owner["plan_sha256"] != plan["plan_sha256"] or type(owner["pid"]) is not int or owner["pid"] <= 0):
        _fail("Lock owner identity does not match recovery operation", "lock_conflict")
    try:
        os.kill(owner["pid"], 0)
    except ProcessLookupError:
        pass
    except OSError:
        _fail("Cannot establish lock owner's exit", "lock_conflict")
    else:
        _fail("Lock owner still exists; no lock stealing", "lock_conflict")
    info = path.lstat()
    return {"path": str(path), "device": info.st_dev, "inode": info.st_ino,
            "owner_sha256": read_snapshot(path / "migration-owner.json").fingerprint}


def _recovery_scene(journal):
    plan = journal["plan"]
    target = _target_state(plan)
    states = {item["registry"]: _source_state(plan, item["registry"]) for item in plan["sources"]}
    for source, state in states.items():
        if state != "before" and source not in journal["switch_started"]:
            _fail("Unplanned legacy source transition")
    if target == "after" and set(states.values()) not in ({"tombstone"}, {"before"}):
        _fail("Committed V with mixed legacy state requires manual recovery")
    for item in plan["files"]:
        observed = read_snapshot(Path(item["target"]))
        if observed.kind != "absent" and (observed.kind != "file" or observed.fingerprint != item["sha256"]):
            _fail("Recovery archive modified; preserve scene")
    identity = read_snapshot(Path(plan["archive_root"]) / "source-identity.json")
    if identity.kind != "absent" and (identity.kind != "file" or identity.data != _identity_bytes(plan)):
        _fail("Archived source identity changed")
    if target == "after":
        if identity.kind != "file":
            _fail("Committed target is missing archived source identity")
        registry.verify_archived_references(plan["after_registry"]["migration"])
        registry.validate_registry(plan["after_registry"], allowed_user_paths=plan["allowed_user_paths"])
    return {"target": target, "sources": states}


def plan_recovery(journal_path, *, action):
    """Inspect before/after scene and exited lock owners; do not remove a lock."""
    journal_path = _canonical(journal_path)
    journal, runtime = _load_journal(journal_path)
    if action not in ("continue", "rollback"):
        _fail("Recovery action must be continue or rollback")
    scene = _recovery_scene(journal)
    plan = journal["plan"]
    locks = [item for item in (_stale_observation(path, plan) for path in _lock_paths(runtime, plan)) if item]
    cleanup_only = journal["status"] in ("committed", "rolled_back")
    if cleanup_only and (not locks or action != ("continue" if journal["status"] == "committed" else "rollback")):
        _fail("Closed operation; only explicit stale lock handoff is recoverable, no downgrade/replay")
    finish_only = action == "continue" and scene["target"] == "after" and set(scene["sources"].values()) == {"tombstone"}
    if not cleanup_only and not finish_only:
        _verify_sources(plan, journal)
    result = {"schema_version": 1, "command": "recover-machine-migration", "operation_id": plan["operation_id"],
              "journal": str(journal_path), "journal_sha256": read_snapshot(journal_path).fingerprint,
              "migration_plan_sha256": plan["plan_sha256"], "action": action,
              "scene": scene, "confirmed_stale_locks": locks, "layout": runtime.describe(), "cleanup_only": cleanup_only, "finish_only": finish_only}
    result["plan_sha256"] = _sha(_bytes(result))
    return result


def _rollback(journal, hook):
    plan = journal["plan"]
    runtime = _validate_plan(plan)
    state = _target_state(plan)
    if state == "after":
        _intent(journal, "rollback_target", runtime.registry, hook)
        if _target_state(plan) != "after":
            _fail("Target changed before rollback")
        runtime.registry.unlink()
        _sync_directory(runtime.registry.parent)
        hook("after_rollback_target", runtime.registry)
    for source in reversed(sorted(item["registry"] for item in plan["sources"])):
        path = Path(source)
        state = _source_state(plan, source)
        if state == "before":
            continue
        archived = next(item for item in plan["files"] if item["source"] == source)
        raw = read_snapshot(Path(archived["target"]))
        if raw.kind != "file" or raw.fingerprint != plan["source_sha256"]:
            _fail("Original ledger archive missing; cannot restore")
        if state == "tombstone":
            marker = path / "redirect.json"
            _intent(journal, "rollback_redirect", marker, hook)
            if _source_state(plan, source) != "tombstone":
                _fail("Tombstone changed before rollback")
            marker.unlink()
            _sync_directory(marker.parent)
            state = "empty_tombstone"
        if state == "empty_tombstone":
            _intent(journal, "rollback_directory", path, hook)
            path.rmdir()
            _sync_directory(path.parent)
        _intent(journal, "rollback_source", path, hook)
        if read_snapshot(path).kind != "absent":
            _fail("Legacy ledger appeared during rollback")
        _put(path, raw.data, archived["mode"])
        hook("after_rollback_source", path)
    if _target_state(plan) != "before" or any(_source_state(plan, item["registry"]) != "before" for item in plan["sources"]):
        _fail("Rollback did not restore a single legacy state source")
    journal["status"] = "rolled_back"
    journal["intent"] = None
    _save(Path(plan["journal"]), journal)
    hook("after_rollback_finish", Path(plan["journal"]))
    return {"status": "rolled_back", "journal": plan["journal"], "operation_id": plan["operation_id"]}


def recover_migration(recovery_plan, approval, *, hook=None):
    """Explicitly approved continue/rollback, including separately bound stale locks."""
    _approval(recovery_plan, approval)
    observed = plan_recovery(recovery_plan["journal"], action=recovery_plan["action"])
    if observed != recovery_plan:
        _fail("Recovery scene/locks changed since approval", "source_drift")
    journal, runtime = _load_journal(Path(recovery_plan["journal"]))
    plan = journal["plan"]
    hook = hook or (lambda event, path: None)
    # Stale-lock removal is never implicit: action, owner exit, inode and bytes
    # are all part of the separate recovery approval; inner locks go first.
    for observation in sorted(recovery_plan["confirmed_stale_locks"], key=lambda item: len(Path(item["path"]).parts), reverse=True):
        path = Path(observation["path"])
        if _stale_observation(path, plan) != observation:
            _fail("Stale lock changed before approved removal", "lock_conflict")
        _intent(journal, "remove_confirmed_stale_lock", path, hook)
        if _stale_observation(path, plan) != observation:
            _fail("Stale lock changed after intent", "lock_conflict")
        (path / "migration-owner.json").unlink()
        path.rmdir()
    with ExitStack() as stack:
        stack.enter_context(_lock(runtime.home / ".mem-sharing-install.lock", plan))
        for info in sorted(plan["sources"], key=lambda item: item["registry"]):
            stack.enter_context(_lock(Path(info["registry"]).parent / ".agm.lock", plan))
        _recovery_scene(journal)
        _mkdir(runtime.var, journal, hook)
        _mkdir(Path(plan["archive_root"]), journal, hook)
        stack.enter_context(_lock(runtime.lock, plan))
        stack.enter_context(_lock(runtime.transaction_lock, plan))
        try:
            if recovery_plan["cleanup_only"]:
                journal["intent"] = None
                _save(Path(plan["journal"]), journal)
                return {"status": journal["status"], "journal": plan["journal"],
                        "operation_id": plan["operation_id"], "cleanup_only": True}
            if recovery_plan["action"] == "continue" and recovery_plan["finish_only"]:
                if _recovery_scene(journal) != recovery_plan["scene"]:
                    _fail("Committed output scene changed before finalization")
                _intent(journal, "finish", Path(plan["journal"]), hook)
                if _recovery_scene(journal) != recovery_plan["scene"]:
                    _fail("Output drift before completion marker")
                journal["status"], journal["intent"] = "committed", None
                _save(Path(plan["journal"]), journal)
                return {"status": "committed", "journal": plan["journal"],
                        "operation_id": plan["operation_id"], "finish_only": True}
            if recovery_plan["action"] == "continue":
                return _finish(journal, hook)
            return _rollback(journal, hook)
        except Exception:
            journal["status"] = "recovery_required"
            _save(Path(plan["journal"]), journal)
            raise


def resolve_reference(model, original_path):
    """Locate and hash-verify archived evidence without requiring its old location."""
    migration = model["migration"]
    if migration is None:
        _fail("No migration reference map")
    registry.verify_archived_references(migration)
    record = migration["reference_map"].get(str(original_path))
    if record is None:
        _fail("Reference not included in approved migration")
    return Path(record["path"])


def archived_recovery_descriptor(model, original_manifest):
    """Read-only adapter: preserve old manifest bytes and resolve sibling before files.

    Callers must never feed the immutable archive directly to old recovery code.
    Old-registry outputs are explicitly flagged for a machine reconciliation plan;
    a raw historical manifest cannot reopen a tombstone or infer deletion rights.
    """
    path = resolve_reference(model, original_manifest)
    original = _json(path)
    resolved = {}
    for entry in original["entries"]:
        meta = entry["before"]
        if meta["kind"] == "file":
            old = Path(original_manifest).parent / meta["backup"]
            archived = resolve_reference(model, old)
            if read_snapshot(archived).fingerprint != meta["fingerprint"]:
                _fail("Archived before snapshot does not match legacy manifest")
            resolved[str(old)] = str(archived)
    return {"original_manifest": str(original_manifest), "archived_manifest": str(path),
            "manifest": original, "before_files": resolved,
            "registry_outputs_requiring_explicit_reconciliation": [entry["path"] for entry in original["entries"]
                if entry["path"] in model["migration"]["tombstones"]]}
