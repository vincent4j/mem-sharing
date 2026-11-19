"""Run the bundled WorkBuddy installer without fetching source code."""
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import subprocess
import sys
import tempfile
from zipfile import ZipFile


def digest(data):
    return hashlib.sha256(data).hexdigest()


def git(directory, *args, stdin=None):
    return subprocess.run(
        ['git', '-C', str(directory), '-c', 'core.hooksPath=/dev/null',
         '-c', 'core.fsmonitor=false', *args],
        input=stdin, check=True, stdout=subprocess.PIPE,
        env=dict(os.environ, GIT_ALLOW_PROTOCOL='', GIT_CONFIG_NOSYSTEM='1',
                 GIT_CONFIG_GLOBAL=os.devnull),
    ).stdout.decode().strip()


def unpack(archive, prefix, target):
    for entry in archive.infolist():
        if not entry.filename.startswith(prefix):
            continue
        relative = PurePosixPath(entry.filename.removeprefix(prefix))
        if relative.is_absolute() or not relative.parts or '..' in relative.parts:
            raise ValueError('Unsafe bundled file path')
        destination = target.joinpath(*relative.parts)
        destination.parent.mkdir(parents=True, exist_ok=True)
        with destination.open('xb') as stream:
            stream.write(archive.read(entry))
        destination.chmod((entry.external_attr >> 16) & 0o777 or 0o644)


def materialize(target, populate):
    if target.is_symlink() or (target.exists() and not target.is_dir()):
        raise ValueError(f'Unexpected source path: {target}')
    if target.exists():
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.workbuddy-', dir=target.parent) as area:
        staged = Path(area) / 'source'
        staged.mkdir()
        populate(staged)
        try:
            staged.rename(target)
        except OSError:
            if not target.is_dir() or target.is_symlink():
                raise


def prepare_keeper(archive, target, identity):
    def populate(staged):
        git(staged, 'init', '--template=', '--initial-branch=main')
        (staged / '.git/shallow').write_text(identity['commit'] + '\n')
        git(staged, 'unpack-objects', '-q', stdin=archive.read('context-keeper.pack'))
        git(staged, 'remote', 'add', 'origin', identity['url'])
        git(staged, 'update-ref', 'refs/remotes/origin/main', identity['commit'])
        git(staged, 'reset', '--hard', identity['commit'])
    materialize(target, populate)
    if (not (target / '.git').is_dir() or (target / '.git').is_symlink()
            or git(target, 'rev-parse', '--show-toplevel') != str(target)
            or git(target, 'rev-parse', 'HEAD') != identity['commit']
            or git(target, 'rev-parse', 'refs/remotes/origin/main') != identity['commit']
            or git(target, 'remote', 'get-url', 'origin') != identity['url']
            or git(target, 'status', '--porcelain', '--untracked-files=all')):
        raise ValueError(f'Existing Context Keeper source differs from this bundle: {target}')


def run(args):
    home = Path(os.environ['HOME']).resolve()
    bundle = Path(__file__).resolve().parent
    packed = bundle / 'assets/runtime.zip'
    manifest = json.loads((bundle / 'manifest.json').read_text())
    expected = next(entry['sha256'] for entry in manifest['files'] if entry['path'] == 'assets/runtime.zip')
    if digest(packed.read_bytes()) != expected:
        raise ValueError('Bundled runtime hash mismatch')
    approval = json.loads(args.approval_file.read_text()) if args.approval_file else None
    base = home / '.local/share'
    with ZipFile(packed) as archive:
        product = json.loads(archive.read('product.json'))
        keeper = json.loads(archive.read('context-keeper.json'))
        root = base / 'mem-sharing-workbuddy' / expected / 'source'
        if root != root.resolve():
            raise ValueError('Bundled source path traverses a symbolic link')
        materialize(root, lambda target: unpack(archive, 'product/', target))
        for name, checksum in product['files'].items():
            path = root / name
            if path != path.resolve() or digest(path.read_bytes()) != checksum:
                raise ValueError(f'Bundled product source changed: {name}')

        if args.action == 'source':
            print(root)
            return 0

        command = [sys.executable, '-B']
        command.append(str(root / 'scripts/install.py'))
        if args.action == 'context-keeper':
            checkout = base / 'context-keeper/source'
            if checkout != checkout.resolve():
                raise ValueError('Context Keeper source path traverses a symbolic link')
            if approval and approval.get('source', {}).get('root') != str(checkout):
                raise ValueError('Approval does not refer to the bundled Context Keeper checkout')
            prepare_keeper(archive, checkout, keeper)
            command.extend(['--context-keeper', '--ck-preview-only', '--ck-source', str(checkout)])
            if args.operation_id:
                command.extend(['--operation-id', args.operation_id])
        elif not approval:
            source_file = root.parent / 'source.json'
            source_info = dict(product, root=str(root))
            with tempfile.NamedTemporaryFile(mode='w', dir=root.parent, delete=False) as stream:
                json.dump(source_info, stream)
                staged = Path(stream.name)
            staged.replace(source_file)
            command.extend(['--source-manifest', str(source_file)])
            for agent in args.agent:
                command.extend(['--agent', agent])
        elif approval.get('source', {}).get('root') != str(root):
            raise ValueError('Approval does not refer to the bundled product checkout')
        if approval:
            command.extend(['--approval-file', str(args.approval_file.resolve())])
    return subprocess.run(command, stdin=subprocess.DEVNULL,
                          env=dict(os.environ, GIT_ALLOW_PROTOCOL='')).returncode


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    actions = parser.add_subparsers(dest='action', required=True)
    install = actions.add_parser('install')
    install.add_argument('--agent', action='append', default=[])
    install.add_argument('--approval-file', type=Path)
    keeper = actions.add_parser('context-keeper')
    keeper.add_argument('--operation-id')
    keeper.add_argument('--approval-file', type=Path)
    actions.add_parser('source')
    args = parser.parse_args()
    try:
        return run(args)
    except (OSError, ValueError, KeyError, StopIteration, subprocess.SubprocessError) as exc:
        parser.exit(2, f'Offline WorkBuddy bundle: {exc}\n')


if __name__ == '__main__':
    raise SystemExit(main())
