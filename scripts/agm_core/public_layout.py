"""Public-memory layout migration for existing 0.1.1/0.1.2 installs (0.1.3).

自包含专用迁移模块(2026-10-31 裁定):把公共 MEMORY 分层为
「索引头契约 + topics/使用约定.md 指南」,各 Agent 用户入口瘦身为
公共指针 + 自身专属规则,Claude 补自身 fallback 受管块。

固定边界:
- 只写已登记三用户路径 + R/memories/MEMORY.md + topics/使用约定.md + V,
  不扩 allowed_user_paths、不新增公共 V 对象、不建第二台账、不加 CLI 命令;
- 仅当本 Agent 存在匹配的已登记公共依赖(import 引用/受管块消费者)才迁移;
  无依赖私文只观察保全零更新;已登记但缺失/漂移拒整单;shared 保持原
  oid/scope/ownership/consumers,仅已知旧模板且现场哈希=登记哈希时可更新指纹;
- 未登记读者门禁:预览即扫描三家配置允许用户路径的现存 @import/已知公共
  指针,未登记报 unregistered_public_reader,零写,先显式接入再重预览;
- 写顺序:入口 fallback 全部 → 读回 → 指南 → 公共索引 → V(V 最后,
  经 registry.commit_registry 完整所有权/创建证据校验);
- 观察绑定:三家用户路径(含 absent)、索引、指南、V 的完整
  kind/hash/mode 快照绑进计划;每入口写前后、索引写前、V 写前、finish 前
  核对所有观察(自身已写 target 期待 after,其余 before);
- guard 复用 ~/.mem-sharing-upgrade.json,且只在固定恢复工具包与 prepared
  journal 落盘读回之后 expected-absent 创建,收尾才按本 plan 精确字节删除;
- V2 经 registry._apply 完成即不可逆:异常保全全部现场不再写任何输出;
  恢复材料绑定固定 manifest 路径与完整 hash,材料/场景全部核验通过后
  才允许任何写入(含 journal/guard)。

旧模板常量按已提交 0f690ef(=0.1.2,与 0.1.1 字节一致)精确重建;
tests/unit/test_public_layout.py 用旧内核真实基线交叉核验字节一致。
"""
import copy
import os
from contextlib import contextmanager
from contextvars import ContextVar
import json
from datetime import datetime, timezone
from pathlib import Path

from . import legacy_import as legacy, migrate, paths, registry, user_entries
from .entries import (EntryConflict, block_fingerprint, managed_span, remove_block,
                      render_block, sha256)
from .layout import RuntimeLayout
from .transaction import (Change, Snapshot, Transaction, TransactionError, _apply,
                          read_snapshot, recover_manifest, write_lock)

PRODUCT = 'mem-sharing'
HANDLER_TYPE = 'public-memory-layout-v1'
TARGET_VERSION = '0.1.3'
_UPGRADE_PREVIEW = ContextVar('public_layout_upgrade_preview', default=None)


@contextmanager
def _upgrade_preview(after_registry_hex):
    """Only the verified upgrade planner supplies this in-process capability."""
    token = _UPGRADE_PREVIEW.set(after_registry_hex)
    try:
        yield
    finally:
        _UPGRADE_PREVIEW.reset(token)
INDEX_REL = 'memories/MEMORY.md'
TOPIC_REL = 'memories/topics/使用约定.md'
PLAN_KEYS = ('schema_version command operation_id handler layout product allowed_user_paths '
             'user_paths observations v1_registry_hex v1_registry_sha256 v2_registry_hex '
             'final_registry_sha256 targets public noop guard journal backup_scope manifest_path '
             'tools agents_table_hex launcher_sha256 directories order plan_sha256')
JOURNAL_KEYS = ('schema_version product_id operation_id plan approval status phase intent '
                'manifest manifest_sha256')

_BASE = {'start': user_entries.BASE_MARKER['start'], 'end': user_entries.BASE_MARKER['end']}
_CFALLBACK = {'start': user_entries.CLAUDE_FALLBACK_MARKER['start'],
              'end': user_entries.CLAUDE_FALLBACK_MARKER['end']}

# 固定恢复 launcher:依赖随 plan 冻结的工具包(backup_scope/tools),不依赖活动 C。
LAUNCHER = br'''import hashlib, json, stat, sys
from pathlib import Path
sys.dont_write_bytecode = True
root = Path(__file__).resolve().parent
if sys.argv[1] == "preview":
    journal_path = Path(sys.argv[2])
elif sys.argv[1] == "apply":
    approval = json.loads(Path(sys.argv[2]).read_text())
    journal_path = Path(approval["journal"])
else:
    raise ValueError("Use preview JOURNAL continue|rollback, or apply APPROVAL.json")
if journal_path != root / "journal.json" or journal_path.is_symlink():
    raise ValueError("Recovery journal path mismatch")
journal = json.loads(journal_path.read_text())
plan = journal["plan"]
body = dict(plan)
digest = body.pop("plan_sha256")
encoded = (json.dumps(body, ensure_ascii=False, sort_keys=True, indent=2)+"\n").encode()
if hashlib.sha256(encoded).hexdigest() != digest or plan["backup_scope"] != str(root):
    raise ValueError("Recovery plan identity mismatch")
if hashlib.sha256(Path(__file__).read_bytes()).hexdigest() != plan["launcher_sha256"]:
    raise ValueError("Recovery launcher changed")
tools = root / "tools" / "agm_core"
if tools.is_symlink() or not tools.is_dir():
    raise ValueError("Invalid toolkit")
if {p.name for p in tools.iterdir()} != {item["path"] for item in plan["tools"]}:
    raise ValueError("Toolkit closure changed")
for item in plan["tools"]:
    path = tools / item["path"]
    if (Path(item["path"]).name != item["path"] or path.is_symlink()
            or not path.is_file() or stat.S_IMODE(path.stat().st_mode) != 0o600
            or hashlib.sha256(path.read_bytes()).hexdigest() != item["sha256"]):
        raise ValueError("Toolkit changed before import")
sys.path.insert(0, str(root / "tools"))
from agm_core import public_layout
if sys.argv[1] == "preview":
    result = public_layout.plan_recovery(str(journal_path), action={"continue":"finish"}.get(sys.argv[3],sys.argv[3]))
else:
    recovery = {k:v for k,v in approval.items() if k not in ("confirmed_at","reference")}
    result = public_layout.recover_migration(recovery, approval)
print(json.dumps(result, ensure_ascii=False))
'''

# ---- 0.1.1/0.1.2 旧模板(字节精确;测试用 git 导出旧内核交叉核验) ------------
# 2026-11-01 冻结:经历开关退役后当前 fallback/治理文案改按新职责生成,旧模板
# 一律固化为历史字面量(不 alias 当前常量),历史字节识别与迁移匹配不受当前
# 生成器演进影响;未知定制/漂移仍整单拒绝,不做文本模糊替换。

_OLD_GOVERNANCE = (
    "用户规则治理:公共内容只写公共指定文件(R/memories)，Agent 独有内容保留于各自用户文件，永不并入公共或自动删除。"
    "进入 Git 主 checkout 时，未登记项目默认启用项目规则：创建缺失的 AGENTS.md 骨架并追加项目经历短协议，已有全文保留。"
    "默认启用不创建 CK 记录库、不调用 CK 安装或初始化；首次 /context-keeper 进入 CK 流程，首次保存按其流程确认位置。"
    "项目政策已为 disabled 时，默认流程不得重新启用入口、自动记录经历或初始化；已有 CK 自动规则也不能覆盖此政策。"
    "重新启用须用户显式执行 enable-memory；解除 disabled 须显式 enable-memory --memory 并批准精确计划。"
    "Claude 和 WorkBuddy 项目入口只由各自实际使用时补齐，其他执行器不得预建；非 Git 目录和 linked worktree 不触发。"
)
_OLD_CLAUDE_FALLBACK = (
    "仅 Claude Code 在本项目实际使用且项目已启用、政策非 disabled 时补引用：CLAUDE.md 不存在才创建仅含 @AGENTS.md 的文件；"
    "已有正文必须完整保留，仅追加缺失的 @AGENTS.md 引用行，重复执行不改字节。"
)
_OLD_WORKBUDDY_FALLBACK = "仅 WorkBuddy 在本项目实际使用产生原生 .workbuddy/memory 目录，且项目已启用、政策非 disabled 时，补顶部 AGENTS.md 指针；保留已有正文字节，不预建原生目录。"
_OLD_CODEX_FALLBACK = "仅 Codex 首次实际使用时，按默认启用条款补缺失 AGENTS.md；已 disabled 项目不自动恢复。"
_OLD_MENU_ITEM5 = "整理用户规则：公共与独有分开，逐条计划后一次批准 → 按 SKILL.md 治理流程执行\n"


