"""Read-only guarded live ensure plus disposable real-installer rehearsal.

Run from the AGM checkout. No init/save/migrate is called on live projects.
"""
import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
SOURCE = REPO.parent / 'context-keeper'
sys.dont_write_bytecode = True
sys.path[:0] = [str(REPO / 'scripts'), str(REPO / 'tests/unit'), str(REPO / 'tests/integration')]
from agm_core import enable, paths, registry
from test_m204_enable import EnableFixture
from test_m204_subprocess import PROBE_STUB


def sha(data):
    return hashlib.sha256(data).hexdigest()


def snapshot(path):
    """Store only aggregate hash, file count and mtime hash for protected trees."""
    path = Path(path)
    if not path.exists() and not path.is_symlink():
        return {'kind': 'absent'}
    if path.is_symlink():
        return {'kind': 'symlink', 'target_sha256': sha(os.readlink(path).encode()), 'mtime_ns': path.lstat().st_mtime_ns}
    if path.is_file():
        return {'kind': 'file', 'sha256': sha(path.read_bytes()), 'mtime_ns': path.stat().st_mtime_ns}
    rows = []
    for p in sorted(path.rglob('*')):
        st = p.lstat()
        rows.append([str(p.relative_to(path)), st.st_mtime_ns, st.st_mode,
                     sha(os.readlink(p).encode()) if p.is_symlink() else sha(p.read_bytes()) if p.is_file() else None])
    return {'kind': 'tree', 'entry_count': len(rows), 'aggregate_sha256': sha(json.dumps(rows).encode())}


def rehearsal():
    fixture = EnableFixture(methodName='runTest')
    fixture.setUp()
    try:
        (fixture.source / 'scripts/install.py').write_bytes((SOURCE / 'scripts/install.py').read_bytes())
        (fixture.source / 'scripts/context_keeper_probe.py').write_text(PROBE_STUB)
        calls = []
        def runner(command, **kwargs):
            calls.append(command[2:])
            return subprocess.run(command, **kwargs)
        fixture.request['runner'] = runner
        bridge = fixture.root / '.workbuddy/memory/MEMORY.md'
        bridge.parent.mkdir(parents=True)
        bridge.write_bytes((OUT / 'agent-group-memory.before.block.md').read_bytes() + b'\n\n# preserved notes\r\n')
        before = snapshot(bridge)
        first = fixture.apply('yes', True)
        fixture.assertEqual(snapshot(bridge), before)
        fixture.request['approval'] = None
        second = enable.run(fixture.request)
        fixture.assertEqual(second['status'], 'completed', second)
        fixture.assertEqual(second['changes'], [])
        fixture.assertEqual(snapshot(bridge), before)
        fixture.assertEqual(bridge.read_bytes().count(enable.WORKBUDDY_MARKER['start'].encode()), 1)
        return {'scope': 'temporary HOME/project/provider checkout', 'first_status': first['status'],
                'second_status': second['status'], 'second_changes': second['changes'],
                'legacy_file_bytes_and_mtime_unchanged': True,
                'upstream_workbuddy_ensure_calls': sum('--ensure-bridge' in c and '--workbuddy' in c for c in calls),
                'probe': 'disposable stub; does not prove live store/runtime behavior'}
    finally:
        fixture.doCleanups()


def live():
    home = str(Path.home())
    config = paths.select_platform(paths.load_agents_table(), 'darwin')
    ledger_path = REPO / 'scripts/registry.json'
    ledger = registry.load_registry(ledger_path, allowed_user_paths=paths.allowed_user_paths(config, None, home=home))
    targets = [REPO.parent / name for name in ('agent-group-memory', 'knowwind', 'poster-fit')]
    protected = {str(ledger_path)} | {paths.expand_path(c['user_entry'], home=home) for c in config.values()}
    for root in targets:
        project = ledger['projects'][str(root)]
        assembly = project['checkouts'][str(root)]
        protected.add(assembly['store']['path'])
        protected.update(o['path'] for o in assembly['objects'].values())
        protected.update(ledger['shared_objects'][oid]['path'] for oid in assembly['shared_object_ids'])
    before = {p: snapshot(p) for p in sorted(protected)}
    (OUT / 'protected-before.json').write_text(json.dumps(before, ensure_ascii=False, indent=2) + '\n')
    assembly = ledger['projects'][str(REPO)]['checkouts'][str(REPO)]
    enable._preflight_objects(assembly, ledger['shared_objects'])
    bridge = REPO / '.workbuddy/memory/MEMORY.md'
    desired = enable._bridge_template(SOURCE, 'workbuddy')
    data = bridge.read_bytes()
    span = enable.entries.managed_span(data, **enable._marker_args(enable.WORKBUDDY_MARKER))
    assert span and span[0] == 0 and data[slice(*span)] == desired
    fingerprints = enable._source_fingerprints(SOURCE)
    argv = ['install.py', '--ensure-bridge', '--skill-dir', str(REPO / '.workbuddy/skills/context-keeper'),
            '--root', str(REPO), '--workbuddy', '--approved']
    results = []
    for _ in range(2):
        result = enable._call({'home': home}, SOURCE, argv, fingerprints=fingerprints)
        assert result['scope'] == 'project' and result['bridge'] == str(bridge) and result['action'] == 'unchanged', result
        results.append(result)
    checked = subprocess.run([sys.executable, str(REPO / 'scripts/agm.py'), 'check-memory', '--all'],
                             capture_output=True, text=True, env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1'))
    (OUT / 'check-all.json').write_text(checked.stdout)
    assert checked.returncode == 0, checked.stderr + checked.stdout
    check = json.loads(checked.stdout)
    assert check['status'] == 'completed' and len(check['projects']) == 3
    assert all(not p['gaps'] for p in check['projects'])
    after = {p: snapshot(p) for p in sorted(protected)}
    (OUT / 'protected-after.json').write_text(json.dumps(after, ensure_ascii=False, indent=2) + '\n')
    assert before == after, 'Protected file/tree changed; inspect evidence before any further action'
    rows = []
    sampled = json.loads((OUT / 'before.json').read_text())
    for old in sampled:
        p = Path(old['path']); data = p.read_bytes()
        span = enable.entries.managed_span(data, **enable._marker_args(enable.WORKBUDDY_MARKER))
        block = data[slice(*span)]
        (OUT / (old['project'] + '.after.block.md')).write_bytes(block)
        row = dict(project=old['project'], file_sha256=sha(data), block_sha256=sha(block),
                   start=span[0], start_count=data.count(enable.WORKBUDDY_MARKER['start'].encode()),
                   end_count=data.count(enable.WORKBUDDY_MARKER['end'].encode()))
        assert row['file_sha256'] == old['file_sha256'] and row['block_sha256'] == old['block_sha256']
        rows.append(row)
    (OUT / 'after.json').write_text(json.dumps(rows, ensure_ascii=False, indent=2) + '\n')
    return {'ensure_command': [sys.executable, str(SOURCE / 'scripts' / argv[0])] + argv[1:],
            'results': results, 'check_exit': checked.returncode, 'check_status': check['status'],
            'projects': [dict(project=p['main_checkout'], gaps=len(p['gaps'])) for p in check['projects']],
            'protected_snapshots_equal': before == after, 'protected_path_count': len(protected)}


if __name__ == '__main__':
    result = {'observed_at_utc': datetime.now(timezone.utc).isoformat(),
              'rehearsal': rehearsal(), 'live': live(), 'workbuddy_new_session_runtime': 'not performed; optional user acceptance'}
    (OUT / 'takeover.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(result, ensure_ascii=False, indent=2))
