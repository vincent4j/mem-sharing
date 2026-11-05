"""Skill-first memory sharing: the Agent proposes, this tool executes exactly.

Four user steps only: shared directory -> read the agents' real native user
memory -> the current Agent summarizes and the user picks numbers -> complete
originals are written to public first, precise entries and content are
verified, then the exact source spans are deleted. No cloud model, hook or
service; no registry, installer or release state is required to read memory.

Semantic understanding stays with the Agent. Byte-identical originals of one
group share a single public copy only when every source span can be re-verified
byte-for-byte from that copy; formatting variants each keep their own copy.
Every migration (including duplicates inside one file) is recorded in the
Transaction manifest's optional top-level ``operation_metadata`` before the
manifest first persists; manifests are history and are never edited later.
Return runs on explicit Agent plans over current bytes and records consumed
references in its own manifest, preventing double returns without a parallel
index.
"""
from __future__ import annotations

import copy
import json
import os
import re
from pathlib import Path

from . import entries, layout, paths
from .transaction import (Change, Snapshot, Transaction, TransactionError,
                          inspect_recovery, read_snapshot, recover_manifest,
                          write_lock)

COMMAND = 'share-user-memory'
RETURN_COMMAND = 'return-user-memory'
RECOVER_COMMAND = 'recover-memory-share'
TOPIC_NAME = 'user-rules.md'
CK_MARKERS = ((b'<!-- context-keeper:start -->', b'<!-- context-keeper:end -->'),
              (b'<!-- context-keeper:workbuddy:start -->',
               b'<!-- context-keeper:workbuddy:end -->'))
AGM_MARKER = re.compile(rb'<!-- mem-sharing:([a-zA-Z0-9_-]+):start -->')
ENTRY_MARKER = {'start': b'<!-- mem-sharing:memory-index:start -->',
                'end': b'<!-- mem-sharing:memory-index:end -->'}


class ShareError(ValueError):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


def _fail(code, message):
    raise ShareError(code, message)


def _encoded(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True,
                       separators=(',', ':')) + '\n').encode()


def _meta(snapshot):
    return {'kind': snapshot.kind, 'sha256': snapshot.fingerprint,
            'mode': snapshot.mode, 'target': snapshot.target}


def _runtime(request):
    runtime = layout.from_request(request)
    runtime = layout.resolve_layout(runtime.home.resolve())
    runtime.validate_paths()
    return runtime


def _dsh_home_redirected(home):
    """DSH_HOME 是否把 DSH 用户规则根重定向到非默认位置（纯布尔，不回显原值）。

    语义与 agm_core.user_entries 的冻结合同一致，测试锁定两处行为相同；核心
    不 import 安装层模块，避免反向依赖。空白视为未设置；~/ 与 ~\\ 前缀按给定
    home 展开后仅转换此前缀的分隔符，再绝对规范化；规范化后等于 <home>/.dsh
    不算重定向。DSH_AGENTS_HOME 只影响 Skill 根，不进入本判断，也不得据此
    阻断仍有效的用户入口。
    """
    value = os.environ.get('DSH_HOME')
    if value is None or not value.strip():
        return False
    root = value
    if root.startswith('~'):
        rest = root[1:]
        if not rest:
            root = str(home)
        elif rest.startswith(('/', '\\')):
            root = str(home) + '/' + rest[1:]
    return os.path.abspath(root) != os.path.abspath(os.path.join(str(home), '.dsh'))


def _opencode_config_redirected(home):
    """OpenCode 配置根是否被环境变量重定向/覆盖（纯布尔，不回显原值，fail closed）。

    语义与 agm_core.user_entries 的冻结合同一致，测试锁定两处行为相同：
    XDG_CONFIG_HOME/OPENCODE_CONFIG_DIR 仅在绝对且等于默认落点时放行；
    OPENCODE_CONFIG 值域未证实，任何非空取值即视为重定向。
    """
    for name, default in (('XDG_CONFIG_HOME', '.config'),
                          ('OPENCODE_CONFIG_DIR', os.path.join('.config', 'opencode'))):
        value = os.environ.get(name)
        if value is None or not value.strip():
            continue
        if not os.path.isabs(value) or os.path.abspath(value) != \
                os.path.abspath(os.path.join(str(home), default)):
            return True
    override = os.environ.get('OPENCODE_CONFIG')
    return bool(override is not None and override.strip())


def _native_paths(request, runtime):
    config = request['platform_config']
    agents = request.get('agents') or []
    if not agents:
        _fail('invalid_request', '参与的 Agent 必须显式指定')
    if len(set(agents)) != len(agents):
        _fail('invalid_request', 'Agent 不得重复')
    for agent in agents:
        if agent not in config or 'user_entry' not in config[agent]:
            _fail('invalid_request', '本切片不支持的 Agent：' + str(agent))
    # ZCode 规则根只由 HOME/USERPROFILE 后备 homedir 决定（CLI 经 --home 或
    # Path.home()），ZCODE_HOME 不是规则根：既不据此寻址，也不据此阻断。
    if 'dsh' in agents and _dsh_home_redirected(runtime.home):
        _fail('dsh_home_redirected',
              'DSH_HOME 已重定向 DSH 用户规则根，默认入口 <home>/.dsh/AGENTS.md 的'
              '读取无法确认，拒绝本次共享/归还（DSH_AGENTS_HOME 只影响 Skill 根，'
              '不影响本判断）')
    if 'opencode' in agents and _opencode_config_redirected(runtime.home):
        _fail('opencode_config_redirected',
              'OpenCode 配置根被 XDG_CONFIG_HOME/OPENCODE_CONFIG_DIR/OPENCODE_CONFIG'
              ' 重定向或覆盖，默认入口 <home>/.config/opencode/AGENTS.md 的读取'
              '无法确认，拒绝本次共享/归还')
    return {a: paths.expand_path(config[a]['user_entry'], home=str(runtime.home))
            for a in agents}


def _entry_kind(agent):
    # workbuddy/dsh/zcode/opencode 均为各自原生用户文件（MEMORY.md/AGENTS.md）
    # 的整文件读取者：入口是文件内的受管指针块，与 codex 同一机制；只有 claude
    # 的原生读取机制是 @ 引用行，不得把 @ 泛化到其他执行器。
    return {'claude': 'at_import', 'codex': 'memory_index_block',
            'workbuddy': 'memory_index_block', 'dsh': 'memory_index_block',
            'zcode': 'memory_index_block', 'opencode': 'memory_index_block'}.get(agent)


