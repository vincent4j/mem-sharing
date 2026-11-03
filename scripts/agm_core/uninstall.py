"""Exact-preview whole-machine removal with independent per-Agent memory copies.

No current installation detection can discard a previously connected reader.
Public historical originals are copied intact; active reading instructions are
detached from product-only governance. Unknown content/dependencies fail closed.
"""
import argparse
import copy
import json
import os
from pathlib import Path
import re
import socket
import stat
import subprocess
import sys
from datetime import datetime, timezone, timedelta
from urllib.parse import unquote, urlsplit

from . import entries, paths, registry, user_install, versions
from .layout import resolve_layout
from . import policy_migration, uninstall_memory
from . import uninstall_recovery as recovery

COMMAND = 'uninstall-machine'
RETURN_DIR = 'memsharing-return'


def _append_directories(changes, path, home):
    missing = []
    current = Path(path)
    while current != Path(home) and recovery.snapshot(current)['kind'] == 'absent':
        missing.append(current)
        current = current.parent
    for directory in reversed(missing):
        key = str(directory)
        changes.setdefault(key, {'path': key, 'before': {'kind':'absent'},
                                  'after': {'kind':'directory','mode':0o700}, 'stage':'return'})


def _change(changes, path, after, stage):
    path = str(path)
    before = recovery.snapshot(path)
    if path in changes:
        changes[path]['after'] = after
        return
    if before != after:
        changes[path] = {'path': path, 'before': before, 'after': after, 'stage': stage}


def _file(raw, mode=0o600):
    return {'kind': 'file', 'hex': raw.hex(), 'mode': mode}


def _without_object(raw, obj):
    """Only verified created units may be removed; never whole private files."""
    if obj['ownership'] != 'created' or not obj.get('fingerprint'):
        raise recovery.Conflict('Dependency ownership not proven: ' + obj['path'])
    from .transaction import Snapshot
    actual = registry._unit_fingerprint(Snapshot('file',raw,0o600), obj)
    if actual != obj['fingerprint']['value']:
        raise recovery.Conflict('Managed dependency drift: ' + obj['path'])
    if obj.get('lifecycle'):
        return entries.remove_lifecycle_unit(raw, obj)
    if obj.get('marker'):
        return entries.remove_block(raw, **obj['marker'], expected_fingerprint=actual)
    # Native import ownership can cover a complete file. Remove only its exact
    # public-source import line, never infer that unrelated bytes are ours.
    lines = raw.splitlines(keepends=True)
    matched = [line for line in lines if line.strip().startswith(b'@') and b'.mem-sharing/memories/MEMORY.md' in line]
    if len(matched) != 1:
        raise recovery.Conflict('Cannot isolate owned native import: ' + obj['path'])
    return raw.replace(matched[0], b'', 1)


def _preserve_ck(obj,roots,raw=None):
    marker=obj.get('marker') or {}
    keeper=(Path(obj['path']).name=='context-keeper' or obj.get('bridge_owner')=='context-keeper'
            or marker.get('start','').startswith(('<!-- context-keeper:','<!-- context-keeper:start')))
    if not keeper:return False
    target=obj.get('link_target') or ''
    if target:
        resolved=Path(os.path.normpath(str(Path(obj['path']).parent/target)))
        if any(resolved==Path(root) or resolved.is_relative_to(root) for root in roots):
            raise recovery.Conflict('Context Keeper depends on product; migrate it independently before uninstall: '+obj['path'])
    content=target.encode()
    if raw is not None and marker:
        span=entries.managed_span(raw,**marker)
        if span is not None:content+=raw[span[0]:span[1]]
    if any(str(root).encode() in content for root in roots):
        raise recovery.Conflict('Context Keeper depends on product; migrate it independently before uninstall: '+obj['path'])
    return True


def _redirect_import(raw, obj, old_index, new_index):
    """Explicitly approved dependency redirect; confers no deletion ownership."""
    if obj['kind']!='import' or obj.get('marker') is not None or obj['ownership']!='reused':
        raise recovery.Conflict('Not a proven native import dependency')
    if recovery.digest(raw)!=(obj.get('fingerprint') or {}).get('value'):
        raise recovery.Conflict('Native import whole-file fingerprint drift')
    token = ('@'+str(old_index)).encode()
    # Require exactly one complete import line. Whitespace/newline bytes are
    # outside the path token and remain untouched, including absent final LF.
    lines = raw.splitlines(keepends=True)
    matches = [line for line in lines if line.strip()==token]
    if len(matches)!=1 or raw.count(token)!=1:
        raise recovery.Conflict('Missing/ambiguous native public import')
    return raw.replace(token,('@'+str(new_index)).encode(),1)


