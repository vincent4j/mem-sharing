"""Explicit release upgrade/rollback, registry-last commit and fixed-tool recovery.

No CLI, import-time work, implicit migration, network, or default HOME. The exact
conversion list is a release input (and part of approval), never SemVer guessing.
"""
import ast
import copy
import json
import os
import re
import sys
import uuid
from contextlib import ExitStack
from datetime import datetime, timezone
from pathlib import Path

from . import legacy_import as legacy, migrate, paths, registry, user_entries, versions
from . import user_install as install
from . import public_layout
from .layout import RuntimeLayout
from .transaction import Snapshot, _apply, read_snapshot

PRODUCT = 'mem-sharing'
PLAN_KEYS = ('schema_version command operation_id direction channel layout source source_files tools '
             'before_registry before_registry_hex before_product after_registry_hex final_registry_sha256 '
             'before_inventory target_inventory conversion migration_plan outputs obsolete_directories directories '
             'bootstrap journal archive launcher_hex metadata_scopes allowed_user_paths entry_facts noop changes plan_sha256')
JOURNAL_KEYS = ('schema_version product_id operation_id plan approval status intent created_directories '
                'final_registry_sha256 phase')
PHASES = ('prepare', 'archive', 'inventory', 'code', 'verify', 'commit')

_ENTRY_CONTRACT_NAMES = ('scripts/agents.json', 'scripts/agm_core/user_entries.py')

# A single reviewed contract transition, not a general "preserve" escape hatch.
# Target commit/tree live in the external exact conversion to avoid a source
# commit hashing itself. Contract bytes and the predecessor are fixed here.
WORKBUDDY_PREDECESSOR = {
    'url': 'https://github.com/vincent4j/mem-sharing',
    'commit': '4cfe7bedfde695b0bd4085ccc453afd3ef161711',
    'tree_sha256': '5af4e9208884560741ce05081d157cfa57d42789b3d87cd6554491cb951e875b',
}
WORKBUDDY_ENTRY_CONVERSION = {
    'type': 'workbuddy-public-index-v1',
    'before_contract': {
        'scripts/agents.json': '9a4f127be6582956544ec10b605f33635fecb63a4c0e315246fb7bf4a7a508ab',
        'scripts/agm_core/user_entries.py': '155eba8df9b14ccb96e017bc19e3975930be544019fdb1d3aaa17f3aa563be44',
    },
    'after_contract': {
        'scripts/agents.json': '9a4f127be6582956544ec10b605f33635fecb63a4c0e315246fb7bf4a7a508ab',
        'scripts/agm_core/user_entries.py': 'eda73b02e99d8092f6f587d786d163efd4d8bbc72340e79de0ad1ffabd25c85a',
    },
}

# 0.1.3 public-memory-layout-v1:两个精确前身(0.1.1=04c32e2,0.1.2=0f690ef,
# tree 均经 git 核验)。前身及目标合同均为冻结的发行字面量;
# 固定 handler 校验运行模块与精确目标合同一致。
PUBLIC_LAYOUT_TARGET_VERSION = '0.1.3'
PUBLIC_LAYOUT_BEFORE_CONTRACT = {
    'scripts/agents.json': '9a4f127be6582956544ec10b605f33635fecb63a4c0e315246fb7bf4a7a508ab',
    'scripts/agm_core/user_entries.py': 'eda73b02e99d8092f6f587d786d163efd4d8bbc72340e79de0ad1ffabd25c85a',
}
PUBLIC_LAYOUT_PREDECESSORS = (
    {'product_code_version': '0.1.1', 'source': {
        'url': 'https://github.com/vincent4j/mem-sharing',
        'commit': '04c32e24b9ab9504514908f2368cddca4356e478',
        'tree_sha256': '15cd779745ab6ef80f3d966ef8c9850ee1e87abc48c314158a6502434127e179'}},
    {'product_code_version': '0.1.2', 'source': {
        'url': 'https://github.com/vincent4j/mem-sharing',
        'commit': '0f690ef7aabf747a23bacc7662c19bee34c4bf52',
        'tree_sha256': '1fb1e199c992e07747bbf031fcb83cd74d2b85b5c9c491cda7d2836fca1dd353'}},
)
PUBLIC_MEMORY_LAYOUT_CONVERSION = {'type': public_layout.HANDLER_TYPE}


# 0.1.5 native-entry-refresh-v1:现机真实前身 0.1.4(local-checkout 来源)→新 0.1.5
# 的专用一次性入口合同转换。前身 url/commit/tree 与前后入口合同均为冻结发行
# 字面量(前身合同字节与现装 .agm-code-manifest.json 核对一致);目标 S/tree 只由
# 外部精确 conversion 绑定,源码不自引用。入口/公共模板字节刷新不在升级核心内
# 隐式执行:代码升级后由既有入口装配与 agm.py migrate-policy(私文/指纹保全)
# 另行精确预览批准。历史 SOURCE 常量与 same-version/漂移/缺转换门禁不变。
NATIVE_ENTRY_PREDECESSOR = {
    'url': 'local-checkout:file:///Users/vincent4j/.local/share/mem-sharing-upgrade-sources/d14a3c0d121576cc7dbcab0c55ef4a680985f84e',
    'commit': 'd14a3c0d121576cc7dbcab0c55ef4a680985f84e',
    'tree_sha256': '5f65647a0b496bed48feadae67107a968fc086173e9766db74dc5b01fe80dfca',
}
NATIVE_ENTRY_TARGET_VERSION = '0.1.5'
NATIVE_ENTRY_CONVERSION = {
    'type': 'native-entry-refresh-v1',
    'before_contract': {
        'scripts/agents.json': '5aff7ec53cfddea2dca86e844a85903411c017488dd66f5f8ea7cb3e2a07f038',
        'scripts/agm_core/user_entries.py': '48e5677857b2aaece1cf2e711db4bb90ec2b9d6447b3baf682b76959c422346f',
    },
    'after_contract': {
        'scripts/agents.json': 'aa9a28a27f3c9bea6ca603dfa2cc24560a9feda3e5085a65d26960790fea9b24',
        'scripts/agm_core/user_entries.py': '81646d141068d76ccc8cb236c1dfd59e9379bbefd6b132fc6c461ff753ff8033',
    },
}

