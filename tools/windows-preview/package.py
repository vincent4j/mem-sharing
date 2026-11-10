#!/usr/bin/env python3
"""Deterministic, independent Windows preview archive. No tags or installation.

The existing production/Paseo release chain and version are not changed.
Preview identity is the existing core_version plus a full source Git revision.
Checksums establish byte integrity, not publisher authenticity.
"""
import argparse
import ast
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import re
import stat
import subprocess
import zipfile

OFFICIAL = 'https://github.com/vincent4j/mem-sharing'
CORE = (
    'scripts/windows_preview.py', 'scripts/agm_core/__init__.py',
    'scripts/agm_core/entries.py', 'scripts/agm_core/transaction.py',
    'scripts/agm_core/windows_preview.py', 'scripts/agm_core/windows_native.py',
    'scripts/agm_core/platform_diagnostics.py', 'scripts/agm_core/paths.py',
)
MANIFEST = 'preview-manifest.json'
GUIDE_SOURCE = 'tools/windows-preview/INSTALL.md'
FORMAT = 'memsharing-windows-preview-package-1'


class PackageError(ValueError):
    pass


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def canonical(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + '\n').encode('utf-8')


def git(source, *args):
    return subprocess.run(['git', '-C', str(source), *args], capture_output=True,
                          check=True).stdout


def pinned_file(source, revision, name):
    row = git(source, 'ls-tree', revision, '--', name).decode().strip().split()
    if len(row) != 4 or row[0] not in ('100644', '100755') or row[1] != 'blob' or row[3] != name:
        raise PackageError('Pinned regular file missing: ' + name)
    raw = git(source, 'cat-file', 'blob', revision + ':' + name)
    path = source / name
    if path.is_symlink() or not path.is_file() or path.read_bytes() != raw:
        raise PackageError('Worktree differs from pinned bytes: ' + name)
    return raw


def manifest_for(source, revision):
    source = Path(source).resolve()
    if not re.fullmatch(r'[0-9a-f]{40}|[0-9a-f]{64}', revision):
        raise PackageError('Full source revision required')
    if git(source, 'rev-parse', 'HEAD').decode().strip() != revision:
        raise PackageError('HEAD must match source revision')
    if git(source, 'status', '--porcelain', '--untracked-files=all'):
        raise PackageError('Clean source checkout required')
    origin = git(source, 'config', '--get', 'remote.origin.url').decode().strip()
    if origin not in (OFFICIAL, OFFICIAL + '.git', 'git@github.com:vincent4j/mem-sharing.git'):
        raise PackageError('Official repository origin required; arbitrary URL not echoed')
    files = {n: pinned_file(source, revision, n) for n in CORE}
    tree = ast.parse(files['scripts/agm_core/windows_preview.py'])
    declared = next((ast.literal_eval(n.value) for n in tree.body if isinstance(n, ast.Assign)
                     and any(isinstance(t, ast.Name) and t.id == 'SOURCE_FILES' for t in n.targets)), None)
    if tuple(declared or ()) != CORE:
        raise PackageError('Core dependency closure changed; review package scope')
    version = json.loads(pinned_file(source, revision, 'scripts/core-version.json'))
    if set(version) != {'version'} or not re.fullmatch(r'\d+\.\d+\.\d+', version['version']):
        raise PackageError('Invalid pinned core version')
    files['INSTALL.md'] = pinned_file(source, revision, GUIDE_SOURCE)
    manifest = {'schema': FORMAT, 'channel': 'windows-preview', 'repository': OFFICIAL,
                'core_version': version['version'], 'preview_revision': revision,
                'entrypoint': 'scripts/windows_preview.py', 'clients': ['zcode', 'workbuddy'],
                'general_windows_support': False, 'upgrade_or_migration': False,
                'files': {n: {'size': len(raw), 'sha256': sha(raw)} for n, raw in sorted(files.items())}}
    return manifest, files


