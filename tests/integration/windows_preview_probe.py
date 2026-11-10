"""Bounded real-Windows CLI lifecycle; writes only inside the supplied new root."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

sys.dont_write_bytecode = True
SOURCE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(SOURCE / 'scripts'))
from agm_core import windows_preview as wp


def main():
    root = Path(sys.argv[1])
    if sys.platform != 'win32' or not root.is_absolute() or root.name != 'lifecycle':
        raise ValueError('new Windows lifecycle root required')
    root.mkdir()  # Must be a new root, never reuse a previous fixture.
    home = root / 'home'; home.mkdir()
    evidence = root / 'evidence'; evidence.mkdir()
    native = home / wp.NATIVE[0]; native.parent.mkdir()
    original = b'\xef\xbb\xbf# synthetic private\r\nkeep-private-byte-for-byte\r\nlast line'
    native.write_bytes(original)
    (evidence / 'original-native.bin').write_bytes(original)
    calls = []
    entry = SOURCE / 'scripts/windows_preview.py'
    def call(*args, expected=0):
        command = [sys.executable, '-I', '-S', '-B', str(entry),
                   *args, '--home', str(home)]
        r = subprocess.run(command, capture_output=True, text=True, encoding='utf-8', timeout=90)
        calls.append({'argv': command, 'exit': r.returncode, 'stdout': r.stdout, 'stderr': r.stderr})
        (evidence / 'commands.json').write_bytes(wp.encoded(calls))
        if r.returncode != expected:
            raise ValueError('CLI result mismatch: ' + r.stdout + r.stderr)
        return json.loads(r.stdout)
    shown = call('plan', '--source', str(SOURCE), '--output', str(evidence / 'install-plan.json'), expected=5)
    installed = call('apply', '--plan', shown['plan'], '--plan-sha256', shown['plan_sha256'])
    entry = home / wp.CODE / 'scripts/windows_preview.py'
    call('add', '--text', 'synthetic ZCode shared record')
    call('add', '--text', 'synthetic WorkBuddy shared record')
    public = (home / wp.PUBLIC).read_bytes()
    before_exit = {name: wp.packed(wp.snap(home / name)) for name in wp.NATIVE + (wp.PUBLIC, wp.RECEIPT)}
    (evidence / 'before-exit.json').write_bytes(wp.encoded(before_exit))
    shown = call('exit-plan', '--output', str(evidence / 'exit-plan.json'), expected=5)
    exited = call('apply', '--plan', shown['plan'], '--plan-sha256', shown['plan_sha256'])
    export = Path(exited['export']['path']).read_bytes()
    manifest = json.loads(Path(installed['manifest']).read_bytes())
    backup = next(e for e in manifest['entries'] if e['path'] == str(native))['before']['backup']
    checks = {
        'original_native_exact': native.read_bytes() == original,
        'backup_exact': (Path(installed['manifest']).parent / backup).read_bytes() == original,
        'new_shared_records_exported_exact': export == public,
        'export_hash_equal': hashlib.sha256(export).hexdigest() == exited['export']['sha256'],
        'owned_native_removed': all(not (home / n).exists() for n in wp.NATIVE[1:]),
        'owned_code_files_removed': not any(n.is_file() for n in (home / wp.CODE).rglob('*')),
        'public_and_receipt_removed': all(not (home / n).exists() for n in (wp.PUBLIC, wp.RECEIPT)),
        'backup_and_export_outside_code': home / wp.CODE not in Path(exited['export']['path']).parents
            and home / wp.CODE not in Path(installed['manifest']).parents,
    }
    result = {'status': 'passed' if all(checks.values()) else 'failed', 'checks': checks,
              'client_loading_verified': False, 'production_support': False,
              'install': installed, 'exit': exited, 'pty_outer_exit': 'unknown'}
    (evidence / 'result.json').write_bytes(wp.encoded(result))
    print(json.dumps(result, ensure_ascii=False))
    return 0 if all(checks.values()) else 1


if __name__ == '__main__':
    raise SystemExit(main())