# 目标合同冻结字面量(2026-11-01 增OpenCode桌面安装信号按授权重冻结;
# test_opencode_desktop与既有投影/冻结完整性定向验证,历史SOURCE不变;
# 六家接入与V2入口预测按授权重冻结;
# test_upgrade_entry_projection 验证历史内核单次批准和真实执行比较;
# 2026-10-31 桌面双端适配按裁定显式
# 重冻结——agents.json 增 dsh/zcode 五家、user_entries.py 增专属兜底/DSH_HOME
# 守卫、public_layout.py native 模板按执行器分派。SOURCE 前身合同
# (WORKBUDDY_ENTRY_CONVERSION / PUBLIC_LAYOUT_BEFORE_CONTRACT / PREDECESSORS)
# 保持原值不动;版本仍 0.1.3;冻结完整性由 test_public_layout 的 freeze-integrity
# 用例守护)。
# 2026-11-01 经历开关退役按裁定重冻结——user_entries.py 模板按新职责生成
# (历史停用登记文案/菜单改接入项目规则/接口名不变),public_layout.py 冻结
# _OLD_CLAUDE_FALLBACK/_OLD_WORKBUDDY_FALLBACK 历史字面量;agents.json 不变;
# 版本仍 0.1.3;SOURCE 前身合同(PUBLIC_LAYOUT_BEFORE_CONTRACT/PREDECESSORS/
# WORKBUDDY_ENTRY_CONVERSION)保持原值;门禁不放宽,固定 handler 仍要求运行
# 模块哈希与目标合同精确一致。
PUBLIC_LAYOUT_TARGET_CONTRACT = {
    'scripts/agents.json': 'aa9a28a27f3c9bea6ca603dfa2cc24560a9feda3e5085a65d26960790fea9b24',
    'scripts/agm_core/user_entries.py': '81646d141068d76ccc8cb236c1dfd59e9379bbefd6b132fc6c461ff753ff8033',
    'scripts/agm_core/public_layout.py': '61277d0bb247bdfd1187ade9f19ff9e23d13975365cbf02cf2ce6222c51fadb3',
}


def _public_layout_target_contract():
    """目标合同摘要:固定字面量,不再随当前内核动态自算。"""
    frozen = dict(PUBLIC_LAYOUT_TARGET_CONTRACT)
    placeholder = frozen['scripts/agm_core/public_layout.py']
    if placeholder is None:
        _fail('Conversion contract is not frozen for this release', 'upgrade_unsupported')
    return frozen


def _public_layout_before(before):
    return any(before['product_code_version'] == item['product_code_version']
               and before['source'] == item['source']
               for item in PUBLIC_LAYOUT_PREDECESSORS)


def _public_layout_conversion(before, after, direction, entry_conversion, request):
    return (entry_conversion == PUBLIC_MEMORY_LAYOUT_CONVERSION
            and direction == 'upgrade'
            # Explicit agents limit onboarding only; existing public readers
            # still migrate as one complete, precisely approved dependency set.
            and _public_layout_before(before)
            and after['schema_version'] == 3 and after['product_structure_version'] == 1
            and after['product_code_version'] == PUBLIC_LAYOUT_TARGET_VERSION)


def _workbuddy_conversion(before, after, direction, entry_conversion):
    return (entry_conversion == WORKBUDDY_ENTRY_CONVERSION
            and direction == 'upgrade'
            and before == dict(schema_version=3, product_structure_version=1,
                               product_code_version='0.1.0', source=WORKBUDDY_PREDECESSOR)
            and after['schema_version'] == 3 and after['product_structure_version'] == 1
            and after['product_code_version'] == '0.1.1')


def _native_entry_conversion(before, after, direction, entry_conversion):
    """Dedicated 0.1.4→0.1.5 gate: exact frozen predecessor, target S/tree free.

    The after identity (commit/tree) is bound only by the external exact
    conversion request; the handler pins direction, versions and the frozen
    entry contracts so no other predecessor or target can ride this path.
    """
    return (entry_conversion == NATIVE_ENTRY_CONVERSION
            and direction == 'upgrade'
            and before == dict(schema_version=3, product_structure_version=1,
                               product_code_version='0.1.4', source=NATIVE_ENTRY_PREDECESSOR)
            and after['schema_version'] == 3 and after['product_structure_version'] == 1
            and after['product_code_version'] == NATIVE_ENTRY_TARGET_VERSION)



LAUNCHER = b'''import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / "tools"))
from agm_core import upgrade
if sys.argv[1] == "preview":
    result = upgrade.plan_recovery(sys.argv[2], action=sys.argv[3])
elif sys.argv[1] == "apply":
    approval = json.loads(Path(sys.argv[2]).read_text())
    plan = {k:v for k,v in approval.items() if k not in ("confirmed_at", "reference")}
    result = upgrade.recover_upgrade(plan, approval)
else:
    raise ValueError("Use preview JOURNAL continue|rollback, or apply APPROVAL.json")
print(json.dumps(result, ensure_ascii=False))
'''


class UpgradeError(ValueError):
    def __init__(self, message, code='upgrade_conflict'):
        super().__init__(message); self.code = code


def _fail(message, code='upgrade_conflict'):
    raise UpgradeError(message, code)


def marker(runtime):
    return runtime.home / '.mem-sharing-upgrade.json'


def _seal(plan):
    plan['plan_sha256'] = legacy.digest(legacy.encoded(plan)); return plan


def _product(source, op, previous=None):
    result = copy.deepcopy(previous) if previous else {
        'product_id':PRODUCT, 'installation_id':op, 'product_structure_version':1}
    result.update(product_code_version=source['version'], source={k:source[k] for k in ('url','commit','tree_sha256')},
                  installation_status='complete', last_operation_id=op)
    return result


def _entry_facts(data):
    """Exact observed machine objects; release conversions cannot broaden ownership."""
    user_entries._preflight_machine_units(data)
    return {obj['path']:install._node(obj['path']) for obj in data['machine']['objects'].values()}


UNIFIED_ENTRY_CONVERSION = {'type': 'unified-user-entry-layout-v1'}
UNIFIED_ENTRY_PREDECESSOR = {
    'url': 'https://github.com/vincent4j/mem-sharing',
    'commit': 'eb31607bcd5fb1c2e5a6332e9e67682cd0cf956b',
    'tree_sha256': '3e792c336cd1b73c250e2f51aa2a919126920f96ec98e498b0b9864ed57e0303'}
UNIFIED_ENTRY_BEFORE = {
    'scripts/agents.json': 'aa9a28a27f3c9bea6ca603dfa2cc24560a9feda3e5085a65d26960790fea9b24',
    'scripts/agm_core/user_entries.py': '81646d141068d76ccc8cb236c1dfd59e9379bbefd6b132fc6c461ff753ff8033'}


