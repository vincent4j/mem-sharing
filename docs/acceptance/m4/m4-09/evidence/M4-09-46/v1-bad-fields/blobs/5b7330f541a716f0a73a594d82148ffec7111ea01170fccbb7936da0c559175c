#!/usr/bin/env python3
"""M1 retry acceptance driver. No provider source edits; fail -> record/recover/exit.

Comparison projects explicit observable keys; backup_file is never compared.
Run from project root. Each dependent command is checked synchronously.
"""
import datetime as dt
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import stat
import subprocess
import sys

R = Path(__file__).resolve().parents[3]
S = Path('/Users/vincent4j/Tools/Source/context-keeper')
HOME = Path.home()
RUN = dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '-retry'
E = R / 'docs/acceptance/m1-03' / RUN
E.mkdir()
AUTH = 'paseo message 2ffbc551-b22b-46e9-8d47-37e7ca6f5fb2; prior 7b6244d9-426f-4681-9d22-b94566ae21f1'
KEYS = ('path', 'exists', 'type', 'mode', 'mtime_ns', 'sha256', 'bytes', 'target', 'resolved', 'block_sha256', 'outside_sha256')
MARKERS = [('<!-- context-keeper:start -->', '<!-- context-keeper:end -->'), ('<!-- context-keeper:workbuddy:start -->', '<!-- context-keeper:workbuddy:end -->'), ('<!-- agent-group-memory:keeper-exception:start -->', '<!-- agent-group-memory:keeper-exception:end -->')]
def now(): return dt.datetime.now(dt.timezone.utc).isoformat().replace('+00:00', 'Z')
def sha(b): return hashlib.sha256(b).hexdigest()
def write(p, obj): p.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + '\n')
def snap(p):
    d = {'path': str(p), 'exists': os.path.lexists(p)}
    if not d['exists']: return d
    st = p.lstat()
    d.update(mode=oct(stat.S_IMODE(st.st_mode)), mtime_ns=st.st_mtime_ns)
    if p.is_symlink(): d.update(type='symlink', target=os.readlink(p), resolved=str(p.resolve()))
    elif p.is_file():
        b = p.read_bytes(); d.update(type='file', sha256=sha(b), bytes=len(b))
        for start, end in MARKERS:
            a, z = start.encode(), end.encode()
            assert b.count(a) == b.count(z) and b.count(a) <= 1, f'marker conflict: {p}'
            if a in b:
                i, j = b.index(a), b.index(z) + len(z)
                assert j > i
                d.update(block_sha256=sha(b[i:j]), outside_sha256=sha(b[:i]+b[j:]))
    elif p.is_dir(): d.update(type='directory')
    else: raise RuntimeError(f'unsupported object {p}')
    return d
def observed(d): return {k: d[k] for k in KEYS if k in d}
def same(a,b): return observed(a) == observed(b)
def command(name, argv, rc=0):
    result = subprocess.run([str(x) for x in argv], capture_output=True, text=True)
    write(E / (name+'.json'), dict(argv=[str(x) for x in argv], observed_at=now(), rc=result.returncode, stdout=result.stdout, stderr=result.stderr))
    assert result.returncode == rc, f'{name}: rc={result.returncode}'
    return result.stdout
users = [HOME/'.codex/AGENTS.md', HOME/'.claude/CLAUDE.md', HOME/'.workbuddy/MEMORY.md']
bases = [R/'AGENTS.md', R/'CLAUDE.md']
links = [R/x/'skills/context-keeper' for x in ('.agents', '.codex', '.claude', '.workbuddy')]
wb = R/'.workbuddy/memory/MEMORY.md'
reg = R/'scripts/registry.json'
transactions = []
originals = {}
created_dirs = set()
def backup(label, paths):
    directory = R/'scripts/backups'/(RUN+'-'+label)
    directory.mkdir(mode=0o700)
    entries = []
    for i,p in enumerate(paths):
        d = snap(p)
        if p not in originals: originals[p] = dict(d)
        row = {'before': d, 'path': str(p), 'expected_after': None, 'recovery': 'not-needed'}
        if d.get('type') == 'file':
            dest = directory/(str(i)+'.bin'); dest.write_bytes(p.read_bytes()); dest.chmod(0o600)
            row['backup_file'] = str(dest)
            if 'backup_file' not in originals[p]: originals[p]['backup_file'] = str(dest)
        entries.append(row)
        for parent in p.parents:
            if parent == R or parent == HOME: break
            if not parent.exists(): created_dirs.add(parent)
    m = dict(operation=label, authorization=AUTH, observed_at=now(), observable_keys=KEYS, objects=entries)
    mp = directory/'manifest.json'; write(mp,m); transactions.append((mp,m))
    return mp,m
