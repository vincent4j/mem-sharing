"""Opt-in, evidence-bound reconciliation of a legacy Claude import.

Only an independently changed CK span may differ from a proven historical
whole-file baseline. Ordinary policy migration retains its strict drift gate.
No history is rewritten and no ownership or deletion rights are acquired.
"""
import argparse
import copy
import json
import os
from pathlib import Path
import re
import stat

from . import entries, layout, migrate, policy_migration, registry, user_entries, public_layout, paths
from . import uninstall_recovery as recovery, user_install, legacy_import as legacy
from .transaction import Change, Snapshot, Transaction, write_lock

COMMAND = 'reconcile-legacy-import'
CK = {'start': '<!-- context-keeper:start -->', 'end': '<!-- context-keeper:end -->'}
SHA = re.compile(r'[0-9a-f]{64}')
META = set('existed kind mode link_target fingerprint backup'.split())
TOP = set('schema_version operation status registry_path created_directories entries error'.split())
ROW = set('path before after attempted restoration'.split())


# Exported from Git ea553738f37a5cc5befb34bf241d12da33f07b21; public seals are not a trust root.
HISTORICAL_TOOLS = (
    ('__init__.py', 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855'),
    ('batch_enable.py', '78369ad55edf8d7f3cec42bb8dc707cd8602dbff1e7a2b09be4587f4b7b4f099'),
    ('check.py', '8b084c0e2bb55ce0eb348107acd5ee90ea193a3f208d94dcdd62c42937393aa3'),
    ('ck_install.py', 'e845c2cc4b7ebfd9eec8773970aafec9b964841656113ccebabb5e4cc5abf8be'),
    ('detect.py', '7a3272dfa201350ec68b0dc0f40daff0890122b99fcec183bcc2a3bf4080ed06'),
    ('enable.py', '77994bb45901663d7c71671e5b78ef14652fb6cdcbb2e14f30e2c809f56fd23b'),
    ('entries.py', '36fded9f7712477e7323b4e8630349cc6cf10711c57be9fda2b80b0f115026bd'),
    ('layout.py', '254f28dca67b0277480eb2001ec98f52102989cdaa4ee97a0d7e2540333ecb44'),
    ('legacy_import.py', 'cf77248dbe8c2fd844a29a8c95c99dfaa772e31408d32b68f0ae9ff3adaad73c'),
    ('migrate.py', 'e8d6685897bf47603666ef31fea0d1fd0593a0845362efc8b32722aa0af7c46b'),
    ('paths.py', '6217d83f286c2fc87cad493ecd1942ffd1515f46058d0f2036fce21c3a88b4cf'),
    ('project.py', 'cd532670de9931f8948743814107db78f4eb7e8dc368c129b4a37a4b338bf705'),
    ('public_layout.py', 'b1ab0123bcea50884a37bb6890e0e23938c73a470577d65ae654b1936016d96f'),
    ('registry.py', 'ca98ab798e43dca8be4cf24efb8e11ff6f1ce5c39b41da81fcdf35fb8cd1119c'),
    ('remove.py', 'f67fa93aa24dfbbca3183714a6facbf89a479e79eacd6271a82e0a3ba3867283'),
    ('transaction.py', '32b05568b060138429a408381ec5b1a67bb9bc187052569290f828b45dd1a06e'),
    ('upgrade.py', '34f628737538aeaa6b9ba2883f1a272e23e161128a0494332b8e361a0a335973'),
    ('user_entries.py', '48e5677857b2aaece1cf2e711db4bb90ec2b9d6447b3baf682b76959c422346f'),
    ('user_install.py', '173f2a2ae89f59e3ccc0cc118edf421cac957aca9b6f7adfd58a064a03ee37b5'),
    ('user_rules_organize.py', 'd3807d8a3d728f4b91463fdebb42ed81fb3af2b3772cd6fab1565633fe94fad0'),
    ('versions.py', '74b611283e393450dd77a10afeab76b415144d0ba49d296b4e0a92a637bcbe7b'),
)
HISTORICAL_LAUNCHER_SHA256 = 'cba8dae584c7dd1db47ff7fcfe5144db4261589601757044282efee32314daf8'


class ReconcileError(ValueError):
    code = 'legacy_reconcile_conflict'


def _fail(message):
    raise ReconcileError(message)


def _keys(value, keys):
    if not isinstance(value, dict) or set(value) != keys:
        _fail('Unknown historical evidence schema')


def _path(value, home=None):
    if not isinstance(value, str):
        _fail('Invalid evidence path')
    p = Path(value)
    if not p.is_absolute() or str(p) != os.path.normpath(value):
        _fail('Expected a normalized absolute path')
    if home is not None and (p == home or not p.is_relative_to(home)):
        _fail('Historical evidence belongs to another HOME')
    return p


def _real(path, home=None, directory=False):
    path = _path(str(path), home)
    # Check the entire existing chain without reading through any symlink.
    for node in [*reversed(path.parents), path]:
        try:
            st = node.lstat()
        except FileNotFoundError:
            _fail('Historical evidence is missing')
        if stat.S_ISLNK(st.st_mode):
            _fail('Evidence symlink refused')
        if node != path and not stat.S_ISDIR(st.st_mode):
            _fail('Evidence parent is not a directory')
    if directory and not stat.S_ISDIR(st.st_mode):
        _fail('Evidence directory required')
    return path


def _file(path, *, home=None, mode=None):
    path = _real(path, home)
    if not stat.S_ISREG(path.lstat().st_mode):
        _fail('Evidence must be a regular file')
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        st = os.fstat(fd)
        if not stat.S_ISREG(st.st_mode) or (mode is not None and stat.S_IMODE(st.st_mode) != mode):
            _fail('Evidence must be a regular file with producer mode')
        with os.fdopen(fd, 'rb', closefd=False) as stream:
            raw = stream.read()
        current = path.lstat()
        stable = lambda s: (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_mode)
        if stable(st) != stable(current) or stable(st) != stable(os.fstat(fd)):
            _fail('Evidence changed while being read')
    finally:
        os.close(fd)
    return raw, {'sha256': entries.sha256(raw), 'mode': stat.S_IMODE(st.st_mode),
                 'device': st.st_dev, 'inode': st.st_ino, 'mtime_ns': st.st_mtime_ns}


def _json(raw):
    value = json.loads(raw, object_pairs_hook=registry._no_duplicates)
    if not isinstance(value, dict):
        _fail('JSON object required')
    return value


def _capture(path, observations, runtime, *, mode=None):
    raw, fact = _file(path, home=runtime.home, mode=mode)
    observations[str(path)] = fact
    return raw


def _metadata(value, *, before, index):
    _keys(value, META)
    if value['kind'] == 'absent':
        if (value['existed'] is not False or value != dict(existed=False, kind='absent', mode=None,
                          link_target=None, fingerprint=None, backup=None) or not before):
            _fail('Invalid absent historical input')
    elif value['kind'] == 'file':
        if (value['existed'] is not True or type(value['mode']) is not int
                or not 0 <= value['mode'] <= 0o7777 or value['link_target'] is not None
                or not isinstance(value['fingerprint'], str) or not SHA.fullmatch(value['fingerprint'])
                or value['backup'] != (str(index)+'.before' if before else None)):
            _fail('Invalid historical file fingerprint/mode/backup')
    else:
        _fail('Historical producer requires regular file changes')


def _candidates(runtime):
    _real(runtime.backups, runtime.home, directory=True)
    found = []
    for directory in sorted(runtime.backups.iterdir()):
        if directory.is_symlink():
            _fail('Backup directory symlink refused')
        if not directory.is_dir():
            continue
        direct = directory/'manifest.json'
        nested = directory/'tx'
        if os.path.lexists(direct):
            found.append(direct)
        if os.path.lexists(nested):
            _real(nested, runtime.home, directory=True)
            if os.path.lexists(nested/'manifest.json'):
                found.append(nested/'manifest.json')
    return found


def _directory(path, runtime):
    _real(path, runtime.home, directory=True)
    st = path.lstat()
    return {'device': st.st_dev, 'inode': st.st_ino, 'mode': stat.S_IMODE(st.st_mode),
            'names': sorted(p.name for p in path.iterdir())}


def _candidate_state(runtime, own=None):
    root = _directory(runtime.backups, runtime)
    if own is not None and own.directory.exists():
        if (own.directory.parent != runtime.backups
                or _json(_file(own.manifest_path, home=runtime.home, mode=0o600)[0]) != own.manifest
                or own.manifest['operation'] != COMMAND
                or own.manifest['registry_path'] != str(runtime.registry)):
            _fail('Unknown executing Transaction metadata')
        own_names = {'manifest.json'} | {r['before']['backup'] for r in own.manifest['entries']
                                          if r['before']['backup'] is not None}
        if (_directory(own.directory, runtime)['names'] != sorted(own_names)
                or stat.S_IMODE(own.directory.lstat().st_mode) != 0o700):
            _fail('Unknown executing Transaction closure')
        for row in own.manifest['entries']:
            backup = row['before']['backup']
            if backup is not None and entries.sha256(_file(own.directory/backup, home=runtime.home, mode=0o600)[0]) != row['before']['fingerprint']:
                _fail('Executing Transaction backup differs')
        root['names'].remove(own.directory.name)
    state = {'root': root, 'containers': {}, 'manifests': {}}
    for name in root['names']:
        container = runtime.backups/name
        if container.is_symlink():
            _fail('Backup directory symlink refused')
        if not container.is_dir():
            continue
        state['containers'][str(container)] = _directory(container, runtime)
        for candidate in (container/'manifest.json', container/'tx/manifest.json'):
            if os.path.lexists(candidate.parent) and candidate.parent != container:
                state['containers'][str(candidate.parent)] = _directory(candidate.parent, runtime)
            if os.path.lexists(candidate):
                state['manifests'][str(candidate)] = _file(candidate, home=runtime.home, mode=0o600)[1]
    return state


def _required_targets(runtime, plan, before, snapshots, users, agents, public):
    """Reverse the frozen producer's output decisions, never trust targets.

    This route supports the proven old-index conversion. Unchanged registered
    native entries require a whole-file canonical-new-template observation;
    richer no-op histories without persisted bytes cannot establish that branch.
    """
    required = []
    objects = list(before['machine']['objects'].values()) + list(before['shared_objects'].values())
    for agent, name in zip(agents, users):
        observed = plan['observations'][name]
        if agent == 'claude':
            imports = [o for o in objects if o['path'] == name and o['marker'] is None and agent in o['agents']]
            raw = snapshots.get(name)
            if (not imports or raw is None or observed['kind'] != 'file'
                    or any(o['kind'] != 'import' or o['fingerprint']['value'] != entries.sha256(raw) for o in imports)
                    or entries.managed_span(raw, **user_entries.CLAUDE_FALLBACK_MARKER) is not None
                    or any(o['path'] == name and o['marker'] == user_entries.CLAUDE_FALLBACK_MARKER for o in objects)):
                _fail('Historical Claude append branch cannot be proven')
            required.append(('claude_fallback', name, agent))
            continue
        occupants = [o for o in objects if o['path'] == name and o['marker'] == user_entries.BASE_MARKER and agent in o['agents']]
        if not occupants:
            # _entry_target returns [] for an unregistered reader, without
            # adopting or writing its private file. No current scene is read.
            continue
        if (len(occupants) != 1 or occupants[0]['kind'] not in ('block', 'user_convention')
                or observed['kind'] != 'file'):
            _fail('Historical native entry branch cannot be proven')
        fingerprint = occupants[0]['fingerprint']['value']
        new_hash = entries.sha256(policy_migration.legacy(agent, runtime))
        if agent in ('codex', 'workbuddy') and fingerprint == entries.sha256(policy_migration.legacy('old_'+agent, runtime)):
            required.append(('managed_block', name, agent))
        elif fingerprint == new_hash and observed['fingerprint'] == new_hash:
            pass  # Known whole-file new block: proven producer no-op.
        else:
            _fail('Unsupported historical native no-op/custom branch')
    topic = plan['observations'][public['topic']]
    if topic['kind'] == 'absent' or topic.get('fingerprint') == entries.sha256(policy_migration.legacy('old_topic', runtime)):
        required.append(('guide_topic', public['topic'], None))
    elif topic.get('fingerprint') != entries.sha256(policy_migration.legacy('topic', runtime)):
        _fail('Historical topic branch cannot be proven')
    raw_index = snapshots.get(public['index'])
    if raw_index is None or not raw_index.startswith(public_layout._INDEX_PREFIX+policy_migration.legacy('old_contract', runtime)):
        _fail('Historical old-index conversion evidence required')
    required.append(('public_index', public['index'], None))
    actual = [(t.get('kind'), t.get('path'), t.get('agent')) for t in plan['targets'] if isinstance(t, dict)]
    if len(actual) != len(plan['targets']) or actual != required:
        _fail('Historical required producer outputs differ')


def _producer(runtime, manifest, doc, manifest_raw, snapshots, observations, directories):
    # Only the historical public-layout producer persists enough evidence to
    # prove its complete after registry. Never execute its archived Python.
    container = manifest.parent.parent
    journal_path = container/'journal.json'
    journal = _json(_capture(journal_path, observations, runtime, mode=0o600))
    _keys(journal, set(public_layout.JOURNAL_KEYS.split()))
    plan = journal['plan']
    _keys(plan, set(public_layout.PLAN_KEYS.split()))
    sealed = dict(plan); digest = sealed.pop('plan_sha256')
    op = container.name[len('migration-'):]
    if (type(journal['schema_version']) is not int or journal['schema_version'] != 1
            or journal['product_id'] != 'mem-sharing' or journal['operation_id'] != op
            or journal['status'] != 'committed' or journal['phase'] != 'finish'
            or journal['intent'] is not None or journal['manifest'] != str(manifest)
            or journal['manifest_sha256'] != entries.sha256(manifest_raw)
            or type(plan['schema_version']) is not int or plan['schema_version'] != 1
            or plan['command'] != 'migrate-public-layout' or plan['operation_id'] != op
            or entries.sha256(legacy.encoded(sealed)) != digest
            or plan['layout'] != runtime.describe() or plan['backup_scope'] != str(container)
            or plan['journal'] != str(journal_path) or plan['manifest_path'] != str(manifest)
            or plan['guard'] != str(runtime.home/'.mem-sharing-upgrade.json')):
        _fail('Historical producer journal identity/status/plan differs')
    migrate._approval(plan, journal['approval'])
    table_raw = bytes.fromhex(plan['agents_table_hex'])
    # ea553738 historical producer bytes; never alias evolving release gates.
    contract = {
        'scripts/agents.json': '5aff7ec53cfddea2dca86e844a85903411c017488dd66f5f8ea7cb3e2a07f038',
        'scripts/agm_core/user_entries.py': '48e5677857b2aaece1cf2e711db4bb90ec2b9d6447b3baf682b76959c422346f',
        'scripts/agm_core/public_layout.py': 'b1ab0123bcea50884a37bb6890e0e23938c73a470577d65ae654b1936016d96f'}
    expected_handler = {'type': 'public-memory-layout-v1',
        'module_sha256': contract['scripts/agm_core/public_layout.py'],
        'user_entries_sha256': contract['scripts/agm_core/user_entries.py'],
        'memory_index': str(runtime.root/'memories/MEMORY.md')}
    if entries.sha256(table_raw) != contract['scripts/agents.json'] or plan['handler'] != expected_handler:
        _fail('Unsupported frozen historical producer contract')
    expected_tools = [dict(path=name, sha256=digest, mode=0o644) for name, digest in HISTORICAL_TOOLS]
    if plan['tools'] != expected_tools:
        _fail('Historical toolkit differs from frozen complete producer')
    if plan['launcher_sha256'] != HISTORICAL_LAUNCHER_SHA256:
        _fail('Unknown historical recovery launcher')
    tools = container/'tools/agm_core'
    names = set()
    for tool in plan['tools']:
        _keys(tool, {'path', 'sha256', 'mode'})
        name = tool['path']
        if (not isinstance(name, str) or Path(name).name != name or not name.endswith('.py')
                or name in names or type(tool['mode']) is not int or not 0 <= tool['mode'] <= 0o777):
            _fail('Invalid historical toolkit scope')
        names.add(name)
        if entries.sha256(_capture(tools/name, observations, runtime, mode=0o600)) != tool['sha256']:
            _fail('Historical toolkit fingerprint differs')
    if (set(_directory(tools, runtime)['names']) != names
            or not {'public_layout.py', 'user_entries.py'} <= names
            or next(t['sha256'] for t in plan['tools'] if t['path']=='public_layout.py') != expected_handler['module_sha256']
            or next(t['sha256'] for t in plan['tools'] if t['path']=='user_entries.py') != expected_handler['user_entries_sha256']
            or entries.sha256(_capture(container/'recover.py', observations, runtime, mode=0o600)) != plan['launcher_sha256']):
        _fail('Historical producer toolkit closure differs')
    for folder, names, modes in ((tools, {n for n, _ in HISTORICAL_TOOLS}, {0o700}),
                                 (tools.parent, {'agm_core'}, {0o700, 0o755}),
                                 (container, {'tools', 'tx', 'journal.json', 'recover.py'}, {0o700})):
        fact = _directory(folder, runtime)
        # pathlib creates the intermediate tools/ with default mode: the
        # original producer uses 022 or private 077 umask, not chmod(0700).
        if fact['mode'] not in modes or set(fact['names']) != names:
            _fail('Historical producer archive path/mode closure differs')
    directories[str(tools)] = _directory(tools, runtime)
    directories[str(tools.parent)] = _directory(tools.parent, runtime)
    config = paths.select_platform(_json(table_raw), paths.current_platform())
    agents = ('codex', 'claude', 'workbuddy', 'dsh', 'zcode')
    users = [paths.expand_path(config[a]['user_entry'], home=str(runtime.home)) for a in agents]
    allowed = list(dict.fromkeys(users))
    public = {'index': str(runtime.root/public_layout.INDEX_REL),
              'topic': str(runtime.root/public_layout.TOPIC_REL)}
    if (plan['user_paths'] != users or plan['allowed_user_paths'] != allowed
            or plan['public'] != public or set(plan['observations']) != set(users+[str(runtime.registry),*public.values()])
            or plan['noop'] is not False):
        _fail('Historical producer path scope differs')
    before_raw, after_raw = bytes.fromhex(plan['v1_registry_hex']), bytes.fromhex(plan['v2_registry_hex'])
    before, after = _json(before_raw), _json(after_raw)
    for ledger in (before, after):
        registry.require_installed(registry.validate_registry(ledger, allowed_user_paths=allowed,
                                                            _pending_manifest=str(manifest)))
    if (before_raw != snapshots[str(runtime.registry)]
            or entries.sha256(before_raw) != plan['v1_registry_sha256']
            or entries.sha256(after_raw) != plan['final_registry_sha256']
            or plan['product'] != {'installed_version': before['product']['product_code_version'],
                'target_version': '0.1.3', 'identity': before['product']}
            or before['product'] != after['product']
            or doc['entries'][-1]['before']['mode'] != 0o600
            or doc['entries'][-1]['after']['mode'] != 0o600):
        _fail('Historical before/after registry identity differs')
    for observed in plan['observations'].values():
        if not isinstance(observed, dict):
            _fail('Invalid historical observation schema')
        if observed.get('kind') == 'absent':
            _keys(observed, {'kind'})
        else:
            _keys(observed, {'kind', 'fingerprint', 'mode'})
            if (observed['kind'] != 'file' or type(observed['mode']) is not int
                    or not 0 <= observed['mode'] <= 0o7777
                    or not isinstance(observed['fingerprint'], str)
                    or not SHA.fullmatch(observed['fingerprint'])):
                _fail('Invalid historical observation')
    # This loader uses only approved metadata for attempted historical outputs;
    # it does not inspect/replay the old HOME scene or current product version.
    _required_targets(runtime, plan, before, snapshots, users, agents, public)
    public_layout._manifest_bounds(plan, doc)
    updated = copy.deepcopy(before)
    targets = plan['targets']
    if not isinstance(targets, list) or not targets:
        _fail('Historical producer targets missing')
    expected_order = []
    ranks = []
    for target in targets:
        kind = target.get('kind')
        _keys(target, set('kind path before after outside_fingerprint'.split()) |
              ({'agent'} if kind in ('claude_fallback', 'managed_block') else set()))
        name = target['path']; expected_order.append(name)
        if name not in snapshots or target['before'] == target['after']:
            _fail('Historical active output lacks proven before bytes')
        raw = snapshots[name]
        if raw is None and kind != 'guide_topic':
            _fail('Historical target requires existing input')
        if kind == 'claude_fallback':
            if target['agent'] != 'claude' or name != users[1]:
                _fail('Historical Claude target outside scope')
            block = policy_migration.legacy('claude', runtime)
            if entries.managed_span(raw, **user_entries.CLAUDE_FALLBACK_MARKER) is not None:
                _fail('Historical append already contains fallback')
            final = raw + (b'' if not raw or raw.endswith(b'\n') else b'\n') + block
            if target['outside_fingerprint'] != entries.sha256(raw):
                _fail('Historical Claude outside bytes differ')
            found = False
            for store in (updated['machine']['objects'], updated['shared_objects']):
                for obj in store.values():
                    if obj['path'] == name and obj['kind'] == 'import':
                        if obj['agents'] != ['claude'] or obj['fingerprint']['value'] != entries.sha256(raw):
                            _fail('Historical import registry differs from input')
                        obj['fingerprint']['value'] = entries.sha256(final); found = True
            if not found:
                _fail('Historical Claude import was not registered')
            oid = name+'#claude-fallback'
            if oid in updated['machine']['objects']:
                _fail('Historical fallback object already registered')
            updated['machine']['objects'][oid] = dict(kind='block', path=name, scope='machine', agents=['claude'],
                ownership='created', marker=user_entries.CLAUDE_FALLBACK_MARKER,
                fingerprint=dict(algorithm='sha256', basis='block_bytes', value=entries.sha256(block)),
                original_existed=False, link_target=None, backup_manifest=str(manifest), consumers=[])
        elif kind == 'managed_block':
            agent = target['agent']
            if agent not in ('codex', 'workbuddy') or name != users[agents.index(agent)]:
                _fail('Unsupported historical block target')
            marker = user_entries.BASE_MARKER
            old = policy_migration.legacy('old_'+agent, runtime)
            block = policy_migration.legacy(agent, runtime)
            span = entries.managed_span(raw, **marker)
            if span is None or raw[span[0]:span[1]] != old or target['outside_fingerprint'] != entries.sha256(raw[:span[0]]+raw[span[1]:]):
                _fail('Historical managed block input differs')
            final = entries.render_block(raw, block, **marker, expected_fingerprint=entries.sha256(old))
            matches = [o for store in (updated['machine']['objects'], updated['shared_objects']) for o in store.values()
                       if o['path'] == name and o['marker'] == marker and agent in o['agents']]
            if len(matches) != 1 or matches[0]['fingerprint']['value'] != entries.sha256(old):
                _fail('Historical managed block registry differs')
            matches[0]['fingerprint']['value'] = entries.sha256(block)
        elif kind == 'guide_topic':
            if name != public['topic'] or raw not in (None, policy_migration.legacy('old_topic', runtime)) or target['outside_fingerprint'] is not None:
                _fail('Historical topic output outside contract')
            final = policy_migration.legacy('topic', runtime)
        elif kind == 'public_index':
            prefix = public_layout._INDEX_PREFIX
            head = policy_migration.legacy('old_contract', runtime)
            if name != public['index'] or not raw.startswith(prefix+head):
                _fail('Historical public index outside contract')
            tail = raw[len(prefix)+len(head):]
            if target['outside_fingerprint'] != entries.sha256(tail):
                _fail('Historical public index outside bytes differ')
            tail = tail.replace(public_layout._OLD_TOPIC_DIR_LINE, b'', 1)
            if b'](topics/'+ '使用约定.md'.encode()+b')' not in tail:
                tail += (b'' if not tail or tail.endswith(b'\n') else b'\n') + public_layout._USAGE_TOPIC_LINE
            final = prefix+policy_migration.legacy('contract', runtime)+b'\n'+tail
        else:
            _fail('Unknown historical producer output')
        ranks.append(users.index(name) if name in users else len(users)+(0 if name == public['topic'] else 1))
        if target['after'] != dict(kind='file', fingerprint=entries.sha256(final), mode=target['before'].get('mode', 0o600)):
            _fail('Historical output after bytes/mode are inconsistent')
    if (not isinstance(plan['directories'], list) or plan['directories'] != sorted(set(plan['directories']))
            or any(not any(_path(d, runtime.home) in Path(t['path']).parents for t in targets)
                   for d in plan['directories'])):
        _fail('Historical producer directory scope differs')
    if (ranks != sorted(set(ranks)) or plan['order'] != expected_order+[str(runtime.registry)]
            or len(set(expected_order)) != len(expected_order)
            or updated != after
            or registry.serialize_registry(updated, allowed_user_paths=allowed, _pending_manifest=str(manifest)) != after_raw):
        _fail('Historical producer registry transition/scope differs')
    directories[str(container)] = _directory(container, runtime)


def _history(runtime, path, registered, old_block, observations, directories, current_mode):
    baselines, evidence = [], []
    for manifest in _candidates(runtime):
        raw, manifest_fact = _file(manifest, home=runtime.home, mode=0o600)
        doc = _json(raw)
        rows = doc.get('entries')
        if not isinstance(rows, list):
            continue  # Another, non-Transaction backup format is not a trust source.
        matches = [r for r in rows if isinstance(r, dict) and r.get('path') == str(path)
                   and isinstance(r.get('after'), dict) and r['after'].get('fingerprint') == registered]
        if not matches:
            continue
        _keys(doc, TOP)
        if (type(doc['schema_version']) is not int or doc['schema_version'] != 1
                or doc['status'] != 'committed' or doc['error'] is not None
                or doc['registry_path'] != str(runtime.registry)):
            _fail('Historical Transaction is not committed for this HOME')
        if doc['operation'] == 'migrate-public-layout':
            if (manifest.parent.name != 'tx' or manifest.parent.parent.parent != runtime.backups
                    or not manifest.parent.parent.name.startswith('migration-')):
                _fail('Unknown public-layout evidence location')
            migrate._op(manifest.parent.parent.name[len('migration-'):])
        else:
            _fail('Unsupported historical Transaction producer')
        if (stat.S_IMODE(manifest.parent.stat().st_mode) != 0o700
                or not isinstance(doc['created_directories'], list)):
            _fail('Invalid historical Transaction directory')
        for name in doc['created_directories']:
            _path(name, runtime.home)  # Historical targets need not still exist.
        seen, expected_files, snapshots = set(), {'manifest.json'}, {}
        observations[str(manifest)] = manifest_fact
        for index, row in enumerate(rows):
            _keys(row, ROW)
            target = _path(row['path'], runtime.home)
            if str(target) in seen or row['attempted'] is not True or row['restoration'] != 'not_needed':
                _fail('Ambiguous or incomplete historical transaction')
            seen.add(str(target))
            _metadata(row['before'], before=True, index=index)
            _metadata(row['after'], before=False, index=index)
            if row['before']['kind'] == 'file':
                name = row['before']['backup']; expected_files.add(name)
                blob = _capture(manifest.parent/name, observations, runtime, mode=0o600)
                if entries.sha256(blob) != row['before']['fingerprint']:
                    _fail('Historical before bytes do not match fingerprint')
                snapshots[str(target)] = blob
            else:
                snapshots[str(target)] = None
        if (not rows or rows[-1]['path'] != str(runtime.registry) or len(matches) != 1
                or {p.name for p in manifest.parent.iterdir()} != expected_files):
            _fail('Historical transaction scope or backup closure differs from producer')
        directories[str(manifest.parent)] = _directory(manifest.parent, runtime)
        row = matches[0]
        if row['before']['kind'] != 'file' or row['after']['mode'] != current_mode:
            _fail('Historical Claude input/mode is not compatible')
        _producer(runtime, manifest, doc, raw, snapshots, observations, directories)
        before = snapshots[str(path)]
        if entries.managed_span(before, **user_entries.CLAUDE_FALLBACK_MARKER) is not None:
            _fail('Historical append must start without a fallback block')
        baseline = before + (b'' if not before or before.endswith(b'\n') else b'\n') + old_block
        if entries.sha256(baseline) != registered:
            _fail('Frozen append does not reconstruct registered baseline')
        baselines.append(baseline)
        evidence.append({'manifest': str(manifest), 'manifest_sha256': manifest_fact['sha256'],
                         'operation': doc['operation'], 'before_sha256': row['before']['fingerprint'],
                         'after_sha256': registered, 'before_file': str(manifest.parent/row['before']['backup'])})
    if not baselines or any(b != baselines[0] for b in baselines):
        _fail('No unique proven historical baseline')
    return baselines[0], evidence


def _ck(data):
    span = entries.managed_span(data, **CK)
    if span is None:
        _fail('A unique independent CK span is required')
    return span


def _reference(data, runtime, ck_span):
    line = ('@'+str(runtime.root/'memories/MEMORY.md')).encode()
    found, offset = [], 0
    for raw in data.splitlines(keepends=True):
        if raw.rstrip(b'\r\n') == line:
            found.append((offset, offset+len(raw)))
        offset += len(raw)
    if len(found) != 1 or found[0][0] < ck_span[1] and found[0][1] > ck_span[0]:
        _fail('Exactly one independent public import reference is required')
    return entries.sha256(line)


def _running_kernel(runtime):
    # Execution from a checkout must carry the same Python/config bytes as C;
    # matching this one new module alone does not bind its helper semantics.
    meta = _json(_file(runtime.code/'.agm-code-manifest.json', home=runtime.home)[0])
    root = Path(__file__).resolve().parents[2]
    for item in meta['files']:
        name = item['path']
        if name.endswith('.py') or name == 'scripts/agents.json':
            if entries.sha256(_file(root/name)[0]) != item['sha256']:
                _fail('Executing kernel differs from installed code')


def _fence(runtime):
    layout.from_request({'home': str(runtime.home)})
    if os.path.lexists(runtime.home/'.mem-sharing-install.lock'):
        _fail('Machine installer lock present')


def preview(*, home):
    runtime = layout.resolve_layout(home)
    _fence(runtime)
    if os.path.lexists(runtime.lock):
        _fail('Product writer lock present')
    return _preview(runtime)


def _preview(runtime):
    _fence(runtime)
    config = policy_migration.config()
    allowed = paths_for(runtime, config)
    raw_registry, registry_fact = _file(runtime.registry, home=runtime.home)
    ledger = registry.require_installed(registry.load_registry(runtime.registry, allowed_user_paths=allowed))
    if ledger != _json(raw_registry):
        _fail('Registry changed while being read')
    user_install._code_matches(runtime, ledger['product'])
    _running_kernel(runtime)
    module = runtime.code/'scripts/agm_core/legacy_reconcile.py'
    if _file(module, home=runtime.home)[0] != Path(__file__).read_bytes():
        _fail('Installed code cannot carry this reconciliation route')
    path = Path(user_entries.agm_paths.expand_path(config['claude']['user_entry'], home=str(runtime.home)))
    raw, current_fact = _file(path, home=runtime.home)
    objects = [(scope, oid, obj) for scope in ('machine', 'shared_objects')
               for oid, obj in (ledger['machine']['objects'] if scope == 'machine' else ledger[scope]).items()
               if obj['path'] == str(path)]
    imports = [(s, oid, o) for s, oid, o in objects if o['kind'] == 'import']
    blocks = [(s, oid, o) for s, oid, o in objects if o.get('marker') == user_entries.CLAUDE_FALLBACK_MARKER]
    if (not imports or not blocks or not any(s == 'machine' for s, _, _ in imports)
            or any(o['kind'] == 'file' or o['kind'] == 'import' and o.get('lifecycle') for _, _, o in objects)):
        _fail('Expected only registered legacy Claude import and fallback units')
    for _, _, obj in imports:
        if (obj['agents'] != ['claude'] or obj['ownership'] != 'reused'
                or obj['marker'] is not None or obj['fingerprint']['basis'] != 'file_bytes'):
            _fail('Import ownership or semantics are not the supported legacy contract')
    if any(sum(s == scope for s, _, _ in imports) > 1 or
           sum(s == scope for s, _, _ in blocks) > 1 for scope in ('machine', 'shared_objects')):
        _fail('Ambiguous legacy import or fallback registration')
    registered = imports[0][2]['fingerprint']['value']
    if any(o['fingerprint']['value'] != registered for _, _, o in imports):
        _fail('Conflicting legacy import baselines')
    span = entries.managed_span(raw, **user_entries.CLAUDE_FALLBACK_MARKER)
    ck_span = _ck(raw)
    reference_sha = _reference(raw, runtime, ck_span)
    if span is None or span[0] < ck_span[1] and span[1] > ck_span[0]:
        _fail('Fallback and CK spans must be independent')
    unit = raw[span[0]:span[1]]
    if any(o['agents'] != ['claude'] or o['ownership'] != 'created'
           or o['kind'] != 'block' or o.get('lifecycle')
           or o['fingerprint']['value'] != entries.sha256(unit) for _, _, o in blocks):
        _fail('Fallback ownership or registered block bytes drifted')
    desired = user_entries._wrap_block(user_entries.CLAUDE_FALLBACK_MARKER, user_entries.CLAUDE_FALLBACK_TEXT)
    observations = {str(runtime.registry): registry_fact, str(path): current_fact}
    module_raw, module_fact = _file(module, home=runtime.home)
    observations[str(module)] = module_fact
    body = {'schema_version': 1, 'command': COMMAND, 'home': str(runtime.home),
            'path': str(path), 'registry_path': str(runtime.registry),
            'registered_sha256': registered, 'current_sha256': current_fact['sha256'],
            'before_hex': raw.hex(), 'before_registry_hex': raw_registry.hex(),
            'module_sha256': entries.sha256(module_raw), 'observations': observations,
            'evidence': [], 'candidates': _candidate_state(runtime), 'directories': {}, 'fingerprints': [], 'ck': {'current_span': list(ck_span),
                'current_sha256': entries.sha256(raw[ck_span[0]:ck_span[1]]), 'policy': 'preserved'},
            'import_line_sha256': reference_sha, 'noop': False}
    if current_fact['sha256'] == registered:
        if unit != desired:
            _fail('No legacy import drift to reconcile; use ordinary policy migration')
        body.update(noop=True, after_hex=raw.hex(), mode=current_fact['mode'], after_registry=ledger)
    else:
        old_block = policy_migration.legacy('claude', runtime)
        if unit != old_block:
            _fail('Fallback is not the exact known historical template')
        baseline, evidence = _history(runtime, path, registered, old_block, observations, body['directories'], current_fact['mode'])
        old_ck = _ck(baseline)
        _reference(baseline, runtime, old_ck)
        if (baseline[:old_ck[0]] + baseline[old_ck[1]:] != raw[:ck_span[0]] + raw[ck_span[1]:]
                or baseline[old_ck[0]:old_ck[1]] == raw[ck_span[0]:ck_span[1]]):
            _fail('Only a changed independent CK span may differ from historical baseline')
        final = entries.render_block(raw, desired, **user_entries.CLAUDE_FALLBACK_MARKER,
                                     expected_fingerprint=entries.sha256(old_block))
        updated = copy.deepcopy(ledger)
        for scope, oid, _ in imports+blocks:
            target = updated['machine']['objects'] if scope == 'machine' else updated[scope]
            after = entries.sha256(final if target[oid]['kind'] == 'import' else desired)
            body['fingerprints'].append({'scope': scope, 'object_id': oid,
                'before': target[oid]['fingerprint']['value'], 'after': after})
            target[oid]['fingerprint']['value'] = after
        body.update(evidence=evidence, after_hex=final.hex(), mode=current_fact['mode'], after_registry=updated)
        body['ck'].update(historical_span=list(old_ck), historical_sha256=entries.sha256(baseline[old_ck[0]:old_ck[1]]), outside='byte_identical')
    if _candidate_state(runtime) != body['candidates']:
        _fail('Historical candidate set changed during preview')
    body['after_sha256'] = entries.sha256(bytes.fromhex(body['after_hex']))
    body['after_registry_sha256'] = entries.sha256(registry.serialize_registry(body['after_registry'], allowed_user_paths=allowed))
    return recovery.seal(body)


def paths_for(runtime, config):
    return user_entries.agm_paths.allowed_user_paths(config, None, home=str(runtime.home))


def view(plan):
    return {k: plan[k] for k in ('schema_version', 'command', 'home', 'path', 'registry_path',
            'registered_sha256', 'current_sha256', 'module_sha256', 'evidence', 'ck',
            'import_line_sha256', 'fingerprints', 'noop', 'after_sha256', 'after_registry_sha256', 'plan_sha256')} | {
        'scope': 'exact legacy Claude import and owned fallback only',
        'changes': [] if plan['noop'] else [{'path': plan['path'], 'after_sha256': plan['after_sha256'], 'mode': plan['mode']},
                  {'path': plan['registry_path'], 'after_sha256': plan['after_registry_sha256']}],
        'preserved': ['CK bytes', 'private bytes and line endings', 'reference position', 'ownership', 'deletion rights'],
        'runtime_acceptance': 'pending'}


def _verify_evidence(plan, own=None):
    runtime = layout.resolve_layout(plan['home'])
    _fence(runtime)
    user_install._code_matches(runtime, plan['after_registry']['product'])
    _running_kernel(runtime)
    if _candidate_state(runtime, own) != plan['candidates']:
        _fail('Approved historical candidate set changed')
    for name, expected in plan['directories'].items():
        if _directory(Path(name), runtime) != expected:
            _fail('Approved evidence directory changed')
    for raw, expected in plan['observations'].items():
        # User entry and V are guarded by Transaction before/after snapshots.
        if raw in (plan['path'], plan['registry_path']):
            continue
        if _file(Path(raw), home=Path(plan['home']))[1] != expected:
            _fail('Approved evidence changed')


def execute(approval, *, home, hook=None):
    plan = preview(home=home)
    recovery.approve(approval, view(plan))
    if plan['noop']:
        return {'status': 'completed', 'changes': [], 'noop': True, 'context_keeper': 'unchanged'}
    runtime = layout.resolve_layout(home)
    with write_lock(runtime.lock):
        # _preview is deliberately called beneath the lock, not preview's lock fence.
        fresh = _preview(runtime)
        recovery.approve(approval, view(fresh))
        _verify_evidence(fresh)
        def guarded(event, path):
            if hook is not None:
                hook(event, path)
            if event == 'before_write':
                _verify_evidence(fresh, tx)
        tx = Transaction(lock_path=runtime.transaction_lock, backup_root=runtime.backups,
                         allowed_roots=[Path(fresh['path']), runtime.registry], operation=COMMAND, hook=guarded)
        changes = [Change.file(fresh['path'], bytes.fromhex(fresh['after_hex']),
                    expected=Snapshot('file', bytes.fromhex(fresh['before_hex']), fresh['mode']))]
        result = registry.commit_registry(runtime.registry, fresh['after_registry'], transaction=tx,
                    expected=Snapshot('file', bytes.fromhex(fresh['before_registry_hex']),
                                      fresh['observations'][str(runtime.registry)]['mode']),
                    changes=changes, previous=_json(bytes.fromhex(fresh['before_registry_hex'])),
                    allowed_user_paths=paths_for(runtime, policy_migration.config()))
    return {'status': 'completed', 'changes': result['changed'], 'manifest': result['manifest'],
            'noop': False, 'context_keeper': 'unchanged', 'runtime_acceptance': 'pending'}


def cli(argv, *, home=None):
    parser = argparse.ArgumentParser(prog=COMMAND, allow_abbrev=False)
    parser.add_argument('command', choices=[COMMAND])
    parser.add_argument('--approval-file')
    parser.add_argument('--json', action='store_true')
    args = parser.parse_args(argv)
    try:
        if args.approval_file:
            result = execute(_json(_file(Path(args.approval_file))[0]), home=Path.home() if home is None else home)
        else:
            plan = preview(home=Path.home() if home is None else home)
            result = {'status': 'completed' if plan['noop'] else 'approval_required',
                      'approval_required': not plan['noop'], 'plan': view(plan), 'noop': plan['noop']}
        print(json.dumps(result, ensure_ascii=False))
        return recovery.exit_code(result)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(json.dumps({'status': 'failed', 'errors': [{'code': getattr(exc, 'code', 'legacy_reconcile_conflict'),
              'message': str(exc)}]}, ensure_ascii=False))
        return 2
