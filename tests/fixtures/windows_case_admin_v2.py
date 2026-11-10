"""Fixture-only helper template. Bind a reviewed plan before CLI use.

Run with -I -S -B, never -O. No UAC request, retry, auto-rollback or lock stealing.
fsutil takes a path: snapshots do NOT bind its mutation atomically. Use only a
human-controlled, otherwise idle synthetic fixture. This is not W02 recovery.
"""
import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import uuid

BOUND_PLAN = None


class Refused(RuntimeError):
    pass


def require(condition, message):
    if not condition:
        raise Refused(message)


def runtime_guards():
    require(sys.flags.optimize == 0, 'Optimized Python refused')
    require(sys.flags.isolated == 1 and sys.flags.no_site == 1 and sys.dont_write_bytecode,
            'Use isolated interpreter flags: -I -S -B')


def persist(path, value):
    # Exclusive append-only evidence files. fsync the file; no claim of full
    # directory-entry/power-loss durability is made by this preparation helper.
    with path.open('x', encoding='utf8') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.flush()
        os.fsync(stream.fileno())


def error_info(exc):
    return {'type': type(exc).__name__, 'message': str(exc),
            'winerror': getattr(exc, 'winerror', None)}


def validate_snapshot(value, plan, case):
    require((value.get('volume_id'), value.get('file_id')) ==
            (plan['identity']['volume_id'], plan['identity']['file_id']), 'Fixture identity drift')
    require(value.get('security', {}).get('sha256') == plan['security_sha256'], 'Fixture security drift')
    require(type(value.get('case_sensitive_directory')) is bool, 'Case flag unknown')
    require(not list(case.iterdir()), 'Fixture not empty')


def run(plan, action, runtime, *, writer=persist):
    require(action in ('check', 'prepare', 'restore'), 'Unknown action')
    require(isinstance(plan, dict), 'Unbound helper')
    root, case = Path(plan['root']), Path(plan['case_path'])
    require(root.is_absolute(), 'Absolute bound root required')
    require(str(uuid.UUID(plan['run_id'])) == plan['run_id'], 'Invalid bound run ID')
    require(case == root/'synthetic-home'/('dell-fixture-'+plan['run_id'])/'case', 'Unbound fixture path')
    runtime.validate_support_paths(root)
    lock = root/'tmp'/'case-admin-v2.lock'
    receipt = root/'evidence'/('case-admin-v2-'+str(uuid.uuid4()))
    record = {'run_id': plan['run_id'], 'action': action, 'started': time.time(),
              'status': 'refused', 'command_attempted': False, 'command': None,
              'before': None, 'after': None, 'receipt': str(receipt),
              'lock_path': str(lock), 'race_free': False,
              'identity_bound_during_fsutil': False, 'exclusive_fixture_required': True,
              'cooperative_lock_only': True,
              'restore': {'action': 'restore', 'interpreter_flags': ['-I', '-S', '-B'],
                          'helper': plan.get('helper_path'), 'case_path': str(case),
                          'may_refuse_identity_security_or_nonempty_drift': True,
                          'never_delete_lock_without_confirming_inactive_owner': True}}
    # Existing locks are never interpreted as stale using only PID or age.
    receipt.mkdir()
    locked, lock_id = False, None
    owner_committed, owner_id, owner_hash = False, None, None
    owner_record = {'operation': str(receipt), 'pid': os.getpid(), 'run_id': plan['run_id']}
    try:
        lock.mkdir()
        locked = True
        lock_id = runtime.identity(lock)
        writer(lock/'owner.json', owner_record)
        owner_raw = (lock/'owner.json').read_bytes()
        require(json.loads(owner_raw) == owner_record, 'Initial lock ownership drift')
        owner_id = runtime.identity(lock/'owner.json')
        owner_hash = hashlib.sha256(owner_raw).hexdigest()
        owner_committed = True
        before = runtime.snapshot(case)
        record['before'] = before
        validate_snapshot(before, plan, case)
        if action == 'prepare':
            require(before['case_sensitive_directory'] is False, 'Already enabled; inspect and use restore')
        record['status'] = 'intent'
        # Nothing invokes fsutil unless the intent has been flushed/fsynced.
        writer(receipt/'intent.json', dict(record))
        if action != 'check':
            record['command_attempted'] = True
            record['command_may_have_changed_flag'] = True
            try:
                cp = runtime.command(case, 'enable' if action == 'prepare' else 'disable')
                record['command'] = {'exit': cp.returncode,
                                     'stdout_base64': base64.b64encode(cp.stdout).decode('ascii'),
                                     'stderr_base64': base64.b64encode(cp.stderr).decode('ascii')}
            except subprocess.TimeoutExpired as exc:
                record['command'] = {'timeout': True,
                                     'stdout_base64': base64.b64encode(exc.stdout or b'').decode('ascii'),
                                     'stderr_base64': base64.b64encode(exc.stderr or b'').decode('ascii')}
                raise
            require(cp.returncode == 0, 'fsutil failed; no retry or automatic restore')
        after = runtime.snapshot(case)
        record['after'] = after
        validate_snapshot(after, plan, case)
        if action != 'check':
            require(after['case_sensitive_directory'] == (action == 'prepare'), 'Unexpected case flag')
        record['status'] = 'succeeded'
    except BaseException as exc:
        if not isinstance(exc, Exception):
            record['interrupted'] = True
            record['lock_retained'] = True
            record['command_outcome_unknown'] = record['command_attempted']
        record['status'] = 'needs_inspection' if record['command_attempted'] else 'refused'
        record['error'] = error_info(exc)
    finally:
        if record['after'] is None:
            try:
                record['after'] = runtime.snapshot(case)
            except Exception as exc:
                record['after_error'] = error_info(exc)
        record['finished'] = time.time()
        record['lock_acquired'] = locked
        record['owner_committed'] = owner_committed
        record['automatic_restore_attempted'] = False
        record['automatic_retry_attempted'] = False
        try:
            writer(receipt/'result.json', dict(record))
        except Exception as exc:
            # Do not hide a missing terminal receipt or release the cooperative
            # lock when durable evidence cannot be retained.
            record['receipt_error'] = error_info(exc)
            record['status'] = 'evidence_failed'
            record['lock_retained'] = True
        else:
            if not locked:
                record['lock_not_acquired'] = True
            elif record.get('lock_retained'):
                pass  # Interrupted command outcome unknown; no lock stealing/release.
            else:
                try:
                    require(lock_id is not None, 'Lock identity unknown; retain scene')
                    require(runtime.identity(lock) == lock_id, 'Lock identity drift; retain scene')
                    owner = lock/'owner.json'
                    if owner_committed:
                        require(owner.is_file(), 'Committed lock owner missing; retain scene')
                        require(runtime.identity(owner) == owner_id, 'Lock owner node replaced')
                        raw = owner.read_bytes()
                        require(hashlib.sha256(raw).hexdigest() == owner_hash, 'Lock owner bytes changed')
                        require(json.loads(raw) == owner_record, 'Lock ownership drift')
                        owner.unlink()
                    else:
                        require(not owner.exists() and not owner.is_symlink(),
                                'Uncommitted owner file exists; retain scene')
                    lock.rmdir()  # Unknown added files prevent removal; no recursive cleanup.
                    record['lock_released'] = True
                    writer(receipt/'completion.json', {'status': record['status'], 'lock_released': True})
                except Exception as exc:
                    record['lock_cleanup_error'] = error_info(exc)
                    record['lock_released_before_cleanup_error'] = record.get('lock_released', False)
                    record['status'] = 'needs_inspection'
                    try:
                        writer(receipt/'cleanup-error.json', dict(record))
                    except Exception as evidence_exc:
                        record['cleanup_evidence_error'] = error_info(evidence_exc)
    return record