def _old_menu_text(code):
    cli = "python3 %s/scripts/agm.py" % code
    installer = "python3 %s/scripts/install.py" % code
    head = (
        "/mem-sharing 菜单:\n"
        "给项目启用记忆：为当前项目建立共享规则入口 → %s enable-memory --project <项目绝对路径> --memory\n"
        "添加新的 Agent：接入已安装的执行器 → %s --agent <执行器名>\n"
        "健康检查：只读检查已登记入口 → %s check-memory --project <项目绝对路径>\n"
        "停用记忆：撤入口并保留数据 → %s remove-memory --project <项目绝对路径>；仅禁自动项目经历记录、保留入口用 enable-memory --no-memory\n"
        % (cli, installer, cli, cli))
    return head + _OLD_MENU_ITEM5 + \
        "批量启用记忆：扫描给定目录，汇总预览后一次批准 → %s enable-memory-batch --directory <目录绝对路径>\n" % cli


def _old_contract_text(code):
    return ('读取契约：L0 恒读 → 需要时读该主题 L1 概要段 → 仍不足才读 L2 全文。\n'
            'L0 一主题一行：主题名 + 一句话当前结论 + 链接；索引 ≤200 行 / 25KB。\n'
            'L1 位于主题文件开头，简列当前有效结论与待办；L2 为全文及 references/ 手册。\n'
            '摘要在记忆整理时手写，不自动生成；增加主题文件，不加长索引。\n'
            + _OLD_GOVERNANCE + '\n'
            + _OLD_CLAUDE_FALLBACK + '\n'
            + _old_menu_text(code) + '\n\n')


def _old_read_text(memory_index):
    return "开始任务前读取并遵守 %s;读不到就说明。" % memory_index


def old_codex_block(memory_index, code):
    body = "\n".join([_old_read_text(memory_index), _OLD_GOVERNANCE, _OLD_CODEX_FALLBACK,
                      _old_menu_text(code)])
    return user_entries._wrap_block(user_entries.BASE_MARKER, body)


def old_workbuddy_block(memory_index, code):
    body = "\n".join([_old_read_text(memory_index), user_entries.WORKBUDDY_CONVENTION_TEXT,
                      _OLD_GOVERNANCE, _OLD_WORKBUDDY_FALLBACK, _old_menu_text(code)])
    return user_entries._wrap_block(user_entries.BASE_MARKER, body)


def old_topic(code):
    return ('# 使用约定\n\n## L1 概要\n\n'
            '当前有效结论：公共记忆采用索引与主题文件，摘要由 Agent 手写，不自动生成。\n'
            '用户规则治理条款、兜底接入条款与 /mem-sharing 菜单全文见索引头部。\n'
            '待办：有新事实且获准记录时，更新对应主题结论与索引行。\n\n'
            '## L2 正文\n\n'
            '主题文件全文及 references/ 手册仅在概要不足时读取。\n'
            + _OLD_GOVERNANCE + '\n'
            + _OLD_CLAUDE_FALLBACK + '\n'
            + _old_menu_text(code) + '\n').encode('utf-8')


def new_contract_bytes():
    return (user_entries.public_memory_contract_text() + '\n').encode('utf-8')


def new_topic_bytes(code):
    return user_entries.usage_convention_topic_text(code).encode('utf-8')


def new_codex_block(memory_index):
    return user_entries._wrap_block(user_entries.BASE_MARKER, "\n".join(
        filter(None, [user_entries.public_read_text(memory_index), user_entries.CODEX_FALLBACK_TEXT])))


def new_workbuddy_block(memory_index):
    return user_entries._wrap_block(user_entries.BASE_MARKER, "\n".join(
        [user_entries.public_read_text(memory_index), user_entries.WORKBUDDY_CONVENTION_TEXT,
         user_entries.WORKBUDDY_FALLBACK_TEXT]))


def new_claude_fallback_block():
    return user_entries._wrap_block(user_entries.CLAUDE_FALLBACK_MARKER, user_entries.CLAUDE_FALLBACK_TEXT)


_INDEX_PREFIX = '# 公共记忆\n\n'.encode('utf-8')
# v0 导入旧索引的产品占位行(0.1.1/0.1.2 固定字节):迁移时整行删除,
# 未知用户目录行不动。
_OLD_TOPIC_DIR_LINE = '- 主题目录：新增主题按需维护，当前请先查看既有原文。[目录](topics/)\n'.encode('utf-8')
_USAGE_TOPIC_LINE = '- 使用约定：操作指南与维护规则。[概要与全文](topics/使用约定.md)\n'.encode('utf-8')


def migrate_index_bytes(raw, code):
    """旧索引 → 新索引:替换精确识别的旧产品头部,未知主题尾逐字节保留。

    额外仅做两处已识别产品行处理:删除 v0 占位主题目录行(固定旧字节),
    缺失时补《使用约定》真实可达链接行;其余尾字节顺序全等。
    返回 (new_bytes, old_head_len);头部无法精确识别时 new_bytes 为 None。
    """
    if not raw.startswith(_INDEX_PREFIX):
        return None, 0
    pre_route_head = (user_entries.PRE_UNINSTALL_ROUTE_TEMPLATES['pre_route_contract'] + '\n').encode('utf-8')
    if raw.startswith(_INDEX_PREFIX + pre_route_head):
        tail = raw[len(_INDEX_PREFIX) + len(pre_route_head):]
        return _INDEX_PREFIX + new_contract_bytes() + tail, len(_INDEX_PREFIX) + len(pre_route_head)
    old_head = _old_contract_text(code).encode('utf-8')
    if raw.startswith(_INDEX_PREFIX + old_head):
        tail = raw[len(_INDEX_PREFIX) + len(old_head):]
        tail = tail.replace(_OLD_TOPIC_DIR_LINE, b'', 1)
        if b'](topics/' + '使用约定.md'.encode('utf-8') + b')' not in tail:
            tail = tail + (b'' if tail.endswith(b'\n') or not tail else b'\n') + _USAGE_TOPIC_LINE
        return _INDEX_PREFIX + new_contract_bytes() + tail, \
            len(_INDEX_PREFIX) + len(old_head)
    if raw.startswith(_INDEX_PREFIX + new_contract_bytes()):
        return raw, 0  # 已是新头部,幂等
    return None, 0


class MigrationError(ValueError):
    def __init__(self, code, message, status='failed'):
        super().__init__(message)
        self.code, self.status = code, status


def _fail(code, message, status='failed'):
    raise MigrationError(code, message, status)


def _seal(obj):
    obj['plan_sha256'] = legacy.digest(legacy.encoded(obj))
    return obj


def guard_path(runtime):
    return runtime.home / '.mem-sharing-upgrade.json'


def _journal_dir(runtime, operation_id):
    return runtime.backups / ('migration-' + operation_id)


def _observe(path):
    """完整观察:kind/fingerprint/mode(absent 无后两者)。"""
    snap = read_snapshot(path)
    if snap.kind == 'absent':
        return {'kind': 'absent'}
    return {'kind': snap.kind, 'fingerprint': snap.fingerprint, 'mode': snap.mode}


def _observed(path, bound):
    return _observe(Path(path)) == bound


def _snapshot_meta(snap):
    if snap.kind == 'absent':
        return {'kind': 'absent'}
    return {'kind': snap.kind, 'fingerprint': snap.fingerprint, 'mode': snap.mode}


# ---- 未登记读者门禁 ---------------------------------------------------------

def _pointer_evidence(agent, config, raw, memory_index):
    """只读识别用户入口文件中的已知公共指针;不递归 HOME、不碰项目入口。"""
    mode = config[agent]['rule_mode']
    if mode == 'import_agents':
        line = ('@' + str(memory_index)).encode('utf-8')
        return 'public_import' if any(l.strip() == line for l in raw.splitlines()) else None
    try:
        span = managed_span(raw, **_BASE)
    except EntryConflict as exc:
        _fail('entry_conflict', '公共入口标记损坏，不能排除未知读者: ' + str(exc))
    if span is None:
        return None
    block_lines = set(raw[span[0]:span[1]].splitlines())
    for text in (_old_read_text(memory_index), user_entries.public_read_text(memory_index)):
        if text.encode('utf-8') in block_lines:
            return 'public_pointer'
    return None


