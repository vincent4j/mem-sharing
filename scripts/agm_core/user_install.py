"""Explicit machine classification/first installation. No CLI and no implicit writes.

Installation approvals bind every content output plus bootstrap metadata scopes.
The active V is committed last. User-entry orchestration reuses run_user_entries
against an operation-local staged ledger, never a second active registry.
"""
import ast
import copy
import json
import os
import re
import shutil
import sys
import stat
import subprocess
import uuid
import unicodedata
from contextlib import ExitStack
from datetime import datetime, timezone
from pathlib import Path

from . import detect, legacy_import as legacy, migrate, paths, registry, user_entries, versions
from .layout import RuntimeLayout
from .transaction import Snapshot, TransactionError, _apply, _atomic_file, read_snapshot

PRODUCT = 'mem-sharing'
JOURNAL_KEYS = 'schema_version product_id operation_id plan approval status intent created_directories completed snapshot_complete snapshot_location entry_registry_sha256 final_registry_sha256'
PLAN_KEYS = 'schema_version command operation_id channel layout source source_files tools versions requested_agents effective_agents entry_plan entry_inputs observations scene_sha256 legacy_identity legacy_import outputs directories bootstrap journal staged_registry metadata_scopes changes agent_facts source_tree_sha256 inventory plan_sha256'


class InstallError(ValueError):
    def __init__(self, message, code='install_conflict', journal=None):
        super().__init__(message)
        self.code, self.journal = code, None if journal is None else str(journal)


def _fail(message, code='install_conflict'):
    raise InstallError(message, code)


def _node(path):
    path = Path(path)
    try:
        st = path.lstat()
    except FileNotFoundError:
        return {'kind': 'absent'}
    mode = stat.S_IMODE(st.st_mode)
    if stat.S_ISREG(st.st_mode):
        return {'kind': 'file', 'sha256': legacy.digest(path.read_bytes()), 'mode': mode}
    if stat.S_ISDIR(st.st_mode):
        return {'kind': 'directory', 'mode': mode}
    if stat.S_ISLNK(st.st_mode):
        return {'kind': 'symlink', 'target': os.readlink(path)}
    _fail('Special node: ' + str(path))


def _real_chain(path, home):
    path = Path(path)
    if not path.is_relative_to(home):
        _fail('Path escapes HOME')
    part = home
    for name in path.relative_to(home).parts:
        part = part / name
        node = _node(part)
        if node['kind'] == 'symlink':
            _fail('Symlink in managed path: ' + str(part))
        if part != path and node['kind'] not in ('absent', 'directory'):
            _fail('Non-directory parent: ' + str(part))


def _runtime(request):
    if not request.get('home'):
        _fail('Explicit HOME required')
    # Canonical targets are displayed in the plan, never silently changed later.
    home = Path(request['home']).resolve()
    runtime = RuntimeLayout(home)
    if not home.is_dir():
        _fail('HOME must already exist')
    runtime.validate_paths()
    _real_chain(runtime.code, home)
    return runtime


def _walk(root):
    result = {}
    def visit(path):
        node = _node(path)
        result[str(path)] = node
        if node['kind'] == 'directory':
            children = sorted(path.iterdir())
            folded = [unicodedata.normalize('NFC', p.name).casefold() for p in children]
            if len(set(folded)) != len(folded):
                _fail('case/Unicode collision at ' + str(path))
            for child in children: visit(child)
    visit(Path(root))
    return result


def _source(request):
    source = copy.deepcopy(request['source'])
    registry._keys(source, 'root url commit version files', 'install source')
    root = Path(source['root'])
    if not root.is_absolute() or root != root.resolve() or not root.is_dir():
        _fail('Source must be an existing canonical checkout/export')
    if not re.fullmatch('[0-9a-f]{40}|[0-9a-f]{64}', source['commit']):
        _fail('Pinned source commit required')
    if not re.fullmatch(r'(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)', source['version']):
        _fail('Release SemVer required')
    registry._text(source['url'])
    files = []
    if not isinstance(source['files'], dict) or not {'SKILL.md','scripts/agm.py','scripts/agm_core/__init__.py'} <= source['files'].keys():
        _fail('Missing required product files')
    collisions=set()
    for rel, expected in sorted(source['files'].items()):
        folded=unicodedata.normalize('NFC',rel).casefold()
        if folded in collisions:_fail('Case/Unicode collision in code manifest')
        collisions.add(folded)
        if rel=='.agm-code-manifest.json' or rel=='scripts/registry.json' or rel.startswith(('scripts/backups/','scripts/.agm.lock/')):
            _fail('Runtime state is not managed product code')
        p = Path(rel)
        if p.is_absolute() or str(p) != rel or '..' in p.parts or not p.parts or p.parts[0] == '.git':
            _fail('Unsafe source manifest path')
        target = root / rel
        if target != target.resolve() or not target.is_file():
            _fail('Nonregular/symlink source: ' + rel)
        meta = _node(target)
        if meta['sha256'] != expected:
            _fail('Source manifest drift: ' + rel, 'source_drift')
        if rel.endswith('.py'):
            ast.parse(target.read_bytes(), filename=rel, feature_version=(3,9))
        files.append({'path':rel, 'sha256':expected, 'mode':meta['mode'] & 0o777})
    if (root / '.git').exists():
        env = dict(os.environ, GIT_OPTIONAL_LOCKS='0')
        head = subprocess.run(['git','-C',str(root),'rev-parse','HEAD'],capture_output=True,text=True,env=env,check=True).stdout.strip()
        dirty = subprocess.run(['git','-C',str(root),'-c','core.fsmonitor=false','status','--porcelain','--',*source['files']],capture_output=True,text=True,env=env,check=True).stdout
        if head != source['commit'] or dirty:
            _fail('Checkout commit/managed files differ from source approval', 'source_drift')
    source['tree_sha256'] = legacy.digest(legacy.encoded(files))
    return source, files


def _code_matches(runtime, product):
    marker = runtime.code / '.agm-code-manifest.json'
    meta = migrate._json(marker)
    registry._keys(meta, 'product_id source files', 'code manifest')
    if meta['product_id'] != PRODUCT or meta['source'] != product['source']:
        _fail('Code/ledger identity mismatch')
    expected = {str(runtime.code):_node(runtime.code), str(marker):_node(marker)}
    for item in meta['files']:
        registry._keys(item, 'path sha256 mode', 'code file')
        rel = Path(item['path'])
        if rel.is_absolute() or '..' in rel.parts or str(rel) != item['path']:
            _fail('Unsafe code manifest')
        p = runtime.code / rel
        expected[str(p)] = {'kind':'file','sha256':item['sha256'],'mode':item['mode']}
        parent = p.parent
        while parent != runtime.code:
            expected[str(parent)] = _node(parent)
            parent = parent.parent
    if legacy.digest(legacy.encoded(meta['files'])) != product['source']['tree_sha256'] or _walk(runtime.code) != expected:
        _fail('Managed code dirty/extra/missing')