def finish(tx):
    mp,m = tx
    for row in m['objects']: row['expected_after'] = snap(Path(row['path']))
    m['readback'] = 'passed'; write(mp,m)
def protect():
    assert [snap(p) for p in users[:2]] == user_before[:2], 'protected user entry changed'
def install(name, approved):
    args = ['python3', S/'scripts/install.py', '--project', R, '--codex', '--claude', '--workbuddy']
    if approved: args.append('--approved')
    return json.loads(command(name,args))
def rollback(exc):
    # Failure record precedes recovery. No subsequent business commands run.
    write(E/'failure.json', dict(error=repr(exc), observed_at=now(), policy='record -> recover -> exit; store never removed'))
    results=[]
    for p,d in reversed(list(originals.items())):
        current=snap(p)
        expected=next((row['expected_after'] for _,m in reversed(transactions) for row in m['objects'] if row['path']==str(p) and row['expected_after'] is not None),None)
        if same(current,d): results.append(dict(path=str(p),action='unchanged')); continue
        if expected is None or not same(current,expected): results.append(dict(path=str(p),action='recovery_required',reason='unconfirmed post-fingerprint')); continue
        if d.get('type')=='file':
            p.write_bytes(Path(d['backup_file']).read_bytes()); p.chmod(int(d['mode'],8)); os.utime(p,ns=(d['mtime_ns'],d['mtime_ns']))
        elif not d['exists']: p.unlink()
        else: results.append(dict(path=str(p),action='recovery_required')); continue
        results.append(dict(path=str(p),action='restored',verified=same(snap(p),d)))
    for p in sorted(created_dirs,key=lambda p:len(p.parts),reverse=True):
        if p.is_dir() and not any(p.iterdir()): p.rmdir()
    for mp,m in transactions:
        m['recovery']=results; write(mp,m)
    write(E/'rollback.json',results)
    print('STOPPED:',repr(exc),'Evidence:',E)

