"""Pinned independent uninstall compatibility, without replacing installed C."""
import argparse
import json
from pathlib import Path
import sys

from . import legacy_reconcile as history, uninstall, uninstall_recovery as recovery
from . import staging_retirement as trust
from .layout import RuntimeLayout


def verify_public_layout_backup(runtime, directory):
    """Reuse the reviewed frozen producer validator; never execute archived code."""
    directory = Path(directory)
    if (directory.parent != runtime.backups or not directory.name.startswith('migration-')
            or not directory.name[len('migration-'):]):
        raise recovery.Conflict('Unknown migration backup container')
    from . import migrate
    migrate._op(directory.name[len('migration-'):])
    manifest = directory/'tx/manifest.json'
    raw, fact = history._file(manifest, home=runtime.home, mode=0o600)
    doc = history._json(raw); history._keys(doc, history.TOP)
    if (type(doc['schema_version']) is not int or doc['schema_version'] != 1
            or doc['operation'] != 'migrate-public-layout' or doc['status'] != 'committed'
            or doc['error'] is not None or doc['registry_path'] != str(runtime.registry)
            or not isinstance(doc['entries'],list) or not doc['entries']
            or not isinstance(doc['created_directories'],list)):
        raise recovery.Conflict('Migration backup is not a committed known producer')
    for name in doc['created_directories']: history._path(name,runtime.home)
    observations={str(manifest):fact};directories={};snapshots={};seen=set();expected={'manifest.json'}
    for index,row in enumerate(doc['entries']):
        history._keys(row,history.ROW);target=history._path(row['path'],runtime.home)
        if str(target) in seen or row['attempted'] is not True or row['restoration'] != 'not_needed':
            raise recovery.Conflict('Incomplete/duplicate historical output')
        seen.add(str(target))
        history._metadata(row['before'],before=True,index=index)
        history._metadata(row['after'],before=False,index=index)
        if row['before']['kind']=='file':
            name=row['before']['backup'];expected.add(name)
            blob=history._capture(manifest.parent/name,observations,runtime,mode=0o600)
            if recovery.digest(blob)!=row['before']['fingerprint']:
                raise recovery.Conflict('Historical backup bytes drift')
            snapshots[str(target)]=blob
        else:snapshots[str(target)]=None
    txfact=history._directory(manifest.parent,runtime)
    if (doc['entries'][-1]['path']!=str(runtime.registry) or txfact['mode']!=0o700
            or set(txfact['names'])!=expected):
        raise recovery.Conflict('Historical transaction closure differs')
    directories[str(manifest.parent)]=txfact
    history._producer(runtime,manifest,doc,raw,snapshots,observations,directories)
    # Snapshot only the fully verified fixed closure. Bind bytes/modes and the
    # exact directory child set into the existing recovery engine's scene.
    tree=recovery.tree(directory)
    for name,meta in observations.items():
        state=tree.get(name)
        if (not state or state['kind']!='file' or state['mode']!=meta['mode']
                or recovery.digest(bytes.fromhex(state['hex']))!=meta['sha256']
                or history._file(Path(name),home=runtime.home,mode=meta['mode'])[1]!=meta):
            raise recovery.Conflict('Historical evidence changed during inventory')
    for name,meta in directories.items():
        if history._directory(Path(name),runtime)!=meta:
            raise recovery.Conflict('Historical directory changed during inventory')
    return tree



