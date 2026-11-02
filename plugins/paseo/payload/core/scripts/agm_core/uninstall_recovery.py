"""Standalone standard-library recovery engine, copied outside the product.

No import from agm_core: the exact same file works after C and R are removed.
All content lives in the private manifest; stdout contains hashes, never bytes.
"""
import argparse
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import stat
import tempfile
import sys
from datetime import datetime
import re
import subprocess


class Conflict(ValueError):
    code = 'uninstall_conflict'


def encoded(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + '\n').encode()


def digest(value):
    return hashlib.sha256(value).hexdigest()


def safe(path):
    path = Path(path)
    if not path.is_absolute() or os.path.normpath(str(path)) != str(path):
        raise Conflict('Expected normalized absolute path: ' + str(path))
    if path.parent.resolve() != path.parent:
        raise Conflict('Symlink parent: ' + str(path))
    return path


def snapshot(path):
    path = safe(path)
    try:
        meta = path.lstat()
    except FileNotFoundError:
        return {'kind': 'absent'}
    mode = stat.S_IMODE(meta.st_mode)
    if stat.S_ISREG(meta.st_mode):
        return {'kind': 'file', 'hex': path.read_bytes().hex(), 'mode': mode}
    if stat.S_ISDIR(meta.st_mode):
        return {'kind': 'directory', 'mode': mode}
    if stat.S_ISLNK(meta.st_mode):
        return {'kind': 'symlink', 'target': os.readlink(path)}
    raise Conflict('Special file: ' + str(path))


def tree(root):
    result = {}
    def visit(path):
        item = snapshot(path)
        result[str(path)] = item
        if item['kind'] == 'directory':
            for child in sorted(path.iterdir()):
                visit(child)
    visit(Path(root))
    return result


def write_file(path, data, mode=0o600):
    path = safe(path)
    fd, temp = tempfile.mkstemp(prefix='.uninstall-', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as stream:
            os.fchmod(stream.fileno(), mode)
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp, path)
        directory = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        if os.path.lexists(temp):
            os.unlink(temp)


def put(path, item):
    path = safe(path)
    kind = item['kind']
    if kind == 'absent':
        if path.is_dir() and not path.is_symlink():
            path.rmdir()  # Never recursively delete unenumerated content.
        elif os.path.lexists(path):
            path.unlink()
    elif kind == 'directory':
        path.mkdir(mode=item['mode'], exist_ok=True)
        os.chmod(path, item['mode'])
    elif kind == 'file':
        write_file(path, bytes.fromhex(item['hex']), item['mode'])
    elif kind == 'symlink':
        if os.path.lexists(path):
            path.unlink()
        path.symlink_to(item['target'])
    else:
        raise Conflict('Unknown snapshot type')


def seal(plan):
    body = dict(plan)
    body.pop('plan_sha256', None)
    plan['plan_sha256'] = digest(encoded(body))
    return plan


def verify_plan(plan):
    body = dict(plan)
    expected = body.pop('plan_sha256', None)
    if digest(encoded(body)) != expected or plan['schema_version'] != 1:
        raise Conflict('Plan hash/schema mismatch')
    home = safe(plan['home'])
    if not home.is_dir():
        raise Conflict('HOME missing')
    for item in plan['changes']:
        path = safe(item['path'])
        if path == home or not path.is_relative_to(home):
            # Project-policy operations explicitly enumerate their own roots.
            if not any(path.is_relative_to(safe(root)) and path != Path(root)
                       for root in plan.get('project_roots', [])):
                raise Conflict('Output outside approved roots')
        for state in (item['before'], item['after']):
            if state['kind'] == 'file':
                bytes.fromhex(state['hex'])


def summary(plan):
    return {'schema_version': 1, 'command': plan['command'], 'home': plan['home'],
            'plan_sha256': plan['plan_sha256'], 'backup_dir': plan['backup_dir'],
            'changes': [{'path': c['path'], 'before': digest(encoded(c['before'])),
                         'after': digest(encoded(c['after'])), 'stage': c['stage']}
                        for c in plan['changes']],
            'agents': plan.get('agents', []), 'runtime_acceptance': 'pending',
            'recovery_runtime':plan.get('recovery_runtime'),
            'host_obligation':plan.get('host_obligation'),
            'scope':'machine_and_paseo' if plan.get('host_obligation') else 'standalone_declared',
            'validation':{'host_new_session':'pending','private_cpython_relocation':'pending'},
            'retained_evidence':plan.get('retained_evidence',[])}


def approve(approval, expected):
    if not isinstance(approval, dict) or set(approval)!={'plan','reference','confirmed_at'} or approval.get('plan') != expected:
        raise Conflict('Approval does not match exact preview')
    if not approval.get('reference') or not approval.get('confirmed_at'):
        raise Conflict('Approval requires reference and confirmed_at')
    stamp=approval['confirmed_at']
    if not isinstance(stamp,str) or not re.fullmatch(r'\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d+)?Z',stamp):
        raise Conflict('Approval requires an actual UTC timestamp')
    datetime.fromisoformat(stamp[:-1]+'+00:00')
    if not isinstance(approval['reference'],str) or not approval['reference'].strip() or approval['reference'].startswith('<'):
        raise Conflict('Approval requires an actual user confirmation reference')