def _standalone_memory(runtime):
    source = runtime.root
    original = {}
    for name in ('memories', 'references'):
        original.update(recovery.tree(source/name))
    if original[str(source/'memories')]['kind'] != 'directory' or recovery.snapshot(source/'memories/MEMORY.md')['kind'] != 'file':
        raise recovery.Conflict('Complete public memory/index required')
    active = {}
    # Exact known generated lines may be retired; custom prose is never guessed.
    from . import user_entries, public_layout
    generated = {user_entries.GOVERNANCE_RULES_TEXT}
    generated.add(policy_migration.LEGACY_TEMPLATES['governance'])
    for name in ('_OLD_GOVERNANCE_RULES_TEXT', '_OLD_GOVERNANCE'):
        value = getattr(public_layout, name, None)
        if isinstance(value, str): generated.add(value)
    expected_topic = user_entries.usage_convention_topic_text(runtime.code).encode()
    known_topics = (expected_topic,policy_migration.legacy('pre_route_topic',runtime),policy_migration.legacy('topic',runtime),policy_migration.legacy('old_topic',runtime))
    for path, state in original.items():
        if state['kind'] == 'symlink':
            target = Path(os.path.normpath(str(Path(path).parent / state['target'])))
            if not target.is_relative_to(source) or str(target) not in original:
                raise recovery.Conflict('External/missing public memory symlink: '+path)
            try:resolved=Path(path).resolve(strict=True)
            except (RuntimeError,OSError) as exc:
                raise recovery.Conflict('Unreadable/cyclic public memory symlink: '+path) from exc
            if str(resolved) not in original or original[str(resolved)]['kind'] not in ('file','directory'):
                raise recovery.Conflict('Public memory symlink resolves outside readable assets: '+path)
            relative = str(Path(path).relative_to(source))
            active[relative] = {'kind':'symlink','target':os.path.relpath(target,Path(path).parent)}
            continue
        if state['kind']=='directory':
            active[str(Path(path).relative_to(source))]=dict(state)
            continue
        if state['kind'] != 'file': continue
        relative = str(Path(path).relative_to(source))
        raw = bytes.fromhex(state['hex'])
        if relative == 'memories/topics/使用约定.md' and raw in known_topics:
            raw = ('# 使用约定\n\n公共记忆已归还本 Agent 独立维护。按索引、主题概要、全文顺序读取；'
                   '只在用户授权范围内修改。历史原文保存在 original/，不作为现行操作指令。\n').encode()
        elif relative == 'memories/MEMORY.md':
            old_contract=policy_migration.legacy('old_contract',runtime)
            if old_contract in raw:
                if raw.count(old_contract)!=1:raise recovery.Conflict('Duplicate public legacy header')
                raw=raw.replace(old_contract,'读取契约：先读索引，再按需读取主题概要与全文；相对链接以文档自身目录解析。\n'.encode(),1)
            kept = []
            for line in raw.splitlines(keepends=True):
                text = line.decode('utf-8',errors='surrogateescape').rstrip('\r\n')
                if text in generated or text.startswith('按需操作指南：/mem-sharing 菜单、绝对命令与公共记忆维护规则由主题'):
                    continue
                kept.append(line)
            raw = b''.join(kept)
        # legacy-v0 is explicitly historical; preserve all original bytes.
        historical = relative.startswith(('memories/legacy-v0-', 'original/'))
        # Remap absolute references to public material into relative links from
        # this document. The same closed graph works in each Agent's copy.
        if relative.endswith('.md'):
            text = raw.decode('utf-8',errors='surrogateescape')
            def remap(match):
                target = match.group(1)
                plain = unquote(target.strip('<>'))
                suffix = ''
                if '#' in plain:plain,suffix=plain.split('#',1);suffix='#'+suffix
                if plain.startswith(str(source)+'/'):
                    resolved = Path(os.path.normpath(plain))
                    if str(resolved) not in original:
                        raise recovery.Conflict('Missing absolute public reference: '+plain)
                    local=os.path.relpath(resolved,Path(path).parent)+suffix
                    if target.startswith('<'):local='<'+local+'>'
                    return match.group(0).replace(target,local,1)
                return match.group(0)
            text=re.sub(r'\]\(\s*(<[^>]+>|[^\s)]+)',remap,text)
            text=re.sub(r'^\s*\[[^\]]+\]:\s*(<[^>]+>|\S+)',remap,text,flags=re.M)
            text=re.sub(r'^\s*@([^\s]+)\s*$',remap,text,flags=re.M)
            raw=text.encode('utf-8',errors='surrogateescape')
        if not historical:
            if any(value.encode() in raw for value in (str(runtime.root),str(runtime.code),str(versions.root(runtime)))):
                raise recovery.Conflict('Unresolved active product dependency: ' + path)
        active[relative] = _file(raw, state['mode'])
    # Static document closure: relative Markdown links and native imports must
    # resolve within the complete copy, even if the host has never loaded it.
    for relative, state in active.items():
        if state['kind']!='file':continue
        if not relative.endswith('.md'):
            continue
        text = bytes.fromhex(state['hex']).decode('utf-8',errors='replace')
        targets=re.findall(r'\]\(\s*(<[^>]+>|[^\s)]+)',text)
        targets+=re.findall(r'^\s*\[[^\]]+\]:\s*(<[^>]+>|\S+)',text,re.M)
        targets+=re.findall(r'^\s*@([^\s]+)\s*$',text,re.M)
        for target in targets:
            target = unquote(target.strip('<>'))
            if urlsplit(target).scheme or target.startswith('#'): continue
            target = target.split('#',1)[0]
            resolved = (source / relative).parent / target
            resolved = Path(os.path.normpath(str(resolved)))
            if not resolved.is_relative_to(source) or str(resolved) not in original:
                raise recovery.Conflict('Memory link closure failed: ' + relative + ' -> ' + target)
    return original, active


def _verify_inventory(runtime):
    root = versions.root(runtime)
    if not root.exists(): return
    allowed = {str(root)}
    for release_file in sorted(root.glob('*/*/release.json')):
        release = json.loads(release_file.read_text())
        # Existing release encoding is the shared canonical legacy encoder.
        from .legacy_import import encoded
        marker = encoded({'product_id':'mem-sharing','source':release['source'],'files':release['files']})
        item = {'slot':str(release_file.parent),'release':release,'marker_hex':marker.hex()}
        versions.verify(runtime,item)
        allowed.update(recovery.tree(release_file.parent))
        allowed.add(str(release_file.parent.parent))
    activation = root/'activations'
    if activation.exists():
        allowed.add(str(activation))
        for path in activation.iterdir():
            if recovery.snapshot(path)['kind']!='file':
                raise recovery.Conflict('Unknown activation receipt')
            receipt = json.loads(path.read_text())
            registry._keys(receipt,'schema_version operation_id release journal registry_sha256 phase proof','activation receipt')
            if receipt['schema_version']!=1 or receipt['phase'] not in ('before','after') or path.name!=receipt['operation_id']+'-'+receipt['phase']+'.json':
                raise recovery.Conflict('Invalid activation receipt identity')
            versions.verify(runtime,receipt['release'])
            versions._proof(runtime,receipt['proof'],receipt['operation_id'])
            if not versions.installed_before(runtime,receipt['release']):
                raise recovery.Conflict('Activation has no verified installation proof')
            allowed.add(str(path))
    if set(recovery.tree(root)) != allowed:
        raise recovery.Conflict('Unknown version inventory content')


def _verify_backups(runtime, ledger):
    """A backup namespace is not blanket deletion ownership over its children."""
    observations = {}
    if not runtime.backups.exists():return observations
    for directory in runtime.backups.iterdir():
        if recovery.snapshot(directory)['kind']!='directory':
            raise recovery.Conflict('Unknown backup object: '+str(directory))
        imported = ledger.get('legacy_import')
        if imported and directory==Path(imported['manifest_path']).parent:
            journal_path = runtime.home/('.mem-sharing-install-'+imported['operation_id'])/'journal.json'
            journal, bound = user_install._load_journal(journal_path)
            if bound!=runtime or journal['status']!='committed':
                raise recovery.Conflict('Import backup lacks committed ownership')
            source = journal['plan']['legacy_import']
            if source['manifest']!=imported['manifest_path'] or source['source_tree_sha256']!=imported['source_tree_sha256']:
                raise recovery.Conflict('Import backup ledger identity mismatch')
            user_install._snapshot_verify(journal['plan'],source['snapshot'])
            if {p.name for p in directory.iterdir()}!={'source','import-manifest.json'}:
                raise recovery.Conflict('Unknown import backup child')
            continue
        migration = ledger.get('migration')
        if migration and directory==Path(migration['archive_root']):
            registry.verify_archived_references(migration)
            expected = {str(directory)}
            for item in migration['reference_map'].values():
                path = Path(item['path']);expected.add(str(path))
                while path.parent!=directory:
                    path=path.parent;expected.add(str(path))
            if set(recovery.tree(directory))!=expected:
                raise recovery.Conflict('Unknown archived backup child')
            continue
        manifest = directory/'manifest.json'
        if (directory.name.startswith('upgrade-')
                and recovery.snapshot(manifest)['kind']=='absent'):
            from .uninstall_compat import verify_upgrade_backup
            observations.update(verify_upgrade_backup(runtime,directory))
            continue
        if (directory.name.startswith('migration-')
                and recovery.snapshot(manifest)['kind']=='absent'):
            from .uninstall_compat import verify_public_layout_backup
            observations.update(verify_public_layout_backup(runtime,directory))
            continue
        if recovery.snapshot(manifest)['kind']!='file':
            raise recovery.Conflict('Unknown backup directory: '+str(directory))
        receipt = json.loads(manifest.read_text())
        registry._keys(receipt,'schema_version operation status registry_path created_directories entries error','transaction backup')
        if receipt['schema_version']!=1 or receipt['status'] not in ('committed','rolled_back'):
            raise recovery.Conflict('Pending/unknown transaction backup')
        expected = {'manifest.json'}
        for item in receipt['entries']:
            before = item['before']
            if before['kind']=='file':
                name = before['backup']
                if not isinstance(name,str) or Path(name).name!=name:
                    raise recovery.Conflict('Unsafe transaction backup name')
                saved = directory/name
                if recovery.snapshot(saved)['kind']!='file' or recovery.digest(saved.read_bytes())!=before['fingerprint']:
                    raise recovery.Conflict('Transaction backup bytes missing/drifted')
                expected.add(name)
        if {p.name for p in directory.iterdir()}!=expected:
            raise recovery.Conflict('Unknown transaction backup child')

    return observations

