"""Recoverable configuration transactions; only explicit writers take a lock.

Atomic replacement is per file, not across files. Registry commits last. A mkdir
lock is deliberately never stolen: crashes require explicit operator recovery.
No fcntl dependency and no untested cross-platform durability claim.
The mkdir lock excludes cooperating AGM writers only. Last-moment snapshot
checks preserve observed foreign edits, but are not OS compare-and-swap:
noncooperating writers can still race the final check and replace/unlink.
"""
import hashlib
import json
import os
import stat
import tempfile
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


class TransactionError(ValueError):
    def __init__(self, message, *, code="transaction_failed", manifest=None, recovery_errors=None):
        super().__init__(message)
        self.code = code
        self.manifest = None if manifest is None else str(manifest)
        self.recovery_errors = list(recovery_errors or [])


def _hash(data):
    return hashlib.sha256(data).hexdigest()


def _safe_path(path):
    path = Path(path)
    if not path.is_absolute() or os.path.normpath(str(path)) != str(path):
        raise TransactionError("expected normalized absolute output path")
    if path.parent.resolve() / path.name != path:
        raise TransactionError("symlink parent conflict: " + str(path), code="path_conflict")
    return path


@dataclass(frozen=True)
class Snapshot:
    kind: str
    data: Optional[bytes] = None
    mode: Optional[int] = None
    target: Optional[str] = None

    def __post_init__(self):
        if self.kind == "absent":
            valid = self.data is None and self.mode is None and self.target is None
        elif self.kind == "file":
            valid = isinstance(self.data, bytes) and type(self.mode) is int and 0 <= self.mode <= 0o7777 and self.target is None
        elif self.kind == "symlink":
            valid = self.data is None and self.mode is None and isinstance(self.target, str) and bool(self.target) and "\x00" not in self.target
        else:
            valid = False
        if not valid:
            raise TransactionError("invalid snapshot")

    @property
    def fingerprint(self):
        if self.kind == "file":
            return _hash(self.data)
        if self.kind == "symlink":
            return _hash(self.target.encode("utf-8"))
        return None


def read_snapshot(path):
    """Read only. Never follows a link leaf and never mkdirs."""
    path = _safe_path(path)
    try:
        mode = path.lstat().st_mode
    except FileNotFoundError:
        return Snapshot("absent")
    if stat.S_ISLNK(mode):
        return Snapshot("symlink", target=os.readlink(path))
    if stat.S_ISREG(mode):
        return Snapshot("file", path.read_bytes(), stat.S_IMODE(mode))
    raise TransactionError("occupied non-file output: " + str(path), code="path_conflict")


@dataclass(frozen=True)
class Change:
    path: Path
    after: Snapshot
    expected: Snapshot

    def __post_init__(self):
        object.__setattr__(self, "path", _safe_path(self.path))
        if not isinstance(self.after, Snapshot) or not isinstance(self.expected, Snapshot):
            raise TransactionError("change requires typed before/after snapshots")

    @classmethod
    def file(cls, path, data, *, expected, mode=None):
        if expected.kind == "symlink":
            raise TransactionError("refusing to replace symlink with file", code="path_conflict")
        if not isinstance(data, bytes):
            raise TypeError("file content must be bytes")
        return cls(Path(path), Snapshot("file", data, mode if mode is not None else (expected.mode if expected.kind == "file" else 0o600)), expected)

    @classmethod
    def symlink(cls, path, target, *, expected):
        target = str(Path(target).resolve())
        path = Path(path)
        if expected.kind != "absent":
            if expected.kind != "symlink" or (path.parent / expected.target).resolve() != Path(target):
                raise TransactionError("occupied or foreign Skill link", code="path_conflict")
            return cls(path, expected, expected)  # Preserve an equivalent relative link.
        return cls(path, Snapshot("symlink", target=target), expected)

    @classmethod
    def delete(cls, path, *, expected):
        # Ownership is checked by remove.py; this primitive verifies exact bytes.
        return cls(Path(path), Snapshot("absent"), expected)