def exit_code(output):
    if output.get('status')=='approval_required':return 5
    if output.get('status') in ('failed','recovery_required','pending'):return 2
    return 0


def lock_paths(home):
    home = Path(home)
    return [home / '.mem-sharing-install.lock',home / '.mem-sharing/var/.agm.lock']


def lock_state(home, manifest, *, allow_self=False):
    result = []
    for path in lock_paths(home):
        if not os.path.lexists(path): continue
        if snapshot(path)['kind']!='directory' or {p.name for p in path.iterdir()}!={'uninstall-owner.json'}:
            raise Conflict('Unknown writer lock; operator recovery required: '+str(path))
        owner = json.loads((path/'uninstall-owner.json').read_text())
        if set(owner)!={'pid','manifest'} or owner['manifest']!=str(Path(manifest)/'manifest.json') or type(owner['pid']) is not int or owner['pid']<=0:
            raise Conflict('Writer lock identity mismatch: '+str(path))
        try:
            os.kill(owner['pid'],0)
        except ProcessLookupError:
            pass
        else:
            if not allow_self or owner['pid']!=os.getpid():
                raise Conflict('Uninstall writer is still running: '+str(path))
        result.append({'path':str(path),'owner':owner})
    return result


@contextmanager
def locks(home, manifest):
    """Share installer and project-writer locks, never steal unknown locks."""
    acquired = []
    home = Path(home)
    # Only an explicitly approved recovery may retire an identified exited
    # owner. Unknown locks and a still-live process always stop.
    stale = lock_state(home,manifest)
    for item in stale:
        path = Path(item['path'])
        (path/'uninstall-owner.json').unlink()
        path.rmdir()
    paths = [home / '.mem-sharing-install.lock']
    product = home / '.mem-sharing/var/.agm.lock'
    if product.parent.is_dir():
        paths.append(product)
    def acquire(path):
        if path in acquired:return
        try:
            path.mkdir(mode=0o700)
        except FileExistsError as exc:
            raise Conflict('Writer lock exists; explicit operator recovery required: '+str(path)) from exc
        acquired.append(path)
        write_file(path/'uninstall-owner.json',encoded({'pid':os.getpid(),'manifest':str(Path(manifest)/'manifest.json')}))
    def release_product():
        if product in acquired:
            (product/'uninstall-owner.json').unlink()
            product.rmdir()
            acquired.remove(product)
    def ensure_product():
        if product.parent.is_dir(): acquire(product)
    try:
        for path in paths:
            acquire(path)
        yield ensure_product, release_product
    finally:
        for path in reversed(acquired):
            (path/'uninstall-owner.json').unlink()
            path.rmdir()


def _evidence_scene(plan):
    for root in plan.get('observation_trees',[]):
        base=safe(root)
        expected={path:state for path,state in plan['observations'].items()
                  if Path(path)==base or Path(path).is_relative_to(base)}
        if not expected or tree(base)!=expected:
            raise Conflict('Observed evidence tree drift: '+str(base))
    for path,expected in plan.get('evidence_mtime_ns',{}).items():
        if safe(path).stat().st_mtime_ns!=expected:raise Conflict('Observed evidence mtime drift: '+path)


def _scene(plan):
    lock_state(plan['home'],plan['backup_dir'],allow_self=True)
    _evidence_scene(plan)
    for path, expected in plan.get('observations',{}).items():
        if Path(path) in lock_paths(plan['home']):continue
        if path not in {c['path'] for c in plan['changes']} and snapshot(path)!=expected:
            raise Conflict('Observed input drift: '+path)
    for change in plan['changes']:
        current = snapshot(change['path'])
        if current not in (change['before'], change['after'],change.get('working')):
            raise Conflict('Drift; preserve current content: ' + change['path'])
    # All product-directory child inventories are bound, including extra files.
    allowed = {c['path'] for c in plan['changes']}
    for root in plan.get('delete_roots', []) + plan.get('guard_roots', []):
        if not Path(root).exists():
            continue
        for path in tree(root):
            if any(Path(path)==p or Path(path).is_relative_to(p) for p in lock_paths(plan['home'])):
                continue
            if path not in allowed:
                raise Conflict('Unenumerated product child: ' + path)