def _units_by_slot(ledger):
    units = {}
    for scope, objects in (('machine', ledger['machine']['objects']),
                           ('shared', ledger['shared_objects'])):
        for oid, obj in objects.items():
            key = (obj['path'], obj['marker']['start'] if obj['marker'] else None)
            units.setdefault(key, []).append((scope, oid, obj))
    return units


def scan_unregistered_readers(config, ledger, home, runtime):
    """配置允许的三家用户路径上发现未登记公共指针即收集(调用方整单拒绝)。"""
    readers = []
    memory_index = runtime.root / INDEX_REL
    units = _units_by_slot(ledger)
    for agent in paths.AGENT_ORDER:
        path = Path(paths.expand_path(config[agent]['user_entry'], home=str(home)))
        snap = read_snapshot(path)
        if snap.kind == 'absent':
            continue
        if snap.kind != 'file':
            _fail('entry_conflict', '用户入口不是普通文件，无法安全枚举读者: ' + str(path))
        evidence = _pointer_evidence(agent, config, snap.data, memory_index)
        if evidence is None:
            continue
        slot = None if config[agent]['rule_mode'] == 'import_agents' else _BASE['start']
        occupants = units.get((str(path), slot), [])
        if any(agent in obj['agents'] for _, _, obj in occupants):
            continue
        readers.append({'agent': agent, 'path': str(path), 'evidence': evidence,
                        'fingerprint': snap.fingerprint,
                        'next_action': '先显式接入该执行器(install.py --agent %s)完成登记,再重新预览迁移' % agent})
    return readers


# ---- 规划 -------------------------------------------------------------------

def _entry_target(agent, config, runtime, units, tx_manifest):
    """规划单个 Agent 入口的迁移;返回 (targets, updates)。

    仅当本 Agent 存在匹配的已登记公共依赖(import 引用或受管块消费者)才迁移;
    无依赖的私文只观察保全、零更新,不隐式接入。已登记但入口缺失即拒整单。
    updates 元素为 (store, oid, patch|None):store ∈ machine/shared/None,
    None 表示登记 machine 对象(整体作为 value)。
    """
    entry = config[agent]
    path = Path(paths.expand_path(entry['user_entry'], home=str(runtime.home)))
    mode = entry['rule_mode']
    slot_key = None if mode == 'import_agents' else _BASE['start']
    occupants = [item for item in units.get((str(path), slot_key), [])
                 if agent in item[2]['agents']]
    fallback_slot = [item for item in units.get((str(path), _CFALLBACK['start']), [])
                     if agent in item[2]['agents']] if mode == 'import_agents' else []
    if not occupants and not fallback_slot:
        return [], []  # 私文(或未接入执行器):观察保全,零更新。
    snap = read_snapshot(path)
    if snap.kind == 'absent':
        _fail('drift', '已登记依赖的入口缺失,拒绝整单: ' + str(path))
    if snap.kind != 'file':
        _fail('entry_conflict', '用户级入口不是普通文件: ' + str(path))
    memory_index = runtime.root / INDEX_REL
    if mode == 'import_agents':
        if not occupants or sum(l.strip() == ('@' + str(memory_index)).encode()
                                for l in snap.data.splitlines()) != 1:
            _fail('entry_semantics_missing', '已登记 Claude 公共引用缺失或重复: ' + str(path))
        return _claude_entry(agent, path, snap, units, tx_manifest)
    return _block_entry(agent, mode, path, snap, units, memory_index, runtime)


def _claude_entry(agent, path, snap, units, tx_manifest):
    fallback = new_claude_fallback_block()
    try:
        fallback_span = managed_span(snap.data, **_CFALLBACK)
    except EntryConflict as exc:
        _fail('entry_conflict', 'Claude 兜底标记异常: ' + str(exc))
    if fallback_span is not None and snap.data[fallback_span[0]:fallback_span[1]] != fallback:
        _fail('entry_semantics_missing', 'Claude 兜底块不是已知模板: ' + str(path))
    present = user_entries._claude_fallback_block_intact(snap.data, None)
    base = remove_block(snap.data, **_CFALLBACK, expected_fingerprint=sha256(fallback)) \
        if present else snap.data
    # Existing fallback stays at its original byte offset; private trailing
    # text and Context Keeper blocks must never be moved to append it again.
    final = snap.data if present else base + (b'' if base.endswith(b'\n') or not base else b'\n') + fallback
    occupants = [item for item in units.get((str(path), None), []) if agent in item[2]['agents']]
    for scope, oid, obj in occupants:
        if obj['kind'] != 'import' or obj['marker'] is not None:
            _fail('ownership_conflict',
                  '入口槽位存在非 import 整文件登记(%s %s kind=%s),拒绝整单: %s'
                  % (scope, oid, obj['kind'], path))
        trusted = (obj.get('fingerprint') or {}).get('value')
        if trusted is None:
            _fail('ownership_conflict', '登记无指纹(%s %s),拒绝整单: ' % (scope, oid) + str(path))
        if trusted not in (sha256(base), sha256(final)):
            _fail('drift', '入口整文件字节与登记不一致(手改),拒绝整单: ' + str(path))
    targets, updates = [], []
    if not present:
        targets.append({'kind': 'claude_fallback', 'agent': agent, 'path': str(path),
                        'before': _snapshot_meta(snap),
                        'after': {'kind': 'file', 'fingerprint': sha256(final), 'mode': snap.mode},
                        'outside_fingerprint': sha256(base)})
    # import 指纹(machine 与 shared)按最终整文件字节重绑,不改 ownership;
    # 已重绑(迁移后重预览)则幂等跳过。
    for scope, oid, obj in occupants:
        trusted = (obj.get('fingerprint') or {}).get('value')
        if trusted != sha256(final):
            updates.append((scope, oid, {'fingerprint': {
                'algorithm': 'sha256', 'basis': 'file_bytes', 'value': sha256(final)}}))
    # 兜底块槽位:无登记时——本次真实新增才 created(绑定本事务 manifest,
    # commit_registry 校验创建证据);既存块只 reused 登记实际字节,不追认删除权。
    slot = [item for item in units.get((str(path), _CFALLBACK['start']), [])
            if agent in item[2]['agents']]
    if not slot:
        ownership = 'created' if not present else 'reused'
        updates.append((None, str(path) + '#claude-fallback', {
            'kind': 'block', 'path': str(path), 'scope': 'machine', 'agents': [agent],
            'ownership': ownership, 'marker': user_entries.CLAUDE_FALLBACK_MARKER,
            'fingerprint': {'algorithm': 'sha256', 'basis': 'block_bytes',
                            'value': sha256(fallback)},
            'original_existed': present, 'link_target': None,
            'backup_manifest': tx_manifest if not present else None,
            'consumers': []}))
    else:
        for scope, oid, obj in slot:
            if obj['kind'] != 'block':
                _fail('ownership_conflict', '兜底块槽位存在非块登记(%s %s),拒绝整单' % (scope, oid))
            if not user_entries._claude_fallback_block_intact(snap.data,
                                                              (obj.get('fingerprint') or {}).get('value')):
                _fail('entry_semantics_missing',
                      '兜底块登记哈希/语义不就位(%s %s),拒绝整单: ' % (scope, oid) + str(path))
    return targets, updates


def _block_entry(agent, mode, path, snap, units, memory_index, runtime):
    occupants = [item for item in units.get((str(path), _BASE['start']), [])
                 if agent in item[2]['agents']]
    if not occupants:
        return [], []
    if len(occupants) > 1:
        _fail('ownership_conflict', '入口受管块槽位重叠登记(%s),拒绝整单: %s'
              % (",".join('%s:%s' % (s, o) for s, o, _ in occupants), path))
    scope, oid, obj = occupants[0]
    if obj['kind'] not in ('block', 'user_convention'):
        _fail('ownership_conflict',
              '受管块槽位存在非块登记(%s %s kind=%s),拒绝整单: %s' % (scope, oid, obj['kind'], path))
    trusted = (obj.get('fingerprint') or {}).get('value')
    if trusted is None:
        _fail('ownership_conflict', '登记无指纹(%s %s),拒绝整单: ' % (scope, oid) + str(path))
    try:
        span = managed_span(snap.data, **_BASE)
    except EntryConflict as exc:
        _fail('entry_conflict', '受管块标记异常(%s),拒绝整单: %s' % (exc, path))
    if span is None:
        _fail('drift', '登记受管块缺失,拒绝整单: ' + str(path))
    actual = sha256(snap.data[span[0]:span[1]])
    if actual != trusted:
        _fail('drift', '受管块现场哈希与登记不一致(手改),拒绝整单: ' + str(path))
    if mode == 'native':
        # native 新模板按执行器分派(codex 字节与历史 new_codex_block 一致);
        # 旧模板仅存在于 codex——dsh/zcode 首版即新模板,无历史模板可转换。
        new_block = user_entries.native_public_source_block(agent, memory_index)
        old_block = old_codex_block(memory_index, runtime.code) if agent == 'codex' else None
    else:
        new_block = new_workbuddy_block(memory_index)
        old_block = old_workbuddy_block(memory_index, runtime.code)
    if actual == sha256(new_block):
        return [], []  # 已是新模板,幂等
    if old_block is None or actual != sha256(old_block):
        _fail('entry_semantics_missing', '登记内容既非已知旧模板也非新模板,拒绝整单: ' + str(path))
    outside = snap.data[:span[0]] + snap.data[span[1]:]
    new_data = render_block(snap.data, new_block, **_BASE, expected_fingerprint=trusted)
    return ([{'kind': 'managed_block', 'agent': agent, 'path': str(path),
              'before': _snapshot_meta(snap),
              'after': {'kind': 'file', 'fingerprint': sha256(new_data), 'mode': snap.mode},
              'outside_fingerprint': sha256(outside)}],
            [(scope, oid, {'fingerprint': {'algorithm': 'sha256', 'basis': 'block_bytes',
                                           'value': sha256(new_block)}})])