def verify_source_closure(plan):
    root = Path(plan['root'])
    expected = {'scripts/agm_core/__init__.py', 'scripts/agm_core/paths.py',
                'scripts/agm_core/platform_diagnostics.py', 'scripts/agm_core/windows_native.py'}
    require(set(plan['sources']) == expected, 'Unexpected import closure')
    for name, digest in plan['sources'].items():
        raw = (root/'code'/name).read_bytes()
        require(hashlib.sha256(raw).hexdigest() == digest, 'Source changed: '+name)


class WindowsRuntime:
    def __init__(self, plan):
        require(sys.platform == 'win32', 'Windows required')
        self.root = Path(plan['root'])
        verify_source_closure(plan)
        sys.path.insert(0, str(self.root/'code/scripts'))
        from agm_core import windows_native
        self.native = windows_native

    def validate_support_paths(self, root):
        for path in (root, root/'tmp', root/'evidence'):
            with self.native.inspect_path(str(path)) as value:
                require(value['directory'], 'Support path is not a directory')

    def snapshot(self, case):
        with self.native.inspect_path(str(case), security=True, candidate_metadata=True) as value:
            # No security descriptor contents/SIDs are persisted.
            return {'volume_id': value['volume_id'], 'file_id': value['file_id'],
                    'case_sensitive_directory': value['case_sensitive_directory'],
                    'security': {'sha256': value['security']['sha256']},
                    'case_entry_count': len(list(case.iterdir()))}

    def identity(self, path):
        with self.native.inspect_path(str(path)) as value:
            return value['volume_id'], value['file_id']

    def command(self, case, operation):
        executable = Path(os.environ['SystemRoot'])/'System32/fsutil.exe'
        return subprocess.run([str(executable), 'file', 'setCaseSensitiveInfo', str(case), operation],
                              capture_output=True, timeout=10)


def main():
    runtime_guards()
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['check', 'prepare', 'restore'])
    parser.add_argument('--exclusive-fixture', action='store_true')
    args = parser.parse_args()
    require(args.exclusive_fixture, 'Operator must keep this synthetic fixture otherwise idle; not an OS isolation guarantee')
    require(BOUND_PLAN is not None, 'Unbound helper')
    record = run(BOUND_PLAN, args.action, WindowsRuntime(BOUND_PLAN))
    print(json.dumps(record, ensure_ascii=False))
    return 0 if record['status'] == 'succeeded' else 2


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except Refused as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(2)