def apply_plan(plan, *, action='resume', hook=None):
    verify_plan(plan)
    _scene(plan)  # A single bad file stops the whole operation before mutation.
    changes = list(plan['changes'])
    if action == 'restore':
        changes.reverse()
    elif action != 'resume':
        raise Conflict('Unknown recovery action')
    target = 'before' if action == 'restore' else 'after'
    delayed = []
    modes = []
    return_modes=[]
    with locks(plan['home'], plan['backup_dir']) as (ensure_product, release_product):
        _scene(plan)
        if action=='resume':
            for change in changes:
                if change['stage']=='delete_product' and change.get('working') and snapshot(change['path'])==change['before']:
                    put(change['path'],change['working'])
        else:
            for change in changes:
                if change.get('working') and change['after']['kind']=='directory' and snapshot(change['path'])==change['after']:
                    put(change['path'],change['working'])
        for index, change in enumerate(changes):
            path, wanted = Path(change['path']), change[target]
            if action=='resume' and change['stage']!='return' and return_modes:
                for previous in reversed(return_modes):put(previous['path'],previous['after'])
                return_modes=[]
            if action=='resume' and change['stage']=='return' and wanted['kind']=='directory' and change.get('working'):
                put(path,change['working'])
                return_modes.append(change)
                continue
            if snapshot(path) == wanted:
                continue
            if wanted['kind'] == 'absent' and path.is_dir() and (
                    path == Path(plan['home']) / '.mem-sharing' or
                    path == Path(plan['home']) / '.mem-sharing/var'):
                delayed.append(change)
                continue
            current = snapshot(path)
            if current not in (change['before'], change['after'],change.get('working')):
                raise Conflict('Drift before write: ' + str(path))
            if hook:
                hook('before_write', index, change)
                if snapshot(path) != current:
                    raise Conflict('Drift during write: ' + str(path))
            if action=='resume' and change['stage']=='delete_product':
                _evidence_scene(plan)
                for earlier in plan['changes']:
                    if earlier['stage'] in ('return','detach') and snapshot(earlier['path'])!=earlier['after']:
                        raise Conflict('Returned copy/dependency changed; product retained: '+earlier['path'])
            actual_wanted = wanted
            if action=='restore' and change.get('working') and wanted['kind']=='directory':
                actual_wanted = change['working']
                modes.append(change)
            put(path, actual_wanted)
            ensure_product()
            if snapshot(path) != actual_wanted:
                raise Conflict('Readback failed: ' + str(path))
            if hook:
                hook('after_write', index, change)
        for change in reversed(modes):
            put(change['path'],change[target])
        release_product()
        # Keep the installer lock until the final product directories vanish.
        for change in delayed:
            put(change['path'], change[target])
    for change in plan['changes']:
        if snapshot(change['path']) != change[target]:
            raise Conflict('Final verification failed: ' + change['path'])


def load_manifest(path):
    path = safe(path)
    if path.is_symlink():
        raise Conflict('Manifest symlink')
    result = json.loads(path.read_text())
    plan = result['plan']
    verify_plan(plan)
    if path != Path(plan['backup_dir']) / 'manifest.json':
        raise Conflict('Manifest location mismatch')
    runner = path.parent / 'recover.py'
    if snapshot(runner)['kind'] != 'file' or digest(runner.read_bytes()) != plan['recovery_sha256']:
        raise Conflict('Independent recovery tool changed/missing')
    verify_interpreter(plan)
    return result


def verify_interpreter(plan):
    runtime=plan.get('recovery_runtime')
    if runtime is None:raise Conflict('Independent interpreter identity missing')
    executable=Path(runtime['interpreter'])
    if executable.is_symlink() or snapshot(executable)['kind']!='file' or digest(executable.read_bytes())!=runtime['executable_sha256']:
        raise Conflict('Independent recovery interpreter changed/missing')
    if runtime['kind']=='bundled':
        root=Path(runtime['source']);destination=Path(runtime['destination'])
        expected=set()
        for change in plan['changes']:
            path=Path(change['path'])
            if path==root or path.is_relative_to(root):
                copied=destination/path.relative_to(root)
                state=change['before']
                if state['kind']=='symlink' and Path(state['target']).is_absolute():
                    target=Path(state['target'])
                    if not target.is_relative_to(root):raise Conflict('Bundled interpreter link escapes')
                    state={'kind':'symlink','target':os.path.relpath(destination/target.relative_to(root),copied.parent)}
                if snapshot(copied)!=state:raise Conflict('Independent interpreter bundle changed: '+str(copied))
                expected.add(str(copied))
        if set(tree(destination))!=expected:raise Conflict('Independent interpreter bundle has foreign files')


def recover(manifest, *, action='restore', approval=None, hook=None):
    data = load_manifest(manifest)
    plan = data['plan']
    _scene(plan)
    scene = [{'path': c['path'], 'snapshot_sha256': digest(encoded(snapshot(c['path'])))}
             for c in plan['changes']]
    view = {'command': 'recover-uninstall', 'action': action, 'manifest': str(safe(manifest)),
            'plan_sha256': plan['plan_sha256'], 'scene_sha256': digest(encoded(scene)),
            'stale_locks':lock_state(plan['home'],plan['backup_dir']),
            'changes':[{'path':c['path'],'target_sha256':digest(encoded(c['before' if action=='restore' else 'after']))}
                       for c in plan['changes']]}
    if approval is None:
        return {'status': 'approval_required', 'approval_required': True, 'plan': view,
                'approval': {'plan': view, 'confirmed_at': '<UTC timestamp>', 'reference': '<user approval>'}}
    approve(approval, view)
    apply_plan(plan, action=action, hook=hook)
    data['status'] = 'restored' if action == 'restore' else 'completed'
    write_file(manifest, encoded(data))
    result={'status': data['status'], 'approval_required': False, 'manifest': str(manifest),
            'retained_evidence':plan.get('retained_evidence',[])}
    if action=='resume':result.update(context_keeper=ck_choice(plan['home']),**completion_metadata(plan))
    return result