def _strict_json(path):
    value=json.loads(Path(path).read_bytes(),object_pairs_hook=registry._no_duplicates)
    if not isinstance(value,dict):raise recovery.Conflict('Expected JSON object: '+str(path))
    return value


def _host_staging_receipt(runtime, root, backup):
    """Only retire a receipt-only fixed host root; external evidence never grants deletion."""
    receipt_path=root/'host-receipt.json'
    state=recovery.snapshot(receipt_path)
    if state['kind']!='file' or state['mode']!=0o600 or {p.name for p in root.iterdir()}!={'host-receipt.json'}:
        raise recovery.Conflict('Host staging must contain only its private retirement receipt')
    receipt=_strict_json(receipt_path)
    registry._keys(receipt,'schema_version product_id kind home host staging_root backup_root backup_tree_sha256 generated_at status approval terminal_evidence','host receipt')
    if (type(receipt['schema_version']) is not int or receipt['schema_version']!=1 or
            receipt['product_id']!='mem-sharing' or receipt['kind']!='host-staging-retired' or
            receipt['home']!=str(runtime.home) or receipt['host']!=socket.gethostname() or
            receipt['staging_root']!=str(root) or receipt['status']!='completed'):
        raise recovery.Conflict('Host staging retirement identity/state mismatch')
    registry._time(receipt['generated_at']);registry._digest(receipt['backup_tree_sha256'])
    evidence=receipt['approval'];registry._keys(evidence,'digest confirmed_at reference','host cleanup approval')
    registry._digest(evidence['digest'])
    registry._evidence({k:evidence[k] for k in ('confirmed_at','reference')})
    if evidence['reference'].startswith('<'):raise recovery.Conflict('Host cleanup requires actual independent approval')
    generated=datetime.fromisoformat(receipt['generated_at'][:-1]+'+00:00')
    if generated>datetime.now(timezone.utc)+timedelta(seconds=5):raise recovery.Conflict('Host receipt timestamp is in the future')
    if datetime.fromisoformat(evidence['confirmed_at'][:-1]+'+00:00')>generated:
        raise recovery.Conflict('Host receipt predates its approval')
    external=recovery.safe(receipt['backup_root'])
    forbidden=[runtime.root,runtime.code,versions.root(runtime),backup,
               runtime.code.parent/'mem-sharing-sources',runtime.code.parent/'mem-sharing-runtimes',root]
    if external==runtime.home or runtime.home.is_relative_to(external) or any(
            external==p or external.is_relative_to(p) or p.is_relative_to(external) for p in forbidden):
        raise recovery.Conflict('Host evidence must be independent of all product/removal/recovery roots')
    if recovery.snapshot(external)['kind']!='directory':raise recovery.Conflict('Host evidence directory missing/unsafe')
    rows=receipt['terminal_evidence']
    if not isinstance(rows,list):raise recovery.Conflict('Host terminal evidence must be a list')
    terminal={'completed','failed','rejected','approval_required','gaps','recovered'}
    flows={'dependency','bootstrap','machine','enable','remove','ck','recover','uninstall','ck-uninstall','fusion'}
    known={'operation.json','release-request.json'}|{flow+'-approval.json' for flow in flows}
    # Reject unknown names/types before reading any artifact bytes.
    for directory in external.iterdir():
        if not re.fullmatch('op-[A-Za-z0-9]+',directory.name) or recovery.snapshot(directory)['kind']!='directory':
            raise recovery.Conflict('Unknown host evidence directory')
        for path in directory.iterdir():
            if path.name not in known or path.is_symlink() or not path.is_file():
                raise recovery.Conflict('Unknown/unsafe host evidence artifact')
    inventory=recovery.tree(external)
    expected={str(external)};seen=set();mtime={};observed={str(receipt_path):state}
    for row in rows:
        registry._keys(row,'dir record_state in_memory_running journal_status artifacts','host terminal evidence')
        name=row['dir']
        if not isinstance(name,str) or not re.fullmatch('op-[A-Za-z0-9]+',name) or name in seen:
            raise recovery.Conflict('Unknown/duplicate host operation directory')
        seen.add(name);directory=external/name;expected.add(str(directory))
        if inventory.get(str(directory),{}).get('kind')!='directory' or row['in_memory_running'] is not False:
            raise recovery.Conflict('Host operation active/unknown')
        artifacts=row['artifacts']
        if not isinstance(artifacts,list) or not artifacts:raise recovery.Conflict('Host operation evidence is empty/unknown')
        names=set()
        for artifact in artifacts:
            registry._keys(artifact,'name sha256','host artifact')
            basename=artifact['name']
            if basename not in known or basename in names:raise recovery.Conflict('Unknown/duplicate host artifact')
            registry._digest(artifact['sha256']);names.add(basename)
            path=directory/basename;expected.add(str(path));node=inventory.get(str(path),{})
            if node.get('kind')!='file' or recovery.digest(bytes.fromhex(node['hex']))!=artifact['sha256']:
                raise recovery.Conflict('Host evidence bytes/hash mismatch: '+str(path))
            _strict_json(path)  # Only known JSON artifacts are read, never arbitrary files.
            mtime[str(path)]=path.stat().st_mtime_ns
        if 'operation.json' not in names:
            if row['record_state']!='no_operation_record' or row['journal_status'] is not None:
                raise recovery.Conflict('Unknown orphan host evidence state')
            if any(generated.timestamp()-mtime[str(directory/n)]/1e9<=600 for n in names):
                raise recovery.Conflict('Orphan host evidence has not expired its ten-minute TTL')
            continue
        operation=_strict_json(directory/'operation.json')
        keys=set('id flow phase journal home host state started_at'.split())
        if set(operation) not in (keys,keys-{'journal'}):raise recovery.Conflict('Unknown host operation record keys')
        phase_terminal=terminal|({'already_prepared','identity_missing','payload_missing'}
            if operation['phase']=='preview' else {'stale_plan','no_pending_plan'} if operation['phase']=='execute' else set())
        if operation['flow']=='bootstrap' and operation['phase']=='execute':phase_terminal|={'acquired'}
        if operation['flow']=='fusion':
            phase_terminal = {'completed','failed'} if operation['phase']=='preview' else {'completed','failed','rejected','stale_plan','no_pending_plan'}
        journal=operation.get('journal')
        if operation['flow']=='fusion' and journal is not None:
            raise recovery.Conflict('Fusion journal-bearing operation requires explicit recovery')
        # Preserve the original running/unknown record bytes. Only a separately
        # verified original terminal journal can establish derived recovery.
        recovered=(operation['flow']!='fusion' and row['record_state']=='recovered' and journal is not None and
                   operation['state'] in phase_terminal|{'running','unknown'})
        direct=(operation['state'] in phase_terminal and row['record_state']==operation['state'])
        if (not isinstance(operation['id'],str) or not operation['id'] or operation['flow'] not in flows or
                operation['phase'] not in ('preview','execute') or operation['home']!=str(runtime.home) or
                operation['host']!=socket.gethostname() or not (direct or recovered)):
            raise recovery.Conflict('Host operation is not a proven terminal record')
        registry._time(operation['started_at'])
        if journal is None:
            if row['journal_status'] is not None:raise recovery.Conflict('Host journal evidence mismatch')
        else:
            path=recovery.safe(journal)
            owned=(path.name=='journal.json' and path.parent.parent==runtime.home and path.parent.name.startswith('.mem-sharing-install-')) or (
                path.name in ('manifest.json','journal.json') and path.is_relative_to(runtime.backups))
            if not owned or recovery.snapshot(path)['kind']!='file':
                raise recovery.Conflict('Original host kernel journal missing/unsafe')
            document=_strict_json(path);status=document.get('status')
            layout=document.get('plan',{}).get('layout',{})
            if (status not in ('committed','rolled_back') or row['journal_status']!=status or
                    (layout.get('root')!=str(runtime.root) and document.get('registry_path')!=str(runtime.registry))):
                raise recovery.Conflict('Original host kernel journal is not a proven terminal operation')
            observed[str(path)]=recovery.snapshot(path)
    if set(inventory)!=expected:raise recovery.Conflict('Host evidence tree contains unknown/missing material')
    if _runtime_digest(external)!=receipt['backup_tree_sha256']:raise recovery.Conflict('Host evidence whole-tree hash mismatch')
    observed.update(inventory)
    retained={'path':str(external),'reason':'宿主独立批准清理后外置的原始证据，仅保留与观察，不授删除权',
              'observation_root':str(external),'mtime_ns':mtime,
              'non_active_evidence':{'receipt':str(receipt_path),'status':'completed',
                                     'backup_tree_sha256':receipt['backup_tree_sha256'],
                                     'cleanup_approval_digest':evidence['digest']}}
    return retained,observed


