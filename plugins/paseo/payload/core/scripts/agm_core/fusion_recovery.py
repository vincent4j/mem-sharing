"""Exact-approved CLI wrapper for the existing fusion Transaction rollback."""
import argparse
import copy
import json
from pathlib import Path
import sys

from . import entries, layout, paths, project, registry
from .transaction import Snapshot, read_snapshot, recover_manifest, write_lock, inspect_recovery, Transaction, _recovery_entries

COMMAND = 'recover-memory-fusion'


def _encoded(value):
    return (json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'))+'\n').encode()


def _observe(path):
    snap=read_snapshot(path)
    return {'kind':snap.kind,'sha256':snap.fingerprint,'mode':snap.mode,'target':snap.target}


def build(request, *, terminal_proof=False):
    runtime=layout.from_request(request)
    manifest=Path(request['manifest'])
    if not manifest.is_absolute() or manifest.parent.parent != runtime.backups or manifest.name!='manifest.json':
        raise ValueError('Only a fusion manifest directly below this HOME backup root is eligible')
    snap=read_snapshot(manifest)
    if snap.kind!='file':raise ValueError('Expected regular recovery manifest')
    data=json.loads(snap.data,object_pairs_hook=registry._no_duplicates)
    if (data.get('schema_version')!=1 or data.get('operation')!='organize-user-rules'
            or data.get('status') not in (('committed','rolled_back') if terminal_proof else ('prepared','applying','recovery_required'))
            or data.get('registry_path') not in (None,str(runtime.registry))):
        raise ValueError('Not an interrupted memory fusion transaction')
    config=paths.select_platform(paths.load_agents_table(),sys.platform)
    allowed=set(paths.allowed_user_paths(config,None,home=str(runtime.home)))
    root=None
    if request.get('project'):
        root=project.resolve_project(Path(request['project'])).checkout
        for conf in config.values():
            for key in ('project_rule_entry','project_bridge_entry'):
                allowed.add(paths.expand_path(conf[key],home=str(runtime.home),project=str(root)))
    memories=runtime.root/'memories'
    if data.get('registry_path') is not None:
        if data.get('phased_writes'):raise ValueError('Phased fusion cannot update registry')
        rows=data['entries'];vrows=[r for r in rows if r['path']==str(runtime.registry)]
        native=paths.expand_path(config['claude']['user_entry'],home=str(runtime.home))
        sources=[r for r in rows if r['path']==native]
        if len(vrows)!=1 or rows[-1] is not vrows[0] or len(sources)!=1:
            raise ValueError('Registry recovery must bind one final Claude reference observation')
        vr=vrows[0];sr=sources[0]
        if vr['before']['kind']!='file' or sr['before']['kind']!='file':raise ValueError('Missing reference before evidence')
        name=vr['before']['backup']
        if not isinstance(name,str) or Path(name).name!=name:raise ValueError('Invalid registry backup')
        backup_snapshot=read_snapshot(manifest.parent/name)
        if backup_snapshot.kind!='file':raise ValueError('Registry backup must be a regular file')
        old=registry.validate_registry(json.loads(backup_snapshot.data,object_pairs_hook=registry._no_duplicates),allowed_user_paths=allowed)
        expected=copy.deepcopy(old);ids=[]
        for oid,obj in old['machine']['objects'].items():
            if (obj['path']==native and obj['kind']=='import' and obj['scope']=='machine' and obj['ownership']=='reused'
                and obj['marker'] is None and obj['agents']==['claude'] and obj['original_existed'] is True
                and obj['backup_manifest'] is None and obj['consumers']==[]
                and obj['fingerprint']=={'algorithm':'sha256','basis':'file_bytes','value':sr['before']['fingerprint']}):
                expected['machine']['objects'][oid]['fingerprint']['value']=sr['after']['fingerprint'];ids.append(oid)
        raw=registry.serialize_registry(expected,allowed_user_paths=allowed)
        if len(ids)!=1 or entries.sha256(raw)!=vr['after']['fingerprint']:
            raise ValueError('Recovery would change more than the approved Claude import observation')
        allowed.add(str(runtime.registry))
    observations={str(manifest):_observe(manifest)}
    for item in data['entries']:
        name=item['path']; path=Path(name)
        public=path.is_relative_to(memories) and path.suffix.lower()=='.md'
        if name not in allowed and not public:raise ValueError('Recovery target outside trusted memory sources: '+name)
        if item['before']['kind'] not in ('file','absent') or item['after']['kind']!='file':
            raise ValueError('Fusion recovery only restores regular file/absent snapshots')
        before=item['before']; raw=None
        if before['kind']=='file':
            backup=before['backup']
            if not isinstance(backup,str) or Path(backup).name!=backup:raise ValueError('Invalid backup name')
            backup_path=manifest.parent/backup
            backup_snap=read_snapshot(backup_path)
            if backup_snap.kind!='file' or backup_snap.fingerprint!=before['fingerprint']:
                raise ValueError('Backup missing or changed')
            raw=backup_snap.data;observations[str(backup_path)]=_observe(backup_path)
        expected=Snapshot(before['kind'],raw,before['mode'],before['link_target'])
        observations[name]=_observe(path)
    # The primitive removes these on rollback; restrict them before any write.
    for name in data['created_directories']:
        path=Path(name)
        if not path.is_relative_to(memories) and not any(Path(a).is_relative_to(path) for a in allowed):
            raise ValueError('Unexpected recovery directory')
    roots=[runtime.home,runtime.root]+([root] if root else [])
    if terminal_proof:
        tx=Transaction(lock_path=runtime.transaction_lock,backup_root=runtime.backups,allowed_roots=roots,operation='recover')
        _recovery_entries(tx,manifest,data)
    else:
        inspect_recovery(manifest,allowed_roots=roots)
    plan={'schema_version':1,'command':COMMAND,'home':str(runtime.home),'manifest':str(manifest),
          'project':str(root) if root else None,'manifest_status':data['status'],
          'observations':observations,'action':'restore'}
    plan['plan_sha256']=entries.sha256(_encoded(plan))
    return plan,runtime,root


def run(request):
    try:
        plan,runtime,root=build(request)
        approval=request.get('approval')
        if approval is None:
            return {'command':COMMAND,'status':'approval_required','approval_required':True,
                    'manifest':plan['manifest'],'approval_plan':plan,
                    'next_action':dict(plan,confirmed_at='<UTC timestamp>',reference='<real user confirmation>')}
        evidence={k:approval.get(k) for k in ('confirmed_at','reference')}
        if any(not isinstance(v,str) or not v.strip() or v.startswith('<') for v in evidence.values()):
            raise ValueError('Real confirmation evidence required')
        registry._evidence(evidence)
        if approval!=dict(plan,**evidence):raise ValueError('Recovery approval or scene changed')
        with write_lock(runtime.lock):
            current,_,_=build(request)
            if current!=plan:raise ValueError('Recovery scene changed while acquiring lock')
            result=recover_manifest(Path(plan['manifest']),lock_path=runtime.transaction_lock,
                allowed_roots=[runtime.home,runtime.root]+([root] if root else []),hook=request.get('hook'))
        return {'command':COMMAND,'status':'completed','recovery_status':result['status'],
                'approval_required':False,'manifest':plan['manifest']}
    except (ValueError,OSError,KeyError,TypeError) as exc:
        return {'command':COMMAND,'status':'recovery_required','approval_required':False,
                'manifest':request.get('manifest'),'errors':[{'code':getattr(exc,'code','fusion_recovery_conflict'),'message':str(exc)}]}


def cli(argv=None,*,home=None):
    parser=argparse.ArgumentParser(prog=COMMAND,allow_abbrev=False)
    parser.add_argument('command',choices=[COMMAND])
    parser.add_argument('--manifest',required=True)
    parser.add_argument('--project')
    parser.add_argument('--approval-file')
    ns=parser.parse_args(argv)
    request={'home':str(Path(home or Path.home()).resolve()),'manifest':ns.manifest}
    if ns.project:request['project']=ns.project
    if ns.approval_file:
        try:request['approval']=json.loads(Path(ns.approval_file).read_text(),object_pairs_hook=registry._no_duplicates)
        except (ValueError,OSError) as exc:
            print(json.dumps({'status':'recovery_required','errors':[{'code':'invalid_approval','message':str(exc)}]}));return 2
    result=run(request)
    print(json.dumps(result,ensure_ascii=False))
    return 5 if result.get('approval_required') else 0 if result['status']=='completed' else 2