def ck_choice(home):
    home=Path(home)
    candidates=[]
    product_roots=[home/'.mem-sharing',home/'.local/share/mem-sharing',
                   home/'.local/share/mem-sharing-versions',home/'.local/share/mem-sharing-sources']
    for relative in ('.agents','.codex','.claude','.workbuddy','.cursor','.hermes','.config/opencode','.openclaw'):
        link=home/relative/'skills/context-keeper'
        if not link.is_symlink():continue
        source=link.resolve()
        if any(source==p or source.is_relative_to(p) for p in product_roots):continue
        installer=source/'scripts/install.py'
        if installer.is_file() and not installer.is_symlink() and str(source) not in [x['source'] for x in candidates]:
            candidates.append({'source':str(source),'verification':'candidate_only; explicit source/host selection and provenance validation required'})
    return {'status':'retained','default':'retain','source_candidates':candidates,
            'question':'主产品已完整卸载。是否另行卸载 Context Keeper？默认保留。',
            'next_step':'通过本外置工具显式选择 CK source 和宿主范围，只读预览后另行精确批准。共享位置由 CK 安装器核验，不隐式扩大范围。',
            'effect':'卸载后失去该 Skill 的自动记录、续接、历史检索及经验整理能力；项目规则和历史数据保留。CK 失败不改写主产品结果。'}


CK_AGENTS=('codex','claude','cursor','workbuddy','hermes','opencode','openclaw')


def _completed_scene(manifest):
    data=load_manifest(manifest)
    if data['status']!='completed':raise Conflict('Context Keeper choice requires completed main uninstall')
    plan=data['plan']
    _scene(plan)
    if any(snapshot(c['path'])!=c['after'] for c in plan['changes']):
        raise Conflict('Main uninstall completion scene changed; this is not a general CK manager')
    if any(os.path.lexists(root) for root in plan.get('delete_roots',[])):
        raise Conflict('Main product root still present')
    return data


def _ck_source(source, plan):
    source=safe(source)
    if source.resolve()!=source or not source.is_dir():raise Conflict('Explicit independent canonical CK source required')
    forbidden=[Path(root) for root in plan['delete_roots']]+[Path(plan['backup_dir'])]
    if any(source==p or source.is_relative_to(p) or p.is_relative_to(source) for p in forbidden):
        raise Conflict('CK source is not independent of product/recovery material')
    files={}
    def visit(path):
        for child in sorted(path.iterdir()):
            if child.name in ('.git','__pycache__'):continue
            state=snapshot(child)
            if state['kind']=='directory':visit(child)
            elif state['kind']=='file':files[str(child.relative_to(source))]=digest(bytes.fromhex(state['hex']))
            else:raise Conflict('Unknown/symlink CK source material')
    visit(source)
    if not {'SKILL.md','scripts/install.py'}<=set(files):raise Conflict('Incomplete CK source')
    # Match the upstream supported Git-checkout or hash-verified Skill package
    # identity. A candidate link/path alone never establishes this contract.
    if not (source/'.git').exists():
        descriptor=source/'manifest.json'
        if snapshot(descriptor)['kind']!='file':raise Conflict('Unknown CK source provenance')
        package=json.loads(descriptor.read_text())
        if package.get('type')!='skill' or package.get('code')!='context-keeper' or not isinstance(package.get('files'),list):
            raise Conflict('Unknown CK package identity')
        declared={}
        for item in package['files']:
            name=item['path'];relative=Path(name)
            if relative.is_absolute() or '..' in relative.parts or str(relative)!=name or name in declared:
                raise Conflict('Unsafe CK package declaration')
            declared[name]=item['sha256']
        if not {'SKILL.md','scripts/install.py'}<=set(declared) or any(files.get(p)!=sha for p,sha in declared.items()):
            raise Conflict('CK package source hash mismatch')
        provenance={'kind':'verified-skill-package','manifest_sha256':files['manifest.json']}
    else:
        command=['git','-C',str(source),'rev-parse','--show-toplevel','HEAD']
        inspected=subprocess.run(command,capture_output=True,text=True,timeout=30,
                                 env=dict(os.environ,GIT_OPTIONAL_LOCKS='0'))
        lines=inspected.stdout.splitlines()
        if inspected.returncode or len(lines)!=2 or Path(lines[0]).resolve()!=source or not re.fullmatch('[0-9a-f]{40}|[0-9a-f]{64}',lines[1]):
            raise Conflict('Invalid CK Git checkout identity')
        provenance={'kind':'explicit-git-checkout','commit':lines[1]}
    return {'path':str(source),'files':files,'tree_sha256':digest(encoded(files)),
            'installer_sha256':files['scripts/install.py'],'provenance':provenance}


def _ck_run(argv, *, source, environment):
    try:return subprocess.run(argv,cwd=source,env=environment,capture_output=True,text=True,timeout=60)
    except (OSError,subprocess.TimeoutExpired):
        return subprocess.CompletedProcess(argv,1,stdout='',stderr='CK installer could not run or timed out; main uninstall state unchanged')