def _extra_inventory(runtime, *, backup):
    """Bounded product namespaces only, never a scan through arbitrary HOME."""
    retained, observed, deletes = [], {}, []
    for path in (runtime.home/'.mem-sharing-upgrade.json',runtime.home/'.mem-sharing-source.lock',
                 runtime.home/'.mem-sharing-install.lock',runtime.lock,runtime.transaction_lock):
        state=recovery.snapshot(path);observed[str(path)]=state
        if state['kind']!='absent':
            raise recovery.Conflict('Active/unknown operation marker or writer lock: '+str(path))
    for directory in sorted(runtime.home.glob('.mem-sharing-install-*')):
        if recovery.snapshot(directory)['kind']!='directory':
            raise recovery.Conflict('Unknown installation evidence object: '+str(directory))
        path=directory/'journal.json'
        if recovery.snapshot(path)['kind']!='file':
            raise recovery.Conflict('Installation evidence lacks known journal: '+str(directory))
        raw=json.loads(path.read_text())
        command=raw.get('plan',{}).get('command')
        if command=='install-machine':journal,bound=user_install._load_journal(path)
        elif command=='upgrade-machine':
            from . import upgrade
            journal,bound=upgrade._load_journal(path)
        else:raise recovery.Conflict('Unknown historical installation journal: '+str(path))
        if bound!=runtime or journal['status'] not in ('committed','rolled_back'):
            raise recovery.Conflict('Incomplete installation evidence: '+str(path))
        observed.update(recovery.tree(directory))
        retained.append({'path':str(directory),'reason':'历史安装/升级的独立恢复证据，保留例外已列入预览',
                         'non_active_evidence':{'journal':str(path),'status':journal['status'],
                         'journal_sha256':recovery.digest(path.read_bytes()),'active_guard':'absent'}})
    sources=runtime.code.parent/'mem-sharing-sources'
    observed.update(recovery.tree(sources))
    if sources.exists():
        from . import plugin_release
        allowed={str(sources)}
        for receipt in sources.glob('*/*/release.json'):
            directory=receipt.parent
            manifest=plugin_release._read_manifest(receipt)
            plugin_release._export_source(directory,manifest)
            expected=sources/manifest['source']['version']/manifest['source']['tree_sha256']
            if directory!=expected:raise recovery.Conflict('Export path identity mismatch')
            allowed.update(recovery.tree(directory));allowed.add(str(directory.parent))
        if set(recovery.tree(sources))!=allowed:
            raise recovery.Conflict('Unknown durable export/staging: '+str(sources))
        deletes.append(sources)
    assets=runtime.code.parent/'mem-sharing-runtimes'
    observed.update(recovery.tree(assets))
    if assets.exists():
        _verify_runtime_assets(assets)
        deletes.append(assets)
    # Host staging contains potentially still-active RPC requests. Without a
    # host-side inactivity/ownership receipt this is an explicit blocker.
    for name in ('mem-sharing-plugin-staging',):
        root=runtime.code.parent/name
        state=recovery.snapshot(root);observed[str(root)]=state
        if state['kind']=='directory' and not any(root.iterdir()):deletes.append(root)
        elif state['kind']=='directory':
            evidence,inputs=_host_staging_receipt(runtime,root,backup)
            retained.append(evidence);observed.update(inputs);deletes.append(root)
        elif state['kind']!='absent':
            raise recovery.Conflict('Host asset ownership/lease verification required: '+str(root))
    return retained,observed,deletes


def _runtime_digest(root):
    root=Path(root)
    result=__import__('hashlib').sha256()
    def add(item):
        result.update((json.dumps(item,ensure_ascii=False,separators=(',',':'))+'\n').encode())
    def visit(path):
        state=recovery.snapshot(path);relative=str(path.relative_to(root))
        if relative=='.':relative=''
        if state['kind']=='directory':
            if relative:add([relative,'directory'])
            for child in sorted(path.iterdir(),key=lambda p:p.name.encode('utf-16-be')):visit(child)
        elif state['kind']=='file':add([relative,'file',state['mode']&0o777,recovery.digest(bytes.fromhex(state['hex']))])
        elif state['kind']=='symlink':
            target=path.resolve(strict=True)
            if target==root or not target.is_relative_to(root):raise recovery.Conflict('Runtime link escapes or targets payload root')
            add([relative,'link',state['target']])
        else:raise recovery.Conflict('Unknown runtime node')
    visit(root)
    return result.hexdigest()