@contextmanager
def write_lock(path):
    """Fail-fast exclusive writer lock. Read/check must not call this function."""
    path = _safe_path(path)
    try:
        path.mkdir(mode=0o700)  # Atomic even on platforms without fcntl.
    except FileExistsError as exc:
        raise TransactionError("writer lock exists; do not steal a stale lock", code="lock_conflict") from exc
    identity = path.stat()
    try:
        yield
    finally:
        try:
            current = path.lstat()
        except OSError as exc:
            raise TransactionError("writer lock disappeared; inspect transaction scene", code="recovery_required") from exc
        if (current.st_dev, current.st_ino) != (identity.st_dev, identity.st_ino):
            raise TransactionError("writer lock replaced; preserving scene", code="recovery_required")
        try:
            path.rmdir()
        except OSError as exc:
            raise TransactionError("writer lock cannot be released; inspect transaction scene", code="recovery_required") from exc


def _expect(path, expected):
    if expected is not None and read_snapshot(path) != expected:
        raise TransactionError("output changed immediately before mutation: " + str(path), code="drift")


def _atomic_file(path, data, mode, *, expected=None):
    _safe_path(path)
    if path.is_symlink():
        raise TransactionError("refusing symlink file output", code="path_conflict")
    fd, name = tempfile.mkstemp(prefix=".agm-", dir=str(path.parent))
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(name, mode)
        _expect(path, expected)
        os.replace(name, path)
    finally:
        if os.path.lexists(name):
            os.unlink(name)


def _apply(path, snapshot, *, expected=None):
    _safe_path(path)
    if snapshot.kind == "file":
        if path.is_symlink():
            raise TransactionError("symlink appeared at file output", code="path_conflict")
        _atomic_file(path, snapshot.data, snapshot.mode, expected=expected)
    elif snapshot.kind == "absent":
        _expect(path, expected)
        if os.path.lexists(path):
            path.unlink()
    elif snapshot.kind == "symlink":
        _expect(path, expected)
        if os.path.lexists(path):
            if not path.is_symlink():
                raise TransactionError("nonlink appeared at symlink output", code="path_conflict")
            path.unlink()
            _expect(path, Snapshot("absent"))
        path.symlink_to(snapshot.target, target_is_directory=True)
    else:
        raise TransactionError("unknown snapshot kind")


def _metadata(snapshot, *, path, backup=None):
    # The raw link spelling is kept for exact restoration; its fingerprint uses
    # the resolved absolute target, matching registry link_target semantics.
    fingerprint = snapshot.fingerprint
    if snapshot.kind == "symlink":
        fingerprint = _hash(str((Path(path).parent / snapshot.target).resolve()).encode("utf-8"))
    return {"existed": snapshot.kind != "absent", "kind": snapshot.kind,
            "mode": snapshot.mode, "link_target": snapshot.target,
            "fingerprint": fingerprint, "backup": backup}