def plan_migration(request, code_plan=None):
    """纯规划:固定 handler 合同 + 精确观察/before/after;不写任何文件。

    旧版本(0.1.1/0.1.2)只在外层受限 code-plan 上下文可预览;同版(0.1.3)
    直接预览用于未迁布局的续迁。直连旧版本会被拒绝,不提供可伪造开关。
    """
    config = request['platform_config']
    runtime = RuntimeLayout(Path(request['home']))
    runtime.validate_paths()
    allowed = paths.allowed_user_paths(config, None, home=str(runtime.home))
    if os.path.lexists(guard_path(runtime)):
        _fail('recovery_required', '已有机器操作 guard，须显式恢复')
    registry_snap = read_snapshot(runtime.registry)
    if registry_snap.kind != 'file':
        _fail('machine_not_installed', '缺少正式台账: ' + str(runtime.registry))
    ledger = registry.require_installed(
        registry.load_registry(runtime.registry, allowed_user_paths=allowed))
    readers = scan_unregistered_readers(config, ledger, str(runtime.home), runtime)
    if readers:
        _fail('unregistered_public_reader',
              'unregistered_public_reader 存在未登记公共索引读者,整单拒绝,零写入: '
              + json.dumps(readers, ensure_ascii=False))
    if code_plan is not None and (_UPGRADE_PREVIEW.get() is None
            or code_plan != {'after_registry_hex': _UPGRADE_PREVIEW.get()}):
        _fail('installer_context_required', 'code_plan 仅限已核验升级器内部预览')
    if code_plan is None:
        _installed_contract(runtime, ledger['product'])
    installed_version = ledger['product']['product_code_version']
    if code_plan is None and installed_version != TARGET_VERSION:
        _fail('direct_migration_unsupported',
              '旧版本(%s)仅可经外层升级转换预览迁移;当前版本不匹配目标 %s' % (installed_version, TARGET_VERSION))
    v1_bytes = bytes.fromhex(code_plan['after_registry_hex']) if code_plan is not None \
        else registry_snap.data
    # V2 基于 V1(代码计划预期台账)组装:计划期盘上是 V0,执行期盘上是 V1,
    # 两者机器对象一致但 product 块不同,不能混用。
    base_ledger = json.loads(v1_bytes.decode('utf-8'),
                             object_pairs_hook=registry._no_duplicates) \
        if code_plan is not None else ledger
    # 迁移起点版本/注册表观察一律绑 V1 预期,计划期与执行期(代码已提交)一致。
    installed_version = base_ledger['product']['product_code_version']
    op = migrate._op(request.get('operation_id') or datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '-layout')
    backup_scope = _journal_dir(runtime, op)
    # 确定性事务目录:计划/执行/重放三方一致,新 created 对象的创建证据
    # (backup_manifest)指向该事务 manifest,提交后文件持久存在。
    tx_manifest = str(Path(backup_scope) / 'tx' / 'manifest.json')
    units = _units_by_slot(ledger)
    targets, updates = [], []
    for agent in paths.AGENT_ORDER:
        agent_targets, agent_updates = _entry_target(agent, config, runtime, units, tx_manifest)
        targets.extend(agent_targets)
        updates.extend(agent_updates)
    # 指南主题:absent 新建;旧精确模板替换;等于新目标复用;其他冲突拒绝。
    topic_path = runtime.root / TOPIC_REL
    topic_snap = read_snapshot(topic_path)
    new_topic = new_topic_bytes(runtime.code)
    if topic_snap.kind == 'absent':
        targets.append({'kind': 'guide_topic', 'path': str(topic_path),
                        'before': {'kind': 'absent'},
                        'after': {'kind': 'file', 'fingerprint': sha256(new_topic), 'mode': 0o600},
                        'outside_fingerprint': None})
    elif topic_snap.kind != 'file':
        _fail('entry_conflict', '指南主题不是普通文件: ' + str(topic_path))
    elif topic_snap.data in (old_topic(runtime.code), user_entries.PRE_UNINSTALL_ROUTE_TEMPLATES['pre_route_topic'].replace('__CODE__',str(runtime.code)).encode('utf-8')):
        targets.append({'kind': 'guide_topic', 'path': str(topic_path),
                        'before': _snapshot_meta(topic_snap),
                        'after': {'kind': 'file', 'fingerprint': sha256(new_topic),
                                  'mode': topic_snap.mode},
                        'outside_fingerprint': None})
    elif topic_snap.data != new_topic:
        _fail('entry_semantics_missing',
              '指南主题既非已知旧模板也非新目标,拒绝整单: ' + str(topic_path))
    # 公共索引:仅替换精确识别的旧产品头部;未知主题尾逐字节保留。
    index_path = runtime.root / INDEX_REL
    index_snap = read_snapshot(index_path)
    if index_snap.kind != 'file':
        _fail('entry_conflict', '公共索引缺失或不是普通文件: ' + str(index_path))
    new_index, old_head_len = migrate_index_bytes(index_snap.data, runtime.code)
    if new_index is None:
        _fail('entry_semantics_missing',
              '公共索引头部无法精确识别为旧产品模板,拒绝整单: ' + str(index_path))
    if new_index != index_snap.data:
        targets.append({'kind': 'public_index', 'path': str(index_path),
                        'before': _snapshot_meta(index_snap),
                        'after': {'kind': 'file', 'fingerprint': sha256(new_index),
                                  'mode': index_snap.mode},
                        'outside_fingerprint': sha256(index_snap.data[old_head_len:])})
    # V2:仅更新对象指纹与新增 Claude 兜底对象;shared 保持原 oid/scope/ownership/consumers。
    data = copy.deepcopy(base_ledger)
    for store_name, oid, patch in updates:
        store = data['machine']['objects'] if store_name == 'machine' else \
            data['shared_objects'] if store_name == 'shared' else None
        if store is None:
            data['machine']['objects'][oid] = patch
            continue
        for key, value in patch.items():
            store[oid][key] = value
    v2_bytes = registry.serialize_registry(data, allowed_user_paths=allowed,
                                            _pending_manifest=tx_manifest)
    user_paths = [paths.expand_path(config[a]['user_entry'], home=str(runtime.home))
                  for a in paths.AGENT_ORDER]
    # 观察绑定:三家用户路径(含 absent)+索引+指南的完整 kind/hash/mode;
    # 注册表观察绑 V1 预期(迁移起点),不绑计划期盘上现值。
    plan_v1_sha = legacy.digest(v1_bytes)
    observations = {raw: _observe(Path(raw)) for raw in user_paths}
    observations[str(index_path)] = _snapshot_meta(index_snap)
    observations[str(topic_path)] = _snapshot_meta(topic_snap)
    observations[str(runtime.registry)] = {'kind': 'file', 'fingerprint': plan_v1_sha,
                                           'mode': 0o600}
    tools = [{'path': p.name, 'sha256': sha256(p.read_bytes()), 'mode': p.stat().st_mode & 0o777}
             for p in sorted(Path(__file__).parent.glob('*.py'))]
    directories = set()
    for target in targets:
        parent = Path(target['path']).parent
        while parent != runtime.home and not parent.exists():
            directories.add(str(parent))
            parent = parent.parent
    plan = {'schema_version': 1, 'command': 'migrate-public-layout', 'operation_id': op,
            'handler': {'type': HANDLER_TYPE,
                        'module_sha256': sha256(Path(__file__).read_bytes()),
                        'user_entries_sha256': sha256(Path(user_entries.__file__).read_bytes()),
                        'memory_index': str(runtime.root / INDEX_REL)},
            'layout': runtime.describe(),
            'product': {'installed_version': installed_version,
                        'target_version': TARGET_VERSION, 'identity': base_ledger['product']},
            'allowed_user_paths': allowed,
            'v1_registry_hex': v1_bytes.hex(),
            'v1_registry_sha256': legacy.digest(v1_bytes),
            'v2_registry_hex': v2_bytes.hex(),
            'final_registry_sha256': legacy.digest(v2_bytes),
            'user_paths': user_paths,
            'observations': observations,
            'targets': targets,
            'public': {'index': str(index_path), 'topic': str(topic_path)},
            'noop': not targets and v2_bytes == v1_bytes,
            'guard': str(guard_path(runtime)),
            'journal': str(backup_scope / 'journal.json'),
            'backup_scope': str(backup_scope),
            'manifest_path': tx_manifest,
            'tools': tools, 'directories': sorted(directories),
            'agents_table_hex': (Path(paths.__file__).parent.parent / 'agents.json').read_bytes().hex(),
            'launcher_sha256': sha256(LAUNCHER),
            'order': [t['path'] for t in targets] + [str(runtime.registry)]}
    return _seal(plan)