def _verify_runtime_assets(root):
    allowed={str(root)}
    for marker in root.glob('*/*/asset.json'):
        directory=marker.parent
        if marker.is_symlink() or not marker.is_file():raise recovery.Conflict('Unsafe runtime receipt')
        receipt=json.loads(marker.read_text())
        candidates=[a for a in RUNTIME_ASSETS if a['id']==directory.parent.name and a['arch']==directory.name]
        if len(candidates)!=1:raise recovery.Conflict('Unknown private runtime identity')
        asset=candidates[0]
        if type(receipt.get('schema')) is not int or receipt['schema']!=1 or receipt.get('verified') is not True or receipt!={'schema':1,'id':asset['id'],'sha256':asset['sha256'],'home':str(root),'host':socket.gethostname(),'verified':True}:
            raise recovery.Conflict('Runtime asset receipt identity mismatch')
        if hasattr(os,'getuid') and (marker.stat().st_uid!=os.getuid() or directory.stat().st_uid!=os.getuid()):
            raise recovery.Conflict('Foreign runtime owner')
        if os.path.lexists(directory/'lease.json'):
            raise recovery.Conflict('Runtime lease present; finish host operation first')
        if recovery.snapshot(directory/'payload')['kind']!='directory' or _runtime_digest(directory/'payload')!=asset['treeSha256']:
            raise recovery.Conflict('Runtime payload identity drift')
        names={'asset.json','payload'}
        for path in directory.iterdir():
            if path.name in names:continue
            if not re.fullmatch(r'download-[a-f0-9-]+\.tar\.gz',path.name) or recovery.snapshot(path)['kind']!='file':
                raise recovery.Conflict('Unknown/interrupted runtime staging')
            raw=path.read_bytes()
            if len(raw)!=asset['bytes'] or recovery.digest(raw)!=asset['sha256']:
                raise recovery.Conflict('Runtime download archive drift')
            names.add(path.name)
        allowed.update(recovery.tree(directory));allowed.add(str(directory.parent))
    if set(recovery.tree(root))!=allowed:
        raise recovery.Conflict('Host asset ownership/lease verification required: '+str(root))


def _interpreter_plan(runtime,roots,backup):
    executable=Path(sys.executable).resolve()
    body={'kind':'existing','interpreter':str(executable),
          'executable_sha256':recovery.digest(executable.read_bytes())}
    if any(executable.is_relative_to(root) for root in roots):
        assets=runtime.code.parent/'mem-sharing-runtimes'
        candidates=[p for p in assets.glob('*/*/payload') if executable.is_relative_to(p)]
        if len(candidates)!=1:
            raise recovery.Conflict('Running interpreter is inside removable product without trusted relocatable runtime')
        source=candidates[0]
        body.update(kind='bundled',source=str(source),destination=str(backup/'python-runtime'),
                    interpreter=str(backup/'python-runtime'/executable.relative_to(source)))
    else:
        if any(Path(sys.base_prefix).resolve().is_relative_to(root) for root in roots):
            raise recovery.Conflict('Interpreter stdlib depends on removable product')
    return body


def _prepare_interpreter(plan):
    item=plan['recovery_runtime']
    put=recovery.put_direct if plan.get('memory_return')=='native-direct-v1' else recovery.put
    if item['kind']=='bundled':
        source=Path(item['source']);destination=Path(item['destination'])
        snapshots=[]
        for change in plan['changes']:
            path=Path(change['path'])
            if path==source or path.is_relative_to(source):snapshots.append((path,change['before']))
        snapshots.sort(key=lambda p:(p[1]['kind']!='directory',len(p[0].parts),str(p[0])))
        modes=[]
        for path,state in snapshots:
            target=destination/path.relative_to(source)
            if state['kind']=='directory':
                modes.append((target,state))
                state=dict(state,mode=state['mode']|0o700)
            if state['kind']=='symlink' and Path(state['target']).is_absolute():
                link=Path(state['target'])
                if not link.is_relative_to(source):raise recovery.Conflict('External interpreter symlink')
                state={'kind':'symlink','target':os.path.relpath(destination/link.relative_to(source),target.parent)}
            put(target,state)
        for target,state in reversed(modes):put(target,state)
    recovery.verify_interpreter(plan)
    # Execute the frozen recovery code with the independent interpreter before
    # any original output is changed; -I -S -B avoids user startup/site/pycache.
    probe=subprocess.run([item['interpreter'],'-I','-S','-B',str(Path(plan['backup_dir'])/'recover.py'),
                          '--manifest',str(Path(plan['backup_dir'])/'manifest.json'),'--action','restore'],
                         capture_output=True,text=True,timeout=60)
    if probe.returncode!=5 or json.loads(probe.stdout).get('status')!='approval_required':
        raise recovery.Conflict('Independent recovery interpreter/stdlib probe failed')


_CK_AUDIT_NAME = re.compile(r'ck-install-([A-Za-z0-9][A-Za-z0-9._-]*)\.json')
_CK_SHA256 = re.compile(r'[0-9a-f]{64}')


def _recorded_link_target(name, target):
    """Lexically normalize a recorded symlink target against its own parent.

    Pure string normalization only — never resolve() and never touch the
    current filesystem — so a historical audit stays checkable long after
    the link itself is gone. Returns None for unusable input.
    """
    if not isinstance(target, str) or not target:
        return None
    return os.path.normpath(os.path.join(str(Path(name).parent), target))