def _entry_bytes(agent, runtime):
    index = runtime.root / 'memories' / 'MEMORY.md'
    kind = _entry_kind(agent)
    if kind == 'at_import':
        return ('@' + str(index) + '\n').encode()
    if kind == 'memory_index_block':
        return (ENTRY_MARKER['start'] + b'\n\xe5\xbc\x80\xe5\xb7\xa5\xe5\x85\x88\xe8\xaf\xbb\xe5\x85\xac\xe5\x85\xb1\xe8\xae\xb0\xe5\xbf\x86\xef\xbc\x9a'
                + str(index).encode() + b'\xe3\x80\x82\n' + ENTRY_MARKER['end'] + b'\n')
    _fail('invalid_request', '该 Agent 无原生读取入口适配：' + str(agent))


def _entry_ok(agent, data, runtime):
    return _entry_state(agent, data, runtime) == 1


def _unfenced_offsets(data, token):
    result = []
    offset = 0
    fence = None
    for line in data.splitlines(keepends=True):
        mark = re.match(rb'^ {0,3}(`{3,}|~{3,})', line)
        if mark:
            if fence is None: fence = (mark[1][:1], len(mark[1]))
            elif mark[1][:1] == fence[0] and len(mark[1]) >= fence[1] and not line[mark.end():].strip(): fence = None
        elif fence is None and data[offset:offset+len(token)] == token:
            result.append(offset)
        offset += len(line)
    return result


def _canonical_entry(agent, data, runtime):
    if agent == 'claude':
        return False
    from . import user_entries as ue
    if agent == 'workbuddy':
        block = ue._wrap_block(ue.BASE_MARKER, "\n".join([ue.public_read_text(runtime.root/'memories/MEMORY.md'), ue.WORKBUDDY_CONVENTION_TEXT, ue.WORKBUDDY_FALLBACK_TEXT]))
    elif agent in ue.NATIVE_FALLBACK_TEXTS:
        block = ue.native_public_source_block(agent, runtime.root/'memories/MEMORY.md')
    else:
        return False
    offsets = _unfenced_offsets(data, block)
    if len(offsets) > 1:
        _fail('entry_conflict', '重复公共读取块，需先核对所有权')
    return len(offsets) == 1


def clean_native_navigation(agent, data, runtime, *, original=None, migrated=()):
    """Retire only an exact generated duplicate and a proven emptied rules heading."""
    if _canonical_entry(agent, data, runtime):
        block = _entry_bytes(agent, runtime)
        offsets = _unfenced_offsets(data, block)
        if len(offsets) == 1:
            start = offsets[0]
            data = data[:start] + data[start+len(block):]
    if original is None or not migrated:
        return data
    title_line = '# 用户规则'.encode()
    originals = _unfenced_offsets(original, title_line+b'\n') + _unfenced_offsets(original, title_line+b'\r\n')
    if len(originals) != 1:
        return data
    title = '# 用户规则'.encode()
    candidates = [(left, left+len(title)+len(newline))
                  for newline in (b'\n', b'\r\n')
                  for left in _unfenced_offsets(data, title+newline)]
    if len(candidates) != 1 or not any(r.get('scope', [])[:1] == ['用户规则'] for r in migrated):
        return data
    left, right = candidates[0]
    tail = data[right:]
    headings = [m.start() for m in re.finditer(rb'(?m)^# ', tail) if m.start() in _unfenced_offsets(tail, b'# ')]
    end = right + headings[0] if headings else len(data)
    section = data[right:end]
    for start, stop in reversed(_protected_spans(section)):
        section = section[:start] + section[stop:]
    if section.strip():
        return data
    kept = data[right:end].strip(b'\r\n')
    return data[:left] + (kept+b'\n' if kept else b'') + data[end:]


def _entry_state(agent, data, runtime):
    """Count only the exact current entry; malformed managed blocks fail closed."""
    expected = _entry_bytes(agent, runtime)
    if _entry_kind(agent) == 'at_import':
        return sum(line.rstrip(b'\r\n') == expected.rstrip(b'\n')
                   for line in data.splitlines(keepends=True))
    starts = len(_unfenced_offsets(data, ENTRY_MARKER['start']))
    ends = len(_unfenced_offsets(data, ENTRY_MARKER['end']))
    if starts or ends:
        if starts != 1 or ends != 1 or len(_unfenced_offsets(data, expected)) != 1:
            _fail('entry_conflict', '%s 公共入口目标或完整块漂移' % agent)
        return 1
    return 1 if _canonical_entry(agent, data, runtime) else 0


def _read_source(path):
    try:
        snapshot = read_snapshot(path)
    except TransactionError as exc:
        return {'status': 'unknown', 'reason': str(exc), 'snapshot': None}
    if snapshot.kind == 'absent':
        return {'status': 'missing', 'snapshot': snapshot}
    if snapshot.kind != 'file':
        return {'status': 'unknown', 'reason': '非普通文件', 'snapshot': None}
    try:
        snapshot.data.decode('utf-8')
    except UnicodeError:
        return {'status': 'unknown', 'reason': '非 UTF-8，字节保留不修改',
                'snapshot': None}
    if not snapshot.data.strip():
        return {'status': 'empty', 'snapshot': snapshot}
    return {'status': 'ok', 'snapshot': snapshot}


def _protected_spans(data):
    spans = []
    for start_marker, end_marker in CK_MARKERS:
        offset = data.find(start_marker)
        while offset != -1:
            close = data.find(end_marker, offset)
            if close == -1:
                _fail('entry_conflict', 'CK 标记缺少结束符')
            end = data.find(b'\n', close)
            end = len(data) if end == -1 else end + 1
            spans.append((offset, end))
            offset = data.find(start_marker, end)
    for match in AGM_MARKER.finditer(data):
        close = data.find(b'<!-- mem-sharing:' + match.group(1) + b':end -->',
                          match.end())
        if close == -1:
            _fail('entry_conflict', 'mem-sharing 标记缺少结束符')
        end = data.find(b'\n', close)
        end = len(data) if end == -1 else end + 1
        spans.append((match.start(), end))
    offset = 0
    for raw in data.splitlines(keepends=True):
        stripped = raw.strip()
        if (stripped.startswith(b'<!--') and stripped.endswith(b'-->')) \
                or stripped.startswith(b'@'):
            spans.append((offset, offset + len(raw)))
        offset += len(raw)
    spans.sort()
    merged = []
    for start, end in spans:
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))
    return merged


