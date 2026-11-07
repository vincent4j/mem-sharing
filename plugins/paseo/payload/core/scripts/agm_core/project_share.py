"""Skill-first project memory sharing over the root AGENTS.md base.

Only the current Git main checkout participates; every write stays inside the
project (transaction materials under ``<project>/.mem-sharing/backups``). The
user HOME is read only for the minimal historical disabled-registration check,
fail closed when that record is unreadable or unclear. Independent files count
one source each; content already present in AGENTS.md is deduplicated from the
other files by default and never lands in the optional block. Excluding an
existing AGENTS item requires an explicit per-item destination inside this
project. Order: AGENTS -> every necessary project entry (Claude ``@AGENTS.md``
import line, WorkBuddy project-rules bridge block) -> verify -> precise source
deletion, all through the existing Transaction.
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path

from . import entries, project as project_module
from .layout import RuntimeLayout
from .memory_share import (ShareError, _encoded, _fail, _identity, _meta,
                           _parse_selection, _protected_spans, _read_source,
                           _scope_titles, _segments, _separator,
                           _check_pending, read_snapshot, write_lock)
from .transaction import (Change, Snapshot, Transaction, TransactionError,
                          inspect_recovery, recover_manifest)

COMMAND = 'share-project-memory'
RETURN_COMMAND = 'return-project-memory'
RECOVER_COMMAND = 'recover-memory-share'
AGENTS_NAME = 'AGENTS.md'
CLAUDE_NAME = 'CLAUDE.md'
WORKBUDDY_REL = '.workbuddy/memory/MEMORY.md'
WORKBUDDY_BLOCK = ('<!-- mem-sharing:project-rules:start -->\n'
                   '项目规则读取当前项目根 AGENTS.md。\n'
                   '<!-- mem-sharing:project-rules:end -->').encode()
WORKBUDDY_MARKER = (b'<!-- mem-sharing:project-rules:start -->',
                    b'<!-- mem-sharing:project-rules:end -->')


def _heading_stack(data, start, protected):
    """片段前的有效标题栈：遇级别 L 的标题先弹出栈内级别>=L 的项再压入
    (L,title)；受保护行与代码围栏内的行不产生标题。不维护历史兄弟标题。"""
    stack = []
    offset = 0
    fence = None  # (围栏字符, 开栏长度)：关闭需同字符且长度>=开栏
    for raw in data[:start].splitlines(keepends=True):
        left = offset
        offset += len(raw)
        line = raw.rstrip(b'\r\n')  # 不去前导缩进：缩进行不是标题/围栏
        if fence is not None:
            close = re.fullmatch(rb"(`{3,}|~{3,})\s*", line)  # 关闭仅纯围栏，允许尾空白
            if close and close.group(1)[:1] == fence[0] \
                    and len(close.group(1)) >= fence[1]:
                fence = None
            continue
        if any(left < end and left + len(raw) > begin for begin, end in protected):
            continue
        opened = re.match(rb"^(`{3,}|~{3,})", line)  # 开栏可带语言/信息串
        if opened:
            fence = (opened.group(1)[:1], len(opened.group(1)))
            continue
        match = re.match(rb"^(#{1,6})\s+(.+?)\s*#*\s*$", line)
        if match:
            level = len(match.group(1))
            while stack and stack[-1][0] >= level:
                stack.pop()
            stack.append((level, match.group(2).decode()))
    return stack


def _norm_stack(stack):
    return tuple((int(level), str(title)) for level, title in stack)


def _project_runtime(request):
    identity = project_module.resolve_project(Path(request['project']))
    if str(identity.main_checkout) != str(Path(request['project']).resolve()):
        _fail('invalid_request', '项目路径必须是 Git 主 checkout 根：'
              + str(identity.main_checkout))
    runtime = RuntimeLayout(Path(request['project']).resolve())
    runtime.validate_paths()
    return runtime, identity


def _disabled_state(home, main_checkout):
    """只读最小旧登记检查；未登记放行，损坏/未知不可视为未禁用（fail closed）。"""
    path = Path(home) / '.mem-sharing' / 'var' / 'registry.json'
    if not os.path.lexists(path):
        return None  # 悬空 symlink 用 lexists 识别，不能当缺失放行
    try:
        data = json.loads(path.read_text())
    except (OSError, ValueError):
        return 'unknown'
    if not isinstance(data, dict) or not isinstance(data.get('projects'), dict):
        return 'unknown'
    projects = data['projects']
    key = str(main_checkout)
    if key not in projects:
        return None  # 键不存在才算未登记
    record = projects[key]
    if not isinstance(record, dict):
        return 'unknown'  # 显式 null/非 dict 坏记录：拒绝，不当未登记
    policy = record.get('memory_policy')
    if policy == 'disabled':
        return 'disabled'
    if policy == 'follow_ck':
        return None
    return 'unknown'


def _source_files(runtime):
    return {AGENTS_NAME: runtime.home / AGENTS_NAME,
            'claude': runtime.home / CLAUDE_NAME,
            'workbuddy': runtime.home / WORKBUDDY_REL}


def _entry_kind(name):
    return {'claude': 'at_import', 'workbuddy': 'project_block'}.get(name)


def _entry_bytes(name):
    if name == 'claude':
        return b'@AGENTS.md\n'
    if name == 'workbuddy':
        return WORKBUDDY_BLOCK
    _fail('invalid_request', '该项目文件无原生读取入口适配：' + name)


def _entry_state(name, data):
    if _entry_kind(name) == 'at_import':
        return sum(line.rstrip(b'\r\n') == b'@AGENTS.md'
                   for line in data.splitlines(keepends=True))
    starts, ends = data.count(WORKBUDDY_MARKER[0]), data.count(WORKBUDDY_MARKER[1])
    if starts or ends:
        if starts != 1 or ends != 1 or data.count(WORKBUDDY_BLOCK) != 1:
            _fail('entry_conflict', 'WorkBuddy 项目桥块漂移')
        return 1
    return 0


def _collect(request):
    runtime, identity = _project_runtime(request)
    _check_pending(runtime)
    state = _disabled_state(request.get('home') or str(Path.home()),
                            identity.main_checkout)
    if state == 'disabled':
        _fail('project_disabled', '项目为历史停用登记，默认跳过；重新接入需用户'
              '明确的重新接入计划')
    if state == 'unknown':
        _fail('disabled_unknown', '旧登记存在但不可读或结构未知，不可视为未禁用')
    sources = {}
    for name, path in _source_files(runtime).items():
        info = _read_source(path)
        info['name'], info['path'] = name, str(path)
        sources[name] = info
    for info in sources.values():
        if info['snapshot'] is not None:
            _entry_state(info['name'], info['snapshot'].data or b'')
    segments = []
    for name, info in sorted(sources.items()):
        snapshot = info['snapshot']
        if info['status'] != 'ok':
            continue
        protected = _protected_spans(snapshot.data)
        for start, end in _segments(snapshot.data, protected):
            raw = snapshot.data[start:end]
            segments.append({'source': name, 'start': start, 'end': end,
                             'text': raw.decode(), 'sha256': entries.sha256(raw),
                             'scope': _scope_titles(snapshot.data, start, protected)})
    basis = {str(i['path']): _meta(i['snapshot'])['sha256']
             for i in sources.values() if i['snapshot'] is not None}
    return runtime, identity, sources, segments, basis


def _validate_proposal(request, proposal):
    runtime, identity, sources, segments, basis = _collect(request)
    if not isinstance(proposal, dict) or proposal.get('schema_version') != 1:
        _fail('invalid_proposal', '提案必须是 schema_version 1 的 JSON 对象')
    if proposal.get('basis') != basis:
        _fail('drift', '提案依据与当前文件不一致，请重新预览')
    groups = proposal.get('groups')
    if not isinstance(groups, list) or not groups:
        _fail('invalid_proposal', '提案必须包含非空 groups')
    agents_snap = sources[AGENTS_NAME]['snapshot']
    agents_occurrences = []  # (start, end, sha256, 归一化有效标题栈)
    if agents_snap is not None and sources[AGENTS_NAME]['status'] == 'ok':
        protected = _protected_spans(agents_snap.data)
        for _s, _e in _segments(agents_snap.data, protected):
            raw = agents_snap.data[_s:_e]
            stack = _norm_stack(_heading_stack(agents_snap.data, _s, protected))
            agents_occurrences.append((_s, _e, entries.sha256(raw), stack))
    by_span = {(s['source'], s['start'], s['end']): s for s in segments}
    seen = set()
    validated = []
    for raw in groups:
        if not isinstance(raw, dict) or not isinstance(raw.get('summary'), str) \
                or not raw['summary'].strip() or not isinstance(raw.get('same_content'), bool) \
                or not isinstance(raw.get('items'), list) or not raw['items']:
            _fail('invalid_proposal', '每个分组需要 summary、same_content、非空 items')
        items = []
        for element in raw['items']:
            name = element.get('file') if isinstance(element, dict) else None
            if name not in sources or name == AGENTS_NAME:
                _fail('invalid_proposal', '分组 item 只能引用 AGENTS 之外的独立项目文件')
            if sources[name]['status'] != 'ok':
                _fail('invalid_proposal', 'item 来源不可读：' + name)
            key = (name, element.get('start'), element.get('end'))
            if key not in by_span:
                start, end = key[1:]
                data = sources[name]['snapshot'].data
                if type(start) is not int or type(end) is not int or not (0 <= start < end <= len(data)):
                    _fail('invalid_proposal', '原文字节范围无效')
                protected = _protected_spans(data)
                if any(start < b and end > a for a, b in protected):
                    _fail('invalid_proposal', '原文范围包含受保护入口或协议')
                try:
                    text = data[start:end].decode('utf-8')
                except UnicodeError:
                    _fail('invalid_proposal', '原文范围截断 UTF-8 字符')
                by_span[key] = {'source': name, 'start': start, 'end': end,
                                'text': text, 'sha256': entries.sha256(data[start:end]),
                                'scope': _scope_titles(data, start, protected)}
            if any(name == n and key[1] < e and key[2] > a for n, a, e in seen) or key in seen:
                _fail('invalid_proposal', '来源范围重叠或重复分组：%r' % (key,))
            seen.add(key)
            item = dict(by_span[key])
            source_data = sources[name]['snapshot'].data
            item['scope'] = [[level, title] for level, title in
                             _heading_stack(source_data, item['start'],
                                            _protected_spans(source_data))]
            items.append(item)
        identity_match = len({_identity(i['text']) for i in items}) == 1
        same_scope = len({_norm_stack(i['scope']) for i in items}) == 1
        # AGENTS 侧核验：逐字节相同且完整有效标题层级（作用域）完全一致，且
        # AGENTS 中恰有一处这样的出现，才绑定该精确 span 复用；父级不同而末级
        # 同名、多处重复等不确定匹配一律拒绝自动复用，走完整公共复制。
        member_stack = _norm_stack(items[0]['scope'])
        agents_spans = []
        for index, member in enumerate(items):
            matches = [(a, b) for a, b, sha, stack in agents_occurrences
                       if sha == member['sha256'] and stack == member_stack]
            if len(matches) == 1:
                agents_spans.append({'index': index, 'start': matches[0][0],
                                     'end': matches[0][1]})
        in_agents = identity_match and same_scope and len(agents_spans) == len(items)
        validated.append({'summary': raw['summary'].strip(), 'items': items,
                          'proposed_same': raw['same_content'],
                          'identity_match': identity_match, 'same_scope': same_scope,
                          'agents_spans': agents_spans, 'in_agents': in_agents,
                          'supported_same': raw['same_content'] and identity_match and same_scope,
                          'coverage': sorted({i['source'] for i in items})})
    return runtime, identity, sources, segments, basis, validated


def _blocks(groups, sources):
    """参与集合按实际独立文件（含 AGENTS）去重计票；未知来源阻断默认推荐。"""
    unknown = any(i['status'] == 'unknown' for i in sources.values())
    total = len(sources)
    defaults, optional, singles = [], [], []
    for group in groups:
        coverage = len(group['coverage'])
        if group['in_agents'] and group['supported_same']:
            defaults.append(group)  # AGENTS 既有公共项默认保留并整理重复，不进待选
        elif group['supported_same'] and total >= 2 and coverage == total and not unknown:
            defaults.append(group)
        elif coverage >= 2:
            optional.append(group)  # 仅部分独立文件同文且不在 AGENTS：待选
        else:
            singles.append(group)
    numbered = defaults + optional + singles
    for number, group in enumerate(numbered, 1):
        group['number'] = number
    return defaults, optional, singles, numbered, unknown


def _validate_exclusions(request, proposal_exclusions, sources):
    if not proposal_exclusions:
        return []
    if not isinstance(proposal_exclusions, list):
        _fail('invalid_exclusion', 'exclusions 必须是列表')
    agents_info = sources[AGENTS_NAME]
    if agents_info['status'] != 'ok':
        _fail('invalid_exclusion', 'AGENTS 不可读，不能排除既有公共项')
    data = agents_info['snapshot'].data
    protected = _protected_spans(data)
    targets = {str(i['path']): n for n, i in sources.items() if n != AGENTS_NAME}
    validated = []
    for raw in proposal_exclusions:
        start, end = (raw or {}).get('start'), (raw or {}).get('end')
        if type(start) is not int or type(end) is not int \
                or not (0 <= start < end <= len(data)):
            _fail('invalid_exclusion', '排除范围非法')
        if any(start < b and end > a for a, b in protected):
            _fail('invalid_exclusion', '排除范围包含受保护内容')
        text = data[start:end]
        if text.hex() != (raw.get('text_hex') or ''):
            _fail('drift', '排除范围字节与提案不一致')
        target = raw.get('target') or {}
        name = targets.get(target.get('path'))
        if name is None:
            _fail('invalid_exclusion',
                  '排除既有公共项必须逐项绑定本项目已确认原生文件去向；未给出去向即拒绝')
        snap = sources[name]['snapshot']
        insert_at = target.get('insert_at')
        if snap.kind not in ('absent', 'file') or type(insert_at) is not int \
                or not (0 <= insert_at <= len(snap.data or b'')):
            _fail('invalid_exclusion', '排除目标或插入位置非法')
        validated.append({'path': str(agents_info['path']), 'name': AGENTS_NAME,
                          'start': start, 'end': end, 'text': text,
                          'target_name': name, 'target_path': target['path'],
                          'insert_at': insert_at})
    for i, a in enumerate(validated):
        for b in validated[i + 1:]:
            if a['start'] < b['end'] and a['end'] > b['start']:
                _fail('invalid_exclusion', '排除范围互相重叠')
    return validated


def build_share_plan(request, proposal, selection):
    runtime, identity, sources, segments, basis, groups = _validate_proposal(
        request, proposal)
    exclusions = _validate_exclusions(request, proposal.get('exclusions'), sources)
    defaults, optional, singles, numbered, unknown = _blocks(groups, sources)
    numbers = {g['number'] for g in numbered}
    chosen, view, declined = _parse_selection(selection, numbers)
    if declined:
        chosen, exclusions = set(), []
    elif not view:
        excluded = set()
        import re as _re
        for clause in _re.split(r'[,，;；](?=\s*(?:不共享|共享|不合并|再加入))', selection):
            match = _re.fullmatch(r'\s*(?:不共享|不合并)\s*(\d+(?:\s*[、,，]\s*\d+)*)\s*', clause)
            if match:
                excluded.update(int(v) for v in _re.split(r'[、,，]', match[1]))
        chosen |= {g['number'] for g in defaults} - excluded
    agents_path = runtime.home / AGENTS_NAME
    agents_snap = sources[AGENTS_NAME]['snapshot']
    if agents_snap.kind not in ('absent', 'file'):
        _fail('path_conflict', 'AGENTS 必须是普通文件或不存在')
    public = agents_snap.data or b''
    migrations, exclusion_moves = [], list(exclusions)
    if agents_snap.kind == 'absent' and chosen and not view and not declined:
        public = '# 项目规则\n'.encode()
    if chosen and not view and not declined and unknown:
        _fail('unknown_source', '项目来源未知，先补证再执行共享')
    for group in numbered:
        if group['number'] not in chosen:
            continue
        members = list(group['items'])
        variants = []  # (字节, 首个成员在 items 中的下标)
        for index, member in enumerate(members):
            raw = member['text'].encode()
            if raw not in [v[0] for v in variants]:
                variants.append((raw, index))
        for raw, first_index in variants:
            span = None
            agents_span = None
            match = next((m for m in group.get('agents_spans', [])
                          if m['index'] == first_index), None)
            if match is not None:
                agents_span = {'start': match['start'], 'end': match['end']}
            else:
                offset = len(public)
                public += _separator(public) + raw
                span = (offset + len(_separator(public[:offset])), len(public))
            for member in members:
                if member['text'].encode() != raw:
                    continue
                migrations.append({
                    'group': group['number'], 'summary': group['summary'],
                    'source': member['source'], 'path': str(_source_files(runtime)[member['source']]),
                    'start': member['start'], 'end': member['end'],
                    'scope': member['scope'], 'text_hex': raw.hex(),
                    'text_sha256': entries.sha256(raw),
                    'in_agents': agents_span is not None,
                    'agents_span': agents_span,
                    'public_offset': None if span is None else span[0],
                    'public_end': None if span is None else span[1]})
    for record in sorted(exclusion_moves, key=lambda r: r['start'], reverse=True):
        if public[record['start']:record['end']] != record['text']:
            _fail('drift', 'AGENTS 排除片段与读取时不一致')
        public = public[:record['start']] + public[record['end']:]
    native_after = {}
    deletions = {}
    for record in migrations:
        if record['path'] == str(agents_path) or record['source'] == AGENTS_NAME:
            continue
        deletions.setdefault(record['path'], []).append(record)
    for name, records in deletions.items():
        raw = sources[name if name in sources else
                      next(n for n, i in sources.items() if i['path'] == name)]['snapshot'].data
        for record in sorted(records, key=lambda r: r['start'], reverse=True):
            if raw[record['start']:record['end']] != bytes.fromhex(record['text_hex']):
                _fail('drift', '来源片段与读取时不一致：' + name)
            raw = raw[:record['start']] + raw[record['end']:]
        native_after[name] = raw
    for move in exclusion_moves:
        base = native_after.get(move['target_path'])
        if base is None:
            target_name = move['target_name']
            base = sources[target_name]['snapshot'].data or b''
        at = move['insert_at']
        native_after[move['target_path']] = base[:at] + move['text'] + base[at:]
    entries_created = []
    for name in native_after:
        info = next(i for i in sources.values() if i['path'] == name)
        if _entry_state(info['name'], native_after[name]) == 0:
            block = _entry_bytes(info['name'])
            data = native_after[name]
            native_after[name] = data + (_separator(data) or b'\n') + block
            entries_created.append({'path': name, 'name': info['name'],
                                    'kind': _entry_kind(info['name']),
                                    'bytes_hex': block.hex()})
    outputs = {str(agents_path): public}
    for name, data in native_after.items():
        outputs[name] = data
    agents_after = public
    for record in migrations:
        record['agents_after_sha256'] = entries.sha256(agents_after)
    changes = []
    for name in sorted(outputs):
        before = next((i['snapshot'] for i in sources.values() if i['path'] == name),
                      None) or agents_snap
        after = outputs[name]
        if after == (before.data or b'') and before.kind == 'file':
            continue
        changes.append({'path': name, 'before': _meta(before),
                        'after_sha256': entries.sha256(after),
                        'after_hex': after.hex()})
    operation_metadata = None
    if migrations or exclusion_moves or entries_created:
        operation_metadata = {'project_share_memory': {
            'project': str(runtime.home), 'main_checkout': str(identity.main_checkout),
            'agents_topic': str(agents_path),
            'agents_before_sha256': _meta(agents_snap)['sha256'],
            'migrations': migrations,
            'exclusions_moved': [{'path': m['target_path'],
                                  'from': str(agents_path),
                                  'text_sha256': entries.sha256(m['text'])}
                                 for m in exclusion_moves],
            'entries_created': entries_created,
            'source_after': {name: entries.sha256(data)
                             for name, data in native_after.items()},
            'request': {'project': str(runtime.home)}}}
    observations = {str(i['path']): _meta(i['snapshot']) for i in sources.values()
                    if i['snapshot'] is not None}
    entry_stage = []
    for name, data in native_after.items():
        info = next(i for i in sources.values() if i['path'] == name)
        entry_stage.append({'path': name, 'after_hex': outputs[name].hex()})
    plan = {'schema_version': 1, 'command': COMMAND, 'project': str(runtime.home),
            'main_checkout': str(identity.main_checkout),
            'request': {k: request[k] for k in ('home', 'project') if k in request},
            'proposal': proposal, 'groups': numbered,
            'default_numbers': [g['number'] for g in defaults],
            'optional_numbers': [g['number'] for g in optional],
            'single_numbers': [g['number'] for g in singles],
            'selected_numbers': sorted(chosen), 'view': view, 'declined': declined,
            'in_agents_numbers': [g['number'] for g in numbered if g['in_agents']],
            'unknown_sources': [{'path': i['path'], 'reason': i.get('reason')}
                                for i in sources.values() if i['status'] == 'unknown'],
            'observations': observations, 'changes': changes,
            'operation_metadata': operation_metadata, 'entry_stage': entry_stage}
    plan['plan_sha256'] = entries.sha256(_encoded(plan))
    return plan


def present(plan):
    from .user_rules_organize import present as render
    projected = dict(plan, request=dict(plan['request']), groups=[])
    for group in plan['groups']:
        sources=[dict(source=str(_source_files(RuntimeLayout(Path(plan['project'])))[i['source']]), agents=[i['source']], text=i['text']) for i in group['items']]
        projected['groups'].append(dict(group,sources=sources))
    return render(projected, summaries={g['number']:g['summary'] for g in plan['groups']})


def final_list(plan):
    meta = plan.get('operation_metadata') or {}
    share = meta.get('project_share_memory') or {}
    lines = ['参与范围：当前项目 ' + plan['project'],
             '选定编号：' + str(plan['selected_numbers'])]
    for record in share.get('migrations', []):
        lines += ['', '编号 %s：%s' % (record['group'], record['summary']),
                  '来源 %s 字节 %d-%d：' % (record['path'], record['start'], record['end']),
                  bytes.fromhex(record['text_hex']).decode().rstrip('\n')]
    for moved in share.get('exclusions_moved', []):
        lines += ['', 'AGENTS 既有项显式去向：%s' % moved['path']]
    for created in share.get('entries_created', []):
        lines.append('新增项目读取入口：%s（%s）' % (created['path'], created['kind']))
    lines.append('恢复安排：事务清单持久于 %s/.mem-sharing/backups/，中断用 %s '
                 '--manifest 只读核验后按批准回滚。' % (plan['project'], RECOVER_COMMAND))
    return '\n'.join(lines)


def _result(**fields):
    result = {'command': COMMAND, 'status': 'failed', 'approval_required': False,
              'next_action': None, 'errors': [], 'changes': []}
    result.update(fields)
    return result


def plan_share(request):
    try:
        if request.get('proposal') is None:
            runtime, identity, sources, segments, basis = _collect(request)
            return _result(status='completed', project=str(runtime.home), participants={
                str(i['path']): {'name': i['name'], 'status': i['status'],
                                 'reason': i.get('reason'),
                                 'text': (i['snapshot'].data or b'').decode('utf-8')
                                 if i['status'] in ('ok', 'empty', 'missing') else None}
                for i in sources.values()},
                segments=segments, basis=basis,
                next_action='当前 Agent 阅读完整原文后撰写提案，再带 --proposal-file 预览')
        plan = build_share_plan(request, request['proposal'],
                                request.get('selection', '按默认方案'))
        if plan['view']:
            group = next(g for g in plan['groups'] if g['number'] == plan['view'])
            return _result(status='viewed', approval_plan=plan,
                           view={'number': group['number'], 'summary': group['summary'],
                                 'sources': [{'file': i['source'], 'path':
                                              str(Path(plan['project'], i['source'])),
                                              'start': i['start'], 'end': i['end'],
                                              'text': i['text']} for i in group['items']]})
        if not plan['changes']:
            return _result(status='completed', approval_plan=plan, prompt=present(plan))
        preview = dict(plan, confirmed_at='<UTC timestamp>',
                       reference='<real user confirmation>')
        return _result(status='approval_required', approval_required=True,
                       approval_plan=plan, prompt=present(plan),
                       final_list=final_list(plan), changes=plan['changes'],
                       next_action=json.dumps(preview, ensure_ascii=False))
    except (ValueError, OSError, KeyError, TypeError) as exc:
        return _result(errors=[{'code': getattr(exc, 'code', 'share_failed'),
                                'message': str(exc)}])


def _selection_of(plan):
    import re as _re
    if plan['declined']:
        return '暂不整理'
    defaults = set(plan['default_numbers'])
    chosen = set(plan['selected_numbers'])
    parts = []
    if chosen - defaults:
        parts.append('共享 ' + '、'.join(str(n) for n in sorted(chosen - defaults)))
    if defaults - chosen:
        parts.append('不共享 ' + '、'.join(str(n) for n in sorted(defaults - chosen)))
    return '，'.join(parts) if parts else '按默认方案'


def execute_share(plan, approval, *, request=None, hook=None):
    try:
        import copy
        if plan.get('view'):
            _fail('view_only', '查看不能执行修改')
        if not isinstance(approval, dict):
            _fail('approval_mismatch', '需要完整批准对象')
        evidence = {k: approval.get(k) for k in ('confirmed_at', 'reference')}
        if any(not isinstance(v, str) or not v.strip() or v.startswith('<')
               for v in evidence.values()):
            _fail('approval_mismatch', '需要真实确认证据')
        if approval != dict(plan, **evidence):
            _fail('approval_mismatch', '批准必须与整份精确计划一致')
        request = copy.deepcopy(request or plan['request'])
        rebuilt = build_share_plan(request, plan['proposal'], _selection_of(plan))
        if rebuilt != plan:
            _fail('drift', '场景或计划自预览以来已变化')
        if not plan['changes']:
            return _result(status='completed', approval_plan=plan)
        runtime, identity = _project_runtime(request)
        runtime.lock.parent.mkdir(parents=True, exist_ok=True)
        with write_lock(runtime.lock):
            rebuilt = build_share_plan(request, plan['proposal'], _selection_of(plan))
            if rebuilt != plan:
                _fail('drift', '取得锁后场景已变化')
            state = {}
            for name, meta in plan['observations'].items():
                state[name] = read_snapshot(Path(name))
                if _meta(state[name]) != meta:
                    _fail('drift', '观察基线漂移：' + name)
            agents_path = str(runtime.home / AGENTS_NAME)
            source_paths = {c['path'] for c in plan['changes']} - {agents_path}
            transaction = Transaction(lock_path=runtime.transaction_lock,
                                      backup_root=runtime.backups,
                                      allowed_roots=[runtime.home],
                                      operation=COMMAND, hook=hook,
                                      operation_metadata=plan['operation_metadata'])
            # 真正分阶段：公共 AGENTS → 全部必要项目入口逐一建立核验 → 精确删源。
            # 纯去重时 AGENTS 无变更也照常执行；同一 Transaction 备份/恢复。
            agents_change = next((c for c in plan['changes']
                                  if c['path'] == agents_path), None)
            agents_after = bytes.fromhex(agents_change['after_hex']) if agents_change \
                else (state[agents_path].data or b'')
            tx_changes, order = [], []
            if agents_change is not None:
                tx_changes.append(Change.file(Path(agents_path), agents_after,
                                              expected=state[agents_path]))
                order.append((agents_path, 'public'))
            staged = dict(state)
            source_changes = sorted((c for c in plan['changes']
                                     if c['path'] in source_paths),
                                    key=lambda c: c['path'])
            for c in source_changes:  # 阶段二：先全部建立必要入口
                bridge = _bridge_name(runtime, c['path'])
                base = staged[c['path']].data or b''
                if bridge is not None and _entry_state(bridge, base) == 0:
                    entry_after = base + (_separator(base) or b'\n') + _entry_bytes(bridge)
                    staged_snap = staged[c['path']]
                    entry_snap = Snapshot('file', entry_after,
                                          staged_snap.mode or 0o600)
                    if entry_snap != staged_snap:
                        tx_changes.append(Change.file(Path(c['path']), entry_after,
                                                      expected=staged_snap))
                        order.append((c['path'], 'entry'))
                        staged[c['path']] = entry_snap
            for c in source_changes:  # 阶段三：入口就绪后才精确删源/写入
                after = bytes.fromhex(c['after_hex'])
                if after == (staged[c['path']].data or b''):
                    continue
                tx_changes.append(Change.file(Path(c['path']), after,
                                              expected=staged[c['path']]))
                order.append((c['path'], 'delete'))

            step = {'i': 0}
            deletes_checked = {'done': False}

            def guarded(event, path):
                if hook:
                    hook(event, path)
                if event not in ('before_write', 'after_write'):
                    return
                if step['i'] >= len(order):
                    return
                expected_path, stage = order[step['i']]
                if str(path) != expected_path:
                    _fail('drift', '写入顺序异常：%s（应为 %s）' % (path, expected_path))
                if event == 'before_write' and stage == 'delete' \
                        and not deletes_checked['done']:
                    deletes_checked['done'] = True
                    snap = read_snapshot(Path(agents_path))
                    if snap.kind != 'file' or snap.data != agents_after:
                        _fail('drift', '公共 AGENTS 未完整保存，保留原文')
                    for name in source_paths:  # 全部入口就绪且原文未被动过
                        info_snap = read_snapshot(Path(name))
                        bridge = _bridge_name(runtime, name)
                        if bridge is None or _entry_state(bridge,
                                                          info_snap.data or b'') != 1:
                            _fail('entry_conflict', '删源前项目读取入口未就绪：' + name)
                        if not (info_snap.data or b'').startswith(state[name].data or b''):
                            _fail('drift', '删源前原文已被改动：' + name)
                if event == 'after_write':
                    if stage == 'entry':
                        bridge = _bridge_name(runtime, str(path))
                        data = read_snapshot(Path(path)).data or b''
                        if bridge is None or _entry_state(bridge, data) != 1:
                            _fail('entry_conflict', '入口写入后未就绪：' + str(path))
                    step['i'] += 1
            transaction.hook = guarded
            result = transaction.run(tx_changes, phased_writes=True)
        return _result(status='completed', changes=plan['changes'],
                       manifest=result['manifest'],
                       operation_metadata=plan['operation_metadata'])
    except (ValueError, OSError, KeyError, TypeError, StopIteration) as exc:
        return _result(status='recovery_required'
                       if getattr(exc, 'code', None) == 'recovery_required' else 'failed',
                       errors=[{'code': getattr(exc, 'code', 'share_failed'),
                                'message': str(exc),
                                'manifest': getattr(exc, 'manifest', None)}])


def run_share(request):
    if request.get('approval') is None:
        return plan_share(request)
    approval = request['approval']
    if not isinstance(approval, dict):
        return _result(errors=[{'code': 'approval_mismatch', 'message': '需要批准对象'}])
    plan = {k: v for k, v in approval.items() if k not in ('confirmed_at', 'reference')}
    return execute_share(plan, approval, request=request, hook=request.get('hook'))


# ---- return（项目归还）：与用户主线一致，公共目标为根 AGENTS.md -------------


def _manifests(runtime):
    found = []
    for manifest in sorted(runtime.backups.glob('*/manifest.json')):
        snap = read_snapshot(manifest)
        if snap.kind != 'file':
            _fail('path_conflict', '事务清单异常：' + str(manifest))
        data = json.loads(snap.data)
        if data.get('operation') not in (COMMAND, RETURN_COMMAND):
            continue
        found.append((manifest.parent.name, manifest, data))
    return found


def _consumed_index(runtime):
    consumed = set()
    for _, _, data in _manifests(runtime):
        if data.get('status') != 'committed':
            continue
        meta = (data.get('operation_metadata') or {}).get('return_project_memory') or {}
        for ref in meta.get('consumed', []):
            consumed.add((ref['manifest'], ref['migration']))
    return consumed


def _available_migrations(runtime):
    available = {}
    for name, manifest, data in _manifests(runtime):
        share = (data.get('operation_metadata') or {}).get('project_share_memory')
        if not share or data.get('status') != 'committed':
            continue
        for position, record in enumerate(share['migrations']):
            available[(name, position)] = dict(record, manifest=name,
                                               manifest_path=str(manifest),
                                               position=position)
    return available


def _bridge_name(runtime, path):
    for name, candidate in _source_files(runtime).items():
        if str(candidate) == path and name != AGENTS_NAME:
            return name
    return None


def _strip_project_entry(name, data):
    if _entry_state(name, data) != 1:
        return data
    block = _entry_bytes(name)
    if _entry_kind(name) == 'at_import':
        lines = [line for line in data.splitlines(keepends=True)
                 if line.rstrip(b'\r\n') != b'@AGENTS.md']
        joined = b''.join(lines)
        if joined.endswith(block):
            joined = joined[:-len(block)]
        return joined
    return data.replace(block, b'', 1)


def build_return_plan(request, agent_plan):
    runtime, identity = _project_runtime(request)
    _check_pending(runtime)
    if not isinstance(agent_plan, dict) or agent_plan.get('schema_version') != 1:
        _fail('invalid_return', '归还提案必须是 schema_version 1 的 JSON 对象')
    available = _available_migrations(runtime)
    consumed = _consumed_index(runtime)
    if not available:
        _fail('invalid_request', '没有可归还的项目共享记录')
    agents_path = runtime.home / AGENTS_NAME
    agents_snap = read_snapshot(agents_path)
    if agents_snap.kind != 'file':
        _fail('path_conflict', '公共 AGENTS 缺失或被替换')
    sources = {str(p): n for n, p in _source_files(runtime).items()}
    basis = dict(agent_plan.get('basis') or {})
    if basis.get(str(agents_path)) != agents_snap.fingerprint:
        _fail('drift', '归还提案的公共基线与当前不一致')
    states = {str(agents_path): agents_snap}
    for path, name in sources.items():
        if name == AGENTS_NAME:
            continue
        snap = read_snapshot(Path(path))
        if snap.kind not in ('absent', 'file'):
            _fail('path_conflict', '归还目标异常：' + path)
        states[path] = snap
        if path in basis and _meta(snap)['sha256'] != basis[path]:
            _fail('drift', '归还提案的来源基线与当前不一致：' + path)
    items = agent_plan.get('items')
    if not isinstance(items, list):
        _fail('invalid_return', 'items 必须是列表')
    used_refs, planned_returns, keep_public = set(), [], []
    for raw in items:
        ref = (raw.get('ref'), raw.get('migration'))
        if ref not in available:
            _fail('invalid_return', '引用了不存在的历史迁移：%r' % (ref,))
        if ref in consumed:
            _fail('invalid_return', '该迁移已被先前归还消费：%r' % (ref,))
        if ref in used_refs:
            _fail('invalid_return', '重复引用同一迁移：%r' % (ref,))
        used_refs.add(ref)
        record = available[ref]
        span = raw.get('public_span') or {}
        start, end = span.get('start'), span.get('end')
        if not isinstance(start, int) or not isinstance(end, int) \
                or not (0 <= start < end <= len(agents_snap.data)):
            _fail('invalid_return', '公共范围非法')
        current = agents_snap.data[start:end]
        if current.hex() != (span.get('text_hex') or ''):
            _fail('drift', '公共范围字节与提案不一致（请按当前正文重新提案）')
        if raw.get('action') == 'keep_public':
            keep_public.append((ref, record, start, end))
            continue
        target = raw.get('target') or {}
        path = target.get('path')
        if path not in states or path == str(agents_path):
            _fail('invalid_return', '归还目标必须是本项目原生文件')
        base = states[path].data or b''
        mode = target.get('mode')
        if mode == 'in_place':
            after_sha = None
            for name, manifest, data in _manifests(runtime):
                if name != record['manifest']:
                    continue
                share_meta = (data.get('operation_metadata') or {}).get(
                    'project_share_memory') or {}
                after_sha = share_meta.get('source_after', {}).get(path)
                break
            if after_sha is None or states[path].kind != 'file' \
                    or states[path].fingerprint != after_sha:
                _fail('invalid_return',
                      '来源已变化，不能按原位恢复（请给出当前正文的明确插入位置）：' + path)
            if path != record['path']:
                _fail('invalid_return', '原位归还只能使用原来源文件')
            siblings = [r for r in available.values()
                        if r['manifest'] == record['manifest'] and r['path'] == path
                        and r['start'] < record['start']]
            insert_at = record['start'] - sum(r['end'] - r['start'] for r in siblings)
        elif mode == 'insert_at':
            insert_at = target.get('insert_at')
            if not isinstance(insert_at, int) or not (0 <= insert_at <= len(base)):
                _fail('invalid_return', '插入位置非法')
        else:
            _fail('invalid_return', 'target.mode 必须是 in_place 或 insert_at')
        planned_returns.append({'ref': ref, 'record': record, 'path': path,
                                'insert_at': insert_at, 'text': current,
                                'public_start': start, 'public_end': end})
    additions = agent_plan.get('additions') or []
    if not isinstance(additions, list):
        _fail('invalid_return', 'additions 必须是列表')
    addition_moves = []
    covered = [(r['public_start'], r['public_end']) for r in planned_returns] \
        + [(s, e) for _, _, s, e in keep_public]
    for raw in additions:
        start, end = raw.get('start'), raw.get('end')
        if not isinstance(start, int) or not isinstance(end, int) \
                or not (0 <= start < end <= len(agents_snap.data)):
            _fail('invalid_return', '公共新增范围非法')
        if any(start < b and end > a for a, b in covered):
            _fail('invalid_return', '公共新增范围与迁移片段重叠')
        covered.append((start, end))
        text = agents_snap.data[start:end]
        if text.hex() != (raw.get('text_hex') or ''):
            _fail('drift', '公共新增字节与提案不一致')
        if raw.get('action') == 'keep_public':
            continue
        target = raw.get('target') or {}
        path = target.get('path')
        if path not in states:
            _fail('invalid_return', '新增迁移目标必须是本项目原生文件')
        insert_at = target.get('insert_at')
        base = states[path].data or b''
        if not isinstance(insert_at, int) or not (0 <= insert_at <= len(base)):
            _fail('invalid_return', '新增迁移插入位置非法')
        addition_moves.append({'path': path, 'insert_at': insert_at, 'text': text,
                               'public_start': start, 'public_end': end})
    outputs, inserts = {}, {}
    for item in sorted(planned_returns + addition_moves,
                       key=lambda i: (i['insert_at'],
                                      i.get('record', {}).get('start', 0)), reverse=True):
        base = inserts.get(item['path'], states[item['path']].data or b'')
        inserts[item['path']] = base[:item['insert_at']] + item['text'] \
            + base[item['insert_at']:]
    outputs.update(inserts)
    new_public = agents_snap.data

    def relation_key(record):
        return (record['manifest'], record['public_offset'], record['public_end'])
    moving_refs = {r['ref'] for r in planned_returns}
    outstanding = {relation_key(record) for ref, record in available.items()
                   if ref not in consumed and ref not in moving_refs}
    retained_spans = {(start, end) for _, _, start, end in keep_public}
    retained_spans.update((r['public_start'], r['public_end']) for r in planned_returns
                          if relation_key(r['record']) in outstanding)
    removal_spans = sorted({(r['public_start'], r['public_end'])
                            for r in planned_returns + addition_moves
                            if not r['record'].get('in_agents')} - retained_spans)
    for (a, b), (c, d) in zip(removal_spans, removal_spans[1:]):
        if c < b:
            _fail('invalid_return', '公共归还范围部分重叠')
    if any(a < e and b > s for a, b in removal_spans for s, e in retained_spans):
        _fail('invalid_return', '同一公共范围不能同时归还与保留')
    for start, end in reversed(removal_spans):
        new_public = new_public[:start] + new_public[end:]
    outputs[str(agents_path)] = new_public
    remove_entries = agent_plan.get('remove_entries') is True
    if remove_entries:
        remaining = [ref for ref in available if ref not in consumed
                     and ref not in used_refs]
        if keep_public or remaining:
            _fail('invalid_return', '仍有未处置迁移或保留公共内容，不能移除项目入口')
        original_sha = None
        for name, manifest, data in _manifests(runtime):
            share = (data.get('operation_metadata') or {}).get('project_share_memory')
            if share and (original_sha is None):
                original_sha = share.get('agents_before_sha256')
        # 允许恰好多出工具补的分隔换行（至多两个），其余必须逐字节回到共享前。
        candidates = [new_public]
        for tail in (b'\n', b'\n\n'):
            if new_public.endswith(tail):
                candidates.append(new_public[:-len(tail)])
        if original_sha is None or not any(entries.sha256(c) == original_sha
                                           for c in candidates):
            _fail('invalid_return',
                  'AGENTS 仍未回到共享前原字节，不能移除项目入口（公共新增/排除回迁'
                  '须全部明确处置）')
        for path, data in list(outputs.items()):
            bridge = _bridge_name(runtime, path)
            if bridge is None or data is None:
                continue
            outputs[path] = _strip_project_entry(bridge, data)
    changes = []
    observations = {name: _meta(snap) for name, snap in states.items()}
    for name in sorted(set(outputs) | {str(agents_path)}):
        snap = states[name]
        after = outputs.get(name)
        if after is None or (snap.kind == 'file' and after == snap.data):
            continue
        changes.append({'path': name, 'before': _meta(snap),
                        'after_sha256': entries.sha256(after),
                        'after_hex': after.hex()})
    consumed_records = [{'manifest': ref[0], 'migration': ref[1]}
                        for ref in sorted(r['ref'] for r in planned_returns)]
    operation_metadata = {'return_project_memory': {
        'consumed': consumed_records,
        'kept_public': [{'manifest': ref[0], 'migration': ref[1]}
                        for ref, _, _, _ in keep_public],
        'additions_moved': [{'path': m['path'],
                             'text_sha256': entries.sha256(m['text'])}
                            for m in addition_moves]}}
    plan = {'schema_version': 1, 'command': RETURN_COMMAND, 'project': str(runtime.home),
            'main_checkout': str(identity.main_checkout),
            'request': {k: request[k] for k in ('home', 'project') if k in request},
            'items': [{'ref': list(r['ref']), 'summary': r['record']['summary'],
                       'target': r['path'], 'insert_at': r['insert_at'],
                       'text_hex': r['text'].hex()} for r in planned_returns],
            'kept_public': [list(ref) for ref, _, _, _ in keep_public],
            'additions_moved': operation_metadata['return_project_memory']['additions_moved'],
            'remove_entries': remove_entries,
            'observations': observations, 'changes': changes,
            'operation_metadata': operation_metadata}
    plan['plan_sha256'] = entries.sha256(_encoded(plan))
    return plan


def run_return(request):
    try:
        if request.get('approval') is None:
            plan = build_return_plan(request, request.get('return_plan'))
            preview = dict(plan, confirmed_at='<UTC timestamp>',
                           reference='<real user confirmation>')
            return {'command': RETURN_COMMAND, 'status': 'approval_required',
                    'approval_required': True, 'approval_plan': plan,
                    'next_action': json.dumps(preview, ensure_ascii=False)}
        approval = request['approval']
        evidence = {k: approval.get(k) for k in ('confirmed_at', 'reference')}
        if any(not isinstance(v, str) or not v.strip() or v.startswith('<')
               for v in evidence.values()):
            raise ShareError('approval_mismatch', '需要真实确认证据')
        plan = {k: v for k, v in approval.items()
                if k not in ('confirmed_at', 'reference')}
        if approval != dict(plan, **evidence):
            raise ShareError('approval_mismatch', '归还批准或场景已变化')
        request = dict(request, project=plan['project'])
        request.pop('approval', None)
        runtime, _identity = _project_runtime(request)
        runtime.lock.parent.mkdir(parents=True, exist_ok=True)
        with write_lock(runtime.lock):
            current = build_return_plan(request, request.get('return_plan'))
            if current != plan:
                raise ShareError('drift', '归还场景已变化')
            state = {}
            for name, meta in plan['observations'].items():
                state[name] = read_snapshot(Path(name))
                if _meta(state[name]) != meta:
                    raise ShareError('drift', '观察基线漂移：' + name)
            tx_changes = [Change.file(Path(c['path']), bytes.fromhex(c['after_hex']),
                                      expected=state[c['path']])
                          for c in plan['changes']]
            transaction = Transaction(lock_path=runtime.transaction_lock,
                                      backup_root=runtime.backups,
                                      allowed_roots=[runtime.home],
                                      operation=RETURN_COMMAND,
                                      operation_metadata=plan['operation_metadata'])
            result = transaction.run(tx_changes)
        return {'command': RETURN_COMMAND, 'status': 'completed',
                'changes': plan['changes'], 'manifest': result['manifest']}
    except (ValueError, OSError, KeyError, TypeError) as exc:
        return {'command': RETURN_COMMAND,
                'status': 'recovery_required'
                if getattr(exc, 'code', None) == 'recovery_required' else 'failed',
                'errors': [{'code': getattr(exc, 'code', 'return_failed'),
                            'message': str(exc),
                            'manifest': getattr(exc, 'manifest', None)}]}


def run_recover(request):
    """项目事务恢复：与用户主线同一 Transaction 恢复，材料在项目 backups 下。"""
    try:
        runtime, _identity = _project_runtime(request)
        manifest = Path(request['manifest'])
        if not manifest.is_absolute() or manifest.parent.parent != runtime.backups \
                or manifest.name != 'manifest.json':
            raise ShareError('invalid_request', '仅接受本项目 backups 下的事务清单')
        data = json.loads(read_snapshot(manifest).data)
        if data.get('operation') not in (COMMAND, RETURN_COMMAND):
            raise ShareError('invalid_request', '不是项目共享/归还的事务清单')
        roots = [runtime.home]
        inspected = inspect_recovery(manifest, allowed_roots=roots)
        recovery_plan = {'command': RECOVER_COMMAND, 'manifest': str(manifest),
                         'manifest_sha256': entries.sha256(read_snapshot(manifest).data),
                         'observations': {entry['path']: _meta(read_snapshot(Path(entry['path'])))
                                          for entry in inspected['entries']},
                         'restore': inspected['entries']}
        approval = request.get('approval')
        if approval is None:
            return {'command': RECOVER_COMMAND, 'status': 'approval_required',
                    'approval_required': True, 'manifest': str(manifest),
                    'manifest_status': data.get('status'), 'approval_plan': recovery_plan}
        evidence = {k: approval.get(k) for k in ('confirmed_at', 'reference')}
        if any(not isinstance(v, str) or not v.strip() or v.startswith('<')
               for v in evidence.values()) or approval != dict(recovery_plan, **evidence):
            raise ShareError('approval_mismatch', '恢复批准不完整或不匹配')
        runtime.lock.parent.mkdir(parents=True, exist_ok=True)
        with write_lock(runtime.lock):
            inspect_recovery(manifest, allowed_roots=roots)
            if entries.sha256(read_snapshot(manifest).data) != recovery_plan['manifest_sha256']:
                _fail('drift', '恢复清单已漂移')
            if any(_meta(read_snapshot(Path(name))) != meta
                   for name, meta in recovery_plan['observations'].items()):
                _fail('drift', '恢复对象已漂移')
            result = recover_manifest(manifest, lock_path=runtime.transaction_lock,
                                      allowed_roots=roots, hook=request.get('hook'))
        return {'command': RECOVER_COMMAND, 'status': 'completed',
                'recovery_status': result['status'], 'manifest': str(manifest)}
    except (ValueError, OSError, KeyError, TypeError) as exc:
        return {'command': RECOVER_COMMAND,
                'status': 'recovery_required'
                if getattr(exc, 'code', None) in ('recovery_required', 'lock_conflict')
                else 'failed',
                'manifest': request.get('manifest'),
                'errors': [{'code': getattr(exc, 'code', 'recover_failed'),
                            'message': str(exc),
                            'manifest': getattr(exc, 'manifest', None)}]}


def cli(argv=None, *, home=None):
    import argparse
    import sys
    parser = argparse.ArgumentParser(prog='项目记忆共享', allow_abbrev=False)
    parser.add_argument('command',
                        choices=[COMMAND, RETURN_COMMAND, RECOVER_COMMAND])
    parser.add_argument('--project', required=True)
    parser.add_argument('--proposal-file')
    parser.add_argument('--return-plan-file')
    parser.add_argument('--selection', default=None)
    parser.add_argument('--decline', action='store_true')
    parser.add_argument('--approval-file')
    parser.add_argument('--selection-plan-file', help='此前展示的完整计划')
    parser.add_argument('--selection-reference', help='本次真实用户选择')
    parser.add_argument('--manifest')
    parser.add_argument('--home')
    ns = parser.parse_args(argv)
    try:
        from . import memory_share as ms
        target_home = str(Path(home or ns.home or Path.home()).resolve())
        request = {'home': target_home, 'project': ns.project}
        if ns.approval_file:
            approval = json.loads(Path(ns.approval_file).read_text())
            if ns.command != RECOVER_COMMAND:
                request.update(approval['request'])
            if ns.return_plan_file:
                request['return_plan'] = json.loads(Path(ns.return_plan_file).read_text())
            if ns.manifest:
                request['manifest'] = ns.manifest
            if request['home'] != target_home:
                raise ShareError('approval_mismatch', '批准 HOME 与当前目标不一致')
            if ns.selection is not None or ns.decline or ns.proposal_file:
                raise ShareError('approval_mismatch', '执行批准时不得改变选择或提案')
            request['approval'] = approval
        else:
            if ns.proposal_file:
                request['proposal'] = json.loads(Path(ns.proposal_file).read_text())
            if ns.return_plan_file:
                request['return_plan'] = json.loads(Path(ns.return_plan_file).read_text())
            if ns.manifest:
                request['manifest'] = ns.manifest
            request['selection'] = '暂不整理' if ns.decline else \
                ns.selection or '按默认方案'
        if ns.command == COMMAND:
            result = run_share(request)
            if ns.selection_reference:
                if ns.approval_file or ns.selection is None or not ns.selection_reference.strip() or not ns.selection_plan_file:
                    _fail('approval_mismatch','选择执行须绑定真实选择与此前展示计划')
                if result.get('approval_required') and not result['approval_plan'].get('view'):
                    plan=result['approval_plan'];shown=json.loads(Path(ns.selection_plan_file).read_text())
                    if any(shown.get(k)!=plan.get(k) for k in ('proposal','observations','groups','project','main_checkout')):
                        _fail('drift','原文或编号相对已展示方案变化')
                    from datetime import datetime, timezone
                    evidence={'confirmed_at':datetime.now(timezone.utc).isoformat().replace('+00:00','Z'),'reference':ns.selection_reference}
                    result=execute_share(plan,dict(plan,**evidence),request=request)
        elif ns.command == RETURN_COMMAND:
            result = run_return(request)
        else:
            if not ns.manifest:
                raise ShareError('invalid_request', '恢复需要 --manifest')
            result = run_recover(request)
    except (ValueError, OSError, KeyError, TypeError) as exc:
        result = _result(errors=[{'code': getattr(exc, 'code', 'share_failed'),
                                  'message': str(exc)}])
    print(json.dumps(result, ensure_ascii=False))
    if result['status'] == 'viewed':
        return 0
    if result['status'] in ('failed', 'recovery_required'):
        return 2
    return 5 if result.get('approval_required') else 0