def _validate(plan):
    registry._keys(plan, PLAN_KEYS, 'public layout migration plan')
    body = dict(plan)
    digest = body.pop('plan_sha256')
    if legacy.digest(legacy.encoded(body)) != digest or plan['schema_version'] != 1 \
            or plan['command'] != 'migrate-public-layout':
        _fail('plan_invalid', 'Invalid public layout migration plan')
    if plan['handler']['type'] != HANDLER_TYPE \
            or plan['handler']['module_sha256'] != sha256(Path(__file__).read_bytes()) \
            or plan['handler']['user_entries_sha256'] != sha256(Path(user_entries.__file__).read_bytes()):
        _fail('plan_invalid', 'Migration handler/module drift')
    runtime = RuntimeLayout(Path(plan['layout']['root']).parent)
    runtime.validate_paths()
    op = migrate._op(plan['operation_id'])
    if plan['layout'] != runtime.describe() or plan['backup_scope'] != str(_journal_dir(runtime, op)):
        _fail('plan_invalid', 'Canonical layout/operation mismatch')
    table_raw = bytes.fromhex(plan['agents_table_hex'])
    from . import upgrade
    if sha256(table_raw) != upgrade.PUBLIC_LAYOUT_TARGET_CONTRACT['scripts/agents.json']:
        _fail('plan_invalid', 'Frozen agents table mismatch')
    table = json.loads(table_raw, object_pairs_hook=registry._no_duplicates)
    paths._validate_table(table)
    config = paths.select_platform(table, paths.current_platform())
    expected_users = [paths.expand_path(config[a]['user_entry'], home=str(runtime.home))
                      for a in paths.AGENT_ORDER]
    if (plan['user_paths'] != expected_users or plan['allowed_user_paths'] != paths.allowed_user_paths(config, None, home=str(runtime.home))
            or plan['public'] != {'index': str(runtime.root / INDEX_REL), 'topic': str(runtime.root / TOPIC_REL)}):
        _fail('plan_invalid', 'Fixed migration path scope mismatch')
    if plan['guard'] != str(guard_path(runtime)) \
            or plan['manifest_path'] != str(Path(plan['backup_scope']) / 'tx' / 'manifest.json') \
            or plan['journal'] != str(Path(plan['backup_scope']) / 'journal.json'):
        _fail('plan_invalid', 'Guard/journal/manifest path mismatch')
    if plan['launcher_sha256'] != sha256(LAUNCHER):
        _fail('plan_invalid', 'Launcher drift')
    if legacy.digest(bytes.fromhex(plan['v1_registry_hex'])) != plan['v1_registry_sha256'] \
            or legacy.digest(bytes.fromhex(plan['v2_registry_hex'])) != plan['final_registry_sha256']:
        _fail('plan_invalid', 'V1/V2 digest mismatch')
    allowed_write = set(plan['user_paths']) | {plan['public']['index'], plan['public']['topic'],
                                               str(runtime.registry)}
    for target in plan['targets']:
        if target['path'] not in allowed_write:
            _fail('plan_invalid', 'Target escapes approved write scope: ' + target['path'])
    expected_observed = set(plan['user_paths']) | {plan['public']['index'],
                                                   plan['public']['topic'],
                                                   str(runtime.registry)}
    if set(plan['observations']) != expected_observed:
        _fail('plan_invalid', 'Observation scope mismatch')
    if (plan['order'] != [t['path'] for t in plan['targets']] + [str(runtime.registry)]
            or len(set(plan['order'])) != len(plan['order'])):
        _fail('plan_invalid', 'Output order/uniqueness mismatch')
    for raw in plan['directories']:
        if Path(raw) == runtime.home or not any(Path(raw) in Path(t['path']).parents for t in plan['targets']):
            _fail('plan_invalid', 'Unapproved parent directory')
    if {i['path'] for i in plan['tools']} != {p.name for p in Path(__file__).parent.glob('*.py')}:
        _fail('plan_invalid', 'Toolkit dependency closure mismatch')
    if len({i['path'] for i in plan['tools']}) != len(plan['tools']):
        _fail('plan_invalid', 'Duplicate toolkit member')
    for item in plan['tools']:
        registry._keys(item, 'path sha256 mode', 'migration tool')
        if Path(item['path']).name != item['path'] or not item['path'].endswith('.py'):
            _fail('plan_invalid', 'Unsafe migration tool path')
        registry._digest(item['sha256'])
    return runtime


# ---- 执行 -------------------------------------------------------------------

def _build_changes(plan):
    """按批准计划重建 Change 列表(写顺序:入口→指南→公共索引;V 由 commit_registry 承载)。"""
    changes = []
    for target in plan['targets']:
        path = Path(target['path'])
        snap = read_snapshot(path)
        if _snapshot_meta(snap) != target['before']:
            _fail('approval_mismatch', '目标现场与计划不一致: ' + str(path), 'approval_required')
        if target['kind'] == 'claude_fallback':
            data = snap.data + (b'' if snap.data.endswith(b'\n') or not snap.data else b'\n') \
                + new_claude_fallback_block()
        elif target['kind'] == 'guide_topic':
            data = new_topic_bytes(Path(plan['layout']['code']))
        elif target['kind'] == 'public_index':
            new_index, _ = migrate_index_bytes(snap.data, Path(plan['layout']['code']))
            if new_index is None:
                _fail('approval_mismatch', '公共索引头部无法识别: ' + str(path), 'approval_required')
            data = new_index
        elif target['kind'] == 'managed_block':
            span = managed_span(snap.data, **_BASE)
            mode = _mode_for(target['agent'])
            memory_index = Path(plan['handler']['memory_index'])
            new_block = user_entries.native_public_source_block(target['agent'], memory_index) \
                if mode == 'native' else new_workbuddy_block(memory_index)
            data = render_block(snap.data, new_block, **_BASE,
                                expected_fingerprint=sha256(snap.data[span[0]:span[1]]))
        else:
            _fail('plan_invalid', 'Unknown target kind: ' + target['kind'])
        if sha256(data) != target['after']['fingerprint']:
            _fail('approval_mismatch', '重算结果与批准指纹不一致: ' + str(path), 'approval_required')
        changes.append(Change.file(path, data, expected=snap, mode=target['after']['mode']))
    return changes


def _mode_for(agent):
    table = paths.load_agents_table()
    config = paths.select_platform(table, paths.current_platform())
    return config[agent]['rule_mode']


def _guard_raw(plan):
    return legacy.encoded({'product_id': PRODUCT, 'kind': 'public-layout-migration',
                           'operation_id': plan['operation_id'], 'plan_sha256': plan['plan_sha256'],
                           'journal': plan['journal'], 'manifest': plan['manifest_path'],
                           'module_sha256': plan['handler']['module_sha256'],
                           'tools_sha256': legacy.digest(legacy.encoded(plan['tools'])),
                           'launcher_sha256': plan['launcher_sha256']})