def _ck_audit_journal(path, runtime):
    """Strictly recognize a completed CK audit journal (ck_install producer).

    A name match alone is never trusted. The document must carry the exact
    producer schema {plan, approval, status, result, after} with the single
    success terminal state 'configured'; the plan must be canonical-digest
    self-consistent, bound to this home/registry, to its own path, metadata
    scope and filename main-operation id, and corroborated by its historical
    main journal through the existing loaders (same home, same operation,
    committed). The recorded result and after nodes must match the producer's
    readback contract for that exact plan. Later main-product versions,
    registry growth, or a since-removed CK checkout/skill links never count
    as forgery: only structure, identity and corroboration are checked, and
    nothing is ever replayed. Every failure keeps the original fail-closed
    conflict so unclear operations, locks, forged names and unknown keys
    still block the whole uninstall.
    """
    from . import ck_install, legacy_import as legacy, migrate
    match = _CK_AUDIT_NAME.fullmatch(path.name)
    if (not match or path.is_symlink() or not path.is_file()
            or stat.S_IMODE(path.stat().st_mode) != 0o600):
        raise recovery.Conflict('Unknown runtime metadata or writer lock')
    document = _strict_json(path)
    plan = document.get('plan')
    approval = document.get('approval')
    plan_keys = {'schema_version', 'command', 'scope', 'main_operation_id', 'home',
                 'platform_config', 'registry_path', 'registry_sha256', 'agents',
                 'skipped_upstream_agents', 'main_journal', 'source', 'preview_argv',
                 'argv', 'interpreter', 'upstream_preview', 'observations',
                 'skill_entries', 'rule_files', 'journal', 'metadata_scopes', 'changes',
                 'plan_sha256'}
    structural = (
        set(document) == {'plan', 'approval', 'status', 'result', 'after'}
        and document['status'] == 'configured'
        and isinstance(plan, dict) and set(plan) == plan_keys
        and isinstance(approval, dict) and set(approval) == plan_keys | {'confirmed_at', 'reference'}
        and {key: approval[key] for key in plan_keys} == plan
        and plan['schema_version'] == 1 and plan['command'] == 'install-context-keeper'
        and plan['scope'] == 'user' and plan['home'] == str(runtime.home)
        and plan['registry_path'] == str(runtime.registry)
        and plan['journal'] == str(path) and plan['metadata_scopes'] == [str(path)]
        and plan['main_operation_id'] == match.group(1)
        and isinstance(plan['agents'], list) and plan['agents']
        and all(agent in ck_install.LABELS for agent in plan['agents'])
        and isinstance(plan['skill_entries'], list) and isinstance(plan['rule_files'], list)
        and plan['skill_entries'] and plan['rule_files']
        and isinstance(plan['source'], dict) and plan['source'].get('commit') == ck_install.PIN
        and isinstance(plan['source'].get('root'), str) and isinstance(plan['source'].get('files'), dict)
        and legacy.digest(legacy.encoded({key: value for key, value in plan.items()
                                           if key != 'plan_sha256'})) == plan['plan_sha256'])
    if not structural:
        raise recovery.Conflict('Unknown runtime metadata or writer lock')
    try:
        registry._evidence({key: approval[key] for key in ('confirmed_at', 'reference')})
    except (ValueError, TypeError):
        raise recovery.Conflict('Unknown runtime metadata or writer lock')
    # Corroborate the recorded main operation via its still-present historical
    # journal; upgrades retain old operation evidence, so absence is anomalous.
    main = runtime.home / ('.mem-sharing-install-' + plan['main_operation_id']) / 'journal.json'
    if (plan['main_journal'].get('path') != str(main)
            or main.is_symlink() or not main.is_file()):
        raise recovery.Conflict('Unknown runtime metadata or writer lock')
    saved = migrate._json(main)
    command = saved.get('plan', {}).get('command') if isinstance(saved.get('plan'), dict) else None
    if saved.get('status') != 'committed' or command not in ('install-machine', 'upgrade-machine'):
        raise recovery.Conflict('Unknown runtime metadata or writer lock')
    if command == 'install-machine':
        _, bound = user_install._load_journal(main)
    else:
        from . import upgrade
        _, bound = upgrade._load_journal(main)
    if bound != runtime:
        raise recovery.Conflict('Unknown runtime metadata or writer lock')
    # Recorded readback must mirror the producer's verified result contract.
    # The plan digest is not a root of trust: every recorded set and node is
    # re-derived or shape-checked against the real producer schema.
    result, after = document['result'], document['after']
    skills, rules = plan['skill_entries'], plan['rule_files']
    source_root = os.path.normpath(str(plan['source']['root']))
    files = plan['source']['files']
    expected_skills = sorted(str(runtime.home / root / 'context-keeper')
                             for agent in plan['agents'] for root in ck_install.ROOTS[agent])
    expected_rules = sorted(str(runtime.home / ck_install.RULES[agent]) for agent in plan['agents'])
    safe_files = (
        isinstance(files, dict) and files
        and {'SKILL.md', 'scripts/install.py'} <= set(files)
        and all(isinstance(name, str) and name and not Path(name).is_absolute()
                and '..' not in Path(name).parts for name in files)
        and all(isinstance(item, dict) and set(item) == {'sha256', 'mode'}
                and isinstance(item.get('sha256'), str)
                and _CK_SHA256.fullmatch(item['sha256'])
                and isinstance(item.get('mode'), int) and 0 <= item['mode'] <= 0o777
                for item in files.values()))
    consistent = (
        isinstance(result, dict) and result.get('scope') == 'user'
        and result.get('project') is None
        and result.get('configured_agents') == [ck_install.LABELS[agent] for agent in plan['agents']]
        and result.get('installed') == skills and result.get('removed') == []
        and isinstance(result.get('bridges'), list)
        and all(isinstance(item, dict) and item.get('action') in
                ('created', 'unchanged', 'updated', 'prepended', 'appended')
                for item in result['bridges'])
        and [item.get('file') for item in result['bridges']] == rules
        and sorted(skills) == expected_skills and sorted(rules) == expected_rules
        and isinstance(after, dict) and set(after) == set(skills) | set(rules)
        and all(isinstance(after.get(name), dict) and set(after[name]) == {'kind', 'target'}
                and after[name]['kind'] == 'symlink'
                and _recorded_link_target(name, after[name]['target']) == source_root
                for name in skills)
        and all(isinstance(after.get(name), dict) and set(after[name]) == {'kind', 'sha256', 'mode'}
                and after[name]['kind'] == 'file'
                and isinstance(after[name]['sha256'], str)
                and _CK_SHA256.fullmatch(after[name]['sha256'])
                and isinstance(after[name]['mode'], int)
                and 0 <= after[name]['mode'] <= 0o777
                for name in rules)
        and safe_files)
    if not consistent:
        raise recovery.Conflict('Unknown runtime metadata or writer lock')
    return document