def verify_upgrade_backup(runtime, directory):
    """Known archive is owned only through its committed original upgrade plan."""
    from . import upgrade
    directory=Path(directory)
    op=directory.name[len('upgrade-'):]
    if directory.parent!=runtime.backups or not directory.name.startswith('upgrade-'):
        raise recovery.Conflict('Unknown upgrade archive')
    from . import migrate
    migrate._op(op)
    journal_path=runtime.home/('.mem-sharing-install-'+op)/'journal.json'
    raw,_=history._file(journal_path,home=runtime.home,mode=0o600)
    strict=history._json(raw)
    journal,bound=upgrade._load_journal(journal_path)
    plan=journal['plan']
    if (journal!=strict or bound!=runtime or journal['status']!='committed'
            or journal['intent']!={'kind':'remove_upgrade_marker','path':str(upgrade.marker(runtime))}
            or plan['archive']!=str(directory)):
        raise recovery.Conflict('Archive lacks matching committed upgrade ownership')
    upgrade._verify_before(plan,required=True)
    tree=recovery.tree(directory);expected={str(directory),str(directory/'registry-before.json')}
    for item in plan['outputs']:
        if item['before']['kind']!='file':continue
        path=upgrade._backup_path(plan,item);expected.add(str(path))
        parent=path.parent
        while parent!=directory:
            expected.add(str(parent));parent=parent.parent
    if set(tree)!=expected:
        raise recovery.Conflict('Upgrade archive closure has unknown/missing objects')
    for name,state in tree.items():
        if state['kind'] not in ('directory','file'):
            raise recovery.Conflict('Upgrade archive link/special node refused')
        history._real(Path(name),runtime.home,directory=state['kind']=='directory')
        if state['kind']=='file' and state['mode']!=0o400:
            raise recovery.Conflict('Upgrade archive must retain producer immutable mode')
    if journal_path.read_bytes()!=raw:raise recovery.Conflict('Upgrade journal drift')
    tree[str(journal_path)]=recovery.snapshot(journal_path)
    return tree



def cli(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('tool-commit','paseo-cli','cli-sha256','server-id','plugin-id'):
        parser.add_argument('--'+name,required=True)
    parser.add_argument('--redirect-dsh-reference-to-return','--detach-dsh-reference',dest='redirect_dsh_reference_to_return',action='store_true')
    args,core=parser.parse_known_args(argv)
    try:
        if not core or core[0]!='uninstall-machine':
            raise recovery.Conflict('Independent entry only supports uninstall-machine')
        root=Path(__file__).resolve().parents[2]
        identity=trust.trusted_tool(root,args.tool_commit)
        rt=RuntimeLayout(Path.home());ledger,registry_hash=trust.installed(rt)
        host=trust.host_scene(args.paseo_cli,args.cli_sha256,rt.home/'.paseo',args.server_id,args.plugin_id)
        # Actual public host obligation is mandatory even though target was removed.
        if '--host-obligation' not in core or core[core.index('--host-obligation')+1]!='paseo':
            raise recovery.Conflict('Explicit actual Paseo obligation required')
        if '--host-plugin-id' not in core or core[core.index('--host-plugin-id')+1]!=args.plugin_id:
            raise recovery.Conflict('Host obligation ID differs from verified removed target')
        if args.redirect_dsh_reference_to_return:
            identity['user_conversions']={'dsh_reference':'explicit-single-path-to-return-v1'}
        identity.update(installed_source=ledger['product']['source'],registry_sha256=registry_hash,host=host)
        return uninstall.cli(core,tool_identity=identity)
    except (ValueError,OSError,KeyError,TypeError,IndexError) as exc:
        print(json.dumps({'status':'failed','errors':[{'code':'independent_uninstall_conflict','message':str(exc)}]}));return 2


def detach_dsh_reference(runtime, path, original, detached, mode):
    """Explicit v1 conversion now retires the dependency; no return pointer."""
    old=str(runtime.root/'memories/MEMORY.md').encode()
    prefix='开始任务前读取并遵守 '.encode()
    lines=[line for line in detached.splitlines(keepends=True) if old in line]
    if len(lines)!=1 or detached.count(old)!=1 or not lines[0].strip().startswith(prefix+old):
        raise recovery.Conflict('Missing/ambiguous explicitly approved DSH instruction')
    from . import entries
    ck=entries.managed_span(detached,start='<!-- context-keeper:start -->',end='<!-- context-keeper:end -->')
    offset=detached.index(old)
    if ck is not None and ck[0]<=offset<ck[1]:
        raise recovery.Conflict('Context Keeper text cannot be converted')
    suffix=lines[0].strip()[len(prefix+old):]
    if suffix not in ('；读不到就说明。'.encode(),';读不到就说明。'.encode()):
        raise recovery.Conflict('Unknown DSH user prose; preserve and review')
    return detached.replace(lines[0],b'',1), {'path':str(path),'before_sha256':recovery.digest(original),
        'before_mode':mode,'removed_instruction_sha256':recovery.digest(lines[0]),
        'ownership_transition':'none','conversion':'explicit-dsh-direct-native-v1'}