def _segments(data, protected):
    """One segment per list item / fenced block / paragraph, byte-exact."""
    lines = []
    offset = 0
    for raw in data.splitlines(keepends=True):
        lines.append((offset, offset + len(raw), raw))
        offset += len(raw)
    result = []
    fence = None
    fence_start = 0
    paragraph = None

    def close_paragraph():
        nonlocal paragraph
        if paragraph is not None:
            result.append(paragraph)
            paragraph = None

    for left, right, raw in lines:
        body = raw.rstrip(b'\r\n')
        if any(left < end and right > start for start, end in protected):
            close_paragraph()
            continue
        if fence is not None:
            if re.match(rb'^\s*(```+|~~~+)$', body) and body.strip()[:3] == fence:
                result.append((fence_start, right))
                fence = None
            continue
        if not body.strip() or re.match(rb'^\s*#{1,6}\s', body):
            close_paragraph()
            continue
        if re.match(rb'^\s*(```+|~~~+)', body):
            close_paragraph()
            fence = body.strip()[:3]
            fence_start = left
            continue
        if re.match(rb'^\s*(?:[-*+]\s+|\d+[.)]\s+)', body):
            close_paragraph()
            result.append((left, right))
            continue
        if paragraph is None:
            paragraph = [left, right]
        else:
            paragraph[1] = right
    close_paragraph()
    if fence is not None:
        _fail('entry_conflict', '代码围栏未闭合')
    return result


def _heading_context(data, start, protected):
    stack = []; counts = {}; offset = 0
    for raw in data[:start].splitlines(keepends=True):
        left = offset; offset += len(raw)
        if any(left < end and offset > begin for begin, end in protected): continue
        match = re.match(r'^(#{1,6})\s+(.+)$', raw.decode().rstrip('\r\n'))
        if match:
            depth, title = len(match[1]), match[2].strip()
            stack = [h for h in stack if h[0] < depth]
            key = tuple((h[0], h[1], h[2]) for h in stack) + ((depth, title),)
            counts[key] = counts.get(key, 0) + 1
            stack.append((depth, title, counts[key]))
    return [h[1] for h in stack], [list(h) for h in stack]


def _scope_titles(data, start, protected):
    return _heading_context(data, start, protected)[0]


def _identity(text):
    text = re.sub(r'^\s*(?:[-*+]\s+|\d+[.)]\s+)', '', text)
    return re.sub(r'\s+', '', text)


def _check_pending(runtime):
    for path in runtime.backups.glob('*/manifest.json'):
        snap = read_snapshot(path)
        if snap.kind != 'file':
            _fail('path_conflict', '事务清单不可读：' + str(path))
        manifest = json.loads(snap.data)
        if manifest.get('status') in ('prepared', 'applying', 'recovery_required'):
            _fail('recovery_required', '存在未闭合事务，先恢复：' + str(path))


def _collect(request):
    runtime = _runtime(request)
    _check_pending(runtime)
    native = _native_paths(request, runtime)
    sources = {}
    for agent, path in native.items():
        info = _read_source(path)
        info['agent'] = agent
        info['path'] = str(path)
        sources[str(path)] = info
    for info in sources.values():
        if info['snapshot'] is not None:
            _entry_state(info['agent'], info['snapshot'].data or b'', runtime)
    segments = []
    for name, info in sorted(sources.items()):
        snapshot = info['snapshot']
        if info['status'] != 'ok':
            continue
        protected = _protected_spans(snapshot.data)
        for start, end in _segments(snapshot.data, protected):
            raw = snapshot.data[start:end]
            segments.append({'source': name, 'agent': info['agent'],
                             'start': start, 'end': end,
                             'text': raw.decode(), 'sha256': entries.sha256(raw),
                             'scope': _scope_titles(snapshot.data, start, protected), 'context': _heading_context(snapshot.data, start, protected)[1]})
    basis = {name: _meta(info['snapshot'])['sha256'] for name, info in sources.items()
             if info['snapshot'] is not None}
    return runtime, sources, segments, basis


def _validate_proposal(request, proposal):
    runtime, sources, segments, basis = _collect(request)
    if not isinstance(proposal, dict) or proposal.get('schema_version') != 1:
        _fail('invalid_proposal', '提案必须是 schema_version 1 的 JSON 对象')
    if proposal.get('basis') != basis:
        _fail('drift', '提案依据与当前文件不一致，请重新预览')
    groups = proposal.get('groups')
    if not isinstance(groups, list) or not groups:
        _fail('invalid_proposal', '提案必须包含非空 groups')
    by_span = {(s['source'], s['start'], s['end']): s for s in segments}
    agent_to_path = {info['agent']: name for name, info in sources.items()}
    seen = set()
    validated = []
    for raw in groups:
        if not isinstance(raw, dict) or not isinstance(raw.get('summary'), str) \
                or not raw['summary'].strip() or not isinstance(raw.get('same_content'), bool) \
                or not isinstance(raw.get('items'), list) or not raw['items']:
            _fail('invalid_proposal', '每个分组需要 summary、same_content、非空 items')
        items = []
        for element in raw['items']:
            if not isinstance(element, dict) or element.get('agent') not in agent_to_path:
                _fail('invalid_proposal', 'item 引用了未参与的 Agent')
            name = agent_to_path[element['agent']]
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
                by_span[key] = {'source': name, 'agent': element['agent'],
                                'start': start, 'end': end, 'text': text,
                                'sha256': entries.sha256(data[start:end]),
                                'scope': _scope_titles(data, start, protected), 'context': _heading_context(data, start, protected)[1]}
            if any(name == n and key[1] < e and key[2] > a for n, a, e in seen):
                _fail('invalid_proposal', '来源范围重叠')
            if key in seen:
                _fail('invalid_proposal', '同一片段被重复分组：%r' % (key,))
            seen.add(key)
            item = dict(by_span[key])
            items.append(item)
        identity = len({_identity(i['text']) for i in items}) == 1
        same_scope = len({_encoded(i['context']) for i in items}) == 1
        validated.append({'summary': raw['summary'].strip(), 'items': items,
                          'proposed_same': raw['same_content'],
                          'identity_match': identity, 'same_scope': same_scope,
                          'supported_same': raw['same_content'] and identity and same_scope,
                          'coverage': sorted({i['source'] for i in items})})
    return runtime, sources, segments, basis, validated