def preview(*, home, backup_dir, host_obligation=None, tool_identity=None):
    runtime = resolve_layout(home)
    runtime.validate_paths()
    if os.path.lexists(runtime.home/'.mem-sharing-upgrade.json'):
        raise recovery.Conflict('Pending machine operation; recover it first')
    backup = recovery.safe(backup_dir)
    roots = [runtime.root, runtime.code, versions.root(runtime)]
    retained,extras,extra_deletes=_extra_inventory(runtime,backup=backup)
    roots+=extra_deletes
    if host_obligation and any(Path(host_obligation['source_dir'])==p or Path(host_obligation['source_dir']).is_relative_to(p) for p in roots):
        raise recovery.Conflict('Loaded host plugin source depends on removable product roots; independent migration required')
    if any(backup == p or backup.is_relative_to(p) or p.is_relative_to(backup) for p in roots):
        raise recovery.Conflict('Backup must be independent of all product roots')
    if recovery.snapshot(backup)['kind'] != 'absent' or not backup.parent.is_dir():
        raise recovery.Conflict('Backup must be a new directory in an existing real parent')
    config = policy_migration.config()
    allowed = paths.allowed_user_paths(config,None,home=str(runtime.home))
    ledger = registry.require_installed(registry.load_registry(runtime.registry,allowed_user_paths=allowed))
    if {p.name for p in runtime.root.iterdir()} - {'memories','references','backups','var'}:
        raise recovery.Conflict('Unknown object at public product root')
    # var/ holds the ledger plus, after a real CK install, that operation's
    # completed audit journal. Anything else — or any audit that is not a
    # strictly corroborated 'configured' record — still blocks here.
    for member in runtime.var.iterdir():
        if member.name == 'registry.json':
            continue
        _ck_audit_journal(member, runtime)
    user_install._code_matches(runtime,ledger['product'])
    _verify_inventory(runtime)
    historical_observations = _verify_backups(runtime,ledger)
    for root in roots:
        if root.is_symlink():
            raise recovery.Conflict('Product root symlink: ' + str(root))
    changes = {}
    original = uninstall_memory.public_sources(runtime)
    active = None
    public_body = uninstall_memory.public_body(runtime, original)
    _, controls, observed = policy_migration.retire_controls(ledger)
    for path, raw in controls.items():
        _change(changes,path,_file(raw,recovery.snapshot(path)['mode']),'detach')
    units = list(ledger['machine']['objects'].values()) + list(ledger['shared_objects'].values())
    connected = set()
    user_paths = {agent: Path(paths.expand_path(data['user_entry'],home=str(runtime.home))) for agent,data in config.items()}
    observations = dict(extras)
    observations.update(historical_observations)
    observations.update(observed)
    observations.update({str(p):recovery.snapshot(p) for p in user_paths.values()})
    for obj in units:
        connected.update(obj['agents'])
    # Historical registration persists even if a binary is no longer installed.
    connected.update(a for a,r in ledger['machine']['agents'].items() if r['static']['status']=='ready')
    for agent, path in user_paths.items():
        state = recovery.snapshot(path)
        if state['kind'] == 'file' and str(runtime.root).encode() in bytes.fromhex(state['hex']):
            connected.add(agent)
    if not connected:
        raise recovery.Conflict('No proven recipients; cannot discard the only public copy')
    ordered = [a for a in paths.AGENT_ORDER if a in connected]
    user_reference_redirects = []
    for agent in ordered:
        path = user_paths[agent]
        state = recovery.snapshot(path)
        if state['kind'] != 'file':
            raise recovery.Conflict('Connected Agent entry unavailable: ' + str(path))
        destination = path.parent / RETURN_DIR
        # Existing legacy return packages need the exact old producer closure;
        # a same-named user directory is never deletion permission.
        historical_proof = False
        if os.path.lexists(destination):
            if active is None:
                legacy_original,active=_standalone_memory(runtime)
                if legacy_original!=original:raise recovery.Conflict('Legacy source changed during inventory')
            expected = {}
            for relative, content in active.items():
                expected[str(destination/relative)] = content
            for source, content in original.items():
                if content['kind'] != 'absent':
                    expected[str(destination/'original'/Path(source).relative_to(runtime.root))] = content
            wanted = set(expected)
            for name in list(wanted):
                parent = Path(name).parent
                while parent.is_relative_to(destination):
                    wanted.add(str(parent))
                    if parent == destination: break
                    parent = parent.parent
            actual = recovery.tree(destination)
            if set(actual) != wanted or any(actual.get(k) != v for k,v in expected.items()):
                raise recovery.Conflict('Unknown/stale legacy return package; review required')
            observations.update(actual)
            roots.append(destination)
            historical_proof = True
        raw = bytes.fromhex(state['hex'])
        own_units = [obj for obj in units if obj['path']==str(path)]
        imports = [obj for obj in own_units if obj['kind']=='import']
        if len(imports)>1: raise recovery.Conflict('Multiple registered native imports')
        for obj in own_units:
            if _preserve_ck(obj,roots,raw): continue
            if obj['kind']=='import' and obj['ownership']=='reused':
                if recovery.digest(bytes.fromhex(state['hex']))!=(obj.get('fingerprint') or {}).get('value'):
                    raise recovery.Conflict('Native import whole-file fingerprint drift')
                token=('@'+str(runtime.root/'memories/MEMORY.md')).encode()
                if raw.count(token)!=1 or sum((line.removeprefix(b'\xef\xbb\xbf') if i==0 else line).strip()==token for i,line in enumerate(raw.splitlines()))!=1:
                    raise recovery.Conflict('Missing/ambiguous native public import')
                # Validate against original bytes before removing fallback units.
                continue
            raw = _without_object(raw,obj)
        if imports and imports[0]['ownership']=='reused':
            token=('@'+str(runtime.root/'memories/MEMORY.md')).encode()
            raw=raw.replace(token,b'',1)
        if (agent=='dsh' and not imports and
                ((tool_identity or {}).get('user_conversions') or {}).get('dsh_reference')=='explicit-single-path-to-return-v1'):
            from .uninstall_compat import detach_dsh_reference
            raw, proof = detach_dsh_reference(runtime,path,bytes.fromhex(state['hex']),raw,state['mode'])
            user_reference_redirects.append(proof)
        raw = uninstall_memory.retire_legacy_pointer(raw, path, proven=historical_proof)
        raw = uninstall_memory.strip_generated(raw,runtime,historical_proof=historical_proof)
        if uninstall_memory.contains_text(raw,uninstall_memory.LEGACY_GENERATED_GOVERNANCE):
            raise recovery.Conflict('Unproven historical governance; review required')
        uninstall_memory.require_no_product_dependency(raw,roots,home=runtime.home,document=path)
        _change(changes,path,_file(uninstall_memory.merge_native(raw,public_body),state['mode']),'detach')
    # Retain AGENTS.md, Claude @AGENTS.md, effective WorkBuddy/CK bridges.
    # Remove only proven product-dependent project units, never entire files.
    project_roots = []
    for record in ledger['projects'].values():
        for checkout, assembly in record['checkouts'].items():
            project_roots.append(checkout)
            for obj in assembly['objects'].values():
                if obj.get('marker') == policy_migration.DENIED: continue
                path = obj['path']
                state = recovery.snapshot(path)
                if _preserve_ck(obj,roots,bytes.fromhex(state['hex']) if state['kind']=='file' else None):continue
                if state['kind'] != 'file':
                    if obj['kind']=='skill_symlink':
                        target = obj.get('link_target') or ''
                        if any(target.startswith(str(p)+'/') for p in roots):
                            if obj['ownership']!='created' or registry._unit_fingerprint(__import__('agm_core.transaction',fromlist=['read_snapshot']).read_snapshot(path),obj)!=(obj.get('fingerprint') or {}).get('value'):
                                raise recovery.Conflict('Project link ownership/drift: '+path)
                            _change(changes,path,{'kind':'absent'},'detach')
                    continue
                raw = bytes.fromhex(changes[path]['after']['hex']) if path in changes else bytes.fromhex(state['hex'])
                if obj.get('marker'):
                    span = entries.managed_span(raw,**obj['marker'])
                    unit = b'' if span is None else raw[span[0]:span[1]]
                    if any(str(p).encode() in unit for p in roots):
                        _change(changes,path,_file(_without_object(raw,obj),state['mode']),'detach')
    for path, state in observed.items():
        if state['kind']!='file':continue
        after = changes[path]['after'] if path in changes else state
        if after['kind']=='file' and any(str(p).encode() in bytes.fromhex(after['hex']) for p in roots):
            raise recovery.Conflict('Unresolved project product dependency: '+path)
    # All roots are enumerated exactly; no shutil.rmtree and no default source
    # checkout/legacy ~/.agents-group deletion. Product bytes are deleted last.
    for root in roots:
        inventory = recovery.tree(root)
        for path,state in sorted(inventory.items(),key=lambda p:(p[1]['kind']=='directory',-len(Path(p[0]).parts),p[0])):
            if state['kind']=='absent': continue
            _change(changes,path,{'kind':'absent'},'delete_product')
            if state['kind']=='directory' and state['mode'] & 0o700 != 0o700:
                changes[path]['working'] = {'kind':'directory','mode':state['mode']|0o700}
    # Stable stage order: copies before pointers, detach before delete.
    values = list(changes.values())
    values.sort(key=lambda c: {'return':0,'detach':1,'delete_product':2}[c['stage']])
    for change in values:
        state=change['after']
        if state['kind']=='directory' and state['mode']&0o700!=0o700:
            change['working']={'kind':'directory','mode':state['mode']|0o700}
    runner = Path(recovery.__file__).read_bytes()
    body = {'schema_version':1,'command':COMMAND,'home':str(runtime.home),
            'backup_dir':str(backup),'host_obligation':host_obligation,'installation_id':ledger['product']['installation_id'],
            'agents':ordered,'project_roots':project_roots,'delete_roots':[str(p) for p in roots],
            'memory_return':uninstall_memory.RETURN_SCHEMA,
            'native_identities':{str(user_paths[a]):[user_paths[a].stat().st_dev,user_paths[a].stat().st_ino] for a in ordered},
            'guard_roots':[],
            'changes':values,'recovery_sha256':recovery.digest(runner),
            'observations':observations,
            'retained_evidence':retained,
            'observation_trees':[row['observation_root'] for row in retained if 'observation_root' in row],
            'evidence_mtime_ns':{p:t for row in retained for p,t in row.get('mtime_ns',{}).items()},
            'runtime_acceptance':'pending','context_keeper':'retained'}
    body['recovery_runtime']=_interpreter_plan(runtime,roots,backup)
    if tool_identity is not None: body['independent_tool']=tool_identity
    if user_reference_redirects: body['user_reference_redirects']=user_reference_redirects
    return recovery.seal(body)


