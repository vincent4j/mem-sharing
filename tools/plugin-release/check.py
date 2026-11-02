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
NOTICE_FILES = ('plugins/shared/THIRD_PARTY_NOTICES.md', 'plugins/paseo/THIRD_PARTY_NOTICES.md')
NOTICE_DIRS = ('plugins/shared/notices/', 'plugins/paseo/notices/')
# Release identity is checked by checkout_delivery. Its development-only test
# deliberately rejects a concrete release digest, so select the two common
# tests plus supplier notices in R. Transformations stay in the existing tools.
COMMON_TESTS = ('^every generated common module matches the true source deterministically$'
                '|^the generated copy contains no extra modules$'
                '|^supplier notices are generated from shared disclosure source$')


def _verify_clean_source(root, commit):
    """S must not carry stale generated release artifacts; only R regenerates them.

    The dev sync test deliberately tolerates a non-empty identity when it still
    matches an existing generated manifest, so an old release descriptor, an old
    Paseo payload tree or a leftover concrete identity must be rejected here;
    otherwise a dirty generated state could pass the source stage and pose as
    clean S. Tracked artifacts are found via ls-tree; physical lexists checks
    additionally catch artifacts hidden behind Git ignores (e.g. .git/info/exclude
    keeps status clean) without reading payload content or following links.
    The release stage keeps the opposite, full real-identity checks.
    """
    stale = []
    for record in plugin_release._git(root, 'ls-tree', '-rz', '--full-tree', commit).split(b'\0'):
        if not record:
            continue
        name = record.split(b'\t', 1)[1].decode('utf-8')
        if name == plugin_release.ROOT_MANIFEST or name.startswith(plugin_release.PAYLOAD + '/'):
            stale.append(name)
    stale += [name for name in (plugin_release.ROOT_MANIFEST, plugin_release.PAYLOAD)
              if os.path.lexists(root/name)]
    if stale:
        raise ValueError('Clean source must not carry old generated release artifacts '
                         '(tracked, ignored or untracked): ' + ', '.join(sorted(set(stale))))
    identity = root/plugin_release.IDENTITY
    sentinel = plugin_release._identity_bytes('')
    if (identity != identity.resolve() or not identity.is_file()
            or identity.read_bytes() != sentinel
            or identity.read_bytes() != plugin_release._git(root, 'cat-file', 'blob',
                                                            commit + ':' + plugin_release.IDENTITY)):
        raise ValueError('Source release identity must be the empty dev sentinel '
                         '(old non-empty identity is R-only)')


def _tracked_inputs(root, commit):
    required = {SYNC, TEST, plugin_release.IDENTITY, *NOTICE_FILES}
    entries = {}
    for record in plugin_release._git(root, 'ls-tree', '-rz', '--full-tree', commit).split(b'\0'):
        if not record:
            continue
        meta, raw_name = record.split(b'\t', 1)
        name = raw_name.decode('utf-8')
        if name in required or name.startswith((SOURCE, COMMON, *NOTICE_DIRS)):
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
    for prefix in NOTICE_DIRS:
        directory = root/prefix
        if directory != directory.resolve() or not directory.is_dir():
            raise ValueError('Notices must be a real tracked directory: '+prefix)
        notice_files = {root/name for name in entries if name.startswith(prefix)}
        if not notice_files:
            raise ValueError('Missing tracked supplier license texts: '+prefix)
        allowed_dirs = {parent for path in notice_files for parent in path.parents if parent.is_relative_to(directory)}
        for path in directory.rglob('*'):
            if path.is_symlink() or (path not in notice_files and path not in allowed_dirs):
                raise ValueError('Untracked/unsafe supplier notice: '+path.relative_to(root).as_posix())
    for name, (mode, kind, blob) in entries.items():
        path = root/name
        if kind != b'blob' or mode not in (b'100644', b'100755') or path != path.resolve() or not path.is_file():
            raise ValueError('Nonregular tracked CI input: '+name)
        if stat.S_IMODE(path.stat().st_mode) != (int(mode, 8) & 0o777) or path.read_bytes() != plugin_release._git(root, 'cat-file', 'blob', blob.decode()):
            raise ValueError('CI input differs from pinned Git bytes/mode: '+name)
    return len(sources)


def check(args):
    root, commit = plugin_release.clean_checkout(args.source, args.commit)
    if args.stage == 'source':
        _verify_clean_source(root, commit)
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
    expected = 3 if args.stage == 'release' else 4
    if not re.search(r'(?m)^# pass '+str(expected)+r'$', result.stdout) or not re.search(r'(?m)^# fail 0$', result.stdout):
        raise ValueError('Required common/identity tests did not all run:\n'+result.stdout+result.stderr)
    # Detect changes while the subprocess ran without taking any writer lock.
    plugin_release.clean_checkout(root, commit)
    _tracked_inputs(root, commit)
    if args.stage == 'source':
        # Re-verify the source state itself: a stale artifact ignored during
        # the Node run (or planted while it ran) must not ship as "checked".
        _verify_clean_source(root, commit)
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