def _check_observations(plan, written):
    """核对全部观察:已写 target 期待 after(注册表写后期待 V2),其余期待 before。"""
    registry_path = str(Path(plan['layout']['root']) / 'var' / 'registry.json')
    after_by_path = {t['path']: t['after'] for t in plan['targets']}
    after_by_path[registry_path] = {'kind': 'file', 'fingerprint': plan['final_registry_sha256'],
                                    'mode': 0o600}
    for raw, bound in plan['observations'].items():
        expected = after_by_path.get(raw, bound) if raw in written else bound
        if not _observed(raw, expected):
            _fail('observation_drift', '观察与批准不一致(计划后现场变化),拒绝: ' + raw)


def _installed_contract(runtime, product):
    """Validate the installed release and the frozen running migration contract."""
    from . import upgrade, user_install
    if product['product_code_version'] != TARGET_VERSION:
        _fail('direct_migration_unsupported', '旧版本仅可经外层升级转换预览迁移；仅精确目标版本可直接迁移')
    user_install._code_matches(runtime, product)
    for rel, expected in upgrade.PUBLIC_LAYOUT_TARGET_CONTRACT.items():
        running = (Path(__file__).parent.parent / 'agents.json' if rel == 'scripts/agents.json'
                   else Path(__file__).parent / Path(rel).name)
        if (sha256(running.read_bytes()) != expected
                or sha256((runtime.code / rel).read_bytes()) != expected):
            _fail('direct_migration_unsupported', '已装代码/运行合同不符合冻结目标: ' + rel)


def _origin_gates(plan, runtime):
    current = read_snapshot(runtime.registry)
    if current.kind != 'file':
        _fail('direct_migration_unsupported', '缺少正式台账')
    product = json.loads(current.data, object_pairs_hook=registry._no_duplicates)['product']
    if product != plan['product']['identity']:
        _fail('direct_migration_unsupported', '已装发行身份与批准不一致')
    _installed_contract(runtime, product)


def _stage_toolkit(plan, hook=None):
    """冻结固定恢复工具包+launcher 到 backup_scope,读回验证;guard 前完成。"""
    tools_dir = Path(plan['backup_scope']) / 'tools/agm_core'
    if tools_dir.exists():
        _fail('recovery_required', '工具包已存在,不得覆盖,转入恢复: ' + str(tools_dir))
    tools_dir.mkdir(parents=True, mode=0o700)
    for item in plan['tools']:
        dest = tools_dir / item['path']
        _apply(dest, Snapshot('file', (Path(__file__).parent / item['path']).read_bytes(), 0o600),
               expected=Snapshot('absent'))
        if sha256(dest.read_bytes()) != item['sha256'] or dest.stat().st_mode & 0o777 != 0o600:
            _fail('toolkit_drift', '固定工具包读回不一致: ' + str(dest))
    launcher = Path(plan['backup_scope']) / 'recover.py'
    _apply(launcher, Snapshot('file', LAUNCHER, 0o600), expected=Snapshot('absent'))
    if sha256(launcher.read_bytes()) != plan['launcher_sha256']:
        _fail('toolkit_drift', '固定 launcher 读回不一致')


def _verify_toolkit(plan, *, required):
    tools_dir = Path(plan['backup_scope']) / 'tools/agm_core'
    launcher = Path(plan['backup_scope']) / 'recover.py'
    if tools_dir.exists() and {p.name for p in tools_dir.iterdir()} - {i['path'] for i in plan['tools']}:
        _fail('toolkit_drift', 'Unexpected toolkit member')
    if required or launcher.exists():
        if _observe(launcher) != {'kind': 'file', 'fingerprint': plan['launcher_sha256'], 'mode': 0o600}:
            _fail('toolkit_drift', '固定 launcher 缺失/被改,拒绝恢复')
    for item in plan['tools']:
        p = tools_dir / item['path']
        meta = _observe(p)
        if meta == {'kind': 'absent'} and not required:
            continue
        if meta != {'kind': 'file', 'fingerprint': item['sha256'], 'mode': 0o600}:
            _fail('toolkit_drift', '固定工具包缺失/被改,拒绝恢复: ' + item['path'])


def execute_migration(plan, approval, request=None, hook=None):
    """执行已批准迁移:固定工具包 → prepared journal → guard → 事务 → 收尾。"""
    runtime = _validate(plan)
    migrate._approval(plan, approval)
    req = dict(request or {}, home=str(runtime.home), operation_id=plan['operation_id'])
    if plan['noop']:
        fresh = plan_migration(req)
        if not fresh['noop'] or fresh['plan_sha256'] != plan['plan_sha256']:
            _fail('approval_mismatch', '现场已变化,须重新预览', 'approval_required')
        return {'status': 'completed', 'noop': True, 'operation_id': plan['operation_id'],
                'migration_phase': 'noop'}
    with write_lock(runtime.lock):
        fresh = plan_migration(req)
        if fresh['plan_sha256'] != plan['plan_sha256']:
            _fail('approval_mismatch', '预览与执行之间现场已变化,已停止写入;请重新预览确认',
                  'approval_required')
        _origin_gates(plan, runtime)
        _check_observations(plan, written=set())
        if read_snapshot(runtime.registry).fingerprint != plan['v1_registry_sha256']:
            _fail('v1_mismatch', 'V1 台账漂移,停止迁移')
        # R2:已有 guard 或同 op 材料 → 不得覆盖,转恢复。
        if read_snapshot(Path(plan['guard'])).kind != 'absent':
            _fail('recovery_required', 'guard 已存在,转入恢复: ' + plan['guard'])
        journal_path = Path(plan['journal'])
        if journal_path.exists() or Path(plan['backup_scope']).exists():
            _fail('recovery_required', '同操作材料已存在,不得覆盖,转入恢复: ' + plan['journal'])
        # R2:先完成全部准备(build_changes + 固定工具包 + prepared journal 读回),
        # 之后才 expected-absent 创建 guard;guard 后异常统一保存恢复阶段。
        changes = _build_changes(plan)
        journal_path.parent.mkdir(parents=True, mode=0o700, exist_ok=True)
        journal = {'schema_version': 1, 'product_id': PRODUCT, 'operation_id': plan['operation_id'],
                   'plan': plan, 'approval': approval, 'status': 'prepared', 'phase': 'prep',
                   'intent': None, 'manifest': plan['manifest_path'], 'manifest_sha256': None}
        _apply(journal_path, Snapshot('file', legacy.encoded(journal), 0o600),
               expected=Snapshot('absent'))
        _stage_toolkit(plan, hook)
        journal['phase'] = 'prepared'
        migrate._put(journal_path, legacy.encoded(journal), 0o600)
        if read_snapshot(journal_path) != Snapshot('file', legacy.encoded(journal), 0o600):
            _fail('journal_invalid', 'Prepared journal readback mismatch')
        _verify_toolkit(plan, required=True)
        guard = Path(plan['guard'])
        if hook:
            hook('before_guard', guard)
        _apply(guard, Snapshot('file', _guard_raw(plan), 0o600), expected=Snapshot('absent'))
        if read_snapshot(guard) != Snapshot('file', _guard_raw(plan), 0o600):
            _fail('guard_drift', 'guard 读回不一致')
        # The persisted prepared journal can recover a crash immediately after guard creation.
        try:
            journal['phase'] = 'guarded'
            migrate._put(journal_path, legacy.encoded(journal), 0o600)
            if hook:
                hook('after_guard', guard)
            return _execute_after_guard(plan, runtime, journal, journal_path, changes,
                                        base_hook=hook)
        except BaseException as exc:
            journal['status'] = 'recovery_required'
            journal['phase'] = 'post-guard:' + getattr(exc, 'code', type(exc).__name__)
            journal['manifest_sha256'] = _file_digest(Path(plan['manifest_path']))
            migrate._put(journal_path, legacy.encoded(journal), 0o600)
            raise MigrationError('migration_recovery_required',
                                 '迁移中断(post-guard %s);恢复 journal: %s'
                                 % (exc, journal_path), 'recovery_required') from exc


