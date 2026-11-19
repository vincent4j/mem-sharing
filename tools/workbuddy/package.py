"""Build memSharing's shallow WorkBuddy ZIP with an offline Context Keeper snapshot."""
import argparse
import io
import json
from pathlib import Path
import re
import subprocess
import tempfile
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

from offline import digest

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
PRODUCT_URL = 'https://github.com/vincent4j/mem-sharing.git'
KEEPER_URL = 'https://github.com/vincent4j/context-keeper.git'


def git(root, *args, data=None):
    return subprocess.run(
        ['git', '-C', str(root), '-c', 'core.hooksPath=/dev/null', *args],
        input=data, capture_output=True, check=True, timeout=120,
    ).stdout


def snapshot(root, commit):
    files = {}
    for entry in git(root, 'ls-tree', '-rz', commit).split(b'\0'):
        if not entry:
            continue
        meta, path = entry.split(b'\t')
        mode, kind, blob = meta.decode().split()
        name = path.decode()
        if name in {'SKILL.md', 'README.md', 'INSTALL.md', 'DESIGN.md', 'llms.txt'} or (
                name.startswith('docs/') and name.endswith('.md')) or name.startswith('scripts/'):
            if kind != 'blob' or mode not in ('100644', '100755'):
                raise ValueError(f'Unexpected tracked entry: {name}')
            files[name] = git(root, 'cat-file', 'blob', blob), int(mode, 8)
    return files


def zip_bytes(files):
    stream = io.BytesIO()
    with ZipFile(stream, 'w', ZIP_DEFLATED) as archive:
        for name, (data, mode) in sorted(files.items()):
            entry = ZipInfo(name, (2000, 1, 1, 0, 0, 0))
            entry.external_attr = mode << 16
            archive.writestr(entry, data, compress_type=ZIP_DEFLATED)
    return stream.getvalue()


def json_bytes(value):
    return (json.dumps(value, ensure_ascii=False, indent=2) + '\n').encode()


def build(version, output):
    if not re.fullmatch(r'(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)', version):
        raise ValueError('Provide a numeric release version')
    output = output.expanduser().resolve()
    if output.is_relative_to(ROOT):
        raise ValueError('Write the WorkBuddy ZIP outside the memSharing repository')
    commit = git(ROOT, 'rev-parse', 'HEAD').decode().strip()
    files = snapshot(ROOT, commit)
    market = json.loads((ROOT / 'manifest.json').read_bytes())
    market['version'] = version
    core_version = json.loads(files['scripts/core-version.json'][0])['version']
    product = {
        'url': PRODUCT_URL, 'commit': commit, 'version': core_version,
        'files': {name: digest(data) for name, (data, _) in files.items()},
    }
    with tempfile.TemporaryDirectory(prefix='workbuddy-keeper-') as temporary:
        checkout = Path(temporary)
        git(checkout, 'init', '--template=')
        git(checkout, 'fetch', '--depth=1', '--no-tags', KEEPER_URL, 'refs/heads/main')
        keeper_commit = git(checkout, 'rev-parse', 'FETCH_HEAD').decode().strip()
        keeper_version = json.loads(git(checkout, 'show', keeper_commit + ':manifest.json'))['version']
        pack = git(checkout, 'pack-objects', '--revs', '--stdout', data=(keeper_commit + '\n').encode())

    runtime = {f'product/{name}': payload for name, payload in files.items()}
    runtime.update({
        'product.json': (json_bytes(product), 0o100644),
        'context-keeper.json': (json_bytes({
            'url': KEEPER_URL, 'commit': keeper_commit, 'version': keeper_version,
        }), 0o100644),
        'context-keeper.pack': (pack, 0o100644),
    })
    icon = (ROOT / 'assets/icon.png').read_bytes()
    if (len(icon) > 500_000 or icon[:8] != b'\x89PNG\r\n\x1a\n'
            or icon[16:24] != b'\0\0\x02\0\0\0\x02\0'):
        raise ValueError('WorkBuddy icon must be a 512×512 PNG within 500 KB')
    stage = {
        'SKILL.md': ((HERE / 'SKILL.md').read_text().replace('@VERSION@', version).encode(), 0o100644),
        'offline.py': ((HERE / 'offline.py').read_bytes(), 0o100644),
        'assets/icon.png': (icon, 0o100644),
        'assets/runtime.zip': (zip_bytes(runtime), 0o100644),
    }
    market['files'] = [{'path': name, 'sha256': digest(data)} for name, (data, _) in sorted(stage.items())]
    stage['manifest.json'] = (json_bytes(market), 0o100644)
    artifact = zip_bytes(stage)
    if len(artifact) > 3_000_000:
        raise ValueError('WorkBuddy ZIP exceeds 3 MB')
    with ZipFile(io.BytesIO(artifact)) as archive:
        if archive.testzip() is not None or any(name.count('/') > 1 for name in archive.namelist()):
            raise ValueError('Invalid WorkBuddy upload ZIP')
        for entry in market['files']:
            if digest(archive.read(entry['path'])) != entry['sha256']:
                raise ValueError(f"Hash mismatch: {entry['path']}")
    with output.open('xb') as stream:
        stream.write(artifact)
    print(f'{output} ({len(artifact):,} bytes)')
    print(f'Context Keeper {keeper_version} from {keeper_commit}')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--version', required=True)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    try:
        build(args.version, args.output)
    except subprocess.CalledProcessError as exc:
        parser.exit(1, exc.stderr.decode(errors='replace') + '\n')
    except (OSError, ValueError) as exc:
        parser.exit(1, f'{exc}\n')
