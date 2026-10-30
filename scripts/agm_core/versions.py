"""Persistent, verified release inventory. Never the active-version authority.

Slots are complete releases, independent of operation backups. Creating a slot
never authorizes activation; V is committed separately and last by the caller.
"""
import json
import os
from pathlib import Path

from . import legacy_import as legacy, migrate, registry
from .transaction import read_snapshot

PRODUCT = 'agent-group-memory'


def root(runtime):
    return runtime.code.parent / (PRODUCT + '-versions')


def _chain(path, home):
    path = Path(path)
    if not path.is_relative_to(home):
        raise ValueError('Version path outside HOME')
    current = Path(home)
    for part in path.relative_to(home).parts:
        current /= part
        if current.is_symlink():
            raise ValueError('Version path symlink: ' + str(current))
        if current.exists() and current != path and not current.is_dir():
            raise ValueError('Version parent is not a directory')


def descriptor(runtime, source, files):
    identity = {k: source[k] for k in ('url', 'commit', 'tree_sha256')}
    release = {'schema_version': 1, 'product_id': PRODUCT,
               'versions': {'schema_version': 2, 'product_structure_version': 1,
                            'product_code_version': source['version']},
               'source': identity, 'files': files}
    marker = legacy.encoded({'product_id': PRODUCT, 'source': identity, 'files': files})
    slot = root(runtime) / source['version'] / source['tree_sha256']
    _chain(slot, runtime.home)
    result = {'slot': str(slot), 'release': release, 'marker_hex': marker.hex()}
    if slot.exists():
        verify(runtime, result)
    return result


def validate(runtime, item):
    registry._keys(item, 'slot release marker_hex', 'version slot')
    release = item['release']
    registry._keys(release, 'schema_version product_id versions source files', 'release')
    versions = release['versions']
    product = {'product_id': PRODUCT, 'installation_id': 'inventory-validation',
               'product_structure_version': versions['product_structure_version'],
               'product_code_version': versions['product_code_version'],
               'source': release['source'], 'installation_status': 'complete', 'last_operation_id': 'inventory-validation'}
    data = registry.empty_registry(); data['product'] = product
    registry.validate_registry(data)
    if release['schema_version'] != 1 or release['product_id'] != PRODUCT or versions != {
            'schema_version': 2, 'product_structure_version': 1,
            'product_code_version': product['product_code_version']}:
        raise ValueError('Unknown release versions')
    files = release['files']; seen = set()
    if not isinstance(files, list): raise ValueError('Invalid release files')
    for file in files:
        registry._keys(file, 'path sha256 mode', 'release file')
        rel = file['path']; p = Path(rel)
        if (not isinstance(rel, str) or str(p) != rel or p.is_absolute() or '..' in p.parts
                or not p.parts or p.parts[0] == '.git' or rel == '.agm-code-manifest.json' or rel in seen):
            raise ValueError('Unsafe/duplicate version file')
        registry._digest(file['sha256'])
        if type(file['mode']) is not int or file['mode'] < 0 or file['mode'] > 0o777:
            raise ValueError('Invalid release file mode')
        seen.add(rel)
    if not {'SKILL.md', 'scripts/agm.py', 'scripts/agm_core/__init__.py'} <= seen:
        raise ValueError('Incomplete release')
    if legacy.digest(legacy.encoded(files)) != release['source']['tree_sha256']:
        raise ValueError('Release tree mismatch')
    expected = root(runtime)/product['product_code_version']/release['source']['tree_sha256']
    if str(expected) != item['slot']: raise ValueError('Version slot scope mismatch')
    marker = legacy.encoded({'product_id': PRODUCT, 'source': release['source'], 'files': files})
    if item['marker_hex'] != marker.hex(): raise ValueError('Version marker mismatch')
    _chain(expected, runtime.home)
    return expected


def _files(item):
    result = {f['path']: (f['sha256'], f['mode'] & 0o555) for f in item['release']['files']}
    result['.agm-code-manifest.json'] = (legacy.digest(bytes.fromhex(item['marker_hex'])), 0o400)
    return result


def verify(runtime, item, *, location=None):
    slot = validate(runtime, item) if location is None else Path(location)
    _chain(slot, runtime.home)
    if not slot.is_dir(): raise ValueError('Missing version slot')
    expected = {'release.json': legacy.encoded(item['release']),
                'complete.json': legacy.encoded({'schema_version': 1, 'release_sha256': legacy.digest(legacy.encoded(item['release']))})}
    allowed = {str(slot), str(slot/'code')}
    for rel, (digest, mode) in _files(item).items():
        path = slot/'code'/rel; allowed.add(str(path))
        parent = path.parent
        while parent != slot:
            allowed.add(str(parent)); parent = parent.parent
        snap = read_snapshot(path)
        if snap.kind != 'file' or snap.fingerprint != digest or snap.mode != mode:
            raise ValueError('Version bytes/type/mode drift: ' + str(path))
    for rel, content in expected.items():
        path = slot/rel; allowed.add(str(path)); snap = read_snapshot(path)
        if snap.kind != 'file' or snap.data != content or snap.mode != 0o400:
            raise ValueError('Version receipt drift')
    for path in [slot, *slot.rglob('*')]:
        if path.is_symlink() or str(path) not in allowed:
            raise ValueError('Foreign node in version slot')
        if str(path) not in {str(slot/'code'/rel) for rel in _files(item)} | {str(slot/k) for k in expected} and not path.is_dir():
            raise ValueError('Version parent type conflict')
    return item


