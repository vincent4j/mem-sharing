"""Independent, opt-in retirement of the narrow legacy Paseo staging format.

This producer runs from a separately trusted clean Git pin; it never installs
itself into C. Unknown formats remain blocked, not adopted by adjacency.
"""
import argparse
import copy
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import socket
import stat
import subprocess

from . import plugin_release, registry, uninstall, uninstall_recovery as recovery, user_install, paths, policy_migration, project, entries
from .layout import RuntimeLayout
from .transaction import write_lock

COMMAND = 'retire-legacy-staging'
FLOWS = {'dependency', 'bootstrap', 'machine', 'enable', 'remove', 'ck', 'recover', 'fusion'}
SHA = re.compile(r'[0-9a-f]{64}')


def strict(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result: raise recovery.Conflict('Duplicate JSON key')
            result[key] = value
        return result
    return json.loads(raw, object_pairs_hook=pairs)


def _keys(value, keys):
    if not isinstance(value, dict) or set(value) != set(keys.split()):
        raise recovery.Conflict('Unknown legacy schema')


def _node(path, kind, mode):
    path = recovery.safe(path)
    st = path.lstat()
    if ((kind == 'file' and not stat.S_ISREG(st.st_mode)) or
        (kind == 'directory' and not stat.S_ISDIR(st.st_mode)) or
        stat.S_IMODE(st.st_mode) != mode or st.st_uid != os.getuid() or
        (kind == 'file' and st.st_nlink != 1)):
        raise recovery.Conflict('Unsafe legacy node: ' + str(path))
    result = {'mode': mode, 'inode': st.st_ino, 'device': st.st_dev,
              'mtime_ns': st.st_mtime_ns, 'size': st.st_size}
    if kind == 'directory': result['children'] = sorted(p.name for p in path.iterdir())
    if kind == 'file': result['sha256'] = recovery.digest(path.read_bytes())
    return result


def trusted_tool(root, commit):
    root, commit = plugin_release.clean_checkout(root, commit)
    # git status alone can conceal assume-unchanged/skip-worktree changes.
    for row in plugin_release._git(root, 'ls-tree', '-rz', commit, '--', 'scripts').split(b'\0'):
        if not row: continue
        header, name = row.split(b'\t', 1)
        mode, kind, blob = header.split()
        p = root / os.fsdecode(name)
        if kind != b'blob' or mode not in (b'100644', b'100755'):
            raise recovery.Conflict('Unsupported tool source node')
        if p.is_symlink() or stat.S_IMODE(p.stat().st_mode) != (0o755 if mode == b'100755' else 0o644) or p.read_bytes() != plugin_release._git(root, 'cat-file', 'blob', blob.decode()):
            raise recovery.Conflict('Tool source differs from pin')
    if Path(__file__).resolve() != root / 'scripts/agm_core/staging_retirement.py':
        raise recovery.Conflict('Tool imported outside trusted checkout')
    return {'root': str(root), 'commit': commit}


def host_scene(cli, expected_hash, home, server_id, plugin_id):
    if plugin_id != 'memsharing-synthetic-dev':
        raise recovery.Conflict('Unsupported legacy plugin owner; exact known ID required')
    cli = Path(cli)
    # Explicit native CLI symlink is allowed; its final bytes are pinned.
    if not SHA.fullmatch(expected_hash) or recovery.digest(cli.read_bytes()) != expected_hash:
        raise recovery.Conflict('Paseo CLI identity drift')
    def run(*args):
        p = subprocess.run([str(cli), *args, '--home', str(home), '--json'], capture_output=True, timeout=15)
        if p.returncode: raise recovery.Conflict('Official Paseo query failed')
        return strict(p.stdout)
    before = run('status'); plugins = run('plugin', 'ls'); after = run('status')
    fields = ('home', 'serverId', 'pid', 'startedAt', 'localDaemon', 'connectedDaemon')
    scene = {k: before.get(k) for k in fields}
    if (scene != {k: after.get(k) for k in fields} or scene['home'] != str(home)
        or scene['serverId'] != server_id or scene['localDaemon'] != 'running'
        or scene['connectedDaemon'] != 'reachable' or type(scene['pid']) is not int
        or not isinstance(plugins, list) or any(not isinstance(x, dict) or not isinstance(x.get('id'), str) for x in plugins)
        or len({x['id'] for x in plugins}) != len(plugins)
        or any(x['id'] == plugin_id for x in plugins)):
        raise recovery.Conflict('Host target not stably removed')
    return {'cli': str(cli), 'cli_sha256': expected_hash, 'target': plugin_id,
            'status': scene, 'other_plugins_sha256': recovery.digest(recovery.encoded(plugins))}


def installed(rt):
    rt.validate_paths()
    before = rt.registry.read_bytes()
    ledger = registry.require_installed(registry.load_registry(rt.registry, allowed_user_paths=paths.allowed_user_paths(policy_migration.config(), None, home=str(rt.home))))
    p = ledger['product']
    if p['product_code_version'] != '0.1.6' or p['installation_status'] != 'complete':
        raise recovery.Conflict('Requires complete installed 0.1.6')
    if (p['source'].get('commit') != 'eb31607bcd5fb1c2e5a6332e9e67682cd0cf956b' or
        p['source'].get('tree_sha256') != '3e792c336cd1b73c250e2f51aa2a919126920f96ec98e498b0b9864ed57e0303'):
        raise recovery.Conflict('Unsupported installed source identity')
    user_install._code_matches(rt, p)
    if rt.registry.read_bytes() != before: raise recovery.Conflict('Registry changed during identity read')
    return ledger, recovery.digest(before)



def _enable_history(data, rt, ledger):
    """Prove the only supported historical branch: first Codex AGENTS append.

    Detection fingerprints are opaque historical observations, NEVER authority.
    Authority comes from the current registered created object and complete
    committed Transaction, independently replayed using the frozen append rule.
    No historical code or approval is executed.
    """
    main = data['main_checkout']; checkout = data['checkout']
    registered = ledger['projects'].get(main)
    if (not registered or registered.get('memory_policy') != 'follow_ck'
        or data['agents'] != ['codex'] or set(registered.get('checkouts', {})) != {checkout}):
        raise recovery.Conflict('No supported registered enable assembly')
    identity = project.resolve_project(Path(checkout))
    if (str(identity.main_checkout) != main or str(identity.git_common_dir) != data['git_common_dir']
        or identity.checkout != identity.main_checkout):
        raise recovery.Conflict('Enable Git identity mismatch')
    assembly = registered['checkouts'][checkout]
    target = str(Path(checkout)/'AGENTS.md'); oid = target+'#experience'
    if (assembly.get('agents') != ['codex'] or assembly.get('git_common_dir') != data['git_common_dir']
        or set(assembly.get('objects', {})) != {oid} or assembly.get('shared_object_ids') != []
        or len(data['changes']) != 1 or data['changes'][0]['path'] != target):
        raise recovery.Conflict('Approval target not the exact registered producer output')
    obj = assembly['objects'][oid]
    manifest = recovery.safe(obj.get('backup_manifest', ''))
    if (manifest.name != 'manifest.json' or manifest.parent.parent != rt.backups
        or not re.fullmatch(r'[0-9]{8}T[0-9]{6}Z-[0-9a-f]{32}', manifest.parent.name)):
        raise recovery.Conflict('Enable transaction outside fixed backup root')
    started = datetime.strptime(manifest.parent.name.split('-')[0], '%Y%m%dT%H%M%SZ').replace(tzinfo=timezone.utc)
    confirmed = datetime.fromisoformat(data['confirmed_at'].replace('Z','+00:00'))
    if not 0 <= (started-confirmed).total_seconds() <= 600:
        raise recovery.Conflict('Approval not contemporaneous with registered transaction')
    evidence = {}
    def fact(path, kind='file', mode=0o600):
        value = _node(path,kind,mode); evidence[str(path)] = value; return value
    fact(manifest.parent,'directory',0o700);fact(manifest)
    tx = strict(manifest.read_bytes())
    _keys(tx,'schema_version operation status registry_path created_directories entries error')
    if (type(tx['schema_version']) is not int or tx['schema_version'] != 1
        or tx['operation'] != 'enable-memory' or tx['status'] != 'committed'
        or tx['registry_path'] != str(rt.registry) or tx['created_directories'] != []
        or tx['error'] is not None or not isinstance(tx['entries'],list)
        or len(tx['entries']) != 2):
        raise recovery.Conflict('Unsupported historical enable transaction')
    if {p.name for p in manifest.parent.iterdir()} != {'manifest.json','0.before','1.before'}:
        raise recovery.Conflict('Unexpected historical transaction closure')
    raw = []
    for index, (row, expected_path) in enumerate(zip(tx['entries'],(target,str(rt.registry)))):
        _keys(row,'path before after attempted restoration')
        if row['path'] != expected_path or row['attempted'] is not True or row['restoration'] != 'not_needed':
            raise recovery.Conflict('Historical enable output scope/status mismatch')
        for key in ('before','after'):
            node=row[key];_keys(node,'existed kind mode link_target fingerprint backup')
            if (node['existed'] is not True or node['kind'] != 'file'
                or type(node['mode']) is not int or not 0 <= node['mode'] <= 0o777
                or node['link_target'] is not None or not isinstance(node['fingerprint'],str)
                or not SHA.fullmatch(node['fingerprint'])):
                raise recovery.Conflict('Invalid historical file metadata')
        if (row['before']['backup'] != str(index)+'.before' or row['after']['backup'] is not None
            or row['before']['mode'] != row['after']['mode'] or index == 1 and row['before']['mode'] != 0o600):
            raise recovery.Conflict('Historical backup/mode mismatch')
        backup=manifest.parent/(str(index)+'.before');fact(backup);body=backup.read_bytes()
        if recovery.digest(body) != row['before']['fingerprint']:raise recovery.Conflict('Historical before bytes drift')
        raw.append(body)
    marker = {'start':'<!-- mem-sharing:project-experience:start -->','end':'<!-- mem-sharing:project-experience:end -->'}
    # Frozen public producer text from ef742a2 enable.py; do not trust journal units.
    unit = ('<!-- mem-sharing:project-experience:start -->\n'
            '位置：项目经历记录库由 Context Keeper 管理，默认位于 docs/context-keeper/。\n'
            '入口：使用 /context-keeper，首次保存按 Context Keeper 流程确认位置并初始化。\n'
            '职责：命令、记录格式、保存与查找流程由 Context Keeper 自行定义。\n'
            '<!-- mem-sharing:project-experience:end -->').encode()
    if entries.managed_span(raw[0], **marker) is not None:raise recovery.Conflict('Not a first owned append')
    prefix = b'\n' if raw[0] and not raw[0].endswith(b'\n') else b''
    after = raw[0]+prefix+unit
    change = data['changes'][0]
    if (change['before_fingerprint'] != recovery.digest(raw[0])
        or change['after_fingerprint'] != recovery.digest(after)
        or tx['entries'][0]['after']['fingerprint'] != recovery.digest(after)):
        raise recovery.Conflict('Approval not the proven producer before/after')
    expected_object = {'kind':'block','path':target,'scope':'project','agents':['codex'],
        'ownership':'created','marker':marker,'fingerprint':{'algorithm':'sha256','basis':'block_bytes','value':recovery.digest(unit)},
        'original_existed':False,'link_target':None,'backup_manifest':str(manifest),'consumers':[checkout],
        'lifecycle':{'version':1,'unit_hex':unit.hex(),'prefix_hex':prefix.hex(),'suffix_hex':'',
            'file_created':False,'operation_id':manifest.parent.name,'container_units':[oid]}}
    expected_project = registry.new_project(identity,['codex'])
    expected_project['checkouts'][checkout]['objects'][oid] = expected_object
    if registered != expected_project:raise recovery.Conflict('Registered object does not match frozen producer')
    before_ledger = strict(raw[1])
    allowed=paths.allowed_user_paths(policy_migration.config(),None,home=str(rt.home))
    registry.require_installed(registry.validate_registry(before_ledger,allowed_user_paths=allowed))
    if main in before_ledger['projects'] or before_ledger['product']['installation_id'] != ledger['product']['installation_id']:
        raise recovery.Conflict('Not the same installed first-enable history')
    after_ledger=copy.deepcopy(before_ledger);after_ledger['projects'][main]=expected_project
    encoded=(json.dumps(after_ledger,ensure_ascii=False,indent=2)+'\n').encode()
    if recovery.digest(encoded) != tx['entries'][1]['after']['fingerprint']:
        raise recovery.Conflict('Historical registry after not the exact producer result')
    # Bind every supporting node into preview and write-time revalidation.
    for path,value in evidence.items():
        if _node(Path(path),'file' if 'sha256' in value else 'directory',value['mode']) != value:
            raise recovery.Conflict('Historical evidence changed during validation')
    return evidence


def _fusion_history(data,rt):
    """Recognize an exact approved fusion only with its terminal producer tx."""
    from . import user_rules_organize as fusion
    from .transaction import Transaction, _recovery_entries
    if not isinstance(data,dict): raise recovery.Conflict('Invalid fusion approval')
    registry._evidence({k:data[k] for k in ('confirmed_at','reference')})
    plan={k:v for k,v in data.items() if k not in ('confirmed_at','reference')}
    digest=plan.pop('plan_sha256',None)
    _keys(plan,'schema_version command layout request declined scope project agents agent_facts groups default_numbers optional_numbers single_numbers selected_numbers view unknown_sources items blocked_entries protected_units observations public_listing changes phased_writes steps retention_paths public_paths registry_policy'+(' reference_rebindings' if 'reference_rebindings' in plan else '')+(' operation_metadata' if 'operation_metadata' in plan else ''))
    if digest != entries.sha256(fusion._encoded(plan)): raise recovery.Conflict('Fusion approval digest mismatch')
    if (plan.get('schema_version')!=2 or plan.get('command')!='organize-user-rules'
        or plan.get('layout')!=rt.describe() or plan.get('scope') not in ('user','project')
        or plan.get('request',{}).get('home')!=str(rt.home)
        or plan['request'].get('platform_config')!=policy_migration.config()):
        raise recovery.Conflict('Unknown fusion producer identity')
    if type(plan['phased_writes']) is not bool or plan['request'].get('scope','user') != plan['scope']:
        raise recovery.Conflict('Unknown fusion approval scope')
    if plan['scope']=='project' and str(recovery.safe(plan['request'].get('project',''))) != plan['project']:
        raise recovery.Conflict('Fusion project identity mismatch')
    ordered=plan.get('steps') if plan.get('phased_writes') else plan.get('changes')
    if not isinstance(ordered,list) or not ordered: raise recovery.Conflict('No fusion execution proof')
    candidates=list(rt.backups.glob('*/manifest.json'))
    if len(candidates)>256: raise recovery.Conflict('Bounded fusion history exhausted')
    confirmed=datetime.fromisoformat(data['confirmed_at'].replace('Z','+00:00'))
    for manifest in candidates:
        txdata=strict(manifest.read_bytes())
        if (txdata.get('operation')!='organize-user-rules' or txdata.get('status') not in ('committed','rolled_back')
            or txdata.get('registry_path') not in (None,str(rt.registry)) or len(txdata.get('entries',[]))!=len(ordered)
            or bool(txdata.get('phased_writes'))!=bool(plan.get('phased_writes'))): continue
        if bool(plan.get('reference_rebindings')) != (txdata.get('registry_path')==str(rt.registry)): continue
        if txdata.get('operation_metadata') != plan.get('operation_metadata'): continue
        rows=txdata['entries']
        if any(row['path']!=step['path'] or row['before']['kind']!=step['before']['kind']
            or row['before']['fingerprint']!=step['before']['sha256']
            or row['before']['mode']!=step['before']['mode']
            or row['after']['fingerprint']!=step['after_sha256']
            or entries.sha256(bytes.fromhex(step['after_hex']))!=step['after_sha256']
            for row,step in zip(rows,ordered)): continue
        if not re.fullmatch(r'[0-9]{8}T[0-9]{6}Z-[0-9a-f]{32}',manifest.parent.name):
            raise recovery.Conflict('Invalid fusion transaction identity')
        started=datetime.strptime(manifest.parent.name.split('-')[0],'%Y%m%dT%H%M%SZ').replace(tzinfo=timezone.utc)
        if not 0 <= (started-confirmed).total_seconds() <= 600: continue
        roots=[rt.home,rt.root]+([recovery.safe(plan['project'])] if plan.get('project') else [])
        tx=Transaction(lock_path=rt.transaction_lock,backup_root=rt.backups,allowed_roots=roots,operation='recover')
        if txdata.get('registry_path') is not None:
            from . import fusion_recovery
            fusion_recovery.build({'home':str(rt.home),'manifest':str(manifest)},terminal_proof=True)
        _recovery_entries(tx,manifest,txdata)
        evidence={}
        def fact(path,kind='file',mode=0o600):evidence[str(path)]=_node(path,kind,mode)
        fact(manifest.parent,'directory',0o700);fact(manifest)
        expected={'manifest.json'}
        for row in rows:
            if row['before']['kind']=='file':
                name=row['before']['backup'];expected.add(name);fact(manifest.parent/name)
        if {p.name for p in manifest.parent.iterdir()}!=expected:
            raise recovery.Conflict('Fusion transaction closure incomplete')
        return evidence
    raise recovery.Conflict('No terminal transaction matches this exact fusion approval')


def _artifact(path, rt, ledger, now):
    meta = _node(path, 'file', 0o600)
    data = strict(path.read_bytes())
    if path.name == 'operation.json':
        if not isinstance(data, dict): raise recovery.Conflict('Unknown operation schema')
        keys = 'id flow phase home host state started_at' + (' journal' if 'journal' in data else '')
        _keys(data, keys)
        registry._time(data['started_at'])
        if (not isinstance(data['id'], str) or not data['id'] or not isinstance(data['flow'], str) or data['flow'] not in FLOWS
            or data['phase'] not in ('preview', 'execute') or data['home'] != str(rt.home)
            or data['host'] != socket.gethostname()): raise recovery.Conflict('Operation identity invalid')
        terminal = {'completed', 'failed', 'rejected', 'approval_required', 'gaps', 'recovered'}
        if data['phase'] == 'preview': terminal |= {'already_prepared', 'identity_missing', 'payload_missing'}
        else: terminal |= {'stale_plan', 'no_pending_plan'}
        if data['flow'] == 'bootstrap' and data['phase'] == 'execute': terminal.add('acquired')
        if data['flow'] == 'fusion':
            terminal = {'completed','failed'} if data['phase']=='preview' else {'completed','failed','rejected','stale_plan','no_pending_plan'}
        # Narrow initial producer: journal-based recovery is deliberately not inferred.
        if not isinstance(data['state'], str) or data['state'] not in terminal or data.get('journal') is not None:
            raise recovery.Conflict('Active, unknown or journal-bearing operation')
        record = data['state']
    elif path.name == 'fusion-approval.json':
        meta['history'] = _fusion_history(data,rt)
        record = 'no_operation_record'
    elif path.name == 'enable-approval.json':
        _keys(data, 'schema_version command main_checkout checkout git_common_dir agents memory_policy changes installation native_pending confirmed_at reference')
        if type(data['schema_version']) is not int or data['schema_version'] != 1 or data['command'] != 'enable-memory':
            raise recovery.Conflict('Unknown enable producer')
        registry._evidence({k:data[k] for k in ('confirmed_at', 'reference')})
        project = ledger['projects'].get(data['main_checkout'])
        if (not project or project.get('main_checkout') != data['main_checkout'] or data['memory_policy'] != 'follow_ck'): raise recovery.Conflict('Unregistered approval project')
        for key in ('main_checkout', 'checkout', 'git_common_dir'): recovery.safe(data[key])
        if data['main_checkout'] != data['checkout'] or not Path(data['git_common_dir']).is_relative_to(Path(data['main_checkout'])):
            raise recovery.Conflict('Unsupported project topology')
        if (not isinstance(data['agents'], list) or not data['agents'] or len(set(data['agents'])) != len(data['agents'])
            or any(a not in registry.AGENTS for a in data['agents']) or data['native_pending'] != []
            or not isinstance(data['installation'], dict) or set(data['installation']) != set(data['agents'])):
            raise recovery.Conflict('Unknown enable agents')
        for item in data['installation'].values():
            _keys(item, 'status fingerprint')
            if item['status'] != 'installed' or not isinstance(item['fingerprint'], str) or not SHA.fullmatch(item['fingerprint']):
                raise recovery.Conflict('Unknown installation evidence')
        if not isinstance(data['changes'], list) or not data['changes']: raise recovery.Conflict('Empty enable changes')
        paths = set()
        for c in data['changes']:
            _keys(c, 'path operation before_fingerprint after_fingerprint')
            target = recovery.safe(c['path'])
            if target in paths or not target.is_relative_to(Path(data['checkout'])) or target == Path(data['checkout']):
                raise recovery.Conflict('Enable output scope invalid')
            paths.add(target)
            if c['operation'] != 'update' or any(not isinstance(c[k], str) or not SHA.fullmatch(c[k]) for k in ('before_fingerprint','after_fingerprint')):
                raise recovery.Conflict('Unknown enable change')
        meta['history'] = _enable_history(data,rt,ledger)
        record = 'no_operation_record'
    else:
        raise recovery.Conflict('Unsupported independent artifact (not claimed by adjacent operation)')
    if (now.timestamp() - meta['mtime_ns']/1e9 <= 600 or
        datetime.fromisoformat(data.get('started_at', data.get('confirmed_at')).replace('Z','+00:00')).timestamp() > now.timestamp()):
        raise recovery.Conflict('Artifact not beyond existing quiet TTL')
    return meta, record



def _guards(rt, *, allow_lock=False):
    guards = [rt.lock, rt.home/'.mem-sharing-install.lock', rt.home/'.mem-sharing-source.lock', rt.home/'.mem-sharing-upgrade.json']
    for path in guards:
        if os.path.lexists(path) and not (allow_lock and path == rt.lock):
            raise recovery.Conflict('Writer or upgrade guard exists')

def preview(rt, options, *, tool=None, host=None, installation=None, now=None, allow_lock=False):
    now = now or datetime.now(timezone.utc)
    tool = tool or trusted_tool(Path(__file__).resolve().parents[2], options['tool_commit'])
    ledger, ledger_hash = installation or installed(rt)
    host = host or host_scene(options['paseo_cli'], options['cli_sha256'], rt.home/'.paseo', options['server_id'], options['plugin_id'])
    _guards(rt, allow_lock=allow_lock)
    root = rt.code.parent/'mem-sharing-plugin-staging'
    nodes = {str(root): _node(root, 'directory', 0o700)}
    if {p.name for p in root.iterdir()} != {'pending'}: raise recovery.Conflict('Unknown staging root content')
    pending = root/'pending'; nodes[str(pending)] = _node(pending, 'directory', 0o700)
    rows = []; historical_evidence = {}
    for directory in sorted(pending.iterdir()):
        if not re.fullmatch(r'op-[A-Za-z0-9]+', directory.name): raise recovery.Conflict('Unknown staging directory')
        nodes[str(directory)] = _node(directory, 'directory', 0o700)
        files = sorted(directory.iterdir())
        if len(files) != 1: raise recovery.Conflict('Legacy producer requires independent singleton artifact directories')
        artifacts = []; record = 'no_operation_record'
        for path in files:
            meta, state = _artifact(path, rt, ledger, now)
            for key,value in meta.pop('history',{}).items():
                if key in historical_evidence and historical_evidence[key] != value: raise recovery.Conflict('Historical evidence drift')
                historical_evidence[key]=value
            nodes[str(path)] = meta
            artifacts.append({'name':path.name, 'sha256':meta['sha256']})
            if path.name == 'operation.json': record = state
        rows.append({'dir': directory.name, 'record_state':record, 'in_memory_running':False,
                     'journal_status':None, 'artifacts':artifacts})
    if not rows: raise recovery.Conflict('No legacy artifacts')
    evidence = recovery.safe(options['evidence_dir'])
    _node(evidence, 'directory', 0o700)
    forbidden = [rt.root, rt.code, root, rt.code.parent/'mem-sharing-sources',rt.code.parent/'mem-sharing-versions',rt.code.parent/'mem-sharing-runtimes']
    if evidence == rt.home or rt.home.is_relative_to(evidence) or any(evidence.is_relative_to(p) or p.is_relative_to(evidence) for p in forbidden):
        raise recovery.Conflict('Evidence overlaps managed roots')
    if os.path.lexists(evidence/'retirement-progress.json'): raise recovery.Conflict('Existing retirement attempt requires inspection')
    backup = evidence/'memsharing-host-staging'
    if os.path.lexists(backup): raise recovery.Conflict('Archive destination already exists')
    plan = {'schema_version':1, 'command':COMMAND, 'home':str(rt.home), 'options':options,
            'tool':tool, 'host':host, 'registry_sha256':ledger_hash, 'nodes':nodes,
            'terminal_evidence':rows, 'historical_evidence':historical_evidence, 'backup_root':str(backup), 'receipt_path':str(root/'host-receipt.json')}
    plan['plan_sha256'] = recovery.digest(recovery.encoded(plan))
    return plan


def execute(rt, approval, *, rebuild=preview):
    plan = approval['plan']; options = plan['options']
    recovery.approve(approval, plan)
    if datetime.fromisoformat(approval['confirmed_at'].replace('Z','+00:00')) > datetime.now(timezone.utc):
        raise recovery.Conflict('Approval timestamp is in the future')
    current = rebuild(rt, options)
    if current != plan: raise recovery.Conflict('Approved staging scene drifted')
    with write_lock(rt.lock):
        current = rebuild(rt, options, allow_lock=True)
        if current != plan: raise recovery.Conflict('Locked staging scene drifted')
        evidence = Path(options['evidence_dir'])
        progress = evidence/'retirement-progress.json'
        if os.path.lexists(progress): raise recovery.Conflict('Existing retirement attempt requires inspection')
        recovery.write_file(progress,recovery.encoded({'status':'archiving','plan':plan,'approval':approval}))
        backup = Path(plan['backup_root']); backup.mkdir(mode=0o700)
        # Preserve all bytes before the first source deletion. Partial failures
        # intentionally retain the archive; no implicit resume/retry or rollback.
        for row in plan['terminal_evidence']:
            target = backup/row['dir']; target.mkdir(mode=0o700)
            for artifact in row['artifacts']:
                source = rt.code.parent/'mem-sharing-plugin-staging/pending'/row['dir']/artifact['name']
                meta = plan['nodes'][str(source)]
                if _node(source,'file',0o600) != meta: raise recovery.Conflict('Archive source drift')
                with open(target/artifact['name'], 'xb') as out:
                    os.fchmod(out.fileno(),0o600);out.write(source.read_bytes());out.flush();os.fsync(out.fileno())
                os.utime(target/artifact['name'],ns=(meta['mtime_ns'],meta['mtime_ns']))
                _fsync(target/artifact['name'])
                if recovery.digest((target/artifact['name']).read_bytes()) != meta['sha256']: raise recovery.Conflict('Archive mismatch')
            _fsync(target)
        _fsync(backup); _fsync(backup.parent)
        tree_hash = uninstall._runtime_digest(backup)
        # Whole candidate closure and official host rechecked after archive.
        # preview expects the destination absent; only this owned archive is exempt.
        for path, meta in (plan['nodes'] | plan['historical_evidence']).items():
            if _node(Path(path),'file' if 'sha256' in meta else 'directory', meta['mode']) != meta:
                raise recovery.Conflict('Staging changed before deletion')
        if host_scene(options['paseo_cli'], options['cli_sha256'],rt.home/'.paseo',options['server_id'],options['plugin_id']) != plan['host']:
            raise recovery.Conflict('Host changed before deletion')
        _guards(rt, allow_lock=True)
        if installed(rt)[1] != plan['registry_sha256']: raise recovery.Conflict('Registry drift')
        if uninstall._runtime_digest(backup) != tree_hash: raise recovery.Conflict('Archive changed before deletion')
        recovery.write_file(progress,recovery.encoded({'status':'deleting','plan':plan,'approval':approval,'backup_tree_sha256':tree_hash}))
        for row in plan['terminal_evidence']:
            _guards(rt, allow_lock=True)
            directory = rt.code.parent/'mem-sharing-plugin-staging/pending'/row['dir']
            if {p.name for p in directory.iterdir()} != {x['name'] for x in row['artifacts']}: raise recovery.Conflict('New staging artifact')
            for artifact in row['artifacts']:
                source=directory/artifact['name']
                if _node(source,'file',0o600) != plan['nodes'][str(source)]: raise recovery.Conflict('Pre-unlink drift')
                source.unlink()
            directory.rmdir()
        root = rt.code.parent/'mem-sharing-plugin-staging'; (root/'pending').rmdir()
        _fsync(root)
        if list(root.iterdir()): raise recovery.Conflict('New staging root content; preserving scene')
        receipt = {'schema_version':1,'product_id':'mem-sharing','kind':'host-staging-retired',
                   'home':str(rt.home),'host':socket.gethostname(),'staging_root':str(root),
                   'backup_root':str(backup),'backup_tree_sha256':tree_hash,
                   'generated_at':datetime.now(timezone.utc).isoformat().replace('+00:00','Z'),
                   'status':'completed','approval':{'digest':plan['plan_sha256'],
                     'confirmed_at':approval['confirmed_at'],'reference':approval['reference']},
                   'terminal_evidence':plan['terminal_evidence']}
        recovery.write_file(root/'host-receipt.json',recovery.encoded(receipt));_fsync(root)
        uninstall._host_staging_receipt(rt,root,Path(options['evidence_dir'])/'future-uninstall')
        recovery.write_file(progress,recovery.encoded({'status':'completed','plan_sha256':plan['plan_sha256'],'receipt':receipt}))
        return {'status':'completed','receipt_path':str(root/'host-receipt.json'),'backup_root':str(backup),'backup_tree_sha256':tree_hash}


def _fsync(path):
    fd=os.open(path,os.O_RDONLY)
    try: os.fsync(fd)
    finally: os.close(fd)


def cli(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--approval-file')
    for name in ('tool-commit','paseo-cli','cli-sha256','server-id','plugin-id','evidence-dir'): parser.add_argument('--'+name)
    args=parser.parse_args(argv)
    try:
        if args.approval_file:
            if any(getattr(args,n.replace('-','_')) for n in ('tool-commit','paseo-cli','cli-sha256','server-id','plugin-id','evidence-dir')): raise recovery.Conflict('Approval execution accepts only --approval-file')
            result=execute(RuntimeLayout(Path.home()),strict(Path(args.approval_file).read_bytes()))
        else:
            options={k:v for k,v in vars(args).items() if k!='approval_file'}
            if not all(options.values()): raise recovery.Conflict('All preview identity arguments required')
            result={'status':'approval_required','approval_plan':preview(RuntimeLayout(Path.home()),options)}
        print(json.dumps(result,ensure_ascii=False,indent=2));return 5 if result['status']=='approval_required' else 0
    except (ValueError,OSError,KeyError,TypeError,subprocess.SubprocessError) as exc:
        print(json.dumps({'status':'failed','error':str(exc)}));return 2