def _blocks(groups, sources):
    unknown = any(i['status'] == 'unknown' for i in sources.values())
    total = len(sources)
    defaults, optional, singles = [], [], []
    for group in groups:
        coverage = len(group['coverage'])
        if group['supported_same'] and total >= 2 and coverage == total and not unknown:
            defaults.append(group)
        elif coverage >= 2:
            optional.append(group)
        else:
            singles.append(group)
    numbered = defaults + optional + singles
    for number, group in enumerate(numbered, 1):
        group['number'] = number
    return defaults, optional, singles, numbered, unknown


def _parse_selection(selection, numbers):
    if not isinstance(selection, str):
        _fail('invalid_selection', 'selection 必须是文本')
    if selection == '暂不整理':
        return set(), None, True
    view = re.fullmatch(r'\s*查看\s*(\d+)\s*', selection)
    if view:
        if int(view[1]) not in numbers:
            _fail('invalid_selection', '未知编号')
        return set(), int(view[1]), False
    chosen = set()
    if selection.strip() != '按默认方案':
        for clause in re.split(r'[,，;；](?=\s*(?:不共享|共享|不合并|再加入))', selection):
            match = re.fullmatch(r'\s*(不共享|共享|不合并|再加入)?\s*(\d+(?:\s*[、,，]\s*\d+)*)\s*', clause)
            if not match:
                _fail('invalid_selection', '请使用编号、不共享 n、按默认方案、查看 n 或暂不整理')
            picked = {int(v) for v in re.split(r'[、,，]', match[2])}
            if not picked <= numbers:
                _fail('invalid_selection', '未知编号：' + selection)
            if match[1] in ('不共享','不合并'):
                chosen -= picked
            else:
                chosen |= picked
    return chosen, None, False


def _separator(head):
    if not head:
        return b''
    if head.endswith(b'\n\n'):
        return b''
    if head.endswith(b'\n'):
        return b'\n'
    return b'\n\n'


def build_share_plan(request, proposal, selection):
    runtime, sources, segments, basis, groups = _validate_proposal(request, proposal)
    defaults, optional, singles, numbered, unknown = _blocks(groups, sources)
    numbers = {g['number'] for g in numbered}
    chosen, view, declined = _parse_selection(selection, numbers)
    if not view and not declined:
        excluded = set()
        for clause in re.split(r'[,，;；](?=\s*(?:不共享|共享|不合并|再加入))', selection):
            match = re.fullmatch(r'\s*(?:不共享|不合并)\s*(\d+(?:\s*[、,，]\s*\d+)*)\s*', clause)
            if match:
                excluded.update(int(v) for v in re.split(r'[、,，]', match[1]))
        chosen |= {g['number'] for g in defaults} - excluded
    if declined:
        chosen = set()
    memories = runtime.root / 'memories'
    topic, index = memories / TOPIC_NAME, memories / 'MEMORY.md'
    topic_snapshot, index_snapshot = read_snapshot(topic), read_snapshot(index)
    for path, snap in ((topic, topic_snapshot), (index, index_snapshot)):
        if snap.kind not in ('absent', 'file'):
            _fail('path_conflict', '公共目标必须是普通文件或不存在：' + str(path))
    public = topic_snapshot.data or b''
    index_bytes = index_snapshot.data or b''
    migrations = []
    if topic_snapshot.kind == 'absent' and not view and not declined and chosen:
        public = '# 用户记忆\n'.encode()
    if chosen and not view and not declined and unknown:
        _fail('unknown_source', '参与者原文未知，先补证再执行共享')
    entries_created = []
    native_after = {}
    if not view and not declined and chosen:
        for group in numbered:
            if group['number'] not in chosen:
                continue
            members = sorted(group['items'], key=lambda i: (request['agents'].index(i['agent']), i['start']))
            variants = []
            for member in members:
                raw = member['text'].encode()
                if (raw, member['context']) not in [(v[0], v[1]['context']) for v in variants]:
                    variants.append((raw, member))
            for raw, first_member in variants:
                offset = len(public)
                public += _separator(public) + raw
                span = (offset + len(_separator(public[:offset])), len(public))
                for member in members:
                    if member['text'].encode() != raw or member['context'] != first_member['context']:
                        continue
                    migrations.append({
                        'group': group['number'], 'summary': group['summary'],
                        'agent': member['agent'], 'path': member['source'],
                        'start': member['start'], 'end': member['end'],
                        'scope': member['scope'], 'context': member['context'],
                        'text_hex': raw.hex(), 'text_sha256': entries.sha256(raw),
                        'public_offset': span[0], 'public_end': span[1]})
        link = ('- 用户记忆：[%s](%s)\n' % (TOPIC_NAME, TOPIC_NAME)).encode()
        if link not in index_bytes:
            index_bytes = (index_bytes or '# 公共记忆\n\n'.encode())
            index_bytes += (b'' if index_bytes.endswith(b'\n') else b'\n') + link
    outputs = {}
    if public != (topic_snapshot.data or b''):
        outputs[str(topic)] = public
    if index_bytes != (index_snapshot.data or b''):
        outputs[str(index)] = index_bytes
    deletions = {}
    for record in migrations:
        deletions.setdefault(record['path'], []).append(record)
    for name, records in deletions.items():
        raw = sources[name]['snapshot'].data
        for record in sorted(records, key=lambda r: r['start'], reverse=True):
            if raw[record['start']:record['end']] != bytes.fromhex(record['text_hex']):
                _fail('drift', '来源片段与读取时不一致：' + name)
            raw = raw[:record['start']] + raw[record['end']:]
        native_after[name] = clean_native_navigation(sources[name]["agent"], raw, runtime,
            original=sources[name]["snapshot"].data, migrated=records)
    for name, info in sources.items():
        if name in native_after or info['status'] == 'unknown':
            continue
        original = info['snapshot'].data or b''
        cleaned = clean_native_navigation(info['agent'], original, runtime)
        if migrations and cleaned != original:
            native_after[name] = cleaned
        if _entry_state(info['agent'], original, runtime) == 0 and migrations:
            native_after[name] = info['snapshot'].data or b''  # entry creation only
    for name in native_after:
        info = sources[name]
        data = clean_native_navigation(info["agent"], native_after[name], runtime)
        native_after[name] = data
        if _entry_state(info['agent'], data, runtime) == 0:
            block = _entry_bytes(info['agent'], runtime)
            data += (_separator(data) or b'\n') + block
            entries_created.append({'path': name, 'agent': info['agent'],
                                    'kind': _entry_kind(info['agent']),
                                    'bytes_hex': block.hex()})
            native_after[name] = data
    topic_after = public
    for record in migrations:
        record['topic_after_sha256'] = entries.sha256(topic_after)
    changes = []
    for name in [str(topic), str(index)] + sorted(native_after):
        after = native_after.get(name, outputs.get(name))
        if after is None:
            continue
        before = sources[name]['snapshot'] if name in sources else \
            (topic_snapshot if name == str(topic) else index_snapshot)
        if after == (before.data or b''):
            continue
        changes.append({'path': name, 'before': _meta(before),
                        'after_sha256': entries.sha256(after),
                        'after_hex': after.hex()})
    operation_metadata = None
    if migrations:
        operation_metadata = {'share_user_memory': {
            'topic': str(topic), 'topic_after_sha256': entries.sha256(topic_after),
            'migrations': migrations, 'entries_created': entries_created,
            'source_after': {name: entries.sha256(raw)
                             for name, raw in native_after.items()},
            'request_agents': list(request.get('agents', []))}}
    observations = {name: _meta(info['snapshot']) for name, info in sources.items()
                    if info['snapshot'] is not None}
    observations[str(topic)] = _meta(topic_snapshot)
    observations[str(index)] = _meta(index_snapshot)
    entry_stage = []
    for name, info in sources.items():
        if name not in native_after:
            continue
        before = info['snapshot']
        data = before.data or b''
        if not _entry_ok(info['agent'], data, runtime):
            data += (_separator(data) or b'\n') + _entry_bytes(info['agent'], runtime)
        entry_stage.append({'path': name, 'after_hex': data.hex()})
    plan = {'schema_version': 1, 'command': COMMAND, 'home': str(runtime.home),
            'request': {k: request[k] for k in ('home', 'platform_config', 'agents')
                        if k in request},
            'proposal': proposal, 'groups': numbered,
            'default_numbers': [g['number'] for g in defaults],
            'optional_numbers': [g['number'] for g in optional],
            'single_numbers': [g['number'] for g in singles],
            'selected_numbers': sorted(chosen), 'view': view, 'declined': declined,
            'unknown_sources': [{'path': n, 'reason': i.get('reason')}
                                for n, i in sources.items() if i['status'] == 'unknown'],
            'entry_states': {n: _entry_state(i['agent'], i['snapshot'].data or b'', runtime)
                             for n, i in sources.items() if i['snapshot'] is not None},
            'observations': observations, 'changes': changes,
            'operation_metadata': operation_metadata, 'entry_stage': entry_stage}
    plan['plan_sha256'] = entries.sha256(_encoded(plan))
    return plan