def _ck_targets(home,agents,project=None):
    base=Path(project) if project is not None else Path(home)
    if project is not None and (safe(base).resolve()!=base or not base.is_dir()):raise Conflict('CK project must be an existing canonical directory')
    roots={'codex':['.agents/skills','.codex/skills'],'claude':['.claude/skills'],
           'cursor':['.cursor/skills'],'workbuddy':['.workbuddy/skills'],
           'hermes':['.agents/skills' if project else '.hermes/skills'],
           'opencode':['.opencode/skills' if project else '.config/opencode/skills'],
           'openclaw':['.agents/skills']}
    rules={'codex':base/('AGENTS.md' if project else '.codex/AGENTS.md'),
           'claude':base/('CLAUDE.md' if project else '.claude/CLAUDE.md'),
           'workbuddy':base/('.workbuddy/memory/MEMORY.md' if project else '.workbuddy/MEMORY.md')}
    skills=sorted({str(base/root/'context-keeper') for agent in agents for root in roots[agent]})
    rule_files=[str(rules[a]) for a in agents if a in rules]
    return skills,rule_files


def _ck_bridge_removed(before, *, workbuddy):
    """Expected bytes/actions of the inspected upstream _remove_bridge contract."""
    if before['kind']=='absent':return before,'absent'
    if before['kind']!='file':raise Conflict('CK rule container is not a file')
    original=bytes.fromhex(before['hex']).decode('utf-8')
    first='<!-- context-keeper:workbuddy:start -->' if workbuddy else '<!-- context-keeper:start -->'
    last='<!-- context-keeper:workbuddy:end -->' if workbuddy else '<!-- context-keeper:end -->'
    start,end=original.find(first),original.find(last)
    if start<0 and end<0:return before,'absent'
    if original.count(first)!=1 or original.count(last)!=1 or end<start:
        raise Conflict('Invalid CK rule markers in approved preimage')
    end+=len(last)
    if workbuddy:updated=original[:start]+original[end:]
    else:updated=(original[:start].rstrip()+'\n\n'+original[end:].lstrip('\n')).strip()
    if not updated:return {'kind':'absent'},'removed_file'
    if not workbuddy:updated+='\n'
    return {'kind':'file','hex':updated.encode().hex(),'mode':before['mode']},'removed'


def _verify_ck_result(payload, *, agents,project,skills,rules,before):
    expected_keys={'scope','project','installed','removed','bridges','configured_agents'}
    if not isinstance(payload,dict) or set(payload)!=expected_keys:
        raise Conflict('CK result does not match upstream uninstall JSON contract')
    labels={'codex':'Codex','claude':'Claude Code','cursor':'Cursor','workbuddy':'WorkBuddy',
            'hermes':'Hermes','opencode':'OpenCode','openclaw':'OpenClaw'}
    if (payload['scope']!=('project' if project is not None else 'user') or
            payload['project']!=(str(project) if project is not None else None) or payload['installed']!=[] or
            payload['configured_agents']!=[labels[a] for a in agents]):
        raise Conflict('CK result scope/host/operation mismatch')
    if not isinstance(payload['removed'],list) or not isinstance(payload['bridges'],list):
        raise Conflict('CK result target lists invalid')
    removed={}
    for item in payload['removed']:
        if not isinstance(item,dict) or set(item)!={'path','action'} or item['path'] in removed:
            raise Conflict('CK result removed entries invalid/duplicate')
        removed[item['path']]=item['action']
    bridges={}
    for item in payload['bridges']:
        if not isinstance(item,dict) or set(item)!={'file','action'} or item['file'] in bridges:
            raise Conflict('CK result bridge entries invalid/duplicate')
        bridges[item['file']]=item['action']
    if set(removed)!=set(skills) or set(bridges)!=set(rules):
        raise Conflict('CK result contains missing/unapproved targets')
    for path in skills:
        prior=before[path]['kind']
        expected='absent' if prior=='absent' else 'removed_symlink' if prior=='symlink' else None
        if expected is None or removed[path]!=expected or snapshot(path)['kind']!='absent':
            raise Conflict('CK Skill removal not verified: '+path)
    rule_agents=[a for a in agents if a in ('codex','claude','workbuddy')]
    for path,agent in zip(rules,rule_agents):
        expected,action=_ck_bridge_removed(before[path],workbuddy=agent=='workbuddy')
        if bridges[path]!=action or snapshot(path)!=expected:
            raise Conflict('CK rule removal/private-byte preservation not verified: '+path)


def completion_metadata(plan, host_plugin=None):
    host_plugin=host_plugin or ('pending' if plan.get('host_obligation') else 'not_applicable')
    return {'scope':'machine_and_paseo' if plan.get('host_obligation') else 'standalone_declared',
            'machine_assets':'completed','host_plugin':host_plugin,
            'overall':'completed' if host_plugin in ('removed','not_applicable') else 'partial'}


def _host_cli(cli, target):
    path=safe(cli)
    if path.resolve()!=path or not path.is_file() or not os.access(path,os.X_OK):
        raise Conflict('Canonical executable Paseo CLI required')
    if not isinstance(target,dict) or set(target)!={'kind','value'} or target['kind'] not in ('home','host') or not isinstance(target['value'],str) or not target['value']:
        raise Conflict('Explicit daemon target required')
    if target['kind']=='home':safe(target['value'])
    elif re.search(r'[@\s?#]',target['value']):raise Conflict('Endpoint must not contain credentials/query/private options')
    return {'path':str(path),'sha256':digest(path.read_bytes()),'mode':stat.S_IMODE(path.stat().st_mode)}