def execute(approval, *, home, backup_dir, hook=None, host_obligation=None, tool_identity=None):
    # Rebuild immediately before creating the external backup. The engine takes
    # cooperating writer locks and verifies the complete scene again inside.
    plan = preview(home=home,backup_dir=backup_dir,host_obligation=host_obligation,tool_identity=tool_identity)
    recovery.approve(approval,recovery.summary(plan))
    backup = Path(plan['backup_dir'])
    backup.mkdir(mode=0o700)
    manifest = backup/'manifest.json'
    try:
        recovery.write_backup_file(backup/'recover.py',Path(recovery.__file__).read_bytes(),0o600)
        recovery.persist_manifest(manifest,{'plan':plan,'status':'prepared','approval':approval})
        _prepare_interpreter(plan)
        recovery.load_manifest(manifest)
        # Verify static syntax and all planned restore bytes before first write.
        compile((backup/'recover.py').read_bytes(),str(backup/'recover.py'),'exec')
        if hook is None:
            child=subprocess.run([plan['recovery_runtime']['interpreter'],'-I','-S','-B',str(backup/'recover.py'),
                                  '--manifest',str(manifest),'--execute-prepared'],capture_output=True,text=True)
            if child.returncode!=0:
                raise recovery.Conflict('Independent uninstall executor failed: '+child.stdout.strip())
            return json.loads(child.stdout)
        if plan['recovery_runtime']['kind']!='existing':
            raise recovery.Conflict('Fault hooks cannot execute inside a runtime scheduled for removal')
        recovery.apply_plan(plan,hook=hook)
        recovery.persist_manifest(manifest,{'plan':plan,'status':'completed','approval':approval})
    except Exception:
        # Never auto-rollback over new user writes. Independent recovery previews
        # exact partial state and requires its own approval.
        if manifest.exists():
            recovery.persist_manifest(manifest,{'plan':plan,'status':'recovery_required','approval':approval})
        raise
    return {'status':'completed','approval_required':False,'manifest':str(manifest),
            'agents':plan['agents'],'runtime_acceptance':'pending',
            'validation':{'host_new_session':'pending','private_cpython_relocation':'pending'},
            'retained_evidence':plan.get('retained_evidence',[]),
            'context_keeper':recovery.ck_choice(home),**recovery.completion_metadata(plan)}


def cli(argv, *, home=None, tool_identity=None):
    if argv and argv[0]=='recover-uninstall':
        return recovery.cli(argv[1:])
    parser = argparse.ArgumentParser(prog=COMMAND)
    parser.add_argument('command',choices=(COMMAND,))
    parser.add_argument('--backup-dir',required=True)
    parser.add_argument('--approval-file')
    parser.add_argument('--json',action='store_true')
    parser.add_argument('--host-obligation',choices=('paseo',))
    parser.add_argument('--host-plugin-id')
    parser.add_argument('--host-plugin-source')
    parser.add_argument('--host-plugin-manifest-sha256')
    parser.add_argument('--host-plugin-record-json')
    args = parser.parse_args(argv)
    home = Path.home() if home is None else Path(home)
    try:
        obligation=None
        if args.host_obligation:
            source=recovery.safe(args.host_plugin_source or '')
            if not source.is_dir() or source.resolve()!=source or not args.host_plugin_id or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]*',args.host_plugin_id):
                raise recovery.Conflict('Exact canonical plugin source and installed ID required')
            if args.host_plugin_manifest_sha256 is not None and not re.fullmatch('[a-f0-9]{64}',args.host_plugin_manifest_sha256):
                raise recovery.Conflict('Invalid compiled manifest identity')
            aliases=[]
            if args.host_plugin_record_json:
                record=json.loads(args.host_plugin_record_json)
                if not isinstance(record,dict) or set(record)!={'id','source','path','enabled'} or record['id']!=args.host_plugin_id or record['path']!=str(source) or type(record['enabled']) is not bool:
                    raise recovery.Conflict('Plugin alias config identity mismatch')
                aliases=[record]
            obligation={'kind':'paseo-plugin','plugin_id':args.host_plugin_id,'source_dir':str(source),
                'source_tree_sha256':recovery.digest(recovery.encoded(recovery.tree(source))),
                'manifest_sha256':args.host_plugin_manifest_sha256,'aliases':aliases,
                'host':socket.gethostname(),'required_state':'removed'}
        elif any((args.host_plugin_id,args.host_plugin_source,args.host_plugin_manifest_sha256,args.host_plugin_record_json)):
            raise recovery.Conflict('Plugin identity requires explicit host obligation')
        if args.approval_file:
            result = execute(json.loads(Path(args.approval_file).read_text()),home=home,backup_dir=args.backup_dir,host_obligation=obligation,tool_identity=tool_identity)
        else:
            plan = preview(home=home,backup_dir=args.backup_dir,host_obligation=obligation,tool_identity=tool_identity)
            view = recovery.summary(plan)
            result = {'status':'approval_required','approval_required':True,'plan':view,
                      'approval':{'plan':view,'reference':'<user approval>','confirmed_at':'<UTC timestamp>'}}
            if plan.get('user_reference_redirects'): result['user_reference_redirects']=plan['user_reference_redirects']
        if tool_identity is not None: result['independent_tool']=tool_identity
        print(json.dumps(result,ensure_ascii=False))
        return recovery.exit_code(result)
    except (ValueError,OSError,KeyError,TypeError) as exc:
        print(json.dumps({'status':'failed','errors':[{'code':getattr(exc,'code','uninstall_failed'),'message':str(exc)}]},ensure_ascii=False))
        return 2


# Frozen official dependency identities from baseline production-assets.ts.
RUNTIME_ASSETS = [{'id': 'cpython-3.13.18-20261026', 'arch': 'arm64', 'sha256': '8392b6ea51d94391befb2c31ebe75463f045d0b69dfcf5e1bb3234e1f5fa3405', 'treeSha256': 'ed25297b8d4ac8205da78531ee02bf80808533c97471c08926078d39a396db6c', 'bytes': 25265774}, {'id': 'cpython-3.13.18-20261026', 'arch': 'x86_64', 'sha256': '7412c19d896c99431b74a18a5643e110449a7f9590fbab179c3e5ab27b9aa9e3', 'treeSha256': 'a5c98958c9117b6fe1bfd1b00cc658aaeb73c771bec5442a7711ed2354b20b95', 'bytes': 25055263}, {'id': 'dugite-git-2.56.0-2', 'arch': 'arm64', 'sha256': '1110de343de11cc6f469b782b60f36217b9199b5e06875dd65baa26dd60563c7', 'treeSha256': 'd67bb842e4363f0d70ab800cd003dd6107df7468758a0e40f7d9b3d1c297222a', 'bytes': 63488287}, {'id': 'dugite-git-2.56.0-2', 'arch': 'x86_64', 'sha256': '52cc663281e1ec2f1d76ba781193ca4847e62dbbf767f6c99ec9ec5b978a7659', 'treeSha256': 'b75cb4121aba632c68cf02cf582c6bbb5bc9678801d44492fcf8b42833a7ce11', 'bytes': 67470398}]