def present(plan):
    from .user_rules_organize import present as render
    projected = dict(plan, request=dict(plan['request']), groups=[])
    for group in plan['groups']:
        sources=[dict(source=i['source'], agents=[i['agent']], text=i['text']) for i in group['items']]
        projected['groups'].append(dict(group,sources=sources))
    return render(projected, summaries={g['number']:g['summary'] for g in plan['groups']})


def final_list(plan):
    meta = plan.get('operation_metadata') or {}
    share = meta.get('share_user_memory') or {}
    lines = ['参与范围：' + ','.join(plan['request'].get('agents', [])),
             '选定编号：' + str(plan['selected_numbers'])]
    for record in share.get('migrations', []):
        lines += ['', '编号 %s：%s' % (record['group'], record['summary']),
                  '来源 %s（%s）字节 %d-%d：' % (record['path'], record['agent'],
                                               record['start'], record['end']),
                  bytes.fromhex(record['text_hex']).decode().rstrip('\n'),
                  '公共对应段 %d-%d' % (record['public_offset'], record['public_end'])]
    for created in share.get('entries_created', []):
        lines.append('新增读取入口：%s（%s）' % (created['path'], created['kind']))
    lines += ['恢复安排：事务清单随备份持久；中断用 %s --manifest 只读核验后按批准回滚。'
              % RECOVER_COMMAND]
    return '\n'.join(lines)


def _result(**fields):
    result = {'command': COMMAND, 'status': 'failed', 'approval_required': False,
              'next_action': None, 'errors': [], 'changes': []}
    result.update(fields)
    return result