def _host_query(identity,target):
    if _host_cli(identity['path'],target)!=identity:raise Conflict('Paseo CLI identity drift')
    environment=dict(os.environ)
    for name in ('NODE_OPTIONS','NODE_PATH'):environment.pop(name,None)
    flag=['--'+target['kind'],target['value']]
    def run(arguments):
        result=subprocess.run([identity['path'],*arguments,'--json',*flag],capture_output=True,text=True,
                              stdin=subprocess.DEVNULL,timeout=30,env=environment)
        if result.returncode!=0:raise Conflict('Paseo query failed; removal remains pending')
        return json.loads(result.stdout)
    status=run(['status'])
    if not isinstance(status,dict) or status.get('connectedDaemon')!='reachable' or not isinstance(status.get('serverId'),str) or not status['serverId']:
        raise Conflict('Live reachable daemon handshake required')
    rows=run(['plugin','ls'])
    if not isinstance(rows,list) or any(not isinstance(row,dict) or not isinstance(row.get('id'),str) for row in rows) or len({row['id'] for row in rows})!=len(rows):
        raise Conflict('Full plugin list shape/unique ID contract failed')
    # Recheck the handshake after list so a daemon replacement cannot join two scenes.
    after=run(['status'])
    if not isinstance(after,dict) or after.get('connectedDaemon')!='reachable' or after.get('serverId')!=status['serverId']:
        raise Conflict('Daemon identity changed during full-list query')
    if _host_cli(identity['path'],target)!=identity:raise Conflict('Paseo CLI changed during query')
    return status['serverId'],rows


def bind_host_plugin(manifest, *, cli, target, approval=None):
    data=_completed_scene(manifest);plan=data['plan'];obligation=plan.get('host_obligation')
    if not obligation:raise Conflict('No host plugin obligation in this approved manifest')
    identity=_host_cli(cli,target);server,rows=_host_query(identity,target)
    matches=[row for row in rows if row['id']==obligation['plugin_id']]
    aliases=obligation.get('aliases',[])
    if len(matches)!=1 or len(aliases)!=1:raise Conflict('Cannot initially bind an absent/ambiguous plugin; pending')
    if any(row['id']!=obligation['plugin_id'] and row.get('path')==obligation['source_dir'] for row in rows):
        raise Conflict('Additional alias still references the original plugin source')
    row=matches[0];record=aliases[0];installation=row.get('installation')
    if row.get('path')!=obligation['source_dir'] or not isinstance(installation,dict) or not isinstance(installation.get('identity'),dict):
        raise Conflict('Listed plugin source does not match original loaded source')
    source=installation['identity']
    # Config describes the final directory loaded by the host; CLI installation
    # describes provenance. Managed Git installs publish source=directory too.
    if record['source']!='directory' or (source.get('kind')=='directory' and source.get('path')!=obligation['source_dir']):
        raise Conflict('Plugin installation source identity mismatch')
    if source.get('kind') not in ('directory','git'):raise Conflict('Unknown plugin source identity')
    if digest(encoded(tree(obligation['source_dir'])))!=obligation['source_tree_sha256']:
        raise Conflict('Original plugin source tree drift')
    path=safe(manifest).parent/'host-binding.json'
    view={'command':'bind-host-plugin','manifest':str(safe(manifest)),'plan_sha256':plan['plan_sha256'],
          'host_obligation':obligation,'cli':identity,'daemon_target':target,'server_id':server,
          'plugin':row,'binding_file':str(path)}
    if approval is None:
        return {'status':'approval_required','approval_required':True,'plan':view,
                'approval':{'plan':view,'reference':'<independent host binding approval>','confirmed_at':'<UTC timestamp>'},
                **completion_metadata(plan)}
    approve(approval,view)
    # The just-approved live scene is revalidated immediately before writing.
    again,listed=_host_query(identity,target)
    if again!=server or [r for r in listed if r['id']==obligation['plugin_id']]!=[row]:
        raise Conflict('Host binding scene drift')
    if snapshot(path)['kind']!='absent':raise Conflict('Host binding exists; never silently replace target')
    _completed_scene(manifest)
    if digest(encoded(tree(obligation['source_dir'])))!=obligation['source_tree_sha256']:
        raise Conflict('Plugin source changed during approved binding')
    # Exclusive creation prevents another approved target from being overwritten.
    fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(fd,'wb') as stream:
        stream.write(encoded({'schema_version':1,'plan':view,'approval':approval}))
        stream.flush();os.fsync(stream.fileno())
    return {'status':'completed','approval_required':False,'binding_file':str(path),**completion_metadata(plan)}