def build(source, revision, output):
    source, output = Path(source).resolve(), Path(output).absolute()
    if output == source or source in output.parents or not output.parent.is_dir():
        raise PackageError('Output must have an existing parent outside source checkout')
    manifest, files = manifest_for(source, revision)
    files[MANIFEST] = canonical(manifest)
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w', compression=zipfile.ZIP_STORED) as archive:
        for name, raw in sorted(files.items()):
            entry = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            entry.create_system = 3
            entry.external_attr = (stat.S_IFREG | 0o644) << 16
            archive.writestr(entry, raw)
    data = buffer.getvalue()
    with output.open('xb') as f:
        f.write(data)
        f.flush()
        __import__('os').fsync(f.fileno())
    result = verify(output, expected_sha256=sha(data), expected_revision=revision)
    return dict(result, archive=str(output))


def verify(archive_path, *, expected_sha256=None, expected_revision=None):
    path = Path(archive_path)
    if path.is_symlink() or not path.is_file():
        raise PackageError('Regular archive required')
    raw = path.read_bytes()
    if len(raw) > 2 * 1024 * 1024 or (expected_sha256 is not None and sha(raw) != expected_sha256):
        raise PackageError('Archive checksum/size mismatch')
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        items = archive.infolist()
        names = [i.filename for i in items]
        expected_names = set(CORE) | {'INSTALL.md', MANIFEST}
        if len(names) != len(expected_names) or set(names) != expected_names:
            raise PackageError('Archive closure has duplicates, unsafe paths or unexpected members')
        for item in items:
            p = PurePosixPath(item.filename)
            mode = item.external_attr >> 16
            if (p.is_absolute() or '..' in p.parts or '\\' in item.filename
                    or not stat.S_ISREG(mode) or item.flag_bits & 1
                    or item.file_size > 1024 * 1024 or item.compress_type != zipfile.ZIP_STORED):
                raise PackageError('Nonregular/unsafe archive member')
        manifest = json.loads(archive.read(MANIFEST))
        if (manifest.get('schema') != FORMAT or manifest.get('channel') != 'windows-preview'
                or manifest.get('repository') != OFFICIAL
                or manifest.get('entrypoint') != 'scripts/windows_preview.py'
                or manifest.get('clients') != ['zcode', 'workbuddy']
                or manifest.get('general_windows_support') is not False
                or manifest.get('upgrade_or_migration') is not False
                or not re.fullmatch(r'\d+\.\d+\.\d+', str(manifest.get('core_version', '')))
                or not re.fullmatch(r'[0-9a-f]{40}|[0-9a-f]{64}', str(manifest.get('preview_revision', '')))
                or (expected_revision is not None and manifest['preview_revision'] != expected_revision)
                or set(manifest['files']) != expected_names - {MANIFEST}):
            raise PackageError('Invalid preview identity/scope')
        for name, metadata in manifest['files'].items():
            content = archive.read(name)
            if metadata != {'size': len(content), 'sha256': sha(content)}:
                raise PackageError('Payload checksum mismatch: ' + name)
    return {'status': 'verified', 'schema': FORMAT, 'core_version': manifest['core_version'],
            'preview_revision': manifest['preview_revision'], 'sha256': sha(raw),
            'size': len(raw), 'members': len(names), 'general_windows_support': False,
            'published': False, 'runtime_acceptance': 'separate'}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='action', required=True)
    p = sub.add_parser('build')
    p.add_argument('--source', required=True)
    p.add_argument('--commit', required=True)
    p.add_argument('--output', required=True)
    p = sub.add_parser('verify')
    p.add_argument('--archive', required=True)
    p.add_argument('--sha256')
    p.add_argument('--commit')
    args = parser.parse_args(argv)
    try:
        result = (build(args.source, args.commit, args.output) if args.action == 'build'
                  else verify(args.archive, expected_sha256=args.sha256, expected_revision=args.commit))
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        return 0
    except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError, zipfile.BadZipFile) as exc:
        print(json.dumps({'status': 'failed', 'message': str(exc)}, ensure_ascii=False))
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