# Reviewed target semantics. upgrade.py is deliberately excluded to avoid a hash cycle.
UNIFIED_ENTRY_AFTER = {'scripts/agents.json': 'aa9a28a27f3c9bea6ca603dfa2cc24560a9feda3e5085a65d26960790fea9b24',
 'scripts/agm_core/user_entries.py': '8e22f8876c8437a806ecd1cdc0fa8308c05c317a348e01166a3a0a37b95c62d4',
 'scripts/agm_core/user_entry_layout.py': '2c77e72163edb7fdecb33acc371bff91efc2b5ee958b4bde5509bbb98b4b2abc',
 'scripts/agm_core/entry_layout.py': '347c4c83cbda932c0a8eeb153708673948316b4e6bd344643acc524bad09f50f'}


def _unified_after_contract(source):
    root = Path(__file__).resolve().parents[2]
    for name, expected in UNIFIED_ENTRY_AFTER.items():
        if source['files'].get(name) != expected:
            _fail('Unified layout manifest differs from frozen after contract')
        for base in (Path(source['root']), root):
            candidate = base / name
            if (candidate.is_symlink() or not candidate.is_file()
                    or legacy.digest(candidate.read_bytes()) != expected):
                _fail('Unified layout source/running bytes differ from frozen after contract')
    return True


def _unified_entry_conversion(before, after, direction, entry, request):
    if not (entry == UNIFIED_ENTRY_CONVERSION and direction == 'upgrade'
            and before['product_code_version'] == '0.1.6'
            and before['source'] == UNIFIED_ENTRY_PREDECESSOR):
        return False
    return _unified_after_contract(request['source'])


def _conversion(request, data, target, direction):
    before = {'schema_version':data['schema_version'],
              'product_structure_version':data['product']['product_structure_version'],
              'product_code_version':data['product']['product_code_version'],
              'source':data['product']['source']}
    after = dict(target['release']['versions'], source=target['release']['source'])
    old_version=before['product_code_version'];new_version=after['product_code_version']
    if not re.fullmatch(r'\d+\.\d+\.\d+',old_version):_fail('Unknown predecessor version','upgrade_unsupported')
    old_tuple=tuple(map(int,old_version.split('.')));new_tuple=tuple(map(int,new_version.split('.')))
    if (direction=='upgrade' and old_tuple>=new_tuple) or (direction=='rollback' and old_tuple<=new_tuple):
        _fail('Future/same-version replacement is not an upgrade; rollback must be an older installed release','upgrade_unsupported')
    matches = []
    for item in request.get('conversions', []):
        registry._keys(item, 'before after direction entries', 'release conversion')
        if any(item.get(k) != v for k, v in dict(before=before, after=after, direction=direction).items()):
            continue
        if _unified_entry_conversion(before, after, direction, item['entries'], request):
            matches.append(item)
        elif item['entries'] == 'preserve':
            matches.append(item)
        elif (_workbuddy_conversion(before, after, direction, item['entries'])
              and request.get('agents') == ['workbuddy']):
            matches.append(item)
        elif _public_layout_conversion(before, after, direction, item['entries'], request):
            matches.append(item)
        elif _native_entry_conversion(before, after, direction, item['entries']):
            matches.append(item)
    if len(matches) != 1:
        _fail('Future/unknown release or no exact supported conversion', 'upgrade_unsupported')
    return matches[0]


def _raw_meta(raw, mode=0o600):
    return {'kind':'file', 'sha256':legacy.digest(raw), 'mode':mode}


def _source(request, runtime):
    target = request.get('rollback_target')
    if target is None:
        return install._source(request)
    if request.get('direction') != 'rollback': _fail('Inventory targets are only for explicit rollback')
    registry._keys(target, 'version tree_sha256', 'rollback target')
    if not isinstance(target['version'], str) or not re.fullmatch(r'(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)', target['version']):
        _fail('Invalid rollback version')
    registry._digest(target['tree_sha256'])
    slot=versions.root(runtime)/target['version']/target['tree_sha256']
    versions._chain(slot,runtime.home)
    release=migrate._json(slot/'release.json')
    item={'slot':str(slot),'release':release,'marker_hex':legacy.encoded({
        'product_id':PRODUCT,'source':release['source'],'files':release['files']}).hex()}
    versions.verify(runtime,item)
    if release['versions']['product_code_version']!=target['version'] or release['source']['tree_sha256']!=target['tree_sha256']:
        _fail('Rollback inventory identity mismatch')
    source=dict(release['source'],root=str(slot/'code'),version=target['version'],
        files={f['path']:f['sha256'] for f in release['files']})
    for f in release['files']:
        if f['path'].endswith('.py'):ast.parse((slot/'code'/f['path']).read_bytes(),filename=f['path'],feature_version=(3,9))
    return source,release['files']


