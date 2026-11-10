#!/usr/bin/env python3
"""Prepare Paseo's independent preview payload from a verified standalone ZIP.

Writes only to a new external output directory. No checkout edits, installation,
version selection, production payload generation, Git commits or publishing.
"""
import argparse
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import re
import zipfile

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('preview_package', HERE / 'package.py')
package = importlib.util.module_from_spec(spec)
spec.loader.exec_module(package)


def prepare(archive, sha256, revision, output):
    if not re.fullmatch('[a-f0-9]{64}', sha256):
        raise ValueError('Independent archive SHA256 required')
    # Bind all subsequent reads to these bytes, rather than reopening an archive
    # after verification. The existing verifier checks closure and file hashes.
    archive = Path(archive)
    if archive.is_symlink() or not archive.is_file():
        raise ValueError('Regular standalone archive required')
    raw = archive.read_bytes()
    if hashlib.sha256(raw).hexdigest() != sha256:
        raise ValueError('Archive checksum mismatch')
    report = package.verify(archive, expected_sha256=sha256, expected_revision=revision)
    # Verify the captured bytes too: replacing the path between reads cannot
    # substitute an unrelated ZIP with the same unverified manifest.
    with zipfile.ZipFile(io.BytesIO(raw)) as zipped:
        files = {name: zipped.read(name) for name in zipped.namelist()}
    manifest = json.loads(files[package.MANIFEST])
    if manifest['preview_revision'] != revision:
        raise ValueError('Revision mismatch')
    for name, meta in manifest['files'].items():
        content = files[name]
        if meta != {'size': len(content), 'sha256': package.sha(content)}:
            raise ValueError('Captured file mismatch')
    output = Path(output).absolute()
    root = HERE.parents[1]
    if output == root or root in output.resolve().parents or not output.parent.is_dir():
        raise ValueError('New output must be outside the checkout')
    output.mkdir(mode=0o700)
    payload = output / 'plugins/paseo/windows-preview'
    for name, content in files.items():
        target = payload / name
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open('xb') as stream:
            stream.write(content)
    digest = package.sha(files[package.MANIFEST])
    identity = output / 'plugins/paseo/server/shared/windows-preview-identity.ts'
    identity.parent.mkdir(parents=True, exist_ok=True)
    identity.write_text('// GENERATED from the independently verified Windows preview archive.\n'
                        'export const WINDOWS_PREVIEW_MANIFEST_SHA256 = "' + digest + '";\n')
    return dict(report, output=str(output), manifest_sha256=digest, plugin_installed=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive', required=True)
    parser.add_argument('--sha256', required=True)
    parser.add_argument('--commit', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    try:
        print(json.dumps(prepare(args.archive, args.sha256, args.commit, args.output), sort_keys=True))
        return 0
    except (OSError, ValueError, KeyError, TypeError, zipfile.BadZipFile) as exc:
        print(json.dumps({'status': 'failed', 'message': str(exc)}))
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