def inspect_machine(request):
    """Seven-way readonly routing; never creates logs, locks or empty registries."""
    result = {'scene':'abnormal','channel':'stop','observations':{},'errors':[], 'content_candidate':False}
    try:
        runtime = _runtime(request)
        result['layout'] = runtime.describe()
        guard=runtime.home/'.mem-sharing-upgrade.json'
        if os.path.lexists(guard):
            result.update(scene='interrupted',errors=['upgrade marker: '+str(guard)])
            return result
        observations = result['observations']
        observations.update(_walk(runtime.root))
        observations.update(_walk(runtime.code))
        _real_chain(versions.root(runtime),runtime.home)
        observations.update(_walk(versions.root(runtime)))
        for p in (runtime.code.parent,runtime.code.parent.parent):observations[str(p)]=_node(p)
        known_old = sorted({Path(p).resolve() for p in request.get('legacy_registries', [])} |
                           ({Path(request['source']['root'])/'scripts/registry.json'} if request.get('source') else set()))
        for old in known_old:
            observations[str(old)] = _node(old)
            observations[str(old.parent/'.agm.lock')] = _node(old.parent/'.agm.lock')
        # Seal the native directory's pre-install existence in the original approval.
        for agent in paths.NATIVE_SKILL_ROOTS:
            parent = paths.native_skill_path(agent, home=runtime.home).parent
            _real_chain(parent, runtime.home)
            observations[str(parent)] = _node(parent)
        for key in paths.allowed_user_paths(request['platform_config'], None, home=str(runtime.home)):
            p = Path(key)
            # 入口文件父链不得为符号链接;叶子本身的类型由场景枚举如实记录。
            _real_chain(p.parent, runtime.home)
            observations[str(p)] = _node(p)
        locks = [old.parent/'.agm.lock' for old in known_old] + [runtime.home/'.mem-sharing-install.lock',runtime.lock,runtime.transaction_lock]
        for lock in locks:
            if os.path.lexists(lock):
                result.update(scene='interrupted', errors=['writer lock: '+str(lock)])
                return result
        for opdir in sorted(runtime.home.glob('.mem-sharing-install-*')):
            if opdir.is_symlink() or not opdir.is_dir():
                _fail('Unknown bootstrap path')
            try:
                journal = migrate._json(opdir/'journal.json')
            except (OSError,ValueError):
                result.update(scene='interrupted', errors=['unreadable bootstrap: '+str(opdir)])
                return result
            if journal.get('product_id') != PRODUCT or journal.get('status') not in ('committed','rolled_back'):
                result.update(scene='interrupted', errors=['unfinished/unknown bootstrap: '+str(opdir)])
                return result
            command=journal.get('plan',{}).get('command')
            if command=='install-machine':
                validated,_=_load_journal(opdir/'journal.json')
            elif command=='migrate-machine':
                validated,_=migrate._load_journal(opdir/'journal.json')
            elif command=='upgrade-machine':
                from . import upgrade
                validated,_=upgrade._load_journal(opdir/'journal.json')
            else:
                _fail('Unexplained completed bootstrap metadata')
        v = _node(runtime.registry)
        if v['kind'] != 'absent':
            if v['kind'] != 'file':
                _fail('Invalid active registry type')
            raw = migrate._json(runtime.registry)
            version = raw.get('schema_version')
            product = raw.get('product')
            target = request.get('source',{}).get('version')
            newer = isinstance(product,dict) and ((isinstance(product.get('product_structure_version'),int) and product['product_structure_version']>1)
                     or target and re.fullmatch(r'\d+\.\d+\.\d+',str(product.get('product_code_version'))) and tuple(map(int,product['product_code_version'].split('.')))>tuple(map(int,target.split('.'))))
            if type(version) is int and version>3 or newer:
                result.update(scene='future',errors=['unsupported future version'])
                return result
            allowed = paths.allowed_user_paths(request['platform_config'],None,home=str(runtime.home))
            if type(version) is int and version in (1, 2):
                registry.load_diagnostic_registry(runtime.registry, allowed_user_paths=allowed)
                result.update(scene='unsupported', channel='stop', errors=['Old development ledger is diagnostic-only; preserve and reinstall'])
                return result
            data = registry.require_installed(registry.load_registry(runtime.registry,allowed_user_paths=allowed))
            _code_matches(runtime,data['product'])
            # Simultaneous regular old ledger is never selected by mtime.
            for old in known_old:
                if _node(old)['kind'] == 'file':
                    _fail('dual active ledgers require explicit migration recovery')
                if _node(old)['kind'] != 'absent' and str(old) not in (data.get('migration') or {}).get('tombstones',{}):
                    _fail('unexplained legacy registry')
            source,source_files = _source(request)
            identity = {'url':source['url'],'commit':source['commit'],'tree_sha256':source['tree_sha256']}
            if data['product']['product_code_version']==source['version'] and data['product']['source']==identity:
                result.update(scene='same',channel='upgrade')
            elif 'conversions' in request:
                from . import upgrade
                try:
                    upgrade._conversion(request,data,versions.descriptor(runtime,source,source_files),request.get('direction','upgrade'))
                except ValueError:
                    result.update(scene='future',errors=['no exact supported release conversion'])
                else:
                    result.update(scene='valid_old',channel='upgrade')
            elif {'version':data['product']['product_code_version'],'source':data['product']['source']} in request.get('supported_sources',[]):
                # Historical read-only callers; execution still requires the full
                # exact conversion in upgrade.plan_upgrade, never this short list.
                result.update(scene='valid_old',channel='upgrade')
            else:
                result.update(scene='future',errors=['no supported source conversion'])
            return result
        if any(_node(p)['kind']!='absent' for p in known_old):
            allowed=paths.allowed_user_paths(request['platform_config'],None,home=str(runtime.home))
            existing=[p for p in known_old if os.path.lexists(p)]
            scene=migrate.inspect_migration(runtime,existing,allowed_user_paths=allowed)
            result['legacy_product']=scene
            result.update(scene='unsupported',channel='stop',errors=[scene['message']])
            return result
        # §23:v0 源与目标分离——历史位置 ~/.agents-group(legacy_root)只作只读
        # v0 源,完整枚举进 observations 绑定 scene;产品自身永不写入该目录。
        observations.update(_walk(runtime.legacy_root))
        if os.path.lexists(versions.root(runtime)):
            _fail('Persistent product inventory without active ledger; explicit recovery required')
        if _node(runtime.code)['kind']!='absent':
            _fail('Product code without active ledger; not v0')
        for old in known_old:
            backup=old.parent/'backups'
            if backup.exists() and (not backup.is_dir() or any(backup.iterdir())):
                _fail('Known source recovery evidence without ledger')
        # v0 历史位置中的产品痕迹(历史产品名目录/var 台账)排除纯 v0 身份。
        for rel in ('var','skills/agent-group-memory'):
            if os.path.lexists(runtime.legacy_root/rel):
                _fail('Product/unknown state without ledger: '+str(runtime.legacy_root/rel))
        if runtime.root.exists() and any(runtime.root.iterdir()):
            # R(新位置)在无台账时不应有任何内容;v0 内容只认历史位置。
            _fail('Unexplained content without ledger: '+str(runtime.root))
        if (runtime.backups.exists() and any(runtime.backups.iterdir())):
            _fail('Unexplained backups without ledger')
        for key, meta in observations.items():
            if (meta['kind']=='file' and not Path(key).is_relative_to(runtime.root)
                    and not Path(key).is_relative_to(runtime.legacy_root)):
                raw=Path(key).read_bytes()
                if b'mem-sharing:' in raw or str(runtime.root/'memories/MEMORY.md').encode() in raw:
                    _fail('Product entry without ledger')
        legacy_present = runtime.legacy_root.exists() and any(runtime.legacy_root.iterdir())
        if not legacy_present:
            result.update(scene='empty',channel='fresh')
        else:
            # 历史位置完整枚举已进 observations,无未解释产品信号 → v0 候选。
            result.update(scene='v0',channel='legacy_copy',
                          content_candidate=any((runtime.legacy_root/n).exists() for n in legacy.ROOTS))
    except (ValueError,OSError,KeyError,TypeError) as exc:
        result.update(scene='bad_registry' if 'layout' in result and Path(result['layout']['registry']).exists() else 'abnormal', channel='stop')
        result['errors'].append(str(exc))
    return result