def plan_share(request):
    try:
        if request.get('proposal') is None:
            runtime, sources, segments, basis = _collect(request)
            return _result(status='completed', participants={
                name: {'agent': info['agent'], 'status': info['status'],
                       'reason': info.get('reason'),
                       'text': (info['snapshot'].data or b'').decode('utf-8')
                       if info['status'] in ('ok', 'empty', 'missing') else None} for name, info in sources.items()},
                segments=segments, basis=basis,
                next_action='当前 Agent 阅读完整原文后撰写提案，再带 --proposal-file 预览')
        plan = build_share_plan(request, request['proposal'],
                                request.get('selection', '按默认方案'))
        if plan['view']:
            group = next(g for g in plan['groups'] if g['number'] == plan['view'])
            return _result(status='viewed', approval_plan=plan,
                           view={'number': group['number'], 'summary': group['summary'],
                                 'sources': [{'agent': i['agent'], 'path': i['source'],
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
        runtime = _runtime(request)
        _, sources = _collect(request)[:2]
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
            memories = runtime.root / 'memories'
            public_paths = [str(memories / TOPIC_NAME), str(memories / 'MEMORY.md')]
            source_paths = {c['path'] for c in plan['changes']} - set(public_paths)
            transaction = Transaction(lock_path=runtime.transaction_lock,
                                      backup_root=runtime.backups,
                                      allowed_roots=[runtime.home],
                                      operation=COMMAND, hook=hook,
                                      operation_metadata=dict(plan.get('operation_metadata') or {}, approval=dict(evidence, plan_sha256=plan['plan_sha256'])))
            tx_changes = []
            staged = dict(state)
            for c in plan['changes']:
                if c['path'] in public_paths:
                    tx_changes.append(Change.file(Path(c['path']), bytes.fromhex(c['after_hex']),
                                                  expected=state[c['path']]))
            for c in plan['entry_stage']:
                change = Change.file(Path(c['path']), bytes.fromhex(c['after_hex']),
                                     expected=staged[c['path']])
                tx_changes.append(change)
                staged[c['path']] = change.after
            for c in plan['changes']:
                if c['path'] in source_paths:
                    tx_changes.append(Change.file(Path(c['path']), bytes.fromhex(c['after_hex']),
                                                  expected=staged[c['path']]))

            def guarded(event, path):
                if hook:
                    hook(event, path)
                if event == 'before_write' and str(path) in source_paths:
                    for public in public_paths:
                        snap = read_snapshot(Path(public))
                        change = next((c for c in plan['changes']
                                       if c['path'] == public), None)
                        if change and (snap.kind != 'file'
                                       or snap.data != bytes.fromhex(change['after_hex'])):
                            _fail('drift', '公共记忆未完整保存，保留原文：' + public)
                        if not change and _meta(snap) != plan['observations'][public]:
                            _fail('drift', '公共记忆发生变化：' + public)
                    if read_snapshot(path) == staged[str(path)]:
                        for name, info in sources.items():
                            snap = read_snapshot(Path(name))
                            if not _entry_ok(info['agent'], snap.data or b'', runtime):
                                _fail('entry_conflict', '删源前读取入口未就绪：' + name)
                if event == 'after_write' and str(path) in source_paths:
                    change = next(c for c in plan['changes'] if c['path'] == str(path))
                    data = bytes.fromhex(change['after_hex'])
                    agent = next(i['agent'] for n, i in sources.items() if n == str(path))
                    if _entry_state(agent, data, runtime) != 1:
                        _fail('drift', '读取入口未按计划落盘：' + str(path))

            transaction.hook = guarded
            result = transaction.run(tx_changes, phased_writes=True)
        return _result(status='completed', changes=plan['changes'],
                       manifest=result['manifest'],
                       operation_metadata=plan['operation_metadata'])
    except (ValueError, OSError, KeyError, TypeError) as exc:
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


# ---- return (归还)：Agent 给出当前字节计划，工具精确执行 --------------------


def _manifests(runtime):
    found = []
    for manifest in sorted((runtime.backups).glob('*/manifest.json')):
        snap = read_snapshot(manifest)
        if snap.kind != 'file':
            _fail('path_conflict', '事务清单异常：' + str(manifest))
        data = json.loads(snap.data)
        if data.get('operation') not in (COMMAND, RETURN_COMMAND, 'organize-user-rules'):
            continue
        found.append((manifest.parent.name, manifest, data))
    return found


def _consumed_index(runtime):
    """References already consumed by earlier return manifests (history only)."""
    consumed = set()
    for _, _, data in _manifests(runtime):
        if data.get('status') != 'committed':
            continue
        meta = (data.get('operation_metadata') or {}).get('return_user_memory') or {}
        for ref in meta.get('consumed', []):
            consumed.add((ref['manifest'], ref['migration']))
    return consumed


def _available_migrations(runtime):
    available = {}
    for name, manifest, data in _manifests(runtime):
        share = (data.get('operation_metadata') or {}).get('share_user_memory')
        if not share or data.get('status') != 'committed':
            continue
        for position, record in enumerate(share['migrations']):
            available[(name, position)] = dict(record, topic=share['topic'], manifest=name,
                                               manifest_path=str(manifest),
                                               position=position)
    return available


def build_return_plan(request, agent_plan):
    runtime = _runtime(request)
    _check_pending(runtime)
    if not isinstance(agent_plan, dict) or agent_plan.get('schema_version') != 1:
        _fail('invalid_return', '归还提案必须是 schema_version 1 的 JSON 对象')
    available = _available_migrations(runtime)
    consumed = _consumed_index(runtime)
    if not available:
        _fail('invalid_request', '没有可归还的共享记录')
    topic = runtime.root / 'memories' / TOPIC_NAME
    topic_snapshot = read_snapshot(topic)
    if topic_snapshot.kind != 'file':
        _fail('path_conflict', '公共主题文件缺失或被替换')
    native = _native_paths(request, runtime)
    basis = dict(agent_plan.get('basis') or {})
    if basis.get(str(topic)) != topic_snapshot.fingerprint:
        _fail('drift', '归还提案的公共基线与当前不一致')
    states = {str(topic): topic_snapshot}
    for path in native.values():
        snap = read_snapshot(path)
        if snap.kind not in ('absent', 'file'):
            _fail('path_conflict', '归还目标异常：' + str(path))
        states[str(path)] = snap
        if str(path) in basis and _meta(snap)['sha256'] != basis[str(path)]:
            _fail('drift', '归还提案的来源基线与当前不一致：' + str(path))
    items = agent_plan.get('items')
    if not isinstance(items, list):
        _fail('invalid_return', 'items 必须是列表')
    used_refs = set()
    planned_returns = []
    keep_public = []
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
                or not (0 <= start < end <= len(topic_snapshot.data)):
            _fail('invalid_return', '公共范围非法')
        current = topic_snapshot.data[start:end]
        if current.hex() != (span.get('text_hex') or ''):
            _fail('drift', '公共范围字节与提案不一致（请按当前正文重新提案）')
        if raw.get('action') == 'keep_public':
            keep_public.append((ref, record, start, end))
            continue
        target = raw.get('target') or {}
        path = target.get('path')
        if path not in {str(p) for p in native.values()}:
            _fail('invalid_return', '归还目标必须是本次参与的原生文件')
        snap = states[path]
        base = snap.data or b''
        mode = target.get('mode')
        if mode == 'in_place':
            after_sha = _after_sha(runtime, record)
            if snap.kind != 'file' or snap.fingerprint != after_sha:
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
                or not (0 <= start < end <= len(topic_snapshot.data)):
            _fail('invalid_return', '公共新增范围非法')
        if any(start < b and end > a for a, b in covered):
            _fail('invalid_return', '公共新增范围与迁移片段重叠')
        covered.append((start, end))
        text = topic_snapshot.data[start:end]
        if text.hex() != (raw.get('text_hex') or ''):
            _fail('drift', '公共新增字节与提案不一致')
        if raw.get('action') == 'keep_public':
            continue
        target = raw.get('target') or {}
        path = target.get('path')
        if path not in {str(p) for p in native.values()}:
            _fail('invalid_return', '新增迁移目标必须是本次参与的原生文件')
        insert_at = target.get('insert_at')
        base = states[path].data or b''
        if not isinstance(insert_at, int) or not (0 <= insert_at <= len(base)):
            _fail('invalid_return', '新增迁移插入位置非法')
        addition_moves.append({'path': path, 'insert_at': insert_at, 'text': text,
                               'public_start': start, 'public_end': end})
    outputs = {}
    inserts = {}
    for item in sorted(planned_returns + addition_moves,
                       key=lambda item: (item['insert_at'], item.get('record', {}).get('start', 0)), reverse=True):
        base = inserts.get(item['path'], states[item['path']].data or b'')
        at = item['insert_at']
        if at > len(base):
            _fail('invalid_return', '插入位置越界（多目标插入请按从后到前提案）')
        inserts[item['path']] = base[:at] + item['text'] + base[at:]
    for path, data in inserts.items():
        outputs[path] = data
    new_public = topic_snapshot.data
    removals = planned_returns + addition_moves
    # A shared public copy remains readable while any alias is outstanding.
    def relation_key(record):
        return (record['manifest'], record['public_offset'], record['public_end'])
    moving_refs = {r['ref'] for r in planned_returns}
    outstanding = {relation_key(record) for ref, record in available.items()
                   if ref not in consumed and ref not in moving_refs}
    retained_spans = {(start, end) for _, _, start, end in keep_public}
    retained_spans.update((r['public_start'], r['public_end']) for r in planned_returns
                          if relation_key(r['record']) in outstanding)
    removal_spans = sorted({(r['public_start'], r['public_end']) for r in removals}
                           - retained_spans)
    for (a, b), (c, d) in zip(removal_spans, removal_spans[1:]):
        if c < b:
            _fail('invalid_return', '公共归还范围部分重叠')
    if any(a < e and b > s for a, b in removal_spans for s, e in retained_spans):
        _fail('invalid_return', '同一公共范围不能同时归还与保留')
    for start, end in reversed(removal_spans):
        new_public = new_public[:start] + new_public[end:]
    outputs[str(topic)] = new_public
    remove_entries = agent_plan.get('remove_entries') is True
    entry_removals = []
    if remove_entries:
        remaining = [ref for ref in available if ref not in consumed
                     and ref not in used_refs]
        if keep_public:
            _fail('invalid_return', '仍保留公共迁移内容，不能移除读取入口')
        if remaining:
            _fail('invalid_return', '仍有未处置迁移，不能移除全部读取入口')
        # Only the exact tool-created preamble and separators are inert.
        inert = '# 用户记忆\n'.encode()
        remainder = new_public[len(inert):] if new_public.startswith(inert) else new_public
        if remainder.strip():
            _fail('invalid_return', '公共仍有未归还正文或新增内容，不能移除读取入口')
        for path, snap in states.items():
            if path == str(topic) or snap.kind != 'file':
                continue
            agent = next(a for a, p in native.items() if str(p) == path)
            if _entry_state(agent, snap.data, runtime) == 1:
                after = _strip_entry(agent, inserts.get(path, snap.data), runtime)
                entry_removals.append({'path': path, 'agent': agent,
                                       'after_hex': after.hex()})
                outputs[path] = after
    changes = []
    observations = {name: _meta(snap) for name, snap in states.items()}
    touched = set(outputs) | {e['path'] for e in entry_removals} | {str(topic)}
    for name in sorted(touched - {str(topic)}) + [str(topic)]:
        snap = states[name]
        if name in outputs:
            after = outputs[name]
        elif name in {e['path'] for e in entry_removals}:
            after = bytes.fromhex(
                next(e['after_hex'] for e in entry_removals if e['path'] == name))
        else:
            continue
        if snap.kind == 'file' and after == snap.data:
            continue
        changes.append({'path': name, 'before': _meta(snap),
                        'after_sha256': entries.sha256(after),
                        'after_hex': after.hex()})
    consumed_records = [{'manifest': ref[0], 'migration': ref[1]}
                        for ref in sorted(r['ref'] for r in planned_returns)]
    operation_metadata = {'return_user_memory': {
        'consumed': consumed_records,
        'kept_public': [{'manifest': ref[0], 'migration': ref[1]}
                        for ref, _, _, _ in keep_public],
        'additions_moved': [{'path': m['path'],
                             'text_sha256': entries.sha256(m['text'])}
                            for m in addition_moves]}}
    # Installed compatibility: atomically rebind only Claude's reused import observation.
    if runtime.registry.is_file():
        from . import registry
        from .user_rules_organize import validate_reference_rebinding
        before_v = read_snapshot(runtime.registry)
        allowed = paths.allowed_user_paths(request['platform_config'], None, home=str(runtime.home))
        ledger = registry.load_registry(runtime.registry, allowed_user_paths=allowed)
        claude = str(native.get('claude', ''))
        if claude in outputs and claude in states and not remove_entries:
            updated = copy.deepcopy(ledger)
            touched = []
            for oid,obj in updated['machine']['objects'].items():
                if obj['path']==claude and obj['kind']=='import':
                    obj['fingerprint']['value']=entries.sha256(outputs[claude]);touched.append(oid)
            if touched:
                after_v = registry.serialize_registry(updated, allowed_user_paths=allowed)
                validate_reference_rebinding(before_v.data, after_v, states[claude],
                    Snapshot('file',outputs[claude],states[claude].mode), str(runtime.home))
                observations[str(runtime.registry)] = _meta(before_v)
                changes.append({'path':str(runtime.registry),'before':_meta(before_v),
                    'after_sha256':entries.sha256(after_v),'after_hex':after_v.hex()})
    plan = {'schema_version': 1, 'command': RETURN_COMMAND, 'home': str(runtime.home),
            'request': {k: request[k] for k in ('home', 'platform_config', 'agents')
                        if k in request},
            'items': [{'ref': list(r['ref']), 'summary': r['record']['summary'],
                       'target': r['path'], 'insert_at': r['insert_at'],
                       'text_hex': r['text'].hex()} for r in planned_returns],
            'kept_public': [list(ref) for ref, _, _, _ in keep_public],
            'additions_moved': operation_metadata['return_user_memory']['additions_moved'],
            'remove_entries': remove_entries,
            'observations': observations, 'changes': changes,
            'operation_metadata': operation_metadata}
    plan['plan_sha256'] = entries.sha256(_encoded(plan))
    return plan


def _strip_entry(agent, data, runtime):
    if _entry_state(agent, data, runtime) != 1:
        return data
    expected = _entry_bytes(agent, runtime)
    if _entry_kind(agent) == 'at_import':
        return b''.join(line for line in data.splitlines(keepends=True)
                        if line.rstrip(b'\r\n') != expected.rstrip(b'\n'))
    return data.replace(expected, b'', 1)


def _after_sha(runtime, record):
    for name, manifest, data in _manifests(runtime):
        if name != record['manifest']:
            continue
        share = (data.get('operation_metadata') or {}).get('share_user_memory') or {}
        return share.get('source_after', {}).get(record['path'])
    return None


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
        request = dict(request, agents=list(plan['request'].get('agents', [])))
        request.pop('approval', None)
        runtime = _runtime(request)
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
                                      operation=RETURN_COMMAND, hook=request.get('hook'),
                                      operation_metadata=plan['operation_metadata'])
            metadata = next((c for c in tx_changes if c.path==runtime.registry),None)
            result = transaction.run([c for c in tx_changes if c is not metadata], registry_change=metadata)
        return {'command': RETURN_COMMAND, 'status': 'completed',
                'changes': plan['changes'], 'manifest': result['manifest']}
    except (ValueError, OSError, KeyError, TypeError) as exc:
        return {'command': RETURN_COMMAND,
                'status': 'recovery_required'
                if getattr(exc, 'code', None) == 'recovery_required' else 'failed',
                'errors': [{'code': getattr(exc, 'code', 'return_failed'),
                            'message': str(exc),
                            'manifest': getattr(exc, 'manifest', None)}]}


def _verify_return_registry(runtime, manifest, data):
    if data.get('registry_path') is None:
        return
    if data.get('operation') != RETURN_COMMAND or data['registry_path'] != str(runtime.registry):
        _fail('invalid_request', '未知 registry 恢复范围')
    from . import registry
    config = paths.select_platform(paths.load_agents_table(), os.sys.platform)
    allowed = paths.allowed_user_paths(config, None, home=str(runtime.home))
    native = paths.expand_path(config['claude']['user_entry'],home=str(runtime.home))
    rows=data['entries'];vrows=[r for r in rows if r['path']==str(runtime.registry)]
    sources=[r for r in rows if r['path']==native]
    if len(vrows)!=1 or rows[-1] is not vrows[0] or len(sources)!=1:
        _fail('invalid_request','registry 恢复须绑定最终 Claude 引用观察')
    vr,sr=vrows[0],sources[0]
    name=vr['before'].get('backup')
    if not isinstance(name,str) or Path(name).name!=name:
        _fail('invalid_request','registry 备份路径无效')
    raw=read_snapshot(manifest.parent/name)
    if raw.kind!='file' or raw.fingerprint!=vr['before']['fingerprint']:
        _fail('drift','registry 备份漂移')
    old=registry.validate_registry(json.loads(raw.data),allowed_user_paths=allowed)
    expected=copy.deepcopy(old);matched=[]
    for oid,obj in expected['machine']['objects'].items():
        if obj['path']==native and obj['kind']=='import' and obj['ownership']=='reused' and obj['agents']==['claude'] and obj.get('marker') is None:
            if obj['fingerprint']['value']!=sr['before']['fingerprint']:
                _fail('drift','Claude 引用原观察不匹配')
            obj['fingerprint']['value']=sr['after']['fingerprint'];matched.append(oid)
    if len(matched)!=1 or entries.sha256(registry.serialize_registry(expected,allowed_user_paths=allowed))!=vr['after']['fingerprint']:
        _fail('invalid_request','registry 恢复超出窄重绑范围')


def run_recover(request):
    try:
        runtime = _runtime(request)
        manifest = Path(request['manifest'])
        if not manifest.is_absolute() or manifest.parent.parent != runtime.backups \
                or manifest.name != 'manifest.json':
            raise ShareError('invalid_request', '仅接受本 HOME backups 下的事务清单')
        data = json.loads(read_snapshot(manifest).data)
        if data.get('operation') not in (COMMAND, RETURN_COMMAND):
            raise ShareError('invalid_request', '不是共享/归还的事务清单')
        roots = [runtime.home, runtime.root]
        inspected = inspect_recovery(manifest, allowed_roots=roots)
        _verify_return_registry(runtime,manifest,data)
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
    parser = argparse.ArgumentParser(prog='记忆共享', allow_abbrev=False)
    parser.add_argument('command',
                        choices=[COMMAND, RETURN_COMMAND, RECOVER_COMMAND])
    parser.add_argument('--agent', action='append', dest='agents')
    parser.add_argument('--proposal-file')
    parser.add_argument('--return-plan-file')
    parser.add_argument('--selection', default=None)
    parser.add_argument('--decline', action='store_true')
    parser.add_argument('--approval-file')
    parser.add_argument('--selection-plan-file', help='此前展示的完整 approval_plan')
    parser.add_argument('--selection-reference', help='实际用户选择消息；选择即执行')
    parser.add_argument('--manifest')
    parser.add_argument('--home')
    ns = parser.parse_args(argv)
    try:
        config = paths.select_platform(paths.load_agents_table(),
                                       'darwin' if sys.platform == 'darwin' else sys.platform)
        target_home = str(Path(home or ns.home or Path.home()).resolve())
        request = {'home': target_home, 'platform_config': config}
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
            if ns.selection is not None or ns.decline or ns.agents or ns.proposal_file:
                raise ShareError('approval_mismatch', '执行批准时不得改变选择或提案')
            request['approval'] = approval
        else:
            if ns.agents:
                request['agents'] = ns.agents
            if ns.proposal_file:
                request['proposal'] = json.loads(Path(ns.proposal_file).read_text())
            if ns.return_plan_file:
                request['return_plan'] = json.loads(
                    Path(ns.return_plan_file).read_text())
            if ns.manifest:
                request['manifest'] = ns.manifest
            request['selection'] = '暂不整理' if ns.decline else \
                ns.selection or '按默认方案'
        if ns.command == COMMAND:
            result = run_share(request)
            if ns.selection_reference:
                if ns.approval_file or ns.selection is None or not ns.selection_reference.strip():
                    _fail('approval_mismatch', '选择执行须绑定本次真实选择消息')
                if not ns.selection_plan_file:
                    _fail('approval_mismatch', '选择执行须提供已展示计划')
                if result.get('approval_required') and not result['approval_plan'].get('view'):
                    plan = result['approval_plan']
                    shown = json.loads(Path(ns.selection_plan_file).read_text())
                    if any(shown.get(k) != plan.get(k) for k in ('proposal','observations','groups','agents','layout')):
                        _fail('drift', '原文或编号内容相对已展示计划变化')
                    evidence = {'confirmed_at': datetime.now(timezone.utc).isoformat().replace('+00:00','Z'),
                                'reference': ns.selection_reference}
                    result = execute_share(plan, dict(plan, **evidence), request=request)
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