def ensure(runtime, item, source_root, op, *, mkdir, intent, hook=None):
    """Idempotent slot registration, before touching active C. Caller owns locks."""
    slot = validate(runtime, item)
    if slot.exists(): return verify(runtime, item)
    stage = slot.parent / ('.' + slot.name + '-' + op + '.tmp')
    _chain(stage, runtime.home)
    mkdir(stage/'code')
    payloads = [(rel, Path(source_root)/rel, digest, mode) for rel,(digest,mode) in _files(item).items()]
    for rel, source, digest, mode in payloads:
        content = bytes.fromhex(item['marker_hex']) if rel == '.agm-code-manifest.json' else source.read_bytes()
        if legacy.digest(content) != digest: raise ValueError('Version source drift: ' + rel)
        target = stage/'code'/rel; mkdir(target.parent)
        snap = read_snapshot(target)
        if snap.kind != 'absent':
            if snap.kind != 'file' or snap.fingerprint != digest or snap.mode != mode:
                raise ValueError('Partial inventory drift')
            continue
        intent('version_file', target)
        if read_snapshot(target).kind != 'absent': raise ValueError('Version target appeared')
        migrate._put(target, content, mode)
    for name, data in [('release.json', item['release']), ('complete.json', {
            'schema_version':1, 'release_sha256':legacy.digest(legacy.encoded(item['release']))})]:
        target = stage/name; content = legacy.encoded(data); snap = read_snapshot(target)
        if snap.kind != 'absent':
            if snap.kind != 'file' or snap.data != content or snap.mode != 0o400: raise ValueError('Partial receipt drift')
            continue
        intent('version_receipt', target); migrate._put(target, content, 0o400)
    verify(runtime, item, location=stage)
    intent('version_rename', slot)
    if hook: hook('before_version_rename', slot)
    verify(runtime, item, location=stage)
    if os.path.lexists(slot): raise ValueError('Version target appeared before rename')
    os.rename(stage, slot); migrate._sync_directory(slot.parent)
    if hook: hook('after_version_rename', slot)
    return verify(runtime, item)


def activate(runtime, item, op, journal, registry_sha256, *, mkdir, intent, phase="after"):
    """Durable history receipt. Called only after active V has been read back."""
    if phase not in ("before", "after"): raise ValueError("Unknown activation phase")
    migrate._op(op)
    verify(runtime, item)
    path = root(runtime)/'activations'/(op+'-'+phase+'.json'); _chain(path, runtime.home)
    saved=migrate._json(Path(journal))
    proof={k:saved[k] for k in ('plan','approval','final_registry_sha256')}
    if saved.get('product_id')!=PRODUCT or saved.get('operation_id')!=op:
        raise ValueError('Activation operation mismatch')
    if read_snapshot(runtime.registry).fingerprint!=proof['final_registry_sha256']:
        raise ValueError('Activation requires committed V')
    _proof(runtime,proof,op)
    body = {'schema_version':1,'operation_id':op,'release':item,'journal':str(journal),
            'registry_sha256':registry_sha256, 'phase':phase, 'proof':proof}
    content = legacy.encoded(body); mkdir(path.parent)
    snap = read_snapshot(path)
    if snap.kind != 'absent':
        if snap.kind != 'file' or snap.data != content or snap.mode != 0o400:
            raise ValueError('Activation receipt changed')
        return
    intent('activation_receipt', path)
    if read_snapshot(path).kind != 'absent': raise ValueError('Activation target appeared')
    migrate._put(path, content, 0o400)


def _proof(runtime, proof, op):
    """Self-contained installed-history proof, not a dependency on old backups."""
    registry._keys(proof,'plan approval final_registry_sha256','activation proof')
    plan=proof['plan'];command=plan.get('command') if isinstance(plan,dict) else None
    if command=='install-machine':
        from . import user_install
        bound=user_install._validate(plan,historical=True)
    elif command=='upgrade-machine':
        from . import upgrade
        bound=upgrade._validate(plan)
    else:raise ValueError('Unknown activation operation')
    migrate._approval(plan,proof['approval'])
    registry._digest(proof['final_registry_sha256'])
    if bound!=runtime or plan['operation_id']!=op:
        raise ValueError('Activation proof identity mismatch')
    if command=='upgrade-machine' and plan['final_registry_sha256']!=proof['final_registry_sha256']:
        raise ValueError('Activation proof commit mismatch')
    return plan


def installed_before(runtime, item):
    verify(runtime, item)
    directory = root(runtime)/'activations'; _chain(directory, runtime.home)
    if not directory.exists(): return False
    for path in sorted(directory.iterdir()):
        snap = read_snapshot(path)
        if snap.kind != 'file': raise ValueError('Invalid activation receipt type')
        receipt = migrate._json(path)
        registry._keys(receipt, 'schema_version operation_id release journal registry_sha256 phase proof', 'activation receipt')
        if (type(receipt['schema_version']) is not int or receipt['schema_version']!=1
                or receipt['phase'] not in ('before','after')):raise ValueError('Invalid activation schema/phase')
        registry._digest(receipt['registry_sha256']);migrate._op(receipt['operation_id'])
        if path.name!=receipt['operation_id']+'-'+receipt['phase']+'.json':raise ValueError('Activation filename mismatch')
        if receipt['release'] != item: continue
        journal = Path(receipt['journal'])
        if journal != runtime.home/('.agents-group-install-'+receipt['operation_id'])/'journal.json':
            raise ValueError('Activation journal scope conflict')
        _chain(journal, runtime.home)
        planned = _proof(runtime,receipt['proof'],receipt['operation_id'])
        phase = receipt['phase']
        digest = receipt['proof']['final_registry_sha256'] if phase == 'after' else planned.get('before_registry', {}).get('sha256')
        release = planned.get('inventory', planned.get('target_inventory')) if phase == 'after' else planned.get('before_inventory')
        if digest == receipt['registry_sha256'] and release == item:
            return True
    return False
