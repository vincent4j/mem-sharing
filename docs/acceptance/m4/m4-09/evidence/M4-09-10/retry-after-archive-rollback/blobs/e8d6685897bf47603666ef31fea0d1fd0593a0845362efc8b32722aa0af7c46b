"""Strict diagnostic access to retired development ledgers and shared I/O helpers.

Schema 1/2 ledgers and their migration journals are preserved, never converted or
replayed. Release upgrade and recovery begin with the formal schema 3 baseline.
"""
import hashlib
import json
import os
from pathlib import Path
import re
from contextlib import contextmanager

from . import registry
from .layout import RuntimeLayout
from .transaction import _atomic_file, _safe_path, read_snapshot, write_lock

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


def inspect_migration(runtime, source_registries=(), *, allowed_user_paths=()):
    """Read and validate explicit ledgers without selecting an old write authority."""
    try:
        runtime = _layout(runtime)
        sources = sorted({_canonical(path) for path in source_registries})
        old = []
        for path in sources:
            old.append(registry.load_diagnostic_registry(path, allowed_user_paths=allowed_user_paths))
        if os.path.lexists(runtime.registry):
            active = registry.load_diagnostic_registry(runtime.registry, allowed_user_paths=allowed_user_paths)
            if sources:
                return {"scene": "dual_conflict", "channel": "stop", "journals": [],
                        "message": "Both ledgers exist; preserve both without selecting a writer"}
            if active["schema_version"] == 3:
                registry.require_installed(active)
                return {"scene": "installed_only", "channel": "installed", "journals": [], "message": "Only completed schema 3 ledger"}
            old.append(active)
        if old:
            return {"scene": "legacy_only", "channel": "stop", "journals": [],
                    "message": "Old development ledger is diagnostic-only; preserve and reinstall"}
        return {"scene": "no_ledger", "channel": "stop", "journals": [], "message": "No explicit ledger; no initialization"}
    except (ValueError, OSError, KeyError, TypeError) as exc:
        return {"scene": "conflict", "channel": "stop", "journals": [], "message": str(exc)}


def _retired(*args, **kwargs):
    _fail("Development ledger migration and journal replay are unsupported; preserve materials for diagnosis", "migration_unsupported")


plan_migration = _retired
execute_migration = _retired
plan_recovery = _retired
recover_migration = _retired
_load_journal = _retired
