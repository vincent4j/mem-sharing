#!/usr/bin/env python3
"""Read-only local CI gate; reuse the common sync tests and release verifier."""
import argparse
import json
import os
import re
import stat
import subprocess
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[2]/'scripts'))
from agm_core import plugin_release

SOURCE = 'plugins/shared/src/'
COMMON = 'plugins/paseo/server/shared/common/'
SYNC = 'plugins/shared/sync-to-plugins.mjs'
TEST = 'plugins/paseo/test/sync.test.ts'
# Release identity is checked by checkout_delivery. Its development-only test
# deliberately rejects a concrete release digest, so select just the two common
# tests in R. The original transformation remains solely in the existing tools.
COMMON_TESTS = ('^every generated common module matches the true source deterministically$'
                '|^the generated copy contains no extra modules$')


def _tracked_inputs(root, commit):
    required = {SYNC, TEST, plugin_release.IDENTITY}
    entries = {}
    for record in plugin_release._git(root, 'ls-tree', '-rz', '--full-tree', commit).split(b'\0'):
        if not record:
            continue
        meta, raw_name = record.split(b'\t', 1)
        name = raw_name.decode('utf-8')
        if name in required or name.startswith((SOURCE, COMMON)):
            entries[name] = meta.split()
    if not required <= entries.keys():
        raise ValueError('Missing tracked common sync/check/identity input')
    sources = {name for name in entries if name.startswith(SOURCE) and name.endswith('.ts')}
    if not sources:
        raise ValueError('No tracked shared TypeScript source')
    for prefix in (SOURCE, COMMON):
        directory = root/prefix
        if directory != directory.resolve() or not directory.is_dir():
            raise ValueError('Common source/output must be a real directory')
        for path in directory.iterdir():
            name = path.relative_to(root).as_posix()
            if (prefix == COMMON or path.name.endswith('.ts')) and name not in entries:
                raise ValueError('Untracked common source/output: '+name)
    for name, (mode, kind, blob) in entries.items():
        path = root/name
        if kind != b'blob' or mode not in (b'100644', b'100755') or path != path.resolve() or not path.is_file():
            raise ValueError('Nonregular tracked CI input: '+name)
        if stat.S_IMODE(path.stat().st_mode) != (int(mode, 8) & 0o777) or path.read_bytes() != plugin_release._git(root, 'cat-file', 'blob', blob.decode()):
            raise ValueError('CI input differs from pinned Git bytes/mode: '+name)
    return len(sources)


def check(args):
    root, commit = plugin_release.clean_checkout(args.source, args.commit)
    count = _tracked_inputs(root, commit)
    argv = [args.node, '--experimental-strip-types', '--test', '--test-reporter=tap']
    if args.stage == 'release':
        argv += ['--test-name-pattern='+COMMON_TESTS]
    argv += [str(root/TEST)]
    env = dict(os.environ)
    for key in ('NODE_OPTIONS', 'NODE_V8_COVERAGE', 'NODE_COMPILE_CACHE'):
        env.pop(key, None)  # No injected loaders, coverage or compilation writes.
    result = subprocess.run(argv, cwd=root, env=env, capture_output=True, text=True)
    if result.returncode:
        raise ValueError('Existing common/identity tests failed:\n'+result.stdout+result.stderr)
    expected = 2 if args.stage == 'release' else 3
    if not re.search(r'(?m)^# pass '+str(expected)+r'$', result.stdout) or not re.search(r'(?m)^# fail 0$', result.stdout):
        raise ValueError('Required common/identity tests did not all run:\n'+result.stdout+result.stderr)
    # Detect changes while the subprocess ran without taking any writer lock.
    plugin_release.clean_checkout(root, commit)
    _tracked_inputs(root, commit)
    release = None
    if args.stage == 'release':
        release = plugin_release.checkout_delivery(root, commit, args.version)
    return {'status':'checked', 'stage':args.stage, 'commit':commit,
            'common_modules':count, 'release':release,
            'published':False, 'runtime_acceptance':'pending',
            'common_test_stdout':result.stdout, 'common_test_stderr':result.stderr}


def main():
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument('stage', choices=('source','release'))
    parser.add_argument('--source', required=True, help='Canonical absolute clean repository root')
    parser.add_argument('--commit', required=True, help='Full pinned HEAD, S or R according to stage')
    parser.add_argument('--version', help='Explicit approved product version; release only')
    parser.add_argument('--node', default='node', help='Node with TypeScript stripping (same prerequisite as existing sync tests)')
    args = parser.parse_args()
    if (args.stage == 'release') != (args.version is not None):
        parser.error('--version is required only for release stage')
    try:
        report = check(args)
    except (ValueError, OSError, subprocess.SubprocessError) as exc:
        print(json.dumps({'status':'failed','stage':args.stage,'error':str(exc),'published':False}, ensure_ascii=False))
        return 2
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