class _StagedLayout(RuntimeLayout):
    """Installer-local working ledger, invisible to normal runtime resolution."""
    def __init__(self, home, bootstrap):
        super().__init__(home)
        object.__setattr__(self,'bootstrap',Path(bootstrap))

    @property
    def registry(self): return self.bootstrap/'staged-registry.json'
    @property
    def lock(self): return self.bootstrap/'entry-lock'
    @property
    def backups(self): return self.bootstrap/'entry-backups'


def _entry_request(request,runtime,source,*,approval=None):
    return {k:v for k,v in dict(request,home=str(runtime.home),runtime_layout=runtime,
            verified_product_source=str(source),approval=approval).items()
            if k in ('home','runtime_layout','platform_config','agents','search_paths','app_directories','user_candidates','detect_runner','verified_product_source','approval')}


def _entry_plan(request,runtime,source,fingerprint):
    with user_entries._installer_source(runtime.code,fingerprint,preview=True):
        result=user_entries.run_user_entries(_entry_request(request,runtime,source))
    if result['status']=='completed':
        return None,result
    if result['status']!='approval_required':
        _fail('User-entry preflight: '+json.dumps(result['errors'],ensure_ascii=False))
    plan=json.loads(result['next_action']); plan.pop('confirmed_at'); plan.pop('reference')
    return plan,result