try:
    baseline=json.loads((R/'docs/acceptance/m1-03/baseline.json').read_text())
    assert command('root',['git','rev-parse','--show-toplevel']).strip()==str(R)
    common=command('common',['git','rev-parse','--path-format=absolute','--git-common-dir']).strip()
    assert common==str(R/'.git')
    source_commit=command('source-commit',['git','-C',S,'rev-parse','HEAD']).strip()
    assert source_commit=='a8e584159b3853b11f96b0ec89036d04ce29dce2'
    assert not command('source-status',['git','-C',S,'status','--porcelain']).strip()
    for path,h in baseline['source_hashes'].items(): assert sha((S/path).read_bytes())==h, f'source drift {path}'
    for p,d in zip(bases,baseline['project'][:2]): assert snap(p)['sha256']==d['sha256'], f'base drift {p}'
    user_before=[snap(p) for p in users]
    for d,old in zip(user_before,baseline['users']): assert d['sha256']==old['sha256'], 'user drift'
    assert all(not os.path.lexists(p) for p in links+[wb,reg,R/'docs/context-keeper',R/'context-keeper.json'])
    assert all(not (p/'AGENTS.override.md').exists() for p in [R,*R.parents,HOME/'.codex'])
    assert not list(R.glob('**/AGENTS.override.md'))
    # Explicit regression check: extra backup metadata cannot affect equality.
    assert same(user_before[0],dict(user_before[0],backup_file='metadata-only'))
    write(E/'preflight.json',dict(authorization=AUTH,source_commit=source_commit,users=user_before,project=[snap(p) for p in bases+links],observable_keys=KEYS,backup_metadata_regression='passed',git_status=command('git-before',['git','status','--short']),observed_at=now()))
    spec=importlib.util.spec_from_file_location('keeper_install',S/'scripts/install.py'); module=importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    bridge=module.BRIDGE.encode()
    preview=install('install-preview',False); assert preview.get('approval_required') is True
    tx=backup('install',bases+links)
    base_bytes=[p.read_bytes() for p in bases]
    result=install('install-applied',True); finish(tx)
    assert result['scope']=='project' and result['project']==str(R) and not result.get('approval_required')
    for p,b in zip(bases,base_bytes):
        assert p.read_bytes()==b+(b'\n' if b.endswith(b'\n') else b'\n\n')+bridge
    for p in links: assert p.is_symlink() and p.resolve()==S
    assert [snap(p) for p in users]==user_before
    for agent,alias,p in [('codex','.agents',bases[0]),('claude','.claude',bases[1])]:
        tx=backup('ensure-'+agent,bases+links)
        before=[snap(x) for x in bases+links]
        data=json.loads(command('ensure-'+agent,['python3',S/'scripts/install.py','--ensure-bridge','--skill-dir',R/alias/'skills/context-keeper','--root',R,'--'+agent]))
        finish(tx)
        assert data==dict(scope='project',agent=agent,bridge=str(p),action='unchanged')
        assert all(same(a,snap(p)) for a,p in zip(before,bases+links))
    tx=backup('init',[R/'context-keeper.json'])
    command('init-approved',['python3',S/'scripts/context_keeper_probe.py','init','--root',R,'--store-dir',R/'docs/context-keeper','--approved']); finish(tx)
    status=command('status',['python3',S/'scripts/context_keeper_probe.py','status','--root',R])
    assert (R/'docs/context-keeper/memory-keeper.md').is_file()
    assert all((R/'docs/context-keeper'/d).is_dir() for d in ['plans','worklogs','evolution'])
    assert str(R/'docs/context-keeper') in status or 'docs/context-keeper' in status
    paths=bases+links+list((R/'docs/context-keeper').rglob('*'))+[R/'context-keeper.json']
    before=[snap(p) for p in paths]
    install('install-repeat',True)
    command('init-repeat',['python3',S/'scripts/context_keeper_probe.py','init','--root',R,'--store-dir',R/'docs/context-keeper','--approved'])
    assert all(same(a,snap(p)) for a,p in zip(before,paths)), 'install/init idempotence'
    assert [snap(p) for p in users]==user_before
    write(E/'m1-03-passed.json',dict(observed_at=now(),store_actual=str(R/'docs/context-keeper'),idempotence='bytes/mode/mtime/blocks/links unchanged',workbuddy_bridge='missing; M1-04 next',manifests=[str(p) for p,_ in transactions]))
    print('M1-03 installation/init acceptance passed',flush=True)
    # M1-04 is entered only after all previous checks passed.
    template=(R/'templates/workbuddy-bridge.md').read_bytes()
    for line in bridge.decode().splitlines():
        if line.startswith('- '): assert line in template.decode(), 'WorkBuddy seven semantics differ'
    assert template.startswith(MARKERS[1][0].encode()) and template.count(MARKERS[1][1].encode())==1
    user_clause=('\n<!-- agent-group-memory:keeper-exception:start -->\n'
        '## Context Keeper 项目记忆例外\n\n'
        '项目记忆用 context-keeper 记录库，由项目桥接块驱动。项目规则唯一来源仍为 AGENTS.md；'
        '已启用 context-keeper 的项目，其进度、事实与经验写入已获授权的记录库，项目 .workbuddy/memory/MEMORY.md '
        '可在顶部包含受控桥接块。此条款作为既有“事实归 AGENTS.md、项目 MEMORY 只放指针”约定的记忆例外；其余原文约定保留。\n'
        '<!-- agent-group-memory:keeper-exception:end -->\n').encode()
    tx=backup('workbuddy',[wb,users[2]])
    old_user=users[2].read_bytes()
    wb.parent.mkdir(parents=True,exist_ok=True); wb.write_bytes(template)
    users[2].write_bytes(old_user+user_clause); finish(tx)
    assert wb.read_bytes()==template and users[2].read_bytes()==old_user+user_clause
    assert snap(users[2])['mode']==user_before[2]['mode']; protect()
    before=[snap(p) for p in [wb,users[2]]]
    # Same desired bytes -> no writes; preserve mtime on the second operation.
    for p,want in [(wb,template),(users[2],old_user+user_clause)]:
        if p.read_bytes()!=want: p.write_bytes(want)
    assert all(same(a,snap(p)) for a,p in zip(before,[wb,users[2]]))
    write(E/'workbuddy.json',dict(observed_at=now(),project=snap(wb),user=snap(users[2]),user_original_preserved=True,project_original_existed=False,idempotence='passed; bytes/mode/mtime/blocks unchanged',runtime_acceptance='pending'))
    # Persist schema v1 by hand for M1; not a claim of an implemented AGM CLI.
    tx=backup('registry',[reg])
    timestamp=now()
    fact=lambda ev: dict(status='ready',observed_at=timestamp,evidence=ev)
    states=dict(source_available=fact(str(E/'preflight.json')),skill_installed={a:fact(str(E/'install-applied.json')) for a in ['codex','claude','workbuddy']},bridge_assembled={a:fact(str(E/('workbuddy.json' if a=='workbuddy' else 'ensure-'+a+'.json'))) for a in ['codex','claude','workbuddy']},store_authorized_ready=fact(str(E/'status.json')))
    evidence=dict(confirmed_at=timestamp,reference=AUTH)
    def owned(kind,p,agents,ownership,existed,marker=None):
        d=snap(p)
        if kind=='skill_symlink': basis,value='link_target',sha(str(p.resolve()).encode())
        elif marker:
            b=p.read_bytes(); start,end=[x.encode() for x in marker]; basis,value='block_bytes',sha(b[b.index(start):b.index(end)+len(end)])
        else: basis,value='file_bytes',d['sha256']
        manifest=next((str(mp) for mp,m in transactions if any(row['path']==str(p) for row in m['objects'])),None)
        return dict(kind=kind,path=str(p),scope='user' if p==users[2] else 'project',agents=agents,ownership=ownership,marker=dict(zip(['start','end'],marker)) if marker else None,fingerprint=dict(algorithm='sha256',basis=basis,value=value),original_existed=existed,link_target=str(p.resolve()) if p.is_symlink() else None,backup_manifest=manifest,consumers=[str(R)])
    objects={}
    for p in bases:
        a='codex' if p==bases[0] else 'claude'
        objects[str(p)+'#base']=owned('file',p,[a],'reused',True)
        objects[str(p)+'#keeper']=owned('block',p,[a],'created',False,MARKERS[0])
    for p,a in zip(links,['codex','codex','claude','workbuddy']): objects[str(p)]=owned('skill_symlink',p,[a],'created',False)
    objects[str(wb)]=owned('block',wb,['workbuddy'],'created',False,MARKERS[1])
    objects[str(R/'CLAUDE.md')+'#import']=owned('import',R/'CLAUDE.md',['claude'],'reused',True)
    shared_id=str(users[2])+'#keeper-exception'
    shared={shared_id:owned('user_convention',users[2],['workbuddy'],'created',False,MARKERS[2]),str(users[2])+'#base':owned('file',users[2],['workbuddy'],'reused',True)}
    assembly=dict(git_common_dir=common,agents=['codex','claude','workbuddy'],states=states,store=dict(path=str(R/'docs/context-keeper'),location_approved=True,approval_evidence=evidence),objects=objects,shared_object_ids=list(shared),runtime_acceptance=dict(status='pending',evidence_path=None))
    registry=dict(schema_version=1,projects={str(R):dict(main_checkout=str(R),memory_authorization='yes',authorization_evidence=evidence,provider_source=str(S),checkouts={str(R):assembly})},shared_objects=shared)
    temp=reg.with_suffix('.json.tmp'); write(temp,registry); os.replace(temp,reg); finish(tx)
    assert json.loads(reg.read_text())==registry
    protect()
    assert all(p.resolve()==S for p in links)
    assert not command('source-status-final',['git','-C',S,'status','--porcelain']).strip()
    for path,h in baseline['source_hashes'].items(): assert sha((S/path).read_bytes())==h
    write(E/'final.json',dict(status='passed',observed_at=now(),states=states,objects=[snap(p) for p in bases+links+[wb]+users],backup_manifests=[str(p) for p,_ in transactions],registry=str(reg),registry_sha256=sha(reg.read_bytes()),registry_mode='manual schema-v1 registration; AGM CLI not implemented',runtime_acceptance='pending',source_unchanged=True))
    print('M1-04 assembly acceptance passed; four states ready; runtime pending. Evidence:',E)
except Exception as exc:
    rollback(exc)
    sys.exit(1)