def _execute_after_guard(plan, runtime, journal, journal_path, changes, *, base_hook):
    written = set()

    def observing_hook(event, path):
        if event == 'after_write':
            written.add(str(path))
        if base_hook:
            base_hook(event, path)
        if event in ('before_write', 'after_write', 'before_readback'):
            if read_snapshot(Path(plan['guard'])) != Snapshot('file', _guard_raw(plan), 0o600):
                _fail('guard_invalid', '迁移 guard 第三态')
            _check_observations(plan, written)


    transaction = Transaction(lock_path=runtime.transaction_lock,
                              backup_root=Path(plan['backup_scope']),
                              allowed_roots=[Path(p) for p in plan['user_paths']] +
                              [Path(plan['public']['index']), Path(plan['public']['topic']),
                               runtime.registry],
                              operation='migrate-public-layout', hook=observing_hook)
    # 钉住确定性事务目录:与计划中 created 对象的 backup_manifest 一致。
    transaction.directory = Path(plan['backup_scope']) / 'tx'
    transaction.manifest_path = transaction.directory / 'manifest.json'
    v2_data = json.loads(bytes.fromhex(plan['v2_registry_hex']),
                         object_pairs_hook=registry._no_duplicates)
    v1_data = json.loads(bytes.fromhex(plan['v1_registry_hex']),
                         object_pairs_hook=registry._no_duplicates)
    try:
        result = registry.commit_registry(
            runtime.registry, v2_data, transaction=transaction,
            expected=read_snapshot(runtime.registry), changes=changes,
            allowed_user_paths=plan['allowed_user_paths'], previous=v1_data,
            registry_authoritative=True)
    except TransactionError as exc:
        journal['status'] = 'recovery_required'
        journal['phase'] = 'transaction'
        journal['manifest'] = str(exc.manifest or transaction.manifest_path)
        journal['manifest_sha256'] = _file_digest(Path(journal['manifest']))
        migrate._put(journal_path, legacy.encoded(journal), 0o600)
        try:
            boundary = _scene(journal)['v']
            recovery_hint = 'V2已提交,仅finish' if boundary == 'after' else 'V1,可rollback'
        except (ValueError, OSError):
            recovery_hint = '未知或第三态,禁止猜测恢复动作,须完整预览核验'
        raise MigrationError(
            'migration_recovery_required',
            '迁移中断:%s;恢复边界:V=%s;用 public_layout.plan_recovery(%s) 预览恢复'
            % (exc, recovery_hint, journal_path), 'recovery_required') from exc
    # R6:完整验证后同步双 manifest 终态并读回,再按本 plan 精确字节清 guard。
    registry_path = str(Path(plan['layout']['root']) / 'var' / 'registry.json')
    _check_observations(plan, written=set(t['path'] for t in plan['targets']) | {registry_path})
    if read_snapshot(runtime.registry).fingerprint != plan['final_registry_sha256']:
        _fail('v2_mismatch', 'V2 读回不一致')
    manifest_path = Path(plan['manifest_path'])
    committed = migrate._json(manifest_path)
    if committed.get('status') != 'committed':
        _fail('manifest_final', '事务 manifest 终态不是 committed')
    journal['status'] = 'committed'
    journal['phase'] = 'finish'
    journal['manifest_sha256'] = _file_digest(manifest_path)
    migrate._put(journal_path, legacy.encoded(journal), 0o600)
    _finish_guard(plan)
    return {'status': 'completed', 'operation_id': plan['operation_id'],
            'migration_phase': 'committed', 'manifest': result['manifest'],
            'journal': str(journal_path)}


def _file_digest(path):
    try:
        return sha256(Path(path).read_bytes())
    except OSError:
        return None


def _finish_guard(plan):
    """仅当 guard 是本 plan 的精确字节/mode 时删除;不读任意 guard 就删。"""
    guard = Path(plan['guard'])
    expected = read_snapshot(guard)
    if expected.kind == 'absent':
        saved = migrate._json(Path(plan['journal']))
        if saved['phase'] in ('prep', 'prepared') and saved['status'] == 'rolled_back':
            return
    if expected != Snapshot('file', _guard_raw(plan), 0o600):
        _fail('guard_invalid', 'guard 非本计划精确字节,拒绝删除: ' + plan['guard'])
    _apply(guard, Snapshot('absent'), expected=expected)


# ---- 恢复 -------------------------------------------------------------------

def _load_journal(path):
    path = Path(path)
    if _observe(path).get('kind') != 'file' or _observe(path).get('mode') != 0o600:
        _fail('journal_invalid', 'Journal type/mode mismatch')
    journal = migrate._json(path)
    registry._keys(journal, JOURNAL_KEYS, 'public layout migration journal')
    runtime = _validate(journal['plan'])
    migrate._approval(journal['plan'], journal['approval'])
    if journal['manifest'] != journal['plan']['manifest_path']:
        _fail('journal_invalid', 'Journal manifest path mismatch')
    if str(path) != journal['plan']['journal'] or journal['product_id'] != PRODUCT \
            or journal['operation_id'] != journal['plan']['operation_id']:
        _fail('journal_invalid', '迁移 journal 身份不一致')
    if journal['status'] not in ('prepared', 'guarded', 'committed', 'rolled_back',
                                 'recovery_required'):
        _fail('journal_invalid', '未知迁移 journal 状态')
    return journal, runtime


def _manifest_bounds(plan, manifest):
    registry._keys(manifest, 'schema_version operation status registry_path created_directories entries error',
                   'migration transaction manifest')
    runtime = RuntimeLayout(Path(plan['layout']['root']).parent)
    if (manifest['schema_version'] != 1 or manifest['operation'] != 'migrate-public-layout'
            or manifest['registry_path'] != str(runtime.registry)
            or manifest['status'] not in ('prepared', 'applying', 'recovery_required', 'rolled_back', 'committed')):
        _fail('recovery_invalid', 'Manifest operation/identity/status mismatch')
    # Transaction omits no-op outputs, including an unchanged V.
    by_path = {t['path']: t for t in plan['targets']}
    v_before = plan['observations'][str(runtime.registry)]
    v_after = dict(v_before, fingerprint=plan['final_registry_sha256'])
    by_path[str(runtime.registry)] = {'before': v_before, 'after': v_after}
    expected_order = [raw for raw in plan['order']
                      if by_path[raw]['before'] != by_path[raw]['after']]
    entries = manifest['entries']
    if not isinstance(entries, list) or [e['path'] for e in entries] != expected_order:
        _fail('recovery_invalid', 'Manifest outputs do not equal approved active outputs')
    unattempted = False
    for index, entry in enumerate(entries):
        registry._keys(entry, 'path before after attempted restoration', 'manifest entry')
        if type(entry['attempted']) is not bool or unattempted and entry['attempted']:
            _fail('recovery_invalid', 'Invalid attempted sequence')
        unattempted |= not entry['attempted']
        for side in ('before', 'after'):
            meta = entry[side]
            registry._keys(meta, 'existed kind fingerprint mode link_target backup', 'manifest snapshot')
            bound = by_path[entry['path']][side]
            expected = {'kind': meta['kind']}
            if meta['kind'] != 'absent':
                expected.update(fingerprint=meta['fingerprint'], mode=meta['mode'])
            if (expected != bound or (bound['kind'] == 'absent' and
                    (meta['mode'] is not None or meta['fingerprint'] is not None))
                    or meta['existed'] != (bound['kind'] != 'absent')
                    or meta['link_target'] is not None):
                _fail('recovery_invalid', 'Manifest snapshot differs from approved ' + side)
            wanted_backup = str(index) + '.before' if side == 'before' and bound['kind'] == 'file' else None
            if meta['backup'] != wanted_backup:
                _fail('recovery_invalid', 'Unapproved backup filename')
        if not entry['attempted'] and not _observed(entry['path'], by_path[entry['path']]['before']):
            _fail('third_state', 'Unattempted output changed')
    dirs = manifest['created_directories']
    if (not isinstance(dirs, list) or len(set(dirs)) != len(dirs)
            or not set(dirs) <= set(plan['directories'])):
        _fail('recovery_invalid', 'Unapproved transaction directories')
    return entries


def _backup_evidence(plan, manifest_path):
    manifest_meta = _observe(manifest_path)
    if manifest_meta.get('kind') != 'file' or manifest_meta.get('mode') != 0o600:
        _fail('recovery_invalid', 'Manifest type/mode mismatch')
    manifest = migrate._json(manifest_path)
    entries = _manifest_bounds(plan, manifest)
    evidence = {'manifest': manifest_meta, 'backups': {}}
    prewrite = not any(entry['attempted'] for entry in entries)
    if prewrite:
        # Only a full, plan-bound manifest with no attempted output and a
        # complete observed before scene may omit not-yet-created backups.
        _check_observations(plan, written=set())
    for entry in entries:
        meta = entry['before']
        if meta['backup'] is None:
            continue
        observed = _observe(Path(manifest_path).parent / meta['backup'])
        if prewrite and observed == {'kind': 'absent'}:
            evidence['backups'][meta['backup']] = observed
            continue
        if observed != {'kind': 'file', 'fingerprint': meta['fingerprint'], 'mode': 0o600}:
            _fail('recovery_invalid', 'Backup missing/corrupt/type/mode mismatch: ' + meta['backup'])
        evidence['backups'][meta['backup']] = observed
    return evidence