def plan_install(request):
    if sys.platform!='darwin':_fail('Production installation currently supports macOS only','platform_unsupported')
    if shutil.which('git') is None:_fail('Git missing; install Git manually before retrying','runtime_missing')
    runtime=_runtime(request)
    scene=inspect_machine(request)
    if scene['scene'] not in ('empty','v0'):
        _fail('Machine scene '+scene['scene']+': '+str(scene['errors']), 'machine_route_'+scene['scene'])
    source,files=_source(request)
    op=migrate._op(request.get('operation_id') or datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-'+uuid.uuid4().hex)
    bootstrap=runtime.home/('.mem-sharing-install-'+op)
    if os.path.lexists(bootstrap): _fail('Existing operation requires recovery')
    if (Path(source['root']).is_relative_to(runtime.root) or Path(source['root']).is_relative_to(runtime.code)
            or Path(source['root']).is_relative_to(runtime.legacy_root)):
        _fail('Source overlaps managed installation')
    # §23:v0 源(历史位置,只读)与目标 R 分离;阅读包/快照全部落在 R 下。
    imported=legacy.plan_import(runtime.legacy_root,runtime.root,op) if scene['scene']=='v0' else None
    identity=request.get('legacy_identity')
    if imported and identity not in (None,'confirmed_v0'):
        _fail('Previous product/uncertain identity: stop and recover')
    skill=source['files']['SKILL.md']
    entry_plan,entry_result=_entry_plan(request,runtime,source['root'],skill)
    tools=[{'path':p.name,'sha256':legacy.digest(p.read_bytes()),'mode':0o600} for p in sorted(Path(__file__).parent.glob('*.py'))]
    outputs=[]
    def output(path,after,origin=None,content=None):
        before=_node(path)
        if before['kind']!='absent' and before!=after:
            _fail('Different bytes/type at target: '+str(path))
        outputs.append({'path':str(path),'before':before,'after':after,'origin':origin,'content_hex':None if content is None else content.hex()})
    for item in files:
        output(runtime.code/item['path'],{'kind':'file','sha256':item['sha256'],'mode':item['mode']},origin='code:'+item['path'])
    marker=legacy.encoded({'product_id':PRODUCT,'source':{k:source[k] for k in ('url','commit','tree_sha256')},'files':files})
    output(runtime.code/'.agm-code-manifest.json',{'kind':'file','sha256':legacy.digest(marker),'mode':0o600},content=marker)
    if imported:
        for item in imported['items']:
            if item['disposition']!='copy' or item['type']=='directory': continue
            after={'kind':'symlink','target':item['text']} if item['type']=='symlink' else {'kind':'file','sha256':item['sha256'],'mode':item['mode']}
            output(Path(item['target']),after,origin='v0:'+item['path'])
        index=bytes.fromhex(imported['index_hex'])
    else:
        index='# 公共记忆\n\n'.encode()
    contract=user_entries.public_memory_contract_text(runtime.code)+'\n'
    if imported:
        # Keep legacy bytes and relative targets intact; only the new index is ours.
        index=index.replace(b'- [v0 ', '- v0 原文：历史字节已保存在只读阅读包，按需深读。 [v0 '.encode(),1)
        # v0 旧占位主题目录整行删除,索引只保留真实主题行,不留说明性占位行。
        index=index.replace('- [主题目录](topics/)\n'.encode(), b'')
    index=index.replace('# 公共记忆\n\n'.encode(),('# 公共记忆\n\n'+contract).encode(),1)
    if imported:
        imported['index_hex']=index.hex()
    # v0 源侧零写入:原文(含旧 MEMORY.md)原地不动;新索引是 R 下的全新文件。
    index_path=runtime.root/'memories/MEMORY.md'
    output(index_path,{'kind':'file','sha256':legacy.digest(index),'mode':0o600},content=index)
    # v1.11(2026-10-30 裁定):R 不建 skills/、mcp/,首装结构仅内容两目录+台账+备份。
    directories={str(runtime.root/n) for n in ('memories','references','backups','var')}
    if imported:
        directories.add(imported['package'])
        for item in imported['items']:
            if item['disposition']=='copy' and item['type']=='directory': directories.add(item['target'])
    for item in outputs:
        parent=Path(item['path']).parent
        while parent!=runtime.home and not parent.exists():
            directories.add(str(parent)); parent=parent.parent
    for directory in directories:
        _real_chain(Path(directory),runtime.home)
        if _node(directory)['kind'] not in ('absent','directory'): _fail('Directory conflict: '+directory)
    saved_inputs={k:copy.deepcopy(request[k]) for k in ('platform_config','agents','search_paths','app_directories','user_candidates') if k in request}
    plan={'schema_version':2,'command':'install-machine','operation_id':op,'channel':scene['channel'],
          'layout':runtime.describe(),'source':source,'source_files':files,'tools':tools,
          'versions':{'schema_version':3,'product_structure_version':1,'product_code_version':source['version']},
          'requested_agents':(entry_result.get('agents') or {}).get('requested',paths.resolve_agents(request.get('agents'))),
          'agent_facts':{a:{'status':fact['status'],'fingerprint':detect.detection_fingerprint(fact)} for a,fact in entry_result['detection']['agents'].items()},
          'effective_agents':(entry_result.get('agents') or {}).get('effective',[]),'entry_plan':entry_plan,'entry_inputs':saved_inputs,
          'observations':scene['observations'],'scene_sha256':legacy.digest(legacy.encoded(scene['observations'])),
          'legacy_identity':'confirmed_v0' if imported else None,'source_tree_sha256':imported['source_tree_sha256'] if imported else None,'legacy_import':imported,'outputs':outputs,
          'directories':sorted(directories,key=lambda p:(len(Path(p).parts),p)),
          'inventory':versions.descriptor(runtime,source,files),
          'bootstrap':str(bootstrap),'journal':str(bootstrap/'journal.json'),'staged_registry':str(bootstrap/'staged-registry.json'),
          'metadata_scopes':[str(bootstrap),str(runtime.backups/('v0-'+op))] if imported else [str(bootstrap)]}
    plan['metadata_scopes'] += [str(versions.root(runtime))]
    plan['changes']=([{'path':item['path'],'operation':'reuse' if item['before']==item['after'] else 'create' if item['before']['kind']=='absent' else 'legacy_index',
                       'before':item['before'],'after':item['after']} for item in outputs]
        + [{'path':p,'operation':'mkdir','before':_node(p)} for p in plan['directories'] if _node(p)['kind']=='absent']
        + (entry_plan or {}).get('changes',[])
        + [{'path':str(runtime.registry),'operation':'commit_registry_last','before':{'kind':'absent'},
            'after':{'product':_seed(plan)['product'],'machine_agents':plan['effective_agents'],
                     'machine_objects':(entry_plan or {}).get('machine_objects',[]),'legacy_import':_seed(plan)['legacy_import']}}]
        + [{'path':plan['inventory']['slot'],'operation':'register_persistent_version','before':_node(plan['inventory']['slot'])}]
        + [{'path':scope,'operation':'operation_metadata','before':{'kind':'absent'}} for scope in plan['metadata_scopes']]
        + [{'path':str(p),'operation':'writer_lock','before':{'kind':'absent'}} for p in
           (runtime.home/'.mem-sharing-install.lock',runtime.lock,runtime.transaction_lock)])
    plan['plan_sha256']=legacy.digest(legacy.encoded(plan))
    return plan


def _validate(plan, *, historical=False):
    registry._keys(plan,PLAN_KEYS,'install plan')
    body=dict(plan); digest=body.pop('plan_sha256')
    if legacy.digest(legacy.encoded(body))!=digest or plan['schema_version']!=2 or plan['command']!='install-machine':
        _fail('Invalid installation plan')
    if plan['versions'] != {'schema_version':3,'product_structure_version':1,'product_code_version':plan['source']['version']}:
        _fail('Old development installation journal is diagnostic-only; preserve and reinstall')
    runtime=RuntimeLayout(Path(plan['layout']['root']).parent)
    runtime.validate_paths(); _real_chain(runtime.code,runtime.home)
    versions.validate(runtime,plan['inventory'])
    if plan['inventory']!=versions.descriptor(runtime,plan['source'],plan['source_files']):_fail('Inventory/source mismatch')
    op=migrate._op(plan['operation_id'])
    bootstrap=runtime.home/('.mem-sharing-install-'+op)
    if plan['layout']!=runtime.describe() or plan['bootstrap']!=str(bootstrap) or plan['journal']!=str(bootstrap/'journal.json') or plan['staged_registry']!=str(bootstrap/'staged-registry.json'):
        _fail('Plan scope mismatch')
    if plan['legacy_import'] and (plan['legacy_identity']!='confirmed_v0' or plan['channel']!='legacy_copy'):
        _fail('Explicit v0 identity confirmation required','approval_required')
    if plan['legacy_import']:
        registry._keys(plan['legacy_import'],'identity_warning source source_root source_tree_sha256 snapshot manifest package items links excluded index_hex index_before_sha256','legacy import plan')
    if plan['source_tree_sha256']!=(plan['legacy_import'] or {}).get('source_tree_sha256'):_fail('v0 identity/tree binding mismatch')
    for item in plan['tools']:
        registry._keys(item,'path sha256 mode','recovery tool')
        if Path(item['path']).name!=item['path'] or not item['path'].endswith('.py'):_fail('Unsafe recovery tool path')
        registry._digest(item['sha256'])
    for directory in plan['directories']:
        p=Path(directory)
        if not (p.is_relative_to(runtime.root) or p.is_relative_to(runtime.code) or p in (runtime.code.parent,runtime.code.parent.parent)):
            _fail('Directory outside installation scope')
        _real_chain(p,runtime.home)
    for item in plan['outputs']:
        p=Path(item['path'])
        if not (p.is_relative_to(runtime.root) or p.is_relative_to(runtime.code)):
            _fail('Output escapes managed scope')
        _real_chain(p.parent,runtime.home)
        if item['content_hex'] is not None and legacy.digest(bytes.fromhex(item['content_hex']))!=item['after'].get('sha256'):
            _fail('Planned content fingerprint mismatch')
    return runtime


def _approve(plan,approval):
    migrate._approval(plan,approval)
    if plan.get('legacy_import') and approval.get('legacy_identity')!='confirmed_v0':
        _fail('v0 identity not confirmed','approval_required')


def _save(journal):
    migrate._put(Path(journal['plan']['journal']),legacy.encoded(journal),0o600)


def _intent(journal,kind,path,hook):
    journal['intent']={'kind':kind,'path':str(path)}; _save(journal)
    if hook: hook('intent:'+kind,Path(path))


def _mkdir(journal,path,hook,mode=0o700):
    path=Path(path)
    if path.exists():
        if path.is_symlink() or not path.is_dir(): _fail('Directory drift: '+str(path))
        return
    plan=journal['plan']
    if str(path) not in plan['directories'] and not any(path.is_relative_to(Path(scope)) for scope in plan['metadata_scopes']):
        _fail('Unapproved missing directory: '+str(path))
    if not path.parent.is_dir(): _mkdir(journal,path.parent,hook)
    _intent(journal,'mkdir',path,hook)
    path.mkdir(mode=mode & 0o777)
    journal['created_directories'].append(str(path)); _save(journal)


def _read_backup(journal,item):
    return Path(journal['plan']['bootstrap'])/'before'/legacy.digest(item['path'].encode())


def _capture(journal,item,hook):
    before=item['before']
    if before['kind']=='file':
        target=_read_backup(journal,item)
        _mkdir(journal,target.parent,hook)
        if target.exists():
            if _node(target)['sha256']!=before['sha256']: _fail('Corrupt before archive')
        else:
            if _node(item['path'])!=before: _fail('Before image no longer available')
            _intent(journal,'backup',target,hook)
            migrate._put(target,Path(item['path']).read_bytes(),0o600)


def _before_snapshot(journal,item):
    meta=item['before']
    if meta['kind']=='file':
        p=_read_backup(journal,item)
        if _node(p).get('sha256')!=meta['sha256']: _fail('Before archive missing/corrupt')
        return Snapshot('file',p.read_bytes(),meta['mode'])
    if meta['kind']=='symlink': return Snapshot('symlink',target=meta['target'])
    return Snapshot('absent')


def _source_unchanged(plan):
    source,files=_source({'source':{k:v for k,v in plan['source'].items() if k!='tree_sha256'}})
    if source!=plan['source'] or files!=plan['source_files']: _fail('Source changed','source_drift')


def _content_scene(plan):
    imported=plan['legacy_import']
    if not imported:return
    # §23 源/目标分离后 v0 源侧零写入:任何相对批准清单的变化都是漂移。
    now=legacy.inventory(imported['source_root'])
    if now['tree_sha256']!=imported['source_tree_sha256']:
        _fail('v0 content changed outside approved before/after','source_drift')


def _snapshot_verify(plan,root,*,moving=False):
    imported=plan['legacy_import']; root=Path(root)
    manifest=root/'source-manifest.json'
    if manifest.is_symlink() or _node(manifest).get('mode')!=0o400 or manifest.read_bytes()!=legacy.encoded(imported['source']): _fail('Snapshot manifest mismatch')
    if _node(root) not in ([{'kind':'directory','mode':0o500},{'kind':'directory','mode':0o700}] if moving else [{'kind':'directory','mode':0o500}]):_fail('Snapshot root is not sealed')
    expected={str(manifest)}
    for item in imported['source']['nodes']:
        if item.get('disposition')=='excluded_link':continue
        path=root/item['path']; expected.add(str(path)); node=_node(path)
        if item['type']=='directory':
            if node['kind']!='directory' or node['mode']!=(item['mode'] & 0o555): _fail('Snapshot directory drift')
        elif item['type']=='file':
            if node!={'kind':'file','sha256':item['sha256'],'mode':item['mode'] & 0o555}: _fail('Snapshot file drift')
        elif node!={'kind':'symlink','target':item['text']}: _fail('Snapshot link drift')
    actual=set(_walk(root));actual.remove(str(root))
    if actual!=expected: _fail('Snapshot contains unapproved material')


def _make_snapshot(journal,hook):
    plan=journal['plan']; imported=plan['legacy_import']
    if not imported:return
    stage=Path(plan['bootstrap'])/'source'; final=Path(imported['snapshot'])
    if journal['snapshot_complete']:
        location=Path(journal['snapshot_location'])
        # Crash between rename and journal update is a known before/after pair.
        if not location.exists() and final.exists():location=final
        _snapshot_verify(plan,location,moving=journal['intent']['kind']=='snapshot_move')
    else:
        _content_scene(plan)
        _mkdir(journal,stage,hook)
        for item in imported['source']['nodes']:
            if item.get('disposition')=='excluded_link':continue
            dest=stage/item['path']; source=Path(imported['source_root'])/item['path']
            if item['type']=='directory':_mkdir(journal,dest,hook)
            else:
                _mkdir(journal,dest.parent,hook)
                _intent(journal,'snapshot_copy',dest,hook)
                desired=Snapshot('symlink',target=item['text']) if item['type']=='symlink' else Snapshot('file',source.read_bytes(),item['mode'] & 0o555)
                if desired.kind=='file' and legacy.digest(desired.data)!=item['sha256']: _fail('v0 source drift during snapshot')
                current=read_snapshot(dest)
                if current.kind!='absent' and current!=desired:_fail('Partial snapshot conflict')
                if current!=desired:_apply(dest,desired,expected=current)
        _intent(journal,'snapshot_manifest',stage/'source-manifest.json',hook)
        manifest=stage/'source-manifest.json'
        if manifest.exists():
            if manifest.read_bytes()!=legacy.encoded(imported['source']):_fail('Partial snapshot manifest drift')
        else:migrate._put(manifest,legacy.encoded(imported['source']),0o400)
        for item in reversed(imported['source']['nodes']):
            if item['type']=='directory':
                _intent(journal,'snapshot_chmod',stage/item['path'],hook)
                (stage/item['path']).chmod(item['mode'] & 0o555)
        _intent(journal,'snapshot_seal',stage,hook);stage.chmod(0o500)
        _snapshot_verify(plan,stage)
        journal['snapshot_complete']=True;journal['snapshot_location']=str(stage);_save(journal)
        if hook:hook('snapshot_complete',stage)
        location=stage
    if location!=final:
        _mkdir(journal,final.parent,hook)
        if final.exists():_fail('Snapshot target conflict')
        _intent(journal,'snapshot_move',final,hook)
        location.chmod(0o700)  # Darwin requires a writable moved directory.
        os.rename(location,final);final.chmod(0o500);migrate._sync_directory(final.parent)
        journal['snapshot_location']=str(final);_save(journal)
    _snapshot_verify(plan,final)


def _import_manifest(journal,status,hook):
    plan=journal['plan']; imported=plan['legacy_import']
    if not imported:return
    path=Path(imported['manifest'])
    body={'schema_version':1,'product_id':PRODUCT,'operation_id':plan['operation_id'],
          'approval':{k:journal['approval'][k] for k in ('confirmed_at','reference')},'plan_sha256':plan['plan_sha256'],
          'source_root':imported['source_root'],'snapshot':imported['snapshot'],'source_tree_sha256':imported['source_tree_sha256'],
          'target_root':plan['layout']['root'],'excluded':imported['excluded'],'items':copy.deepcopy(imported['items']),
          'snapshot_complete':journal['snapshot_complete'],'status':status,'registry_sha256':journal['final_registry_sha256']}
    for item in body['items']:
        item['completed']=status in ('outputs_verified','committed')
    _mkdir(journal,path.parent,hook);_intent(journal,'import_manifest',path,hook)
    migrate._put(path,legacy.encoded(body),0o600)


def _toolkit(journal,hook):
    plan=journal['plan']; target=Path(plan['bootstrap'])/'tools/agm_core'
    _mkdir(journal,target,hook)
    for item in plan['tools']:
        dest=target/item['path']; src=Path(__file__).parent/item['path']
        if dest.exists():
            if _node(dest).get('sha256')!=item['sha256']: _fail('Recovery toolkit drift')
            continue
        if legacy.digest(src.read_bytes())!=item['sha256']: _fail('Recovery kernel changed since preview')
        _intent(journal,'toolkit',dest,hook);migrate._put(dest,src.read_bytes(),0o600)


def _output(journal,item,hook):
    path=Path(item['path']);expected=read_snapshot(path);current=_node(path)
    if current==item['after']:return
    if current!=item['before']:_fail('Output has third-state bytes: '+str(path),'drift')
    _capture(journal,item,hook)
    if item['content_hex'] is not None:data=bytes.fromhex(item['content_hex'])
    elif item['origin'].startswith('code:'):
        rel=item['origin'][5:];src=Path(journal['plan']['bootstrap'])/'code-source'/rel
        data=src.read_bytes()
    else:
        src=Path(journal['plan']['legacy_import']['snapshot'])/item['origin'][3:]
        data=src.read_bytes() if item['after']['kind']=='file' else None
    after=item['after']
    desired=Snapshot('symlink',target=after['target']) if after['kind']=='symlink' else Snapshot('file',data,after['mode'])
    if desired.kind=='file' and legacy.digest(data)!=after['sha256']:_fail('Output source corruption')
    _mkdir(journal,path.parent,hook);_intent(journal,'output',path,hook)
    _apply(path,desired,expected=expected)
    if _node(path)!=after:_fail('Output readback mismatch')
    journal['completed'].append(str(path));_save(journal)
    if hook:hook('after_output',path)


def _stage_code(journal,hook):
    plan=journal['plan'];base=Path(plan['bootstrap'])/'code-source'
    for item in plan['source_files']:
        src=Path(plan['source']['root'])/item['path'];dest=base/item['path']
        if dest.exists():
            if _node(dest).get('sha256')!=item['sha256']:_fail('Staged code drift')
            continue
        if legacy.digest(src.read_bytes())!=item['sha256']:_fail('Source code drift')
        _mkdir(journal,dest.parent,hook);_intent(journal,'code_snapshot',dest,hook)
        migrate._put(dest,src.read_bytes(),0o600)


def _seed(plan):
    data=registry.empty_registry()
    data['product']={'product_id':PRODUCT,'installation_id':plan['operation_id'],
        'product_structure_version':1,'product_code_version':plan['source']['version'],
        'source':{k:plan['source'][k] for k in ('url','commit','tree_sha256')},
        'installation_status':'complete','last_operation_id':plan['operation_id']}
    if plan['legacy_import']:
        imported=plan['legacy_import']
        data['legacy_import']={'operation_id':plan['operation_id'],'source_tree_sha256':imported['source_tree_sha256'],
                              'manifest_path':imported['manifest'],'status':'committed'}
    return data


def _recover_entry_manifest(journal,request,path,hook):
    """Validate exact delegated outputs/ancestors before its generic recovery.

    Transaction recovery scopes include created parents (e.g. .codex), while the
    entry writer approves leaf paths. This adapter permits only those exact
    ancestors/outputs, not arbitrary files under the broader HOME scope.
    """
    from .transaction import recover_manifest
    plan=journal['plan'];runtime=_validate(plan);stage=_StagedLayout(runtime.home,plan['bootstrap'])
    manifest=migrate._json(path)
    registry._keys(manifest,'schema_version operation status registry_path created_directories entries error','entry transaction')
    if manifest['schema_version']!=1 or manifest['operation']!=user_entries.COMMAND or manifest['registry_path']!=str(stage.registry):
        _fail('Untrusted delegated transaction identity')
    changes={item['path']:item for item in (plan['entry_plan'] or {}).get('changes',[])}
    allowed=set(changes)|{str(stage.registry)}
    parents=set()
    for raw in allowed:
        parent=Path(raw).parent
        while parent!=runtime.home and parent.is_relative_to(runtime.home):
            parents.add(str(parent));parent=parent.parent
    if not set(manifest['created_directories'])<=parents:_fail('Unapproved delegated directory')
    seen=set()
    seed_hash=legacy.digest(registry.serialize_registry(_seed(plan),allowed_user_paths=paths.allowed_user_paths(request['platform_config'],None,home=str(runtime.home))))
    for item in manifest['entries']:
        registry._keys(item,'path before after attempted restoration','entry transaction output')
        key=item['path']
        if key not in allowed or key in seen:_fail('Unapproved delegated output')
        seen.add(key)
        if key==str(stage.registry):
            if item['before']['kind']!='file' or item['before']['fingerprint']!=seed_hash:_fail('Staged registry before-image mismatch')
        else:
            expected=changes[key]
            initial=plan['observations'][key]
            if item['before']['kind']!=initial['kind'] or item['before']['mode']!=initial.get('mode') or item['before']['link_target']!=initial.get('target'):
                _fail('Delegated before-image metadata differs from approval')
            if item['before']['fingerprint']!=expected['before_fingerprint'] or item['after']['fingerprint']!=expected['after_fingerprint']:
                _fail('Delegated output fingerprints differ from installation approval')
    _intent(journal,'recover_entry_manifest',path,hook)
    return recover_manifest(path,lock_path=stage.bootstrap/'recovery-entry-lock',allowed_roots=[runtime.home],hook=hook)


def _stage_entries(journal,request,hook):
    plan=journal['plan'];runtime=_validate(plan);stage=_StagedLayout(runtime.home,plan['bootstrap'])
    allowed=paths.allowed_user_paths(request['platform_config'],None,home=str(runtime.home))
    if not stage.registry.exists():
        _intent(journal,'staged_registry',stage.registry,hook)
        migrate._put(stage.registry,registry.serialize_registry(_seed(plan),allowed_user_paths=allowed),0o600)
    if journal['entry_registry_sha256']:
        if _node(stage.registry).get('sha256')!=journal['entry_registry_sha256']:_fail('Staged registry drift')
        return registry.load_registry(stage.registry,allowed_user_paths=allowed)
    if plan['entry_plan']:
        # A crash after the delegated commit but before our receipt is a known
        # after state. Verify it instead of replaying the original creation plan.
        staged_data=registry.load_registry(stage.registry,allowed_user_paths=allowed)
        expected_ids=set(plan['entry_plan']['machine_objects'])
        if (set(staged_data['machine']['objects'])==expected_ids
                and set(staged_data['machine']['agents'])==set(plan['effective_agents'])
                and all(s['state']=='after' for s in _entry_states(plan))):
            user_entries._preflight_machine_units(staged_data)
            journal['entry_registry_sha256']=_node(stage.registry)['sha256'];_save(journal)
            return staged_data
        from .transaction import recover_manifest
        for manifest in sorted(stage.backups.glob('*/manifest.json')):
            if migrate._json(manifest)['status'] in ('prepared','applying','recovery_required'):
                _intent(journal,'recover_entry_transaction',manifest,hook)
                _recover_entry_manifest(journal,request,manifest,hook)
        approval=dict(plan['entry_plan'],**{k:journal['approval'][k] for k in ('confirmed_at','reference')})
        _intent(journal,'user_entries',stage.registry,hook)
        with user_entries._installer_source(runtime.code,plan['source']['files']['SKILL.md'],preview=False):
            result=user_entries.run_user_entries(_entry_request(request,stage,Path(plan['bootstrap'])/'code-source',approval=approval))
        if result['status']!='completed':_fail('User-entry execution: '+json.dumps(result,ensure_ascii=False),'entries_incomplete')
    journal['entry_registry_sha256']=_node(stage.registry)['sha256'];_save(journal)
    if hook:hook('after_entries',stage.registry)
    return registry.load_registry(stage.registry,allowed_user_paths=allowed)


def _verify_entry_outputs(plan):
    states=_entry_states(plan)
    if any(item['state']!='after' for item in states):_fail('User entries are not the approved after state')
    changed={item['path'] for item in states}
    home=str(Path(plan['layout']['root']).parent)
    for path in paths.allowed_user_paths(plan['entry_inputs']['platform_config'],None,home=home):
        if path not in changed and _node(path)!=plan['observations'][path]:
            _fail('Unchanged user entry drifted: '+path)


def _package_scope(plan):
    if not plan['legacy_import']:return
    package=Path(plan['legacy_import']['package'])
    allowed={str(package)}|{p for p in plan['directories'] if Path(p).is_relative_to(package)}|{item['path'] for item in plan['outputs'] if Path(item['path']).is_relative_to(package)}
    if package.exists() and set(_walk(package))-allowed:_fail('Unapproved node in legacy reading package')


def _verify_outputs(plan):
    for item in plan['outputs']:
        if _node(item['path'])!=item['after']:_fail('Output drift before commit: '+item['path'])
    _content_scene(plan);_package_scope(plan)
    _code_matches(RuntimeLayout(Path(plan['layout']['root']).parent),_seed(plan)['product'])
    if plan['legacy_import']:_snapshot_verify(plan,plan['legacy_import']['snapshot'])


def _finish(journal,request,hook):
    plan=journal['plan'];runtime=_validate(plan)
    if journal['final_registry_sha256'] and _node(runtime.registry).get('sha256')==journal['final_registry_sha256']:
        _verify_outputs(plan);_verify_entry_outputs(plan)
        allowed=paths.allowed_user_paths(request['platform_config'],None,home=str(runtime.home))
        data=registry.load_registry(runtime.registry,allowed_user_paths=allowed)
        user_entries._preflight_machine_units(data)
        if plan['legacy_import']:_snapshot_verify(plan,plan['legacy_import']['snapshot'])
        _import_manifest(journal,'committed',hook)
        versions.activate(runtime,plan['inventory'],plan['operation_id'],plan['journal'],journal['final_registry_sha256'],
            mkdir=lambda p:_mkdir(journal,p,hook),intent=lambda k,p:_intent(journal,k,p,hook))
        journal['status']='committed';_save(journal)
        return {'status':'completed','journal':plan['journal'],'operation_id':plan['operation_id'],'finalized_only':True}
    _toolkit(journal,hook);_stage_code(journal,hook)
    versions.ensure(runtime,plan['inventory'],Path(plan['bootstrap'])/'code-source',plan['operation_id'],
        mkdir=lambda p:_mkdir(journal,p,hook),intent=lambda k,p:_intent(journal,k,p,hook),hook=hook)
    if plan['legacy_import']:
        if not journal['snapshot_complete']:_import_manifest(journal,'prepared',hook)
        _make_snapshot(journal,hook);_import_manifest(journal,'snapshot_complete',hook)
    for directory in plan['directories']:_mkdir(journal,directory,hook)
    journal['status']='applying';_save(journal);_import_manifest(journal,'applying',hook)
    for item in plan['outputs']:_output(journal,item,hook)
    if hook:hook('after_code',runtime.code)
    data=_stage_entries(journal,request,hook)
    _verify_entry_outputs(plan)
    _verify_outputs(plan)
    _source_unchanged(plan)
    _import_manifest(journal,'outputs_verified',hook)
    journal['status']='outputs_verified';_save(journal)
    if hook:hook('before_commit',runtime.registry)
    _verify_outputs(plan);_source_unchanged(plan)
    # Schema validation also checks created entry transaction evidence.
    allowed=paths.allowed_user_paths(request['platform_config'],None,home=str(runtime.home))
    content=registry.serialize_registry(data,allowed_user_paths=allowed)
    journal['final_registry_sha256']=legacy.digest(content);_save(journal)
    _intent(journal,'registry_commit',runtime.registry,hook)
    _verify_outputs(plan);_verify_entry_outputs(plan);user_entries._preflight_machine_units(data)
    _source_unchanged(plan)
    _apply(runtime.registry,Snapshot('file',content,0o600),expected=Snapshot('absent'))
    if hook:hook('after_commit',runtime.registry)
    if _node(runtime.registry).get('sha256')!=journal['final_registry_sha256']:_fail('Registry commit readback drift')
    _verify_outputs(plan);_verify_entry_outputs(plan);user_entries._preflight_machine_units(data)
    versions.activate(runtime,plan['inventory'],plan['operation_id'],plan['journal'],journal['final_registry_sha256'],
        mkdir=lambda p:_mkdir(journal,p,hook),intent=lambda k,p:_intent(journal,k,p,hook))
    _import_manifest(journal,'committed',hook);journal['status']='committed';_save(journal)
    return {'status':'completed','journal':plan['journal'],'operation_id':plan['operation_id'],'legacy_import':plan['legacy_import'] is not None}


def _request(plan,request=None):
    result=dict(plan['entry_inputs'],home=str(Path(plan['layout']['root']).parent))
    if request and request.get('detect_runner'):result['detect_runner']=request['detect_runner']
    return result


def execute_install(plan,approval,*,request=None,hook=None):
    runtime=_validate(plan);_approve(plan,approval)
    checked=dict(_request(plan,request),source={k:v for k,v in plan['source'].items() if k!='tree_sha256'})
    scene=inspect_machine(checked)
    if scene['channel']!=plan['channel'] or scene['observations']!=plan['observations']:_fail('Machine changed since preview','source_drift')
    _source_unchanged(plan)
    current,current_result=_entry_plan(checked,runtime,plan['source']['root'],plan['source']['files']['SKILL.md'])
    facts={a:{'status':fact['status'],'fingerprint':detect.detection_fingerprint(fact)} for a,fact in current_result['detection']['agents'].items()}
    if current!=plan['entry_plan'] or facts!=plan['agent_facts']:_fail('Executor/entry scene changed since preview','approval_required')
    bootstrap=Path(plan['bootstrap'])
    if bootstrap.exists():_fail('Existing operation; use explicit recovery')
    journal={'schema_version':1,'product_id':PRODUCT,'operation_id':plan['operation_id'],'plan':plan,'approval':approval,
        'status':'prepared','intent':{'kind':'bootstrap','path':str(bootstrap)},'created_directories':[], 'completed':[],
        'snapshot_complete':False,'snapshot_location':None,'entry_registry_sha256':None,'final_registry_sha256':None}
    with migrate._lock(runtime.home/'.mem-sharing-install.lock',plan):
        # Recheck while owning installation lock, excluding that transient lock.
        # Independently compare every bound observation while owning the lock.
        if any(_node(p)!=n for p,n in plan['observations'].items()):_fail('Locked before scene changed','source_drift')
        _source_unchanged(plan)
        bootstrap.mkdir(mode=0o700);_save(journal)
        try:
            _mkdir(journal,runtime.var,hook)
            with migrate._lock(runtime.lock,plan),migrate._lock(runtime.transaction_lock,plan):
                return _finish(journal,checked,hook)
        except BaseException:
            journal['status']='recovery_required';_save(journal)
            raise


def _load_journal(path):
    path=Path(path)
    if path.is_symlink() or path!=path.resolve():_fail('Unsafe journal path')
    journal=migrate._json(path)
    registry._keys(journal,JOURNAL_KEYS,'installation journal')
    runtime=_validate(journal['plan'],historical=journal['status'] in ('committed','rolled_back'));_approve(journal['plan'],journal['approval'])
    if journal['schema_version']!=1 or journal['product_id']!=PRODUCT or journal['operation_id']!=journal['plan']['operation_id'] or str(path)!=journal['plan']['journal']:
        _fail('Journal identity mismatch')
    if type(journal['snapshot_complete']) is not bool:_fail('Invalid snapshot completion marker')
    for field in ('entry_registry_sha256','final_registry_sha256'):
        if journal[field] is not None:registry._digest(journal[field])
    for raw in journal['created_directories']:
        p=Path(raw)
        if raw not in journal['plan']['directories'] and not any(p.is_relative_to(Path(scope)) for scope in journal['plan']['metadata_scopes']):
            _fail('Unapproved journal directory')
        _real_chain(p,runtime.home)
    if not set(journal['completed'])<={item['path'] for item in journal['plan']['outputs']}:_fail('Unapproved journal output')
    if journal['snapshot_location'] not in (None,str(Path(journal['plan']['bootstrap'])/'source'),(journal['plan']['legacy_import'] or {}).get('snapshot')):
        _fail('Snapshot location outside approved operation')
    if journal['status'] not in ('prepared','applying','outputs_verified','committed','rolled_back','recovery_required'):_fail('Unknown installation status')
    imported=journal['plan']['legacy_import']
    if imported and Path(imported['manifest']).exists():
        manifest=migrate._json(Path(imported['manifest']))
        registry._keys(manifest,'schema_version product_id operation_id approval plan_sha256 source_root snapshot source_tree_sha256 target_root excluded items snapshot_complete status registry_sha256','import manifest')
        if manifest['schema_version']!=1 or manifest['product_id']!=PRODUCT or manifest['operation_id']!=journal['operation_id'] or manifest['plan_sha256']!=journal['plan']['plan_sha256'] or manifest['status'] not in ('prepared','snapshot_complete','applying','outputs_verified','committed','recovery_required','rolled_back'):
            _fail('Import manifest identity/status mismatch')
        if (manifest['approval']!={k:journal['approval'][k] for k in ('confirmed_at','reference')}
                or manifest['target_root']!=journal['plan']['layout']['root']
                or type(manifest['snapshot_complete']) is not bool
                or manifest['registry_sha256'] not in (None,journal['final_registry_sha256'])):
            _fail('Import manifest metadata drift')
        expected=copy.deepcopy(imported['items'])
        for item in manifest['items']:
            if type(item.get('completed')) is not bool:_fail('Invalid import completion marker')
        observed=copy.deepcopy(manifest['items'])
        for item in observed:item['completed']=False
        if observed!=expected or any(manifest[k]!=imported[k] for k in ('source_root','snapshot','source_tree_sha256','excluded')):
            _fail('Import manifest payload drift')
    return journal,runtime


def _entry_states(plan):
    observed=[]
    for item in (plan['entry_plan'] or {}).get('changes',[]):
        path=Path(item['path']);snap=read_snapshot(path)
        if snap.fingerprint not in (item['before_fingerprint'],item['after_fingerprint']):
            _fail('User-entry third-state edit: '+str(path))
        observed.append({'path':str(path),'state':'after' if snap.fingerprint==item['after_fingerprint'] else 'before','node':_node(path)})
    return observed


def _recovery_scene(journal):
    plan=journal['plan'];runtime=_validate(plan)
    outputs=[]
    for item in plan['outputs']:
        current=_node(item['path'])
        if current not in (item['before'],item['after']):_fail('Third-state output: '+item['path'])
        outputs.append({'path':item['path'],'state':'after' if current==item['after'] else 'before'})
        if item['before']['kind']=='file' and current==item['after']:_before_snapshot(journal,item)
    entries=_entry_states(plan)
    v=_node(runtime.registry)
    if v['kind']=='absent':target='before'
    elif v['kind']=='file' and v['sha256']==journal['final_registry_sha256']:target='after'
    else:_fail('Active registry changed outside operation')
    if target=='after' and any(item['state']!='after' for item in outputs+entries):
        _fail('V after with incomplete/mixed outputs; manual recovery required')
    _content_scene(plan);_package_scope(plan)
    expected_code={item['path'] for item in plan['outputs'] if Path(item['path']).is_relative_to(runtime.code)}
    expected_code.update(p for p in plan['directories'] if Path(p).is_relative_to(runtime.code))
    if runtime.code.exists() and set(_walk(runtime.code))-expected_code:
        _fail('Foreign node in partial code installation')
    if journal['snapshot_complete']:
        imported=plan['legacy_import'];p=Path(journal['snapshot_location'])
        if not p.exists():p=Path(imported['snapshot'])
        _snapshot_verify(plan,p,moving=journal['intent']['kind']=='snapshot_move')
    for item in plan['tools']:
        p=Path(plan['bootstrap'])/'tools/agm_core'/item['path']
        if p.exists() and _node(p).get('sha256')!=item['sha256']:_fail('Recovery toolkit changed')
    return {'target':target,'outputs':outputs,'entries':entries}


def plan_recovery(journal_path,*,action):
    journal,runtime=_load_journal(journal_path);plan=journal['plan']
    if action not in ('continue','rollback'):_fail('Unknown recovery action')
    scene=_recovery_scene(journal)
    lockpaths=[runtime.home/'.mem-sharing-install.lock',runtime.lock,runtime.transaction_lock]
    locks=[obs for obs in (migrate._stale_observation(p,plan) for p in lockpaths) if obs]
    staged=_StagedLayout(runtime.home,plan['bootstrap'])
    # The op-local child lock has no other legitimate writer. Still require a
    # proven dead installation owner, explicit exact inode approval and emptiness.
    stage_locks=[]
    for path in (staged.lock,staged.transaction_lock):
        if os.path.lexists(path):
            if not locks or path.is_symlink() or not path.is_dir() or set(p.name for p in path.iterdir())-{'transaction'}:
                _fail('Unknown staged lock owner; manual inspection required','lock_conflict')
            info=path.stat();stage_locks.append({'path':str(path),'device':info.st_dev,'inode':info.st_ino})
    closed=journal['status'] in ('committed','rolled_back')
    if closed and (not locks or action!=('continue' if journal['status']=='committed' else 'rollback')):
        _fail('Closed operation; no duplicate import/downgrade')
    if action=='continue' and scene['target']=='before':_source_unchanged(plan)
    result={'schema_version':1,'command':'recover-machine-install','operation_id':plan['operation_id'],
        'journal':str(journal_path),'journal_sha256':_node(journal_path)['sha256'],'installation_plan_sha256':plan['plan_sha256'],
        'action':action,'scene':scene,'stale_locks':locks,'staged_locks':stage_locks,'cleanup_only':closed}
    result['plan_sha256']=legacy.digest(legacy.encoded(result))
    return result


def _rollback_install(journal,request,hook):
    plan=journal['plan'];runtime=_validate(plan)
    # Remove exact V first so restoring config cannot expose a second active state.
    if _node(runtime.registry)['kind']!='absent':
        expected_registry=read_snapshot(runtime.registry)
        _intent(journal,'rollback_registry',runtime.registry,hook)
        _apply(runtime.registry,Snapshot('absent'),expected=expected_registry)
    # Restore user outputs from the transaction's own manifest(s), never reimplement
    # ownership deletion. Completed entry tx requires an explicit recovery copy.
    staged=_StagedLayout(runtime.home,plan['bootstrap'])
    from .transaction import recover_manifest
    if staged.backups.exists():
        for manifest_path in sorted(staged.backups.glob('*/manifest.json'),reverse=True):
            manifest=migrate._json(manifest_path)
            if manifest['status']=='committed':
                recovery=manifest_path.with_name('rollback-manifest.json')
                manifest['status']='recovery_required'
                _intent(journal,'rollback_entry_manifest',recovery,hook)
                migrate._put(recovery,legacy.encoded(manifest),0o600)
                target=recovery
            elif manifest['status'] in ('prepared','applying','recovery_required'):target=manifest_path
            else:continue
            _intent(journal,'rollback_user_entries',target,hook)
            _recover_entry_manifest(journal,request,target,hook)
    for item in reversed(plan['outputs']):
        current=_node(item['path'])
        if current==item['before']:continue
        if current!=item['after']:_fail('Rollback would overwrite a foreign edit')
        expected_output=read_snapshot(item['path'])
        _intent(journal,'rollback_output',Path(item['path']),hook)
        _apply(Path(item['path']),_before_snapshot(journal,item),expected=expected_output)
    journal['status']='rolled_back';_save(journal);_import_manifest(journal,'rolled_back',hook)
    # Keep bootstrap, tools and source snapshot evidence. Only remove ours if empty.
    for directory in reversed(journal['created_directories']):
        p=Path(directory)
        if p.is_relative_to(versions.root(runtime)) or p.is_relative_to(Path(plan['bootstrap'])) or plan['legacy_import'] and p.is_relative_to(Path(plan['legacy_import']['snapshot']).parent):continue
        if p.is_dir() and not p.is_symlink():
            try:p.rmdir()
            except OSError:pass
    return {'status':'rolled_back','journal':plan['journal'],'operation_id':plan['operation_id']}


def recover_install(recovery_plan,approval,*,request=None,hook=None):
    _approve(recovery_plan,approval)
    fresh=plan_recovery(recovery_plan['journal'],action=recovery_plan['action'])
    if fresh!=recovery_plan:_fail('Recovery scene/journal changed since preview','source_drift')
    journal,runtime=_load_journal(recovery_plan['journal']);plan=journal['plan']
    # Remove only approved exited owners, children first, rechecking each inode.
    for item in reversed(recovery_plan['staged_locks']):
        p=Path(item['path']);st=p.stat()
        if (st.st_dev,st.st_ino)!=(item['device'],item['inode']):_fail('Staged lock replaced')
        p.rmdir()
    for item in reversed(recovery_plan['stale_locks']):
        p=Path(item['path'])
        if migrate._stale_observation(p,plan)!=item:_fail('Stale lock changed')
        (p/'migration-owner.json').unlink();p.rmdir()
    if recovery_plan['cleanup_only']:return {'status':journal['status'],'cleanup_only':True}
    req=_request(plan,request)
    with migrate._lock(runtime.home/'.mem-sharing-install.lock',plan):
        _mkdir(journal,runtime.var,hook)
        with migrate._lock(runtime.lock,plan),migrate._lock(runtime.transaction_lock,plan):
            _recovery_scene(journal)
            try:
                if recovery_plan['action']=='rollback':result=_rollback_install(journal,req,hook)
                else:result=_finish(journal,req,hook)
            except BaseException:
                journal['status']='recovery_required';_save(journal)
                raise

    if result['status']=='rolled_back':
        for raw in reversed(journal['created_directories']):
            path=Path(raw)
            if path.is_relative_to(versions.root(runtime)) or path.is_relative_to(Path(plan['bootstrap'])) or plan['legacy_import'] and path.is_relative_to(Path(plan['legacy_import']['snapshot']).parent):continue
            if path.is_dir() and not path.is_symlink():
                try:path.rmdir()
                except OSError:pass
    return result