def check_host_plugin(manifest):
    data=_completed_scene(manifest);plan=data['plan'];obligation=plan.get('host_obligation')
    if not obligation:return {'status':'completed',**completion_metadata(plan)}
    try:
        path=safe(manifest).parent/'host-binding.json'
        if snapshot(path)['kind']!='file' or stat.S_IMODE(path.stat().st_mode)!=0o600:raise Conflict('Pre-removal host binding missing/unsafe')
        binding=json.loads(path.read_text())
        if not isinstance(binding,dict) or set(binding)!={'schema_version','plan','approval'} or type(binding['schema_version']) is not int or binding['schema_version']!=1:
            raise Conflict('Invalid host binding schema')
        view=binding['plan'];approve(binding['approval'],view)
        if view.get('command')!='bind-host-plugin' or view.get('manifest')!=str(safe(manifest)) or view.get('plan_sha256')!=plan['plan_sha256'] or view.get('host_obligation')!=obligation or view.get('binding_file')!=str(path):
            raise Conflict('Host binding does not belong to this completed uninstall')
        server,rows=_host_query(view['cli'],view['daemon_target'])
        if server!=view['server_id']:raise Conflict('Live daemon serverId changed; pending')
        if any(row['id']!=obligation['plugin_id'] and row.get('path')==obligation['source_dir'] for row in rows):
            raise Conflict('Additional plugin alias still present; removal pending')
        matches=[row for row in rows if row['id']==obligation['plugin_id']]
        state='removed' if not matches else 'disabled' if matches[0].get('enabled') is False or matches[0].get('status')=='disabled' else 'pending'
        return {'status':'completed' if state=='removed' else 'pending','proof':'live-full-list',
                'daemon_target':view['daemon_target'],'server_id':server,'plugin_id':obligation['plugin_id'],
                **completion_metadata(plan,state)}
    except (ValueError,OSError,KeyError,TypeError,subprocess.SubprocessError) as exc:
        return {'status':'pending','errors':[{'code':'host_plugin_pending','message':str(exc)}],**completion_metadata(plan)}


def ck_followup(manifest, *, choice='retain', source=None, agents=None, project=None, approval=None):
    """Immediate final-step CK operation, separately approved and never mutates V.

    Failure/preview returns keep the original main manifest byte-for-byte.
    Normal later edits to returned memories intentionally invalidate this scene.
    """
    data=_completed_scene(manifest);plan=data['plan']
    if choice=='retain':
        if source is not None or agents or project is not None or approval is not None:
            raise Conflict('Retain choice does not accept CK execution arguments')
        host_check=check_host_plugin(manifest)
        return {'status':'retained','command':'uninstall-context-keeper','main_status':'completed',
                'approval_required':False,'host_removal':host_check,
                **completion_metadata(plan,host_check['host_plugin'])}
    host_check=check_host_plugin(manifest)
    if host_check['host_plugin'] not in ('removed','not_applicable'):return host_check
    if choice!='uninstall' or source is None or not agents:
        raise Conflict('Explicit uninstall choice, CK source and host selection required')
    if len(set(agents))!=len(agents) or not set(agents)<=set(CK_AGENTS):raise Conflict('Unknown/duplicate CK host selection')
    agents=[agent for agent in CK_AGENTS if agent in agents]
    identity=_ck_source(source,plan)
    skills,rules=_ck_targets(plan['home'],agents,project)
    targets=skills+rules
    before={path:snapshot(path) for path in targets}
    interpreter=plan['recovery_runtime']['interpreter']
    argv=[interpreter,'-I','-S','-B',str(Path(source)/'scripts/install.py'),
          *['--'+agent for agent in agents],'--uninstall']
    if project is not None:argv+=['--project',str(project)]
    environment=dict(os.environ,HOME=plan['home'])
    for name in ('PYTHONPATH','PYTHONHOME','PYTHONUSERBASE'):environment.pop(name,None)
    result=_ck_run(argv,source=source,environment=environment)
    if result.returncode!=0:
        return {'status':'failed','command':'uninstall-context-keeper','main_status':'completed','phase':'preview',
                'errors':[{'code':'ck_preview_failed','message':result.stderr.strip() or result.stdout.strip()}]}
    output=json.loads(result.stdout)
    if output.get('approval_required') is not True or set(output.get('skill_entries',[]))!=set(skills) or set(output.get('rule_files',[]))!=set(rules):
        raise Conflict('CK preview target contract mismatch')
    if _ck_source(source,plan)!=identity or any(snapshot(path)!=state for path,state in before.items()):
        raise Conflict('CK source/targets changed during preview')
    view={'command':'uninstall-context-keeper','choice':'uninstall','manifest':str(safe(manifest)),
          'main_plan_sha256':plan['plan_sha256'],'source':identity['path'],
          'source_tree_sha256':identity['tree_sha256'],'installer_sha256':identity['installer_sha256'],
          'source_provenance':identity['provenance'],
          'interpreter':plan['recovery_runtime'],'agents':agents,'project':None if project is None else str(project),
          'targets':[{'path':p,'before_sha256':digest(encoded(before[p]))} for p in targets],
          'host_removal':host_check,'preview':output,'preview_sha256':digest(result.stdout.encode()),'preview_argv':argv}
    if approval is None:
        return {'status':'approval_required','command':'uninstall-context-keeper','main_status':'completed',
                'approval_required':True,'plan':view,**completion_metadata(plan,host_check['host_plugin']),
                'approval':{'plan':view,'reference':'<separate CK approval>','confirmed_at':'<UTC timestamp>'}}
    approve(approval,view)  # Main uninstall/recovery approval has another command/hash.
    _completed_scene(manifest)
    if check_host_plugin(manifest)!=host_check:raise Conflict('Host removal proof changed before CK execution')
    if _ck_source(source,plan)!=identity or any(snapshot(path)!=state for path,state in before.items()):
        raise Conflict('CK execution source/target drift')
    executed=_ck_run(argv+['--approved'],source=source,environment=environment)
    try:payload=json.loads(executed.stdout)
    except ValueError:payload=None
    error=None
    if executed.returncode==0:
        try:_verify_ck_result(payload,agents=agents,project=project,skills=skills,rules=rules,before=before)
        except (ValueError,OSError,KeyError,TypeError) as exc:error={'code':'ck_result_verification_failed','message':str(exc)}
    else:error={'code':'ck_uninstall_failed','message':executed.stderr.strip()}
    return {'status':'completed' if error is None else 'failed','command':'uninstall-context-keeper',
            'main_status':'completed','approval_required':False,'exit_code':executed.returncode,
            'result':payload,'errors':[] if error is None else [error],**completion_metadata(plan,host_check['host_plugin'])}