def _plan(request, *, allow_marker=False):
    if sys.platform != 'darwin': _fail('Only macOS is supported', 'platform_unsupported')
    runtime = install._runtime(request)
    if os.path.lexists(marker(runtime)) and not allow_marker:
        _fail('Unfinished machine upgrade requires explicit recovery', 'recovery_required')
    for opdir in sorted(runtime.home.glob('.mem-sharing-install-*')):
        if opdir.is_symlink() or not opdir.is_dir(): _fail('Unsafe existing operation')
        saved=migrate._json(opdir/'journal.json')
        if saved.get('product_id')!=PRODUCT or saved.get('status') not in ('committed','rolled_back'):
            _fail('Pending operation requires explicit recovery','recovery_required')
    source, files = _source(request, runtime)
    if Path(source['root']).is_relative_to(runtime.code) or Path(source['root']).is_relative_to(runtime.root):
        _fail('Source overlaps managed runtime')
    target = versions.descriptor(runtime, source, files)
    allowed = paths.allowed_user_paths(request['platform_config'], None, home=str(runtime.home))
    op = migrate._op(request.get('operation_id') or datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-'+uuid.uuid4().hex)
    bootstrap = runtime.home/('.mem-sharing-install-'+op)
    direction = request.get('direction', 'upgrade')
    if direction not in ('upgrade','rollback'): _fail('Unknown direction')
    current = read_snapshot(runtime.registry)
    migration_plan = None; old_inventory = None; old_product = None; noop = False
    if current.kind == 'absent':
        _fail('No formal installed ledger; old development ledgers are diagnostic-only', 'upgrade_unsupported')
    else:
        meta = migrate._json(runtime.code/'.agm-code-manifest.json')
        contract_files = {x['path']:x['sha256'] for x in meta['files']}
        contract_before = {name: contract_files.get(name) for name in _ENTRY_CONTRACT_NAMES}
        contract_after = {name: source['files'].get(name) for name in _ENTRY_CONTRACT_NAMES}
        data = registry.require_installed(registry.load_registry(runtime.registry, allowed_user_paths=allowed))
        install._code_matches(runtime, data['product'])
        old_product = copy.deepcopy(data['product'])
        old_source = dict(old_product['source'], version=old_product['product_code_version'])
        old_inventory = versions.descriptor(runtime, old_source, meta['files'])
        noop = old_inventory == target
        if direction == 'rollback' and noop: _fail('Already at requested rollback version')
        if direction == 'rollback' and not versions.installed_before(runtime, target):
            _fail('Rollback target has no verified successful installation receipt')
        conversion = None if noop else _conversion(request, data, target, direction)
        # public-layout 目标合同含专用迁移模块;_ENTRY_CONTRACT_NAMES 保持两键历史
        # 语义,门禁比较时按目标合同全集对齐。
        contract_after_full = dict(contract_after,
                                   **{'scripts/agm_core/public_layout.py':
                                      source['files'].get('scripts/agm_core/public_layout.py')})
        if contract_before != contract_after:
            entry_conversion = (conversion or {}).get('entries')
            if (entry_conversion == PUBLIC_MEMORY_LAYOUT_CONVERSION
                    and contract_before == PUBLIC_LAYOUT_BEFORE_CONTRACT
                    and contract_after_full == _public_layout_target_contract()
                    and legacy.digest(Path(user_entries.__file__).read_bytes())
                    == contract_after_full['scripts/agm_core/user_entries.py']
                    and legacy.digest(Path(public_layout.__file__).read_bytes())
                    == contract_after_full['scripts/agm_core/public_layout.py']):
                pass  # 固定 handler 审查实际模块可信;入口/公共迁移由专用模块执行。
            elif (entry_conversion == WORKBUDDY_ENTRY_CONVERSION
                    and contract_before == WORKBUDDY_ENTRY_CONVERSION['before_contract']
                    and contract_after == WORKBUDDY_ENTRY_CONVERSION['after_contract']
                    and legacy.digest(Path(user_entries.__file__).read_bytes()) == contract_after['scripts/agm_core/user_entries.py']):
                pass
            elif (entry_conversion == NATIVE_ENTRY_CONVERSION
                    and contract_before == NATIVE_ENTRY_CONVERSION['before_contract']
                    and contract_after == NATIVE_ENTRY_CONVERSION['after_contract']
                    and legacy.digest(Path(user_entries.__file__).read_bytes())
                    == contract_after['scripts/agm_core/user_entries.py']):
                pass  # 专用0.1.4→0.1.5入口合同转换:固定 handler 审查实际模块可信;
                      # 模板字节刷新由代码升级后的入口装配与 migrate-policy 另行
                      # 精确批准执行,不在升级核心内隐式改写用户入口。
            elif (entry_conversion == UNIFIED_ENTRY_CONVERSION
                    and contract_before == UNIFIED_ENTRY_BEFORE
                    and contract_after == {name: UNIFIED_ENTRY_AFTER[name] for name in _ENTRY_CONTRACT_NAMES}
                    and _unified_after_contract(request['source'])):
                pass  # Exact 0.1.6 predecessor, target identity in approved conversion.
            else:
                _fail('Conversion has no handler for changed entry contract')
        elif conversion and conversion['entries'] != 'preserve':
            _fail('WorkBuddy conversion requires its exact changed contract')
        if not noop:
            data['product'] = _product(source, op, old_product)
    if not noop and os.path.lexists(bootstrap): _fail('Operation exists; use recovery')
    facts = _entry_facts(data)
    outputs = []
    old_files = {} if old_inventory is None else {x['path']:x for x in old_inventory['release']['files']}
    new_files = {x['path']:x for x in files}
    for rel in sorted(set(old_files)|set(new_files)|{'.agm-code-manifest.json'}):
        path = runtime.code/rel; before = install._node(path)
        if rel == '.agm-code-manifest.json':
            after = _raw_meta(bytes.fromhex(target['marker_hex']))
        elif rel in new_files: after = {'kind':'file','sha256':new_files[rel]['sha256'],'mode':new_files[rel]['mode']}
        else: after = {'kind':'absent'}
        outputs.append({'path':str(path), 'before':before, 'after':after})
    after_raw = current.data if noop else registry.serialize_registry(data, allowed_user_paths=allowed)
    # 0.1.3 public-memory-layout:迁移子计划嵌入 sealed 升级计划,外层一次批准绑定
    # 两子计划;预览阶段即触发未登记读者门禁,零写拒绝可预见的失败升级。
    if not noop and isinstance((conversion or {}).get('entries'), dict) \
            and conversion['entries'].get('type') == public_layout.HANDLER_TYPE:
        with public_layout._upgrade_preview(after_raw.hex()):
            migration_plan = public_layout.plan_migration(
                dict(request, operation_id=op), code_plan={'after_registry_hex': after_raw.hex()})
    elif (noop and source['version'] == PUBLIC_LAYOUT_TARGET_VERSION
          and (runtime.code / 'scripts/agm_core/public_layout.py').is_file()):
        # 同版代码 noop 但旧布局仍须生成迁移;布局/入口全新才是真零写 noop。
        candidate = public_layout.plan_migration(dict(request, operation_id=op))
        if not candidate['noop']:
            migration_plan = candidate
    archive = runtime.backups/('upgrade-'+op)
    dirs = {str(runtime.backups)}
    for output in outputs:
        p = Path(output['path']).parent
        while p != runtime.home:
            dirs.add(str(p)); p = p.parent
    for path in (runtime.home/'.mem-sharing-install.lock', runtime.lock, runtime.transaction_lock):
        if os.path.lexists(path): _fail('Existing writer lock', 'lock_conflict')
    # A still-regular legacy ledger cannot coexist with V; tombstones stay intact.
    if current.kind != 'absent':
        for path in request.get('legacy_registries', []):
            if install._node(path)['kind'] != 'directory' or str(Path(path).resolve()) not in (data.get('migration') or {}).get('tombstones',{}):
                _fail('Dual/unexplained legacy ledger')
    target_dirs={str(runtime.code)}
    for item in files:
        parent=(runtime.code/item['path']).parent
        while parent!=runtime.code.parent:
            target_dirs.add(str(parent));parent=parent.parent
    obsolete=sorted((d for d in dirs if Path(d).is_relative_to(runtime.code) and d not in target_dirs),
                    key=lambda p:(len(Path(p).parts),p),reverse=True)
    plan = {'schema_version':1, 'command':'upgrade-machine', 'operation_id':op,
        'direction':direction, 'channel':'upgrade', 'layout':runtime.describe(), 'source':source,'source_files':files,
        'tools':[{'path':p.name,'sha256':legacy.digest(p.read_bytes()),'mode':0o600} for p in sorted(Path(__file__).parent.glob('*.py'))],
        'before_registry':install._node(runtime.registry), 'before_registry_hex':(current.data or b'').hex(),
        'before_product':old_product, 'after_registry_hex':after_raw.hex(), 'final_registry_sha256':legacy.digest(after_raw),
        'before_inventory':old_inventory, 'target_inventory':target, 'conversion':conversion, 'migration_plan':migration_plan,
        'outputs':outputs, 'obsolete_directories':obsolete, 'directories':sorted(dirs,key=lambda p:(len(Path(p).parts),p)),
        'bootstrap':str(bootstrap), 'journal':str(bootstrap/'journal.json'), 'archive':str(archive), 'launcher_hex':LAUNCHER.hex(),
        'metadata_scopes':[str(bootstrap),str(archive),str(versions.root(runtime))],
        'allowed_user_paths':allowed, 'entry_facts':facts, 'noop':noop, 'changes':[]}
    if not noop:
        plan['changes'] = ([dict(x,operation='remove' if x['after']['kind']=='absent' else 'create' if x['before']['kind']=='absent' else 'update')
                            for x in outputs if x['before']!=x['after']]
             + [{'path':p,'operation':'remove_owned_empty_code_directory'} for p in obsolete]
             + [{'path':target['slot'],'operation':'register_persistent_version'},
                {'path':str(runtime.registry),'operation':'commit_registry_last'},
                {'path':str(marker(runtime)),'operation':'upgrade_guard'},
                {'path':str(archive),'operation':'before_archive'},
                {'path':str(bootstrap),'operation':'fixed_toolkit_and_journal'}]
             )
    if migration_plan is not None:
        plan['metadata_scopes'].append(migration_plan['backup_scope'])
        plan['changes'] += [dict(t, operation='migrate_public_layout') for t in migration_plan['targets']]
        plan['changes'].append({'path': migration_plan['backup_scope'], 'operation': 'fixed_migration_recovery_material'})
    return _seal(plan)


def plan_upgrade(request):
    """Pure planning. Exact release inputs and all writes appear in the approval."""
    return _plan(request)


def _validate(plan):
    registry._keys(plan, PLAN_KEYS, 'upgrade plan')
    body = dict(plan); digest = body.pop('plan_sha256')
    if legacy.digest(legacy.encoded(body)) != digest or plan['command'] != 'upgrade-machine' or plan['schema_version'] != 1:
        _fail('Invalid upgrade plan')
    runtime = RuntimeLayout(Path(plan['layout']['root']).parent); runtime.validate_paths()
    install._real_chain(runtime.code, runtime.home)
    op = migrate._op(plan['operation_id']); bootstrap = runtime.home/('.mem-sharing-install-'+op)
    if (plan['layout']!=runtime.describe() or plan['bootstrap']!=str(bootstrap)
            or plan['journal']!=str(bootstrap/'journal.json') or plan['archive']!=str(runtime.backups/('upgrade-'+op))):
        _fail('Upgrade path scope mismatch')
    expected_metadata = [str(bootstrap), plan['archive'], str(versions.root(runtime))]
    if plan['migration_plan'] is not None:
        expected_metadata.append(plan['migration_plan']['backup_scope'])
    if plan['metadata_scopes'] != expected_metadata:
        _fail('Upgrade metadata scope mismatch')
    if plan['direction'] not in ('upgrade','rollback') or type(plan['noop']) is not bool: _fail('Invalid upgrade type')
    if plan['launcher_hex']!=LAUNCHER.hex():_fail('Recovery launcher drift')
    versions.validate(runtime,plan['target_inventory'])
    if plan['before_inventory'] is not None: versions.validate(runtime,plan['before_inventory'])
    if legacy.digest(bytes.fromhex(plan['after_registry_hex'])) != plan['final_registry_sha256']:
        _fail('After registry digest mismatch')
    if plan['before_registry']['kind']=='file' and legacy.digest(bytes.fromhex(plan['before_registry_hex'])) != plan['before_registry']['sha256']:
        _fail('Before registry digest mismatch')
    expected_files={x['path'] for x in plan['source_files']} | {'.agm-code-manifest.json'}
    if plan['before_inventory']: expected_files |= {x['path'] for x in plan['before_inventory']['release']['files']}
    if {str(Path(x['path']).relative_to(runtime.code)) for x in plan['outputs']}!=expected_files:
        _fail('Output scope mismatch')
    for item in plan['outputs']:
        registry._keys(item,'path before after','upgrade output')
        p=Path(item['path']); install._real_chain(p.parent,runtime.home)
        if not p.is_relative_to(runtime.code) or '..' in p.parts: _fail('Output escapes code')
    for directory in plan['obsolete_directories']:
        p=Path(directory)
        if p==runtime.code or not p.is_relative_to(runtime.code) or directory not in plan['directories']:
            _fail('Obsolete directory escapes code ownership')
    for directory in plan['directories']:
        p=Path(directory)
        if not (p.is_relative_to(runtime.code) or p in (runtime.code.parent,runtime.code.parent.parent,runtime.root,runtime.var,runtime.backups)):
            _fail('Unapproved code parent directory')
        install._real_chain(p,runtime.home)
    for item in plan['tools']:
        registry._keys(item,'path sha256 mode','upgrade tool')
        if Path(item['path']).name!=item['path'] or not item['path'].endswith('.py'): _fail('Tool escapes toolkit')
        registry._digest(item['sha256'])
    if plan['migration_plan'] is not None:
        migration = plan['migration_plan']
        migration_body = dict(migration)
        migration_digest = migration_body.pop('plan_sha256', None)
        if (not isinstance(migration, dict) or migration_digest is None
                or legacy.digest(legacy.encoded(migration_body)) != migration_digest
                or migration.get('command') != 'migrate-public-layout'
                or migration.get('guard') != str(runtime.home / '.mem-sharing-upgrade.json')
                or not ((plan.get('conversion') or {}).get('entries') == PUBLIC_MEMORY_LAYOUT_CONVERSION
                        or plan['noop'])):
            _fail('Pre-release migration is unsupported', 'upgrade_unsupported')
    return runtime


def _save(journal):
    migrate._put(Path(journal['plan']['journal']),legacy.encoded(journal),0o600)


def _intent(journal,kind,path,hook):
    journal['intent']={'kind':kind,'path':str(path)}; _save(journal)
    if hook: hook('intent:'+kind,Path(path))


def _mkdir(journal,path,hook):
    install._mkdir(journal,path,hook)


def _phase(journal,name,when,hook):
    journal['phase']=name; _save(journal)
    if hook: hook(when+'_phase:'+name,Path(journal['plan']['bootstrap']))


def _node_snapshot(meta, data=None):
    if meta['kind']=='absent': return Snapshot('absent')
    if meta['kind']=='file': return Snapshot('file',data,meta['mode'])
    _fail('Unsupported upgrade node')


def _backup_path(plan,item):
    runtime=_validate(plan)
    return Path(plan['archive'])/'code-before'/Path(item['path']).relative_to(runtime.code)


def _put_bound(journal,path,raw,mode,hook,kind):
    path=Path(path);_mkdir(journal,path.parent,hook)
    snap=read_snapshot(path)
    if snap.kind=='file' and snap.data==raw and snap.mode==mode:return
    if snap.kind!='absent':_fail('Archive/staging drift: '+str(path))
    _intent(journal,kind,path,hook)
    _apply(path,Snapshot('file',raw,mode),expected=Snapshot('absent'))
    if read_snapshot(path)!=Snapshot('file',raw,mode):_fail('Archive readback mismatch')


def _entry_unchanged(plan):
    if any(install._node(path)!=before for path,before in plan['entry_facts'].items()):
        _fail('Machine entry drift since preview', 'source_drift')


def _guard(journal,hook):
    runtime=_validate(journal['plan']);path=marker(runtime)
    raw=legacy.encoded({'product_id':PRODUCT,'operation_id':journal['operation_id'],
        'plan_sha256':journal['plan']['plan_sha256'],'journal':journal['plan']['journal']})
    _put_bound(journal,path,raw,0o600,hook,'upgrade_marker')


def _prepare(journal,hook):
    plan=journal['plan'];runtime=_validate(plan)
    _phase(journal,'prepare','before',hook)
    install._toolkit(journal,hook)
    _put_bound(journal,Path(plan['bootstrap'])/'recover.py',bytes.fromhex(plan['launcher_hex']),0o600,hook,'recovery_launcher')
    # Freeze full code payload before the first active file replacement.
    for item in plan['source_files']:
        source=Path(plan['source']['root'])/item['path']
        staged=Path(plan['bootstrap'])/'code-source'/item['path']
        if staged.exists():
            if install._node(staged)!= {'kind':'file','sha256':item['sha256'],'mode':0o600}:
                _fail('Staged target drift')
            continue
        raw=source.read_bytes()
        if legacy.digest(raw)!=item['sha256']:_fail('Source drift during staging')
        if item['path'].endswith('.py'):ast.parse(raw,filename=item['path'],feature_version=(3,9))
        _put_bound(journal,staged,raw,0o600,hook,'stage_code')
    _phase(journal,'prepare','after',hook)
    _phase(journal,'archive','before',hook)
    for item in plan['outputs']:
        if item['before']['kind']!='file':continue
        dest=_backup_path(plan,item)
        if dest.exists():
            if install._node(dest)!=dict(item['before'],mode=0o400):_fail('Before code archive drift')
            continue
        if install._node(item['path'])!=item['before']:_fail('Before code unavailable')
        _put_bound(journal,dest,Path(item['path']).read_bytes(),0o400,hook,'code_before')
    _put_bound(journal,Path(plan['archive'])/'registry-before.json',bytes.fromhex(plan['before_registry_hex']),0o400,hook,'registry_before')
    if plan['before_inventory']:
        versions.ensure(runtime,plan['before_inventory'],Path(plan['archive'])/'code-before',plan['operation_id'],
            mkdir=lambda p:_mkdir(journal,p,hook),intent=lambda k,p:_intent(journal,k,p,hook),hook=hook)
    _phase(journal,'archive','after',hook)
    _phase(journal,'inventory','before',hook)
    versions.ensure(runtime,plan['target_inventory'],Path(plan['bootstrap'])/'code-source',plan['operation_id'],
        mkdir=lambda p:_mkdir(journal,p,hook),intent=lambda k,p:_intent(journal,k,p,hook),hook=hook)
    _guard(journal,hook)
    _phase(journal,'inventory','after',hook)


def _target_bytes(plan,item):
    runtime=_validate(plan)
    rel=str(Path(item['path']).relative_to(runtime.code))
    raw=(Path(plan['target_inventory']['slot'])/'code'/rel).read_bytes()
    if legacy.digest(raw)!=item['after']['sha256']:_fail('Target payload drift')
    return raw


def _write_code(journal,hook):
    plan=journal['plan'];runtime=_validate(plan)
    _phase(journal,'code','before',hook)
    versions.verify(runtime,plan['target_inventory'])
    # Install the dependency-free gate before other executable code can mix.
    ordered=sorted(plan['outputs'],key=lambda x:(0 if Path(x['path']).relative_to(runtime.code).as_posix()=='scripts/agm_core/layout.py' else 1,x['path']))
    for item in ordered:
        path=Path(item['path']);current=install._node(path)
        if current==item['after']:continue
        if current!=item['before']:_fail('Third-state code: '+str(path))
        before=read_snapshot(path)
        _mkdir(journal,path.parent,hook)
        raw=_target_bytes(plan,item) if item['after']['kind']=='file' else None
        _intent(journal,'code_replace',path,hook)
        if hook:hook('before_code_replace',path)
        _apply(path,_node_snapshot(item['after'],raw),expected=before)
        if hook:hook('after_code_replace',path)
        if install._node(path)!=item['after']:_fail('Code readback drift')
    for directory in plan['obsolete_directories']:
        p=Path(directory)
        if not p.exists():continue
        _intent(journal,'obsolete_directory',p,hook)
        if hook:hook('before_directory_remove',p)
        if p.is_symlink() or not p.is_dir():_fail('Obsolete code parent type drift')
        p.rmdir();migrate._sync_directory(p.parent)
        if hook:hook('after_directory_remove',p)
    _phase(journal,'code','after',hook)
    _phase(journal,'verify','before',hook)
    _verify_outputs(plan)
    _phase(journal,'verify','after',hook)


def _verify_before(plan, *, required):
    for item in plan['outputs']:
        if item['before']['kind']!='file':continue
        meta=install._node(_backup_path(plan,item))
        if required or meta['kind']!='absent':
            if meta!=dict(item['before'],mode=0o400):_fail('Before code archive missing/corrupt')
    path=Path(plan['archive'])/'registry-before.json'
    if required or path.exists():
        if read_snapshot(path)!=Snapshot('file',bytes.fromhex(plan['before_registry_hex']),0o400):_fail('Before registry archive missing/corrupt')


def _verify_outputs(plan):
    runtime=_validate(plan)
    _verify_before(plan,required=True)
    _tools_verify({'plan':plan},required=True)
    if any(install._node(x['path'])!=x['after'] for x in plan['outputs']):_fail('Mixed/incomplete code outputs')
    after=json.loads(bytes.fromhex(plan['after_registry_hex']))
    install._code_matches(runtime,after['product']);_entry_unchanged(plan)
    versions.verify(runtime,plan['target_inventory'])


def _tools_verify(journal, *, required):
    launcher=Path(journal['plan']['bootstrap'])/'recover.py'
    if required or launcher.exists():
        if read_snapshot(launcher)!=Snapshot('file',bytes.fromhex(journal['plan']['launcher_hex']),0o600):_fail('Recovery launcher changed')
    for item in journal['plan']['tools']:
        p=Path(journal['plan']['bootstrap'])/'tools/agm_core'/item['path'];meta=install._node(p)
        if meta['kind']=='absent' and not required:continue
        if meta!={'kind':'file','sha256':item['sha256'],'mode':0o600}:_fail('Fixed recovery toolkit missing/changed')


def _finalize(journal,hook):
    plan=journal['plan'];runtime=_validate(plan)
    _verify_outputs(plan)
    if install._node(runtime.registry).get('sha256')!=plan['final_registry_sha256']:_fail('Final V changed')
    for phase,item,hash_value in [('after',plan['target_inventory'],plan['final_registry_sha256']),
                                ('before',plan['before_inventory'],plan['before_registry'].get('sha256'))]:
        if item:
            versions.activate(runtime,item,plan['operation_id'],plan['journal'],hash_value,
                mkdir=lambda p:_mkdir(journal,p,hook),intent=lambda k,p:_intent(journal,k,p,hook),phase=phase)
    path=marker(runtime)
    if os.path.lexists(path):
        expected=read_snapshot(path)
        _guard(journal,hook)
        _intent(journal,'remove_upgrade_marker',path,hook)
        _apply(path,Snapshot('absent'),expected=expected)
    journal['status']='committed';_save(journal)
    if hook:hook('after_phase:commit',runtime.registry)
    result = {'status':'completed','operation_id':plan['operation_id'],'journal':plan['journal'],
              'version':plan['source']['version'],'direction':plan['direction']}
    entry_conversion = (plan.get('conversion') or {}).get('entries')
    if entry_conversion == PUBLIC_MEMORY_LAYOUT_CONVERSION:
        result.update(scope='product_code', entry_phase='migration_pending',
                      entry_next_action='外层 execute_machine 以同一批准运行 public_layout 迁移;代码恢复不装配入口')
    elif (isinstance(entry_conversion, dict)
          and entry_conversion.get('type') == 'workbuddy-public-index-v1'):
        # Result metadata retains the legacy classification. Execution still
        # requires the exact pinned dict and source contract in _conversion/_plan.
        result.update(scope='product_code', entry_phase='not_run_by_upgrade_core',
                      entry_next_action='Preview and approve same-release install.py --agent workbuddy; code recovery does not assemble user entries')
    elif (isinstance(entry_conversion, dict)
          and entry_conversion.get('type') == 'native-entry-refresh-v1'):
        result.update(scope='product_code', entry_phase='not_run_by_upgrade_core',
                      entry_next_action='代码升级完成后,另经入口装配预览批准接入新增执行器,'
                                        '并以 agm.py migrate-policy 精确预览批准刷新公共/入口模板;'
                                        '代码恢复不装配入口')
    return result


def _finish(journal,hook):
    plan=journal['plan'];runtime=_validate(plan)
    v=install._node(runtime.registry)
    if v.get('sha256')==plan['final_registry_sha256']:
        result=_finalize(journal,hook);result['finalized_only']=True;return result
    _prepare(journal,hook);_write_code(journal,hook)
    _phase(journal,'commit','before',hook)
    raw=bytes.fromhex(plan['after_registry_hex'])
    _intent(journal,'registry_commit',runtime.registry,hook)
    if hook:hook('before_registry_commit',runtime.registry)
    _verify_outputs(plan)
    _apply(runtime.registry,Snapshot('file',raw,0o600),expected=_node_snapshot(plan['before_registry'],bytes.fromhex(plan['before_registry_hex'])))
    if hook:hook('after_registry_commit',runtime.registry)
    if read_snapshot(runtime.registry).data!=raw:_fail('V readback mismatch')
    return _finalize(journal,hook)


def _journal(plan,approval):
    return {'schema_version':1,'product_id':PRODUCT,'operation_id':plan['operation_id'],
        'plan':plan,'approval':approval,'status':'prepared','intent':None,'created_directories':[],
        'final_registry_sha256':plan['final_registry_sha256'],'phase':None}


def _lock_paths(runtime,plan):
    return [runtime.home/'.mem-sharing-install.lock',runtime.lock,runtime.transaction_lock]


def _open_locks(stack,runtime,plan):
    for path in _lock_paths(runtime,plan):stack.enter_context(migrate._lock(path,plan))


def execute_upgrade(plan,approval=None,*,request=None,hook=None):
    runtime=_validate(plan)
    if plan['noop']:
        # No journal, locks, version backfill, entries or timestamps on this path.
        _check_same(plan,runtime)
        return {'status':'completed','noop':True,'changes':[],'version':plan['source']['version']}
    migrate._approval(plan,approval)
    req=dict(request or {},home=str(runtime.home),operation_id=plan['operation_id'],direction=plan['direction'])
    if plan_upgrade(req)!=plan:_fail('Scene/source/plan drift before writes','source_drift')
    journal=_journal(plan,approval)
    with ExitStack() as stack:
        _open_locks(stack,runtime,plan)
        if install._node(runtime.registry)!=plan['before_registry']:_fail('V drift under locks')
        install._code_matches(runtime,plan['before_product']);_entry_unchanged(plan)
        locked_source, locked_files = _source(req, runtime)
        if locked_source != plan['source'] or locked_files != plan['source_files']:
            _fail('Source changed under upgrade locks', 'source_drift')
        Path(plan['bootstrap']).mkdir(mode=0o700);_save(journal)
        try:return _finish(journal,hook)
        except BaseException:
            journal['status']='recovery_required';_save(journal);raise


def _check_same(plan,runtime):
    if os.path.lexists(marker(runtime)) or any(os.path.lexists(p) for p in _lock_paths(runtime,plan)):
        _fail('Machine operation is active','recovery_required')
    if install._node(runtime.registry)!=plan['before_registry']:_fail('Same-version ledger changed')
    data=registry.require_installed(registry.load_registry(runtime.registry,allowed_user_paths=plan['allowed_user_paths']))
    install._code_matches(runtime,data['product']);_entry_unchanged(plan)
    install._source_unchanged(plan)


def run_same_version_entries(request):
    plan=plan_upgrade(request)
    if not plan['noop']:_fail('Separate entry assembly requires an identical installed release')
    return user_entries.run_user_entries(request)


def _load_journal(path):
    path=Path(path);install._real_chain(path,path.parent.parent)
    journal=migrate._json(path);registry._keys(journal,JOURNAL_KEYS,'upgrade journal')
    runtime=_validate(journal['plan']);migrate._approval(journal['plan'],journal['approval'])
    if (str(path)!=journal['plan']['journal'] or journal['schema_version']!=1 or journal['product_id']!=PRODUCT
            or journal['operation_id']!=journal['plan']['operation_id'] or journal['final_registry_sha256']!=journal['plan']['final_registry_sha256']
            or journal['status'] not in ('prepared','recovery_required','committed','rolled_back')):
        _fail('Invalid upgrade journal identity/status')
    for raw in journal['created_directories']:
        p=Path(raw)
        if not any(p.is_relative_to(Path(scope)) for scope in journal['plan']['metadata_scopes']+journal['plan']['directories']):
            _fail('Created directory escapes operation')
    return journal,runtime


def _scene(journal):
    plan=journal['plan'];runtime=_validate(plan)
    observed=[];changed=False
    for item in plan['outputs']:
        current=install._node(item['path'])
        if current not in (item['before'],item['after']):_fail('Third-state output; manual recovery required')
        state='after' if current==item['after'] else 'before';observed.append(state)
        changed |= current!=item['before']
        if item['before']['kind']=='file':
            backup=install._node(_backup_path(plan,item))
            if backup['kind']!='absent' or current!=item['before']:
                if backup!=dict(item['before'],mode=0o400):_fail('Missing/corrupt code-before')
    v=install._node(runtime.registry)
    if v.get('sha256')==plan['final_registry_sha256']:target='after'
    elif v==plan['before_registry']:target='before'
    else:_fail('V third state; do not overwrite external changes')
    if target=='after' and 'before' in observed:_fail('V after with mixed code; manual recovery required')
    _entry_unchanged(plan);_tools_verify(journal,required=changed)
    _verify_before(plan,required=changed)
    expected_files={x['path'] for x in plan['outputs']}
    for path in list(expected_files):
        parent=Path(path).parent
        while parent!=runtime.code.parent:expected_files.add(str(parent));parent=parent.parent
    if runtime.code.exists() and set(install._walk(runtime.code))-expected_files:_fail('Foreign code in partial upgrade')
    if changed:
        versions.verify(runtime,plan['target_inventory'])
        if plan['before_inventory']:versions.verify(runtime,plan['before_inventory'])
    archived=Path(plan['archive'])/'registry-before.json'
    if archived.exists() or changed:
        if read_snapshot(archived)!=Snapshot('file',bytes.fromhex(plan['before_registry_hex']),0o400):_fail('Registry-before archive corrupt')
    guard=marker(runtime)
    if os.path.lexists(guard):
        expected={'product_id':PRODUCT,'operation_id':plan['operation_id'],'plan_sha256':plan['plan_sha256'],'journal':plan['journal']}
        if migrate._json(guard)!=expected:_fail('Upgrade guard identity drift')
    return {'target':target,'outputs':observed}


def plan_recovery(journal_path,*,action):
    if action not in ('continue','rollback'):_fail('Unknown recovery action')
    journal,runtime=_load_journal(journal_path);plan=journal['plan'];scene=_scene(journal)
    if action=='rollback' and scene['target']=='after':
        _fail('Committed V is authoritative; finish only, then request a separately approved release rollback')
    if journal['status']=='rolled_back':_fail('Operation already rolled back')
    child=None
    locks=[x for x in (migrate._stale_observation(p,plan) for p in _lock_paths(runtime,plan)) if x]
    result={'schema_version':1,'command':'recover-machine-upgrade','operation_id':plan['operation_id'],
        'journal':str(journal_path),'journal_sha256':install._node(journal_path)['sha256'],
        'installation_plan_sha256':plan['plan_sha256'],'action':action,'scene':scene,'stale_locks':locks,'migration_recovery':child}
    return _seal(result)


def _rollback(journal,hook):
    plan=journal['plan'];runtime=_validate(plan)
    if install._node(runtime.registry)!=plan['before_registry']:_fail('Rollback requires original V')
    for item in reversed(plan['outputs']):
        path=Path(item['path']);current=install._node(path)
        if current==item['before']:continue
        if current!=item['after']:_fail('Rollback would overwrite third-state bytes')
        raw=_backup_path(plan,item).read_bytes() if item['before']['kind']=='file' else None
        if raw is not None and legacy.digest(raw)!=item['before']['sha256']:_fail('Before archive corrupt')
        _mkdir(journal,path.parent,hook)
        _intent(journal,'rollback_code',path,hook)
        _apply(path,_node_snapshot(item['before'],raw),expected=_node_snapshot(item['after'],_target_bytes(plan,item) if item['after']['kind']=='file' else None))
    guard=marker(runtime)
    if os.path.lexists(guard):
        snap=read_snapshot(guard);_guard(journal,hook);_intent(journal,'rollback_guard',guard,hook)
        _apply(guard,Snapshot('absent'),expected=snap)
    journal['status']='rolled_back';_save(journal)
    # Only newly created, still empty code directories; never inventory/backups.
    for directory in reversed(journal['created_directories']):
        p=Path(directory)
        if p.is_relative_to(runtime.code) and p.is_dir():
            try:p.rmdir()
            except OSError:pass
    return {'status':'rolled_back','journal':plan['journal'],'operation_id':plan['operation_id']}


def recover_upgrade(recovery_plan,approval,*,request=None,hook=None):
    migrate._approval(recovery_plan,approval)
    fresh=plan_recovery(recovery_plan['journal'],action=recovery_plan['action'])
    if fresh!=recovery_plan:_fail('Recovery scene changed since approval','source_drift')
    journal,runtime=_load_journal(recovery_plan['journal']);plan=journal['plan']
    for lock in reversed(recovery_plan['stale_locks']):
        p=Path(lock['path'])
        _intent(journal,'remove_stale_lock',p,hook)
        if migrate._stale_observation(p,plan)!=lock:_fail('Stale lock changed')
        (p/'migration-owner.json').unlink();p.rmdir()
    with ExitStack() as stack:
        _open_locks(stack,runtime,plan);_scene(journal)
        try:
            if recovery_plan['action']=='rollback':return _rollback(journal,hook)
            return _finish(journal,hook)
        except BaseException:
            journal['status']='recovery_required';_save(journal);raise