class Transaction:
    """Execute an already approved exact write set, guarded by before snapshots.

    allowed_roots is the approved output scope (parents must not be symlinks).
    hook(event, path) is optional fault injection/observation, never required by
    production. Stages: before_write, after_write, before_readback,
    before_restore, before_restore_readback. Registry receives the same checks.
    """
    def __init__(self, *, lock_path, backup_root, allowed_roots, operation="enable-memory", hook=None):
        self.lock_path = _safe_path(lock_path)
        self.backup_root = _safe_path(backup_root)
        if self.backup_root.is_symlink():
            raise TransactionError("backup root is a symlink", code="path_conflict")
        self.allowed_roots = tuple(_safe_path(p) for p in allowed_roots)
        if not self.allowed_roots:
            raise TransactionError("approved output scope is required")
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        self.directory = self.backup_root / (stamp + "-" + uuid.uuid4().hex)
        self.manifest_path = self.directory / "manifest.json"
        self.operation = operation
        self.hook = hook or (lambda event, path: None)
        self.manifest = None

    def _scope(self, path):
        path = _safe_path(path)
        if not any(path == root or root in path.parents for root in self.allowed_roots):
            raise TransactionError("output outside approved roots: " + str(path), code="path_conflict")
        if path == self.lock_path or self.lock_path in path.parents or path == self.backup_root or self.backup_root in path.parents:
            raise TransactionError("output overlaps transaction metadata", code="path_conflict")
        return path

    def _save(self):
        data = (json.dumps(self.manifest, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
        _atomic_file(self.manifest_path, data, 0o600)
        if self.manifest_path.read_bytes() != data:
            raise TransactionError("manifest readback mismatch")

    def _verify(self, path, expected, *, restore=False):
        self.hook("before_restore_readback" if restore else "before_readback", path)
        if read_snapshot(path) != expected:
            raise TransactionError("readback mismatch: " + str(path))

    def run(self, changes, *, registry_change=None, registry_authoritative=False, phased_writes=False):
        changes = list(changes)
        if phased_writes and (self.operation != 'organize-user-rules' or registry_change is not None or registry_authoritative):
            raise TransactionError('phased writes are restricted to explicit memory fusion without registry changes')
        if registry_change is not None:
            changes.append(registry_change)
        with write_lock(self.lock_path):
            seen = {}
            for change in changes:
                path = self._scope(change.path)
                if path in seen and not phased_writes:
                    raise TransactionError("duplicate transaction output")
                actual = seen[path] if path in seen else read_snapshot(path)
                if actual != change.expected:
                    raise TransactionError("output drifted before transaction: " + str(change.path), code="drift")
                seen[path] = change.after
                if change.after.kind == "file" and change.expected.kind == "symlink":
                    raise TransactionError("file/link conflict", code="path_conflict")
                if change.after.kind == "symlink" and change.expected.kind not in ("absent", "symlink"):
                    raise TransactionError("link/copy conflict", code="path_conflict")
                if change.after.kind == "symlink" and change.expected.kind == "symlink" and change.after != change.expected:
                    raise TransactionError("refusing to repoint existing link", code="path_conflict")
            # A no-op does not make a backup or touch output mtimes.
            active = [c for c in changes if c.after != c.expected]
            if not active:
                return {"status": "unchanged", "manifest": None, "changed": []}
            attempted = []
            registry_written = False
            self.manifest = {"schema_version": 1, "operation": self.operation,
                             "status": "prepared", "registry_path": str(registry_change.path) if registry_change else None,
                             "created_directories": [], "entries": [], "error": None}
            if phased_writes:
                self.manifest['phased_writes'] = True
            try:
                self.directory.mkdir(parents=True, mode=0o700)
                if registry_authoritative:
                    # Freeze the complete approved output set before any backup
                    # write can fail. No attempted output exists in this phase.
                    self.manifest['entries'] = [
                        {'path': str(c.path),
                         'before': _metadata(c.expected, path=c.path,
                                             backup=str(i)+'.before' if c.expected.kind == 'file' else None),
                         'after': _metadata(c.after, path=c.path),
                         'attempted': False, 'restoration': 'not_needed'}
                        for i, c in enumerate(active)]
                    self._save()
                for i, change in enumerate(active):
                    backup = None
                    if change.expected.kind == "file":
                        backup = str(i) + ".before"
                        _atomic_file(self.directory / backup, change.expected.data, 0o600)
                    if not registry_authoritative:
                        self.manifest["entries"].append({"path": str(change.path),
                            "before": _metadata(change.expected, path=change.path, backup=backup),
                            "after": _metadata(change.after, path=change.path), "attempted": False, "restoration": "not_needed"})
                self._save()
                self.manifest["status"] = "applying"
                self._save()
                for change, entry in zip(active, self.manifest["entries"]):
                    if registry_change is not None and change is registry_change:
                        for prior, _ in attempted:
                            self._verify(prior.path, prior.after)
                    # Verify again immediately before every mutation.
                    if read_snapshot(change.path) != change.expected:
                        raise TransactionError("output changed during transaction", code="drift")
                    missing = []
                    parent = change.path.parent
                    while not parent.exists():
                        missing.append(parent)
                        parent = parent.parent
                    for parent in reversed(missing):
                        self.manifest["created_directories"].append(str(parent))
                        self._save()  # Persist intent before creating a directory.
                        parent.mkdir(mode=0o700)
                    entry["attempted"] = True
                    attempted.append((change, entry))
                    self._save()  # Crash recovery knows which outputs may have changed.
                    self.hook("before_write", change.path)
                    _expect(change.path, change.expected)
                    # Slow hooks may have changed previously staged configs too.
                    if registry_change is not None and change is registry_change:
                        for prior, _ in attempted[:-1]:
                            self._verify(prior.path, prior.after)
                    _apply(change.path, change.after, expected=change.expected)
                    if change is registry_change:
                        registry_written = True
                    self.hook("after_write", change.path)
                    self._verify(change.path, change.after)
                # Recheck every config before committing/returning. Registry is
                # appended last, and prior outputs were individually read back.
                final_outputs = {change.path: change for change in active}
                for change in final_outputs.values():
                    self._verify(change.path, change.after)
                self.manifest["status"] = "committed"
                self._save()
                if registry_authoritative:
                    self.hook("after_commit", self.manifest_path)
            except BaseException as exc:
                # 极窄 opt-in(仅迁移等显式权威提交方使用):注册表 _apply 已完成
                # (读回=after)即不可逆——无论其他输出是否第三态,保全部现场,
                # 不再写任何输出;V 自身第三态同样保全拒绝(不回滚其它输出制造
                # 混合态)。仅确定 V 未提交且读回=before 才走常规回滚;其他使用者
                # 默认行为完全不变。
                if registry_authoritative and registry_change is not None:
                    current_v = read_snapshot(registry_change.path)
                    equal_v = registry_change.expected == registry_change.after
                    durable_commit = False
                    if equal_v:
                        try:
                            saved = json.loads(self.manifest_path.read_bytes())
                            durable_commit = saved == self.manifest and saved['status'] == 'committed'
                        except (OSError, ValueError, KeyError):
                            pass
                    if registry_written or current_v != registry_change.expected or durable_commit:
                        # An equal-V commit is recorded in the existing durable
                        # manifest. Never erase that commit fact on an exception.
                        if not equal_v:
                            self.manifest['status'] = 'recovery_required'
                            self.manifest['error'] = str(exc)
                            self._save()
                        raise TransactionError(str(exc), code='recovery_required',
                                               manifest=self.manifest_path) from exc
                    if equal_v and self.manifest['status'] == 'committed':
                        # A failed commit readback is uncertain, never grounds
                        # for restoring output bytes after a possible commit.
                        raise TransactionError(str(exc), code='recovery_required',
                                               manifest=self.manifest_path) from exc
                errors = []
                for change, entry in reversed(attempted):
                    try:
                        self.hook("before_restore", change.path)
                        current = read_snapshot(change.path)
                        if current not in (change.expected, change.after):
                            raise TransactionError("foreign edit during rollback; preserving output")
                        _apply(change.path, change.expected, expected=current)
                        self._verify(change.path, change.expected, restore=True)
                        entry["restoration"] = "restored"
                    except BaseException as recovery:
                        entry["restoration"] = "failed: " + str(recovery)
                        errors.append(str(change.path) + ": " + str(recovery))
                if not errors:
                    for parent in reversed(self.manifest["created_directories"]):
                        try:
                            Path(parent).rmdir()
                        except FileNotFoundError:
                            pass
                        except OSError as recovery:
                            errors.append(parent + ": " + str(recovery))
                self.manifest["status"] = "recovery_required" if errors else "rolled_back"
                self.manifest["error"] = str(exc)
                try:
                    self._save()
                except BaseException as recovery:
                    errors.append("manifest: " + str(recovery))
                raise TransactionError(str(exc), code="recovery_required" if errors else "transaction_failed",
                                       manifest=self.manifest_path, recovery_errors=errors) from exc
            return {"status": "committed", "manifest": str(self.manifest_path),
                    "changed": [str(c.path) for c in active]}


def _recovery_entries(transaction, manifest_path, manifest):
    """Validate every backup and complete per-path chain before any restore."""
    phased = manifest.get('phased_writes', False)
    if type(phased) is not bool or (phased and (manifest.get('operation') != 'organize-user-rules' or manifest.get('registry_path') is not None)):
        raise TransactionError('invalid phased recovery scope')
    chains = {}; unattempted = False
    for entry in manifest['entries']:
        path = transaction._scope(Path(entry['path']))
        if path in chains and not phased:
            raise TransactionError('duplicate recovery output')
        meta = entry['before']; data = None
        if meta['kind'] == 'file':
            backup = meta['backup']
            if not isinstance(backup,str) or Path(backup).name != backup:
                raise TransactionError('invalid backup path')
            backup_path = manifest_path.parent/backup
            if backup_path.is_symlink(): raise TransactionError('backup is symlink')
            data = backup_path.read_bytes()
            if _hash(data) != meta['fingerprint']: raise TransactionError('backup fingerprint mismatch')
        before = Snapshot(meta['kind'],data,meta['mode'],meta['link_target'])
        key = dict(meta,backup=None)
        after = dict(entry['after'],backup=None)
        if phased and (before.kind not in ('file','absent') or after['kind'] != 'file'):
            raise TransactionError('phased fusion only supports regular memory files')
        if path not in chains:
            chains[path] = {'before':before,'entry':entry,'last':key,'states':[key],'attempted':False}
        chain = chains[path]
        if key != chain['last']: raise TransactionError('broken phased before/after chain')
        if type(entry['attempted']) is not bool: raise TransactionError('invalid attempted flag')
        if entry['attempted']:
            if phased and unattempted: raise TransactionError('phased attempt sequence is not a prefix')
            chain['states'].append(after); chain['attempted'] = True
        else:
            unattempted = True
            if not phased: chain['states'].append(after)
        chain['last'] = after
    planned = []
    for path,chain in chains.items():
        current = read_snapshot(path)
        actual = _metadata(current,path=path)
        if actual not in chain['states']:
            raise TransactionError('recovery output drifted: '+str(path),code='recovery_required',manifest=manifest_path)
        if chain['attempted']:
            planned.append((path,chain['before'],chain['entry'],current))
    for raw in manifest['created_directories']:
        transaction._scope(Path(raw))
    return planned


def inspect_recovery(manifest_path, *, allowed_roots):
    """Read-only validation shared by fusion recovery preview and rollback."""
    manifest_path = _safe_path(manifest_path)
    if manifest_path.is_symlink(): raise TransactionError('recovery manifest is a symlink')
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    if manifest.get('schema_version') != 1 or manifest.get('status') not in ('prepared','applying','recovery_required'):
        raise TransactionError('manifest is not eligible for recovery')
    transaction = Transaction(lock_path=manifest_path.parent/'inspection-lock',backup_root=manifest_path.parent.parent,
                              allowed_roots=allowed_roots,operation='recover')
    _recovery_entries(transaction,manifest_path,manifest)
    return manifest


def _recover_manifest(manifest_path, *, lock_path, allowed_roots, hook=None):
    """Explicit crash rollback under a fresh writer lock; never steals stale locks.

    Operator must inspect and remove a confirmed stale lock first. Only before/
    after fingerprints in this manifest are eligible; unexpected edits stop
    recovery. Files outside approved roots and corrupt backups are rejected
    before any restoration starts. This is a library primitive, not a fourth CLI.
    """
    manifest_path = _safe_path(manifest_path)
    if manifest_path.is_symlink():
        raise TransactionError("recovery manifest is a symlink", code="recovery_required", manifest=manifest_path)
    transaction = Transaction(lock_path=lock_path, backup_root=manifest_path.parent.parent,
                              allowed_roots=allowed_roots, operation="recover", hook=hook)
    with write_lock(transaction.lock_path):
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest.get("schema_version") != 1 or manifest.get("status") not in ("prepared", "applying", "recovery_required"):
            raise TransactionError("manifest is not eligible for recovery")
        planned = _recovery_entries(transaction, manifest_path, manifest)
        errors = []
        for path, before, entry, expected in reversed(planned):
            try:
                transaction.hook("before_restore", path)
                _expect(path, expected)
                _apply(path, before, expected=expected)
                if read_snapshot(path) != before:
                    raise TransactionError("recovery readback mismatch")
                entry["restoration"] = "restored"
                if manifest.get('phased_writes'):
                    for sibling in manifest['entries']:
                        if sibling['path'] == str(path): sibling['restoration'] = 'restored'
            except Exception as exc:
                entry["restoration"] = "failed: " + str(exc)
                errors.append(str(path) + ": " + str(exc))
        if not errors:
            for raw in reversed(manifest["created_directories"]):
                try:
                    Path(raw).rmdir()
                except FileNotFoundError:
                    pass
                except OSError as exc:
                    errors.append(raw + ": " + str(exc))
        manifest["status"] = "recovery_required" if errors else "rolled_back"
        _atomic_file(manifest_path, (json.dumps(manifest, ensure_ascii=False, indent=2) + "\n").encode("utf-8"), 0o600)
        if errors:
            raise TransactionError("crash recovery incomplete", code="recovery_required", manifest=manifest_path, recovery_errors=errors)
        return manifest


def recover_manifest(manifest_path, *, lock_path, allowed_roots, hook=None):
    """Explicit verified crash rollback; see _recover_manifest for policy.

    Malformed/unreadable recovery material is reported as recovery_required,
    with its path, and left intact. No stale lock is removed automatically.
    """
    try:
        return _recover_manifest(manifest_path, lock_path=lock_path, allowed_roots=allowed_roots, hook=hook)
    except TransactionError as exc:
        if exc.code == "lock_conflict":
            raise
        if exc.manifest is None:
            exc.manifest = str(manifest_path)
        exc.code = "recovery_required"
        raise
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise TransactionError("cannot recover manifest: " + str(exc),
                               code="recovery_required", manifest=manifest_path,
                               recovery_errors=[str(exc)]) from exc
