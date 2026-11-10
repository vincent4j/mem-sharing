"""R2 only: synthetic read-only path candidates, never write admission."""
import ctypes
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import uuid

root = Path(sys.argv[1])
run_id = str(uuid.UUID(sys.argv[2]))
sys.path.insert(0, str(root / 'code/scripts'))
from agm_core import windows_native as w

fixtures = root / 'synthetic-home' / ('candidate-' + run_id)
fixtures.mkdir()
evidence = root / 'evidence' / ('native-' + run_id + '.json')
if evidence.exists():
    raise FileExistsError('Refuse evidence overwrite')
result = dict(run_id=run_id, argv=sys.argv, platform=sys.platform, python=sys.version,
              started=time.time(), checks=[], production_write_authorized=False)


def check(name, operation):
    base = fixtures / name
    base.mkdir()
    allowed = base / '允许 中文'
    allowed.mkdir()
    leaf = allowed / 'Sample.txt'
    leaf.write_bytes(b'ONLY SYNTHETIC\r\n')
    try:
        detail = operation(base, allowed, leaf)
        result['checks'].append(dict(name=name, status='passed', detail=detail))
    except Exception as exc:
        result['checks'].append(dict(name=name, status='failed', type=type(exc).__name__,
                                     code=getattr(exc, 'code', None), winerror=getattr(exc, 'winerror', None), message=str(exc)))


def refused(path, allowed, code):
    try:
        with w.inspect_candidate_path(str(path), allowed_root=str(allowed)):
            pass
    except w.NativeInspectionError as exc:
        assert exc.code == code, (exc.code, exc.winerror)
        return dict(code=exc.code, winerror=exc.winerror)
    raise AssertionError('Candidate unexpectedly accepted')


def ordinary(base, allowed, leaf):
    with w.inspect_candidate_path(str(leaf), allowed_root=str(allowed)) as snapshot:
        assert snapshot['path_checks_passed'] and not snapshot['production_write_authorized']
        assert not snapshot['race_free'] and not snapshot['storage_provider_verified']
        assert all(n['case_sensitivity_checked'] for n in snapshot['chain'])
        return {key:snapshot[key] for key in ('number_of_links', 'case_sensitivity_checked', 'path_checks_passed', 'production_write_authorized', 'race_free', 'storage_provider_verified')}


def outside(base, allowed, leaf):
    other = base / 'sibling.txt'
    other.write_bytes(b'OUTSIDE SCOPE SYNTHETIC')
    return refused(other, allowed, 'outside_allowed_root')


def hardlink(base, allowed, leaf):
    alias = allowed / 'alias.txt'
    os.link(leaf, alias)
    try:
        return [refused(p, allowed, 'hardlink_or_unknown_links_refused') for p in (leaf, alias)]
    finally:
        alias.unlink()


def case_alias(base, allowed, leaf):
    with w.inspect_candidate_path(str(leaf).upper(), allowed_root=str(allowed)) as snapshot:
        assert snapshot['path_checks_passed']
        return dict(ancestor_case_flags_checked=True)


def link_drift(base, allowed, leaf):
    alias = allowed / 'late-alias.txt'
    try:
        try:
            with w.inspect_candidate_path(str(leaf), allowed_root=str(allowed)):
                os.link(leaf, alias)
        except w.NativeInspectionError as exc:
            assert exc.code == 'node_drift', (exc.code, exc.winerror)
            return dict(link_count_drift_detected=True)
        raise AssertionError('New hardlink was not detected')
    finally:
        if alias.exists():
            alias.unlink()


def rename_drift(base, allowed, leaf):
    moved = allowed / 'renamed.txt'
    renamed = False
    try:
        try:
            with w.inspect_candidate_path(str(leaf), allowed_root=str(allowed)):
                try:
                    os.replace(leaf, moved)
                    renamed = True
                except PermissionError as exc:
                    return dict(rename_blocked_winerror=exc.winerror)
        except w.NativeInspectionError as exc:
            assert renamed and exc.code == 'node_drift', (exc.code, exc.winerror)
            return dict(rename_allowed=True, named_recheck_detected=True)
        raise AssertionError('Rename was not detected')
    finally:
        if renamed:
            os.replace(moved, leaf)


def cross_volume(base, allowed, leaf):
    return refused('C:\\', allowed, 'cross_volume_refused')


check('ordinary_unicode', ordinary)
check('outside_root', outside)
check('hardlink_both_names', hardlink)
check('insensitive_case_alias', case_alias)
check('new_hardlink_drift', link_drift)
check('candidate_rename_drift', rename_drift)
check('cross_volume', cross_volume)
result['finished'] = time.time()
result['not_covered'] = ['case-sensitive enabled directory pending fixture capability', 'short-name and mapped-drive aliases', 'sync provider detection', 'missing leaf create', 'ACL access-denied injection', 'atomic traversal or writes']
with evidence.open('x', encoding='utf8') as stream:
    json.dump(result, stream, ensure_ascii=False, indent=2)
print(json.dumps([(r['name'], r['status']) for r in result['checks']]))
sys.exit(1 if any(r['status']=='failed' for r in result['checks']) else 0)