def _scene(journal):
    plan = journal['plan']
    runtime = _validate(plan)
    guard = read_snapshot(Path(plan['guard']))
    has_guard = guard.kind != 'absent'
    if has_guard and guard != Snapshot('file', _guard_raw(plan), 0o600):
        _fail('guard_invalid', 'Guard is not this operation')
    if not has_guard and journal['phase'] not in ('prep', 'prepared'):
        _fail('guard_invalid', 'Guard missing after activation')
    _verify_toolkit(plan, required=has_guard)
    states = []
    targets = {t['path']: t for t in plan['targets']}
    for target in plan['targets']:
        meta = _observe(Path(target['path']))
        if meta not in (target['before'], target['after']):
            _fail('third_state', 'Output third state: ' + target['path'])
        states.append({'path': target['path'], 'state': 'after' if meta == target['after'] else 'before'})
    v_meta = _observe(runtime.registry)
    v_before = plan['observations'][str(runtime.registry)]
    v_after = dict(v_before, fingerprint=plan['final_registry_sha256'])
    if v_before == v_after and v_meta == v_before:
        # No registry delta: the existing transaction manifest is the durable
        # commit point. Validate all immutable material before trusting status.
        manifest_path = Path(plan['manifest_path'])
        target = 'before'
        if _observe(manifest_path)['kind'] != 'absent':
            _backup_evidence(plan, manifest_path)
            if migrate._json(manifest_path)['status'] == 'committed':
                target = 'after'
    elif v_meta == v_after:
        target = 'after'
    elif v_meta == v_before:
        target = 'before'
    else:
        _fail('third_state', 'Registry differs from V1/V2 (including kind/mode)')
    for raw, before in plan['observations'].items():
        if raw not in targets and raw != str(runtime.registry) and not _observed(raw, before):
            _fail('third_state', 'Untouched observed dependency changed: ' + raw)
    if target == 'after' and any(s['state'] != 'after' for s in states):
        _fail('third_state', 'Committed registry with mixed outputs')
    if not has_guard and (target != 'before' or any(s['state'] != 'before' for s in states)):
        _fail('third_state', 'Pre-guard operation has changed outputs')
    return {'v': target, 'outputs': states, 'guard': _snapshot_meta(guard)}


def plan_recovery(journal_path, *, action):
    """恢复预览:材料(guard/工具包/manifest/备份)与场景全部核验后才可执行。"""
    if action not in ('rollback', 'finish'):
        _fail('recovery_invalid', 'Unknown recovery action')
    journal, runtime = _load_journal(journal_path)
    plan = journal['plan']
    scene = _scene(journal)
    if journal['status'] == 'rolled_back':
        _fail('recovery_invalid', '操作已回滚')
    manifest_path = Path(plan['manifest_path'])
    has_manifest = _observe(manifest_path)['kind'] != 'absent'
    evidence = None
    if scene['v'] == 'after':
        if action != 'finish':
            _fail('recovery_invalid', 'V2 已提交为权威,只允许 finish,禁止迁移回滚')
        if not has_manifest:
            _fail('recovery_invalid', 'V2 无可信事务 manifest,拒绝 finish,人工核验')
        _manifest_bounds(plan, migrate._json(manifest_path))
        evidence = _backup_evidence(plan, manifest_path)
    else:
        if action != 'rollback':
            _fail('recovery_invalid', 'V1 状态只允许 rollback;重做迁移须新预览批准')
        if has_manifest:
            manifest = migrate._json(manifest_path)
            _manifest_bounds(plan, manifest)
            # R6:已回滚 manifest 不能直接跳过——仅 V1+全部 before 才可清场,
            # 混合 before/after 在预览期即拒绝。
            if manifest.get('status') == 'rolled_back' and any(
                    s['state'] != 'before' for s in scene['outputs']):
                _fail('recovery_invalid', 'manifest 已回滚但输出混合,拒绝,人工核验')
            evidence = _backup_evidence(plan, manifest_path)
        elif any(s['state'] != 'before' for s in scene['outputs']):
            # V1+混合 after 但无可信 manifest:拒绝,不猜恢复材料。
            _fail('recovery_invalid', 'V1 且输出混合但无可信 manifest,拒绝,人工核验')
    result = {'schema_version': 1, 'command': 'recover-public-layout',
              'operation_id': plan['operation_id'], 'journal': str(journal_path),
              'journal_sha256': _file_digest(Path(journal_path)),
              'plan_sha256': plan['plan_sha256'], 'action': action, 'scene': scene,
              'manifest': str(manifest_path) if has_manifest else None,
              'evidence': evidence}
    return _seal(result)


def recover_migration(recovery_plan, approval, *, request=None, hook=None):
    """恢复执行:锁内重验材料/场景/批准后才任何写入(含 journal/guard)。"""
    migrate._approval(recovery_plan, approval)
    journal, runtime = _load_journal(recovery_plan['journal'])
    fresh = plan_recovery(recovery_plan['journal'], action=recovery_plan['action'])
    if fresh != recovery_plan:
        _fail('recovery_invalid', '恢复现场已变化,重新预览')
    plan = journal['plan']
    journal_path = Path(plan['journal'])
    with write_lock(runtime.lock):
        if plan_recovery(recovery_plan['journal'], action=recovery_plan['action']) != recovery_plan:
            _fail('recovery_invalid', '恢复材料/现场在加锁期间变化')
        manifest_path = Path(plan['manifest_path'])
        if recovery_plan['action'] == 'finish':
            # R6:完整验证后同步事务 manifest=committed 与 journal 终态并读回,再清 guard。
            committed = migrate._json(manifest_path)
            committed['status'] = 'committed'
            migrate._put(manifest_path, legacy.encoded(committed), 0o600)
            if read_snapshot(manifest_path) != Snapshot('file', legacy.encoded(committed), 0o600):
                _fail('recovery_invalid', 'Manifest finish readback mismatch')
            journal['status'] = 'committed'
            journal['manifest_sha256'] = _file_digest(manifest_path)
            migrate._put(journal_path, legacy.encoded(journal), 0o600)
            _finish_guard(plan)
            return {'status': 'completed', 'operation_id': plan['operation_id'],
                    'finalized_only': True}
        # rollback:材料/场景已全验;V1+全部 before+无 manifest 时只收尾,
        # 否则经 recover_manifest 的备份核验恢复到迁移 before(含 V1 台账)。
        if not manifest_path.exists():
            journal['status'] = 'rolled_back'
            migrate._put(journal_path, legacy.encoded(journal), 0o600)
            _finish_guard(plan)
            return {'status': 'rolled_back', 'operation_id': plan['operation_id'],
                    'finalized_only': True}
        manifest = migrate._json(manifest_path)
        if manifest.get('status') == 'rolled_back' or not any(e['attempted'] for e in manifest['entries']):
            # R6:已回滚 manifest 不能直接跳过——仅 V1+全部 before+观察未变才清场;
            # 混合 before/after 拒绝,不误报成功。
            fresh_scene = _scene(journal)
            if any(s['state'] != 'before' for s in fresh_scene['outputs']):
                _fail('recovery_invalid', 'manifest 已回滚但输出混合,拒绝,人工核验')
            if manifest['status'] != 'rolled_back':
                manifest['status'] = 'rolled_back'
                migrate._put(manifest_path, legacy.encoded(manifest), 0o600)
            journal['status'] = 'rolled_back'
            journal['manifest_sha256'] = _file_digest(manifest_path)
            migrate._put(journal_path, legacy.encoded(journal), 0o600)
            _finish_guard(plan)
            return {'status': 'rolled_back', 'operation_id': plan['operation_id'],
                    'finalized_only': True}
        def recovery_hook(event, path):
            if hook:
                hook(event, path)
            if event == 'before_restore':
                _scene(journal)
                if _backup_evidence(plan, manifest_path) != recovery_plan['evidence']:
                    _fail('recovery_invalid', '恢复中材料变化')
        recover_manifest(str(manifest_path), lock_path=runtime.transaction_lock,
                         allowed_roots=[Path(p) for p in plan['user_paths']] +
                         [Path(plan['public']['index']), Path(plan['public']['topic']),
                          runtime.registry], hook=recovery_hook)
        final_scene = _scene(journal)
        if final_scene['v'] != 'before' or any(t['state'] != 'before' for t in final_scene['outputs']):
            _fail('third_state', '回滚收尾前现场不再是完整 before')
        journal['status'] = 'rolled_back'
        journal['manifest_sha256'] = _file_digest(manifest_path)
        migrate._put(journal_path, legacy.encoded(journal), 0o600)
        _finish_guard(plan)
        return {'status': 'rolled_back', 'operation_id': plan['operation_id']}