def cli(argv=None):
    parser = argparse.ArgumentParser(description='Independent memSharing recovery; standard library only')
    parser.add_argument('--manifest', required=True)
    parser.add_argument('--action', choices=('restore', 'resume'), default='restore')
    parser.add_argument('--approval-file')
    parser.add_argument('--json',action='store_true')
    parser.add_argument('--execute-prepared',action='store_true',help=argparse.SUPPRESS)
    parser.add_argument('--ck-choice',choices=('retain','uninstall'))
    parser.add_argument('--ck-source')
    parser.add_argument('--ck-agent',action='append',choices=CK_AGENTS)
    parser.add_argument('--ck-project')
    parser.add_argument('--ck-approval-file')
    parser.add_argument('--bind-host-plugin',action='store_true')
    parser.add_argument('--check-host-plugin',action='store_true')
    parser.add_argument('--paseo-cli')
    target=parser.add_mutually_exclusive_group()
    target.add_argument('--paseo-host')
    target.add_argument('--paseo-home')
    parser.add_argument('--host-binding-approval-file')
    args = parser.parse_args(argv)
    try:
        approval = None if args.approval_file is None else json.loads(Path(args.approval_file).read_text())
        if args.bind_host_plugin:
            if args.check_host_plugin or args.ck_choice or args.approval_file or args.execute_prepared:raise Conflict('Host binding is an independent operation')
            target={'kind':'host' if args.paseo_host else 'home','value':args.paseo_host or args.paseo_home}
            selected=None if args.host_binding_approval_file is None else json.loads(Path(args.host_binding_approval_file).read_text())
            output=bind_host_plugin(args.manifest,cli=args.paseo_cli or '',target=target,approval=selected)
        elif args.paseo_cli or args.paseo_host or args.paseo_home or args.host_binding_approval_file:
            raise Conflict('Daemon target can only be selected during explicit pre-removal binding')
        elif args.check_host_plugin:
            if args.ck_choice or args.approval_file or args.execute_prepared:raise Conflict('Host check is an independent read-only operation')
            output=check_host_plugin(args.manifest)
        elif args.ck_choice is not None:
            if args.approval_file or args.execute_prepared:raise Conflict('CK cannot reuse main approval or prepared execution')
            ck_approval=None if args.ck_approval_file is None else json.loads(Path(args.ck_approval_file).read_text())
            output=ck_followup(args.manifest,choice=args.ck_choice,source=args.ck_source,agents=args.ck_agent,
                               project=args.ck_project,approval=ck_approval)
        elif args.ck_source or args.ck_agent or args.ck_project or args.ck_approval_file:
            raise Conflict('CK arguments require an explicit CK choice')
        elif args.execute_prepared:
            data=load_manifest(args.manifest)
            if Path(sys.executable).resolve()!=Path(data['plan']['recovery_runtime']['interpreter']).resolve():
                raise Conflict('Prepared executor is not the approved independent interpreter')
            if data['status']!='prepared':raise Conflict('Prepared execution cannot replay a partial/finished operation')
            approve(data['approval'],summary(data['plan']))
            apply_plan(data['plan'])
            data['status']='completed'
            write_file(args.manifest,encoded(data))
            output={'status':'completed','approval_required':False,'manifest':args.manifest,
                    'agents':data['plan']['agents'],'runtime_acceptance':'pending',
                    'validation':{'host_new_session':'pending','private_cpython_relocation':'pending'},
                    'retained_evidence':data['plan'].get('retained_evidence',[]),
                    'context_keeper':ck_choice(data['plan']['home']),**completion_metadata(data['plan'])}
        else:output = recover(args.manifest, action=args.action, approval=approval)
        print(json.dumps(output, ensure_ascii=False))
        return exit_code(output)
    except (ValueError, OSError, KeyError, TypeError, subprocess.SubprocessError) as exc:
        failure={'status':'failed','errors':[{'code':'ck_followup_failed' if args.ck_choice else 'uninstall_recovery_failed','message':str(exc)}]}
        if args.bind_host_plugin:failure.update(status='pending',command='bind-host-plugin',host_plugin='pending',overall='partial',main_status='unchanged')
        if args.ck_choice:failure.update(command='uninstall-context-keeper',main_status='unchanged')
        print(json.dumps(failure,ensure_ascii=False))
        return 2


if __name__ == '__main__':
    raise SystemExit(cli())
