"""Optional, explicit user-rule organization; classifications are suggestions.

No imports trigger IO. Public memories are content, not V-managed objects.
One transaction edits content; only a verified reused Claude import's
observational whole-file fingerprint may be rebound, without ownership changes.
The cooperative machine lock serializes AGM writers, not arbitrary editors.
"""
from __future__ import annotations

import copy
import json
import re
from datetime import datetime, timezone
from pathlib import Path

from . import entries, layout, paths, registry, detect, project, user_entries
from .transaction import Change, Snapshot, Transaction, TransactionError, read_snapshot, write_lock

COMMAND = 'organize-user-rules'
_SPECIFIC = re.compile(r'codex|claude|workbuddy|cursor|paseo|openai|anthropic|dsh|zcode|opencode|deepseek|DeepSeek Harness|ZCode|OpenCode|mcp|skills?|执行器专属|专属|agent专用|\.codex|\.claude|\.workbuddy|\.dsh|\.zcode|\.opencode|~/.dsh|~/.zcode|~/.config/opencode|[~/$][\w./-]+|`[^`]+`|\b(?:npm|npx|uvx|python\d*|git|bash|zsh)\s+[-\w]', re.I)
_MARKER = re.compile(rb'<!-- mem-sharing:([a-zA-Z0-9_-]+):start -->')


class OrganizeError(ValueError):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


def _fail(code, message):
    raise OrganizeError(code, message)


def _encoded(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'))+'\n').encode()


def _meta(snap):
    return {'kind': snap.kind, 'sha256': snap.fingerprint, 'mode': snap.mode}


def _file(path, *, optional=False):
    snap = read_snapshot(path)
    if snap.kind == 'absent' and optional:
        return snap
    if snap.kind != 'file':
        _fail('path_conflict', 'Expected a regular file: '+str(path))
    try:
        snap.data.decode('utf-8')
    except UnicodeError:
        _fail('encoding_conflict', 'Rules must be valid UTF-8; bytes preserved without edits: '+str(path))
    return snap


def _objects(data):
    return list(data['shared_objects'].values())+list(data['machine']['objects'].values())


def _protected(data, path, runtime, objects):
    spans = []
    markers = {(match.group(0), b'<!-- mem-sharing:'+match.group(1)+b':end -->')
               for match in _MARKER.finditer(data)}
    # External CK blocks remain opaque, regardless of executor or registration.
    # The same strict parser rejects missing, duplicate and reversed markers;
    # the overlap check below also covers CK/CK and CK/AGM crossings.
    markers.update((b'<!-- context-keeper'+suffix+b':start -->',
                    b'<!-- context-keeper'+suffix+b':end -->')
                   for suffix in (b'', b':workbuddy'))
    # End-only/unknown damaged AGM markup must not become ordinary rule text.
    ends = re.findall(rb'<!-- mem-sharing:([a-zA-Z0-9_-]+):end -->', data)
    if set(ends) != {match.group(1) for match in _MARKER.finditer(data)}:
        _fail('entry_conflict', 'Incomplete AGM markers: '+str(path))
    for obj in objects:
        if obj['path'] == str(path) and obj.get('marker'):
            markers.add((obj['marker']['start'].encode(), obj['marker']['end'].encode()))
    for start, end in markers:
        span = entries.managed_span(data, start, end)
        if span:
            spans.append(span)
    offset = 0
    for line in data.splitlines(keepends=True):
        if line.strip() in (('@'+str(runtime.root/'memories/MEMORY.md')).encode(), b'@AGENTS.md'):
            spans.append((offset, offset+len(line)))
        offset += len(line)
    for a, b in spans:
        for c, d in spans:
            if (a, b) != (c, d) and a < c < b < d:
                _fail('entry_conflict', 'Crossed managed blocks')
    return sorted(spans)


def _segments(data, protected=()):
    """Paragraph/list-item ranges, retaining original byte offsets and newlines."""
    lines=[];offset=0
    for raw in data.splitlines(keepends=True):
        lines.append((offset,offset+len(raw),raw));offset+=len(raw)
    result=[];active=None;kind=None;fence=None;list_indent=0
    def close():
        nonlocal active, kind
        if active is not None:
            result.append(tuple(active));active=None;kind=None
    for left,right,raw in lines:
        body=raw.rstrip(b'\r\n'); stripped=body.strip()
        if any(left < end and right > start for start,end in protected):
            close();continue
        is_fence=re.match(rb'^\s*(```+|~~~+)', body)
        if fence is not None:
            active[1]=right
            if is_fence and is_fence.group(1)[:3] == fence:
                fence=None;close()
            continue
        if not stripped or re.match(rb'^\s*#{1,6}\s', body):
            close();continue
        if is_fence:
            close();active=[left,right];kind='code';fence=is_fence.group(1)[:3];continue
        bullet=re.match(rb'^\s*(?:[-*+]\s+|\d+[.)]\s+)', body)
        if bullet:
            indent=len(body)-len(body.lstrip())
            if active is not None and kind=='list' and indent>list_indent:
                active[1]=right
            else:
                close();active=[left,right];kind='list';list_indent=indent
        elif active is None:
            active=[left,right];kind='paragraph'
        else:
            active[1]=right
    close()
    return result


def _context(request, *, allow_active=False):
    runtime=layout.from_request(request)
    # HOME's own ancestry may be an environment alias (/var -> /private/var on
    # macOS). Anchor actual transaction paths canonically, after the shared
    # resolver has rejected links inside the managed chain below HOME.
    runtime=layout.resolve_layout(runtime.home.resolve())
    runtime.validate_paths()
    if not allow_active and runtime.backups.exists():
        for manifest in runtime.backups.glob('*/manifest.json'):
            snap = _file(manifest)
            saved = json.loads(snap.data,object_pairs_hook=registry._no_duplicates)
            if saved.get('operation') == COMMAND and saved.get('status') in ('prepared','applying','recovery_required'):
                _fail('recovery_required','请先恢复未完成的记忆融合：'+str(manifest))
    config=request['platform_config']
    allowed=paths.allowed_user_paths(config,None,home=str(runtime.home))
    snapshot=_file(runtime.registry)
    data=registry.require_installed(registry.load_registry(runtime.registry,allowed_user_paths=allowed))
    memories=runtime.root/'memories'
    if memories.is_symlink() or not memories.is_dir():
        _fail('path_conflict','Public memories must already be a real directory')
    topic_name=request.get('topic','user-rules.md')
    if not isinstance(topic_name,str) or not re.fullmatch(r'[\w-]+\.md',topic_name) or topic_name=='MEMORY.md':
        _fail('invalid_request','topic must be a simple Markdown filename other than MEMORY.md')
    return runtime, data, snapshot, memories, memories/topic_name


def _scope(data, start, protected=()):
    from .memory_share import _heading_context
    return _heading_context(data, start, protected)[0]


def _identity(text):
    # Formatting only: never erase punctuation, case or scope to guess semantics.
    text = re.sub(r"^\s*(?:[-*+]\s+|\d+[.)]\s+)", "", text)
    return re.sub(r"\s+", "", text)


def _participants(request, runtime, ledger):
    requested = paths.resolve_agents(request.get('agents'), default=paths.AGENT_ORDER)
    facts = detect.detect_agents(request['platform_config'], requested, home=str(runtime.home),
        search_paths=request.get('search_paths'), app_directories=request.get('app_directories'),
        user_candidates=request.get('user_candidates'), runner=request.get('detect_runner'))
    selected = [a for a in requested if facts['agents'][a]['status'] == 'installed'
        and ledger['machine']['agents'].get(a, {}).get('installation', {}).get('status') == 'installed']
    return selected, {a: detect.detection_fingerprint(facts['agents'][a]) for a in requested}


def _ck_writeback_matches(runtime, name, snapshot, fingerprint):
    """Accept only reinserted audited CK bytes over an outstanding exact shell."""
    from . import memory_share as ms
    if snapshot.kind != 'file': return False
    body = ms.ck.candidate(snapshot.data, 'claude')
    if body is None: return False
    shell = snapshot.data[:body['start']] + snapshot.data[body['end']:]
    if entries.sha256(shell) != fingerprint: return False
    consumed = ms._consumed_index(runtime)
    return any(ref not in consumed and r.get('kind') == ms.ck.KIND and r['path'] == name
               and ms._after_sha(runtime, r) == fingerprint
               for ref, r in ms._available_migrations(runtime).items())


def _modern_claude_reference(obj, name, request, runtime, ledger):
    """A reused machine @index reference is not ownership of its whole body."""
    if (request.get('scope','user') != 'user' or obj.get('kind') != 'import'
        or obj.get('scope') != 'machine' or obj.get('ownership') != 'reused'
        or obj.get('marker') is not None or obj.get('agents') != ['claude']
        or obj.get('original_existed') is not True or obj.get('backup_manifest') is not None
        or obj.get('consumers') != []): return False
    expected = paths.expand_path(request['platform_config']['claude']['user_entry'],home=str(runtime.home))
    if name != expected: return False
    snapshot = read_snapshot(name)
    if (obj.get('fingerprint') or {}).get('value') != snapshot.fingerprint:
        from .memory_share import _entry_ok
        return (_ck_writeback_matches(runtime, name, snapshot, obj['fingerprint']['value'])
                and _entry_ok('claude', snapshot.data, runtime))
    state = user_entries.connection_status(runtime,request['platform_config'],ledger,['claude'])
    return state.get('claude',{}).get('status') == 'connected'


def validate_reference_rebinding(old_raw, new_raw, source_before, source_after, home):
    """Only the current reused Claude import observation may change in V."""
    config = paths.select_platform(paths.load_agents_table(),'darwin')
    runtime = layout.resolve_layout(Path(home))
    allowed = paths.allowed_user_paths(config,None,home=home)
    old = registry.validate_registry(json.loads(old_raw,object_pairs_hook=registry._no_duplicates),allowed_user_paths=allowed)
    new = registry.validate_registry(json.loads(new_raw,object_pairs_hook=registry._no_duplicates),allowed_user_paths=allowed)
    expected = copy.deepcopy(old)
    native = paths.expand_path(config['claude']['user_entry'],home=home)
    matched=[]
    for oid,obj in old['machine']['objects'].items():
        if (obj['path'] != native or obj['kind'] != 'import' or obj['scope'] != 'machine'
            or obj['ownership'] != 'reused' or obj['marker'] is not None or obj['agents'] != ['claude']
            or obj['original_existed'] is not True or obj['backup_manifest'] is not None or obj['consumers'] != []):continue
        if (obj['fingerprint'] != {'algorithm':'sha256','basis':'file_bytes','value':source_before.fingerprint}
                and not _ck_writeback_matches(runtime, native, source_before, obj['fingerprint']['value'])):
            _fail('drift','Claude引用观察基线不等于本次批准before')
        expected['machine']['objects'][oid]['fingerprint']['value'] = source_after.fingerprint
        matched.append(oid)
    if len(matched)!=1 or expected!=new: _fail('ownership_conflict','只允许精确Claude reused import观察指纹重绑')
    line = ('@'+str(runtime.root/'memories/MEMORY.md')).encode()
    for snap in (source_before,source_after):
        if snap.kind!='file' or sum(l.strip()==line for l in snap.data.splitlines())!=1:
            _fail('entry_conflict','Claude公共引用必须完整唯一保留')
    for marker in (user_entries.CLAUDE_FALLBACK_MARKER,):
        a=entries.managed_span(source_before.data,**marker);b=entries.managed_span(source_after.data,**marker)
        if a is None or b is None or source_before.data[a[0]:a[1]]!=source_after.data[b[0]:b[1]]:
            _fail('entry_conflict','Claude兜底协议必须逐字节保留')
    return matched


def _created_public_span(record, raw):
    """Only the producer that added this exact offset seeds automatic context reuse."""
    manifest = Path(record['manifest_path'])
    producer = json.loads(_file(manifest).data, object_pairs_hook=registry._no_duplicates)
    rows = [r for r in producer.get('entries', []) if r['path'] == record['topic']]
    if len(rows) != 1:
        return False
    before = rows[0]['before']
    if before['kind'] == 'absent':
        prior = b''
    elif before['kind'] == 'file':
        name = before.get('backup')
        if not isinstance(name, str) or Path(name).name != name:
            _fail('content_conflict', '公共 producer 备份缺失')
        prior = _file(manifest.parent/name).data
        if entries.sha256(prior) != before['fingerprint']:
            _fail('content_conflict', '公共 producer 备份漂移')
    else:
        return False
    left, right = record['public_offset'], record['public_end']
    siblings = [r for r in (producer.get('operation_metadata') or {}).get('share_user_memory',{}).get('migrations',[])
                if (r.get('public_offset'),r.get('public_end'),r.get('text_hex')) == (left,right,raw.hex())]
    # A one-plan equivalence may co-create records with different original
    # contexts. Only the first (canonical emitting) context seeds future reuse.
    if not siblings or record.get('context',record['scope']) != siblings[0].get('context',siblings[0]['scope']):
        return False
    return left >= len(prior) and right-left == len(raw)


def _explicit_public_reuse(request, items, public_copies, snapshots, topic):
    declarations = request.get('public_reuse', [])
    if not isinstance(declarations, list):
        _fail('invalid_public_reuse', 'public_reuse 必须为列表')
    if declarations and request.get('scope', 'user') != 'user':
        _fail('invalid_public_reuse', '仅支持已有公共用户正文')
    indexed = {(i['source'], i['start'], i['end']): i for i in items}
    result = {}
    fields = {'source', 'start', 'end', 'source_context', 'public_start', 'public_end',
              'public_context', 'text_sha256', 'equivalent', 'reason', 'source_basis', 'public_basis'}
    for row in declarations:
        if not isinstance(row, dict) or set(row) != fields or row['equivalent'] is not True:
            _fail('invalid_public_reuse', '需要完整精确绑定及明确语境等价声明')
        if not isinstance(row['reason'], str) or not row['reason'].strip():
            _fail('invalid_public_reuse', '需要 Agent 的语境等价理由')
        if any(type(row[k]) is not int for k in ('start','end','public_start','public_end')):
            _fail('invalid_public_reuse', '字节范围必须为整数')
        if not isinstance(row['source'], str):
            _fail('invalid_public_reuse', 'source 必须为精确原生路径字符串')
        for field in ('source_context','public_context'):
            ctx = row[field]
            if not isinstance(ctx, list) or any(not isinstance(h, list) or len(h)!=3
                    or type(h[0]) is not int or not 1<=h[0]<=6 or not isinstance(h[1], str)
                    or type(h[2]) is not int or h[2]<1 for h in ctx):
                _fail('invalid_public_reuse', '语境必须为原始标题层级/文本/次数列表')
        key = (row['source'], row['start'], row['end'])
        item = indexed.get(key)
        if item is None or key in result:
            _fail('invalid_public_reuse', '源片段未知或重复声明')
        if (row['source_basis'] != snapshots[item['source']].fingerprint
                or row['public_basis'] != snapshots[str(topic)].fingerprint):
            _fail('invalid_public_reuse', 'Agent 读取后的源/公共整文件基线已变化')
        raw = item['text'].encode()
        if item['context'] != row['source_context'] or entries.sha256(raw) != row['text_sha256']:
            _fail('invalid_public_reuse', '源语境或原文哈希不符')
        target = public_copies.get((json.dumps(row['public_context']), raw))
        if target != (row['public_start'], row['public_end']):
            _fail('invalid_public_reuse', '目标不是已证明的同字节公共片段/语境')
        result[key] = row
    return result


def _append_declared_sources(request, mode, sources, snapshots, items, protected):
    """Explicit Agent spans only; never widen the default semantic scanner."""
    from .memory_share import _check_source_binding, _heading_context
    equivalents = request.get('equivalent_sources', [])
    reuse = request.get('public_reuse', [])
    if not isinstance(equivalents, list) or not isinstance(reuse, list):
        _fail('invalid_equivalence', '显式来源提案须为列表')
    if not equivalents and not reuse:
        return
    if mode != 'user':
        return  # Preserve existing project proof behavior; no new precut sources.
    bindings = []
    for group in equivalents:
        if not isinstance(group, dict) or set(group) != {'sources', 'canonical_context', 'reason'} or not isinstance(group['sources'], list):
            _fail('invalid_equivalence', '需要完整逐来源等价提案')
        bindings.extend(group['sources'])
    reuse_fields = {'source', 'start', 'end', 'source_context', 'public_start', 'public_end',
                    'public_context', 'text_sha256', 'equivalent', 'reason', 'source_basis', 'public_basis'}
    for row in reuse:
        if not isinstance(row, dict) or set(row) != reuse_fields:
            _fail('invalid_public_reuse', '复用绑定不完整')
        bindings.append({'source': row['source'], 'start': row['start'], 'end': row['end'],
                         'context': row['source_context'], 'text_sha256': row['text_sha256'], 'basis': row['source_basis']})
    for row in bindings:
        if not isinstance(row, dict) or set(row) != {'source', 'start', 'end', 'context', 'text_sha256', 'basis'}:
            _fail('invalid_equivalence', '来源绑定不完整')
        name = row['source']; left = row['start']; right = row['end']
        if not isinstance(name, str) or name not in sources or type(left) is not int or type(right) is not int:
            _fail('invalid_equivalence', '来源必须是本次参与的精确原生路径')
        snap = snapshots.get(name)
        if snap is None or snap.kind != 'file' or not (0 <= left < right <= len(snap.data)):
            _fail('invalid_equivalence', '来源不可读或范围无效')
        spans = protected[name]
        if any(left < end and right > start for start, end in spans):
            _fail('invalid_equivalence', '显式来源不能包含受保护入口或协议')
        try:
            text = snap.data[left:right].decode('utf-8')
        except UnicodeError:
            _fail('invalid_equivalence', '来源范围截断UTF-8字符')
        item = {'source': name, 'agents': sources[name], 'start': left, 'end': right, 'text': text,
                'sha256': entries.sha256(snap.data[left:right]), 'scope': _scope(snap.data, left, spans),
                'context': _heading_context(snap.data, left, spans)[1]}
        _check_source_binding(row, item, snap.fingerprint)
        if any(i['source'] == name and (i['start'], i['end']) == (left, right) for i in items):
            continue
        if any(i['source'] == name and left < i['end'] and right > i['start'] for i in items):
            _fail('invalid_equivalence', '显式来源与既有候选范围重叠')
        items.append(item)


def _equivalent_sources(request, items, snapshots):
    """Single-plan Agent judgment; source context and migration protocol stay intact."""
    from .memory_share import _check_source_binding
    declarations = request.get('equivalent_sources', [])
    if not isinstance(declarations, list):
        _fail('invalid_equivalence', '等价提案须为列表')
    indexed = {(i['source'],i['start'],i['end']):i for i in items}
    bound = {}
    for group in declarations:
        if not isinstance(group,dict) or set(group) != {'sources','canonical_context','reason'}:
            _fail('invalid_equivalence','需要完整来源、公共语境与等价理由')
        if not isinstance(group['reason'],str) or not group['reason'].strip() or not isinstance(group['sources'],list) or len(group['sources'])<2:
            _fail('invalid_equivalence','需要逐来源判断及理由')
        members=[]
        for row in group['sources']:
            if not isinstance(row,dict) or set(row)!={'source','start','end','context','text_sha256','basis'}:
                _fail('invalid_equivalence','来源绑定不完整')
            if not isinstance(row['source'],str) or type(row['start']) is not int or type(row['end']) is not int:
                _fail('invalid_equivalence','来源范围无效')
            key=(row['source'],row['start'],row['end']);item=indexed.get(key)
            if item is None or key in bound or any(key==(m['source'],m['start'],m['end']) for m in members):
                _fail('invalid_equivalence','未知、重叠或重复来源')
            _check_source_binding(row, item, snapshots[item['source']].fingerprint)
            members.append(item)
        canonical=group['canonical_context']
        if not any(_encoded(i['context'])==_encoded(canonical) for i in members) or len({i['text'] for i in members})!=1:
            _fail('invalid_equivalence','公共语境须来自实际来源，原文必须完全相同')
        # Every occurrence in each declared strict group must be covered.
        keys={(i['source'],i['start'],i['end']) for i in members}
        for i in items:
            if i['text']==members[0]['text'] and any(i['context']==m['context'] for m in members) and (i['source'],i['start'],i['end']) not in keys:
                _fail('invalid_equivalence','同语境来源必须逐处完整声明')
        for key in keys: bound[key]=canonical
    return bound


def _build(request):
    import sys
    from .memory_share import _heading_context
    from . import ck_common_trigger as ck
    trusted = paths.select_platform(paths.load_agents_table(), 'darwin' if sys.platform == 'darwin' else sys.platform)
    if request.get('platform_config') != trusted:
        _fail('untrusted_platform_config', '路径配置必须来自当前受信任平台表，批准不能替换')
    if request.get('decisions'):
        _fail('invalid_request','旧action/replacement决策不再执行，请使用编号选择重新预览')
    runtime, ledger, vsnap, memories, topic = _context(request)
    selected, facts = _participants(request, runtime, ledger)
    mode = request.get('scope', 'user')
    if mode not in ('user', 'project'):
        _fail('invalid_request', 'scope must be user or project')
    root = None
    if mode == 'project':
        identity = project.resolve_project(Path(request['project']))
        root = identity.checkout
        topic = root / 'AGENTS.md'
    index = memories / 'MEMORY.md' if mode == 'user' else topic
    objects = _objects(ledger)
    if root:
        for rec in ledger['projects'].values():
            for checkout in rec['checkouts'].values():
                objects.extend(checkout['objects'].values())
    sources = {}
    for agent in selected:
        if root:
            key = 'project_bridge_entry' if agent == 'workbuddy' else 'project_rule_entry'
            name = paths.expand_path(request['platform_config'][agent][key], home=str(runtime.home), project=str(root))
        else:
            name = paths.expand_path(request['platform_config'][agent]['user_entry'], home=str(runtime.home))
        sources.setdefault(str(Path(name)), []).append(agent)
    if root:
        sources.setdefault(str(topic), [])  # Existing public base is always observed.
    snapshots = {str(runtime.registry): vsnap}
    observations = {str(runtime.registry): _meta(vsnap)}
    public_listing = []
    for path in sorted(memories.rglob('*')):
        if path.is_symlink(): _fail('path_conflict','Public content symlink: '+str(path))
        public_listing.append(str(path.relative_to(memories)))
        if path.is_file():
            snap = read_snapshot(path)
            snapshots[str(path)] = snap; observations[str(path)] = _meta(snap)
    items = []; unknown = []; protected_report = []; blocked = []; protected_by_source = {}
    for name, agents in sorted(sources.items()):
        try:
            snap = _file(Path(name), optional=True)
        except (OSError, UnicodeError) as exc:
            unknown.append({'path': name, 'reason': str(exc)}); continue
        except OrganizeError as exc:
            if exc.code != 'encoding_conflict': raise
            unknown.append({'path': name, 'reason': str(exc)}); continue
        snapshots[name] = snap; observations[name] = _meta(snap)
        if snap.kind == 'absent': continue
        spans = _protected(snap.data, Path(name), runtime, objects)
        protected_by_source[name] = spans
        protected_report.extend({'path': name, 'start': a, 'end': b} for a,b in spans)
        if any(o['path'] == name and o['kind'] in ('file', 'import')
               and not (root and entries.free_project_rules(o))
               and not _modern_claude_reference(o,name,request,runtime,ledger) for o in objects):
            blocked.append({'path': name, 'reason': '旧整文件受管入口须先转换，融合不改归属台账。'})
        if mode == 'user':
            common = ck.candidate(snap.data, agents[0], spans)
            if common:
                items.append(dict(common, source=name, agents=agents,
                                  scope=_scope(snap.data, common['start'], spans),
                                  context=_heading_context(snap.data, common['start'], spans)[1]))
        for left,right in _segments(snap.data, spans):
            text = snap.data[left:right].decode()
            if text.lstrip().startswith(('<!--', '@', '```', '~~~')) or _SPECIFIC.search(text):
                continue
            scope = _scope(snap.data, left, spans)
            if any(_SPECIFIC.search(h) for h in scope): continue
            raw = snap.data[left:right]
            items.append({'source': name, 'agents': agents, 'start': left, 'end': right,
                'text': text, 'sha256': entries.sha256(raw), 'scope': scope, 'context': _heading_context(snap.data, left, spans)[1]})
    _append_declared_sources(request, mode, sources, snapshots, items, protected_by_source)
    for path in (topic, index):
        if str(path) not in snapshots:
            snap = _file(path, optional=True); snapshots[str(path)] = snap; observations[str(path)] = _meta(snap)
    public_copies = {}
    if mode == 'user':
        from .memory_share import _available_migrations
        public_raw = snapshots[str(topic)].data or b''
        for record in _available_migrations(runtime).values():
            raw = bytes.fromhex(record['text_hex'])
            left, right = record['public_offset'], record['public_end']
            if (record.get('topic') == str(topic) and public_raw[left:right] == raw
                    and _created_public_span(record, raw)):
                public_copies.setdefault((json.dumps(record.get('context', record['scope'])), raw), (left, right))
    explicit_reuse = _explicit_public_reuse(request, items, public_copies, snapshots, topic)
    equivalents = _equivalent_sources(request, items, snapshots)
    groups = {}
    for item in items:
        ctx = equivalents.get((item['source'],item['start'],item['end']),item['context'])
        key = ck.KIND if item.get('kind') == ck.KIND else _encoded([_identity(item['text']), [h[1] for h in ctx], ctx]).decode()
        groups.setdefault(key, []).append(item)
    defaults = []; optional = []; single = []
    n = len(sources) if root else len(selected)
    for key, members in groups.items():
        canonical = equivalents.get((members[0]['source'],members[0]['start'],members[0]['end']),members[0]['context'])
        members.sort(key=lambda i:i['context']!=canonical)
        coverage = len({i['source'] for i in members})
        existing = bool(root and any(i['source'] == str(topic) for i in members) or mode == 'user' and any((json.dumps(i['context']), i['text'].encode()) in public_copies for i in members))
        declared = [(i['source'],i['start'],i['end']) in explicit_reuse for i in members]
        if any(declared) and any(not d and (json.dumps(i['context']), i['text'].encode()) not in public_copies
                                 for i,d in zip(members,declared)):
            _fail('invalid_public_reuse', '同组语境等价必须逐处声明，不能扩大未声明来源')
        existing = existing or any(declared)
        all_present = n >= 2 and coverage == n and not unknown
        group = {'group_id': entries.sha256(key.encode()), 'summary': members[0]['text'].strip().splitlines()[0],
            'sources': members, 'canonical_context':canonical, 'existing_public': existing, 'default': existing or all_present}
        group['public_reuse'] = [explicit_reuse[(i['source'],i['start'],i['end'])] for i in members
                                 if (i['source'],i['start'],i['end']) in explicit_reuse]
        (defaults if group['default'] else optional if coverage >= 2 else single).append(group)
    numbered = defaults + optional + single
    for number, group in enumerate(numbered, 1): group['number'] = number
    selection = request.get('selection', '按默认方案')
    if not isinstance(selection, str): _fail('invalid_selection', 'selection must be text')
    chosen = {g['number'] for g in defaults}
    view = re.fullmatch(r'\s*查看\s*(\d+)\s*', selection)
    declined = selection == '暂不整理'
    if declined: chosen = set()
    if not view and not declined and selection != '按默认方案':
        clauses = re.split(r'[,，;；](?=\s*(?:不共享|共享|不合并|再加入))', selection)
        for clause in clauses:
            match = re.fullmatch(r'\s*(不共享|共享|不合并|再加入)?\s*(\d+(?:\s*[、,，]\s*\d+)*)\s*', clause)
            if not match: _fail('invalid_selection', 'Use numbered choices, 不共享 n, 按默认方案 or 查看 n')
            nums = {int(v) for v in re.split(r'[、,，]', match[2])}
            if not nums <= {g['number'] for g in numbered}: _fail('invalid_selection', 'Unknown item number')
            if match[1] in ('不共享','不合并'): chosen -= nums
            else: chosen |= nums
    if view and int(view[1]) not in {g['number'] for g in numbered}:
        _fail('invalid_selection', 'Unknown item number')
    excluded_public = [g['number'] for g in defaults if root and g['existing_public'] and g['number'] not in chosen]
    retentions = request.get('retentions', {})
    if not isinstance(retentions, dict): _fail('invalid_request', 'retentions must map item numbers to native paths')
    if set(retentions) - {str(n) for n in excluded_public}:
        _fail('invalid_request', '保留位置仅用于已排除的公共条目')
    if excluded_public and not declined and any(str(n) not in retentions for n in excluded_public):
        _fail('retention_location_required', '已有公共条目须先确认保留位置：'+str(excluded_public))
    # Retention copies precede changes to the existing public base.
    outputs = {}; removals = {}; migrated = []; retention_paths = []
    content = snapshots[str(topic)].data or b''
    if mode == 'user' and any(g['number'] in chosen for g in numbered) and not view and not declined:
        if not content:
            content = '# 用户规则\n'.encode()
    public_removals = []
    if not declined and not view:
        for number in excluded_public:
            destination = retentions[str(number)]
            if not isinstance(destination,str): _fail('invalid_request','保留位置必须为路径')
            target = str((root / destination).absolute()) if not Path(destination).is_absolute() else destination
            if target not in sources or target == str(topic) or target in {str(runtime.registry), str(index)}:
                _fail('invalid_retention_location', '请选择当前项目已参与的独立原生文件保留')
            group = next(g for g in defaults if g['number']==number)
            original = [i for i in group['sources'] if i['source']==str(topic)]
            raw = outputs.get(target, snapshots[target].data or b'')
            for item in original:
                fragment = item['text'].encode()
                if not any(i['source']==target and i['text'].encode()==fragment for i in group['sources']):
                    context = ('\n'+'\n'.join('#'*(level+1)+' '+title for level,title in enumerate(item['scope']))+'\n').encode()
                    raw += context + fragment
                public_removals.append(item)
            outputs[target] = raw
            retention_paths.append(target)
        for item in sorted(public_removals,key=lambda i:i['start'],reverse=True):
            content = content[:item['start']] + content[item['end']:]

    ck_selected = any(g['number'] in chosen and any(i.get('kind') == ck.KIND for i in g['sources']) for g in numbered)
    if ck_selected and not view and not declined:
        if topic.name != 'user-rules.md':
            _fail('invalid_request', 'CK 通用触发仅共享到必读 user-rules.md')
        ck.require_reader(snapshots[str(index)].data or b'')
        span = ck.shared_span(runtime, content, topic)
        if span:
            for g in numbered:
                if any(i.get('kind') == ck.KIND for i in g['sources']):
                    public_copies[(json.dumps(g['canonical_context']), g['sources'][0]['text'].encode())] = span
    public_added = b''
    migrations = []
    emitted_scope = [[1, '用户规则', 1]] if mode == 'user' and not snapshots[str(topic)].data else None
    for group in sorted(numbered, key=lambda group: min(items.index(item) for item in group['sources'])):
        if view or group['number'] not in chosen: continue
        if mode == 'user' or not group['existing_public']:
            copies = dict(public_copies) if mode == 'user' else {}
            for item in group['sources']:
                raw = item['text'].encode()
                canonical = group['canonical_context']
                # Source context stays byte-proven in migration records. The
                # audited host-neutral CK body must not inherit a host's prior
                # private section as its generated public heading.
                public_context = [[2, 'Context Keeper 通用触发', 1]] if item.get('kind') == ck.KIND else canonical
                key = (json.dumps(canonical), raw)
                reuse = explicit_reuse.get((item['source'],item['start'],item['end']))
                if reuse:
                    offset, end = reuse['public_start'], reuse['public_end']
                elif key not in copies:
                    context = ('\n'+'\n'.join('#'*(level+2)+' '+title for level,title in enumerate([h[1] for h in public_context]))+'\n').encode() if public_context else b'\n'
                    if mode == 'user' and emitted_scope == public_context:
                        context = b'\n'
                    emitted_scope = public_context
                    chunk = context + b'\n' + raw
                    offset = len(content) + len(context) + 1
                    content += chunk
                    public_added += chunk
                    copies[key] = (offset, offset + len(raw))
                if not reuse: offset, end = copies[key]
                migrated.append(item)
                for agent in item['agents']:
                    migrations.append({**({'kind': ck.KIND} if item.get('kind') == ck.KIND else {}), 'group': group['number'], 'summary': group['summary'],
                        'agent': agent, 'path': item['source'], 'start': item['start'], 'end': item['end'],
                        'scope': item['scope'], 'context': item['context'], 'text_hex': raw.hex(), 'text_sha256': entries.sha256(raw),
                        'public_offset': offset, 'public_end': end})
        for item in group['sources']:
            if item['source'] != str(topic): removals.setdefault(item['source'], []).append(item)
    phased = bool(set(retention_paths) & set(removals))
    if content != (snapshots[str(topic)].data or b''): outputs[str(topic)] = content
    if mode == 'user' and migrated:
        raw = snapshots[str(index)].data or '# 用户记忆\n'.encode()
        link = ('- 用户记忆：['+topic.name+']('+topic.name+')\n').encode()
        existing = [line for line in raw.splitlines(keepends=True) if line.startswith(b'- ') and ('('+topic.name+')').encode() in line]
        if existing and existing != [link]:
            _fail('content_conflict','已有主题链接含其他结论，保留原文并选择新主题')
        if not existing:
            outputs[str(index)] = raw + (b'' if raw.endswith(b'\n') else b'\n') + link
            if len(outputs[str(index)]) > 25*1024 or len(outputs[str(index)].splitlines()) > 200:
                _fail('content_conflict','L0索引超限，停止而不自动压缩')
    for name, members in removals.items():
        raw = outputs.get(name, snapshots[name].data)
        for item in sorted(members, key=lambda i:i['start'], reverse=True):
            if raw[item['start']:item['end']] != item['text'].encode(): _fail('drift', name)
            raw = raw[:item['start']] + raw[item['end']:]
        if raw != snapshots[name].data: outputs[name] = raw
    if mode == 'user' and not view and not declined:
        from .memory_share import clean_native_navigation
        for name, agents in sources.items():
            if name not in snapshots or snapshots[name].kind != 'file' or not agents: continue
            raw = outputs.get(name, snapshots[name].data)
            cleaned = clean_native_navigation(agents[0], raw, runtime,
                original=snapshots[name].data, migrated=removals.get(name, []))
            if cleaned != raw:
                outputs[name] = cleaned
                removals.setdefault(name, [])
    # Public content/index are written and read back before any source deletion.
    order = retention_paths + [str(topic), str(index)] + sorted(removals)
    changes = []
    for name in dict.fromkeys(order):
        if name not in outputs: continue
        changes.append({'path': name, 'before': _meta(snapshots[name]),
            'after_sha256': entries.sha256(outputs[name]), 'after_hex': outputs[name].hex()})
    # A single durable manifest binds every intermediate and final snapshot.
    steps = []
    if phased:
        phase1 = (snapshots[str(topic)].data or b'') + public_added
        state = dict(snapshots)
        def step(name, raw, stage):
            before = state[name]
            if before.kind == 'file' and before.data == raw: return
            steps.append({'path':name,'before':_meta(before),'after_hex':raw.hex(),
                          'after_sha256':entries.sha256(raw),'stage':stage})
            state[name] = Snapshot('file',raw,before.mode if before.kind=='file' else 0o600)
        step(str(topic),phase1,'public_copy')
        for name in dict.fromkeys(retention_paths+sorted(removals)):
            if name in outputs: step(name,outputs[name],'native_commit')
        step(str(topic),content,'public_remove')
    rebindings=[]
    if mode=='user':
        native=paths.expand_path(request['platform_config']['claude']['user_entry'],home=str(runtime.home))
        if native in outputs and outputs[native]!=snapshots[native].data:
            candidates=[(oid,o) for oid,o in ledger['machine']['objects'].items()
                        if o['path']==native and _modern_claude_reference(o,native,request,runtime,ledger)]
            if candidates:
                updated=copy.deepcopy(ledger)
                for oid,obj in candidates:
                    updated['machine']['objects'][oid]['fingerprint']['value']=entries.sha256(outputs[native])
                raw=registry.serialize_registry(updated,allowed_user_paths=paths.allowed_user_paths(request['platform_config'],None,home=str(runtime.home)))
                after=Snapshot('file',outputs[native],snapshots[native].mode)
                ids=validate_reference_rebinding(vsnap.data,raw,snapshots[native],after,str(runtime.home))
                rebindings=[{'object_id':oid,'path':native,'before':snapshots[native].fingerprint,'after':after.fingerprint} for oid in ids]
                changes.append({'path':str(runtime.registry),'before':_meta(vsnap),'after_hex':raw.hex(),'after_sha256':entries.sha256(raw)})
    saved = {k:copy.deepcopy(request[k]) for k in ('home','platform_config','agents','topic','scope','project','selection',
        'search_paths','app_directories','user_candidates','retentions','public_reuse','equivalent_sources') if k in request}
    saved['home'] = str(runtime.home)
    plan = {'schema_version': 2, 'command': COMMAND, 'layout': runtime.describe(), 'request': saved,
        'declined': declined, 'scope': mode, 'project': str(root) if root else None, 'agents': selected, 'agent_facts': facts,
        'groups': numbered, 'default_numbers': [g['number'] for g in defaults],
        'optional_numbers': [g['number'] for g in optional], 'single_numbers': [g['number'] for g in single],
        'selected_numbers': sorted(chosen), 'view': int(view[1]) if view else None,
        'unknown_sources': unknown, 'items': items, 'blocked_entries': blocked, 'protected_units': protected_report,
        'observations': observations, 'public_listing': public_listing, 'changes': changes,
        'phased_writes': phased, 'steps': steps, 'retention_paths': retention_paths, 'public_paths': list(dict.fromkeys([str(topic),str(index)])),
        'operation_metadata': {'share_user_memory': {'topic': str(topic),
            'topic_after_sha256': entries.sha256(content), 'migrations': migrations,
            **({'superseded_ck_sources': replaced} if (replaced := ck.superseded_sources(runtime, migrations)) else {}),
            'entries_created': [], 'source_after': {name: entries.sha256(outputs[name]) for name in removals if name in outputs},
            'request_agents': selected}} if migrations and mode == 'user' and not phased else None,
        'reference_rebindings':rebindings, 'registry_policy':'only verified reused import fingerprint; ownership and consumers preserved'}
    plan['plan_sha256'] = entries.sha256(_encoded(plan))
    return plan, snapshots


def _verify_readers(plan, request):
    runtime, ledger, *_ = _context(request, allow_active=True)
    if plan['scope'] == 'user':
        status = user_entries.connection_status(runtime, request['platform_config'], ledger, plan['agents'])
        if any(v['status'] != 'connected' for v in status.values()):
            _fail('entry_not_connected', '公共记忆读取入口未核验，原文不删除')
    else:
        root = Path(plan['project'])
        project.resolve_project(root)
        for item in plan['items']:
            name = item['source']
            if name == str(root/'AGENTS.md'): continue
            snap = read_snapshot(name)
            protected = _protected(snap.data, Path(name), runtime, _objects(ledger))
            if not any(b'AGENTS.md' in snap.data[a:b] for a,b in protected):
                _fail('entry_not_connected', '项目读取入口未核验，原文不删除：'+name)


def _result(**fields):
    result={'command':COMMAND,'status':'failed','approval_required':False,'next_action':None,
            'errors':[],'changes':[],'blocked_entries':[]}
    result.update(fields);return result


def plan_organize(request):
    """Read-only request→result; full plan contains unredacted user text locally."""
    try:
        plan,_=_build(request)
        editing = {c['path'] for c in plan['changes']}
        blocked = [b for b in plan['blocked_entries'] if b['path'] in editing]
        if blocked:
            return _result(status='failed',fusion_status='blocked',approval_plan=plan,prompt=present(plan).split('\n\n请告诉我')[0]+'\n当前被阻断，仅供只读诊断，不选择、不执行；可暂不整理。',
                blocked_entries=blocked,errors=[{'code':'ownership_conflict','message':'未知整文件受管入口不能进入融合修改，原文保留。'}],
                next_action='先核对 blocked_entries 的归属证据并另起精确治理；可选择暂不整理以保留现状。')
        if not plan['changes']:
            return _result(status='viewed' if plan.get('view') else 'completed',fusion_status='declined' if plan['declined'] else 'pending_selection' if plan['groups'] else 'unchanged',prompt=present(plan),approval_plan=plan,blocked_entries=plan['blocked_entries'])
        preview=dict(plan,confirmed_at='<UTC timestamp>',reference='<real user confirmation>')
        return _result(status='approval_required',approval_required=True,fusion_status='pending_selection',prompt=present(plan),approval_plan=plan,
                       changes=plan['changes'],blocked_entries=plan['blocked_entries'],
                       next_action=json.dumps(preview,ensure_ascii=False))
    except (ValueError,OSError,KeyError,TypeError) as exc:
        return _result(errors=[{'code':getattr(exc,'code','organize_failed'),'message':str(exc)}])


def execute_organize(plan,approval,*,request=None,hook=None):
    """One approval of the full itemized plan, re-plan under cooperative lock."""
    try:
        if plan.get('view'):_fail('view_only','查看不能执行修改')
        if not isinstance(approval,dict):_fail('approval_mismatch','Approval object required')
        evidence={k:approval.get(k) for k in ('confirmed_at','reference')}
        if any(not isinstance(v,str) or not v.strip() or v.startswith('<') for v in evidence.values()):
            _fail('approval_mismatch','Real confirmation evidence required')
        registry._evidence(evidence)
        expected=dict(plan,**evidence)
        if approval!=expected:_fail('approval_mismatch','Central approval must match the entire exact itemized plan')
        request=copy.deepcopy(request or plan['request'])
        current,_=_build(request)
        if current!=plan:_fail('drift','Scene or item plan changed since preview')
        editing={c['path'] for c in plan['changes']}
        blocked=[b for b in plan['blocked_entries'] if b['path'] in editing]
        if blocked:return _result(errors=[{'code':'ownership_conflict','message':'旧整文件受管入口须先转换，整单零写入。'}],blocked_entries=blocked)
        if not plan['changes']:return _result(status='completed',fusion_status='declined' if plan['declined'] else 'unchanged',blocked_entries=plan['blocked_entries'])
        runtime=_context(request)[0]
        with write_lock(runtime.lock):
            current,snapshots=_build(request)
            if current!=plan:_fail('drift','Scene changed while acquiring machine lock')
            state = dict(snapshots)
            changes = []
            ordered = plan['steps'] if plan.get('phased_writes') else plan['changes']
            for c in ordered:
                change = Change.file(c['path'],bytes.fromhex(c['after_hex']),expected=state[c['path']])
                if _meta(change.expected) != c['before']: _fail('drift','阶段批准输入不一致')
                changes.append(change); state[c['path']] = change.after
            progress = dict(snapshots)
            step_index = [0]

            tx=Transaction(lock_path=runtime.transaction_lock,backup_root=runtime.backups,
                           allowed_roots=[runtime.home,runtime.root]+([Path(plan['project'])] if plan.get('project') else []),operation=COMMAND,hook=hook,operation_metadata=dict(plan.get('operation_metadata') or {}, approval=dict(evidence, plan_sha256=plan['plan_sha256'])))
            def guarded(event,path):
                if hook:hook(event,path)
                # V and all untouched evidence stay bound through the final write.
                if event in ('before_write','after_write'):
                    for name,meta in plan['observations'].items():
                        if name not in editing and _meta(read_snapshot(name))!=meta:
                            _fail('drift','Unedited evidence drift: '+name)
                    memories = runtime.root/'memories'
                    additions = {str(Path(c['path']).relative_to(memories)) for c in plan['changes']
                        if Path(c['path']).is_relative_to(memories) and c['before']['kind']=='absent'}
                    listing = {str(p.relative_to(memories)) for p in memories.rglob('*')}
                    if listing-additions != set(plan['public_listing']):
                        _fail('drift','Public content listing changed during fusion')
                    if plan.get('phased_writes'):
                        current_step = ordered[step_index[0]]
                        if str(path) != current_step['path']: _fail('drift','阶段顺序不一致')
                        for name, expected_snapshot in progress.items():
                            # The current output is read back separately below.
                            if event == 'after_write' and name == str(path): continue
                            if read_snapshot(name) != expected_snapshot:
                                _fail('drift','阶段间文件漂移：'+name)
                        if event == 'before_write':
                            stage = current_step['stage']
                            if stage in ('native_commit','public_remove'):
                                _verify_readers(plan,request)
                        else:
                            after = Snapshot('file',bytes.fromhex(current_step['after_hex']),
                                progress[str(path)].mode if progress[str(path)].kind=='file' else 0o600)
                            if read_snapshot(path) != after: _fail('drift','阶段输出读回失败')
                            progress[str(path)] = after
                            step_index[0] += 1
                        return
                    if event == 'before_write' and str(path) in plan['public_paths'] and plan.get('retention_paths'):
                        for name in plan['retention_paths']:
                            change = next(c for c in plan['changes'] if c['path']==name)
                            if read_snapshot(name).data != bytes.fromhex(change['after_hex']):
                                _fail('drift','保留位置未完整写入，公共原文不删除')
                    if event == 'before_write' and str(path) not in plan['public_paths']+plan.get('retention_paths',[]):
                        _verify_readers(plan, request)
                        for name in plan['public_paths']:
                            change = next((c for c in plan['changes'] if c['path'] == name), None)
                            snap = read_snapshot(name)
                            if change:
                                if snap.kind != 'file' or snap.data != bytes.fromhex(change['after_hex']):
                                    _fail('drift', '公共记忆未完整保存，保留原文：'+name)
                            elif _meta(snap) != plan['observations'][name]:
                                _fail('drift', '公共记忆发生变化：'+name)
            tx.hook=guarded
            metadata = next((c for c in changes if c.path==runtime.registry),None)
            if metadata and (not plan.get('reference_rebindings') or plan.get('phased_writes')):
                _fail('ownership_conflict','不允许通用或分阶段registry改写')
            result=tx.run([c for c in changes if c is not metadata],registry_change=metadata,phased_writes=plan.get('phased_writes',False))
        return _result(status='completed',fusion_status='completed',changes=plan['changes'],manifest=result['manifest'],
                       blocked_entries=plan['blocked_entries'],provenance='exact approved source spans and restricted reference observation; transaction manifest')
    except (ValueError,OSError,KeyError,TypeError) as exc:
        return _result(status='recovery_required' if getattr(exc,'code',None)=='recovery_required' else 'failed',
                       errors=[{'code':getattr(exc,'code','organize_failed'),'message':str(exc),
                                'manifest':getattr(exc,'manifest',None)}],blocked_entries=plan.get('blocked_entries',[]))


def run_organize(request):
    if request.get('approval') is None:return plan_organize(request)
    approval=request['approval']
    if not isinstance(approval,dict):return _result(errors=[{'code':'approval_mismatch','message':'Approval object required'}])
    plan={k:v for k,v in approval.items() if k not in ('confirmed_at','reference')}
    return execute_organize(plan,approval,request=request,hook=request.get('hook'))


run=run_organize


def present(plan, *, summaries=None):
    """Display projection only; caller captions never enter the approved plan.

    An outer Agent supplies semantic summaries after reading full sources.text.
    The CLI fallback is explicitly a faithful source excerpt, never an invented
    semantic decision; full text remains available through read-only view.
    """
    summaries = summaries or {}
    lines = []
    pending = sorted(set(plan['optional_numbers']) | set(plan['single_numbers']))
    names = {'codex':'Codex','claude':'Claude Code','workbuddy':'WorkBuddy','dsh':'DSH','zcode':'ZCode','opencode':'OpenCode'}
    home = plan['request']['home']
    unknown = plan.get('unknown_sources', [])
    if unknown:
        lines.append('以下来源未能完整读取，不能据此判断没有规则或全部内容相同：')
        for item in unknown:
            source = item['path']
            if source.startswith(home+'/'): source = '~'+source[len(home):]
            lines.append('- '+source)
        lines.append('')
    if plan.get('view'):
        group = next(g for g in plan['groups'] if g['number']==plan['view'])
        return '\n'.join('来源：'+i['source']+'\n'+i['text'] for i in group['sources'])
    for label, numbers in [('建议合并的相同规则', plan['default_numbers']), ('需要你确认是否合并', pending)]:
        if not numbers: continue
        lines += [label]
        for group in plan['groups']:
            if group['number'] not in numbers: continue
            excerpt = ' '.join(group['sources'][0]['text'].split())
            caption = summaries.get(group['number']) or ('原文摘录：'+excerpt[:160]+('…' if len(excerpt)>160 else ''))
            suffix = '（单家内容，默认不合并）' if group['number'] in plan['single_numbers'] else ''
            lines.append('%d. %s%s' % (group['number'],caption,suffix))
            sources=[]
            for item in group['sources']:
                source = item['source']
                if source.startswith(home+'/'): source='~'+source[len(home):]
                for agent in item['agents']:
                    value=names.get(agent,agent)+'（'+source+'）'
                    if value not in sources: sources.append(value)
            lines.append('   来源：'+'、'.join(sources))
        lines.append('')
    if not plan['groups']:
        if unknown: return '\n'.join(lines).rstrip()
        scope = '项目' if plan.get('project') or plan['request'].get('scope') == 'project' else '用户'
        return '没有需要合并的'+scope+'规则。'
    choices=[]
    if plan['default_numbers']:
        choices += ['“按默认方案”', '“不合并%d”排除该项' % plan['default_numbers'][0]]
    if pending: choices += ['“再加入%d”合并该项' % pending[0]]
    choices += ['“查看%d”阅读完整原文（不修改）' % plan['groups'][0]['number'], '“暂不整理”']
    lines += ['合并后公共记忆保留一份，移除对应来源的重复内容；专属和未选内容保留。',
              '你可以回复'+'；'.join(choices)+'。选定后直接执行。']
    return '\n'.join(lines)


def continuation(request, *, scope='user', project_path=None):
    """Read-only next stage, never reuses installation approval as fusion consent."""
    req = dict(request, scope=scope)
    req.pop('approval', None)
    if project_path: req['project'] = str(project_path)
    stage = plan_organize(req)
    return {'status': ('completed' if stage.get('fusion_status') == 'unchanged' else 'pending_selection') if stage['status'] != 'failed' else 'blocked',
            'automatic_continue': stage['status'] != 'failed', 'can_decline': True,
            'command': 'organize-project-memory' if scope=='project' else 'organize-user-memory',
            'project': str(project_path) if project_path else None, 'preview': stage}


def cli(argv=None, *, home=None):
    import argparse
    import sys
    parser = argparse.ArgumentParser(prog='记忆共享', allow_abbrev=False)
    parser.add_argument('command', choices=['organize-user-memory','organize-project-memory','organize-user-rules'])
    parser.add_argument('--project')
    parser.add_argument('--topic')
    parser.add_argument('--agent', action='append', dest='agents')
    parser.add_argument('--selection', default=None)
    parser.add_argument('--decline', action='store_true')
    parser.add_argument('--approval-file')
    parser.add_argument('--selection-plan-file', help='此前展示的完整 approval_plan，用于绑定选择前现场')
    parser.add_argument('--selection-reference', help='实际用户选择消息；选择即执行，不另问确认')
    parser.add_argument('--equivalent-sources-file', help='Agent 实际阅读后逐来源精确等价提案，仅限本次')
    parser.add_argument('--public-reuse-file', help='Agent 显式等价语境与已有公共字节范围绑定 JSON 列表')
    parser.add_argument('--retention-file',help='JSON对象：已排除公共条目编号到当前项目原生文件路径')
    ns = parser.parse_args(argv)
    try:
        config = paths.select_platform(paths.load_agents_table(), 'darwin' if sys.platform=='darwin' else sys.platform)
        request = {'home': str(Path(home or Path.home()).resolve()), 'platform_config': config}
        if ns.approval_file:
            approval = json.loads(Path(ns.approval_file).read_text(), object_pairs_hook=registry._no_duplicates)
            if approval['request'].get('platform_config') != config:
                _fail('untrusted_platform_config','批准不得覆盖受信任路径配置')
            request.update(approval['request'])
            if request['home'] != str(Path(home or Path.home()).resolve()):
                _fail('approval_mismatch','批准HOME与当前目标不一致')
            if ns.selection is not None or ns.decline or ns.agents or ns.retention_file or ns.topic or ns.public_reuse_file or ns.equivalent_sources_file:
                _fail('approval_mismatch','执行批准时不得同时改变选择或参与者')
            request['approval'] = approval
        else:
            request['scope'] = 'project' if ns.command=='organize-project-memory' else 'user'
            if ns.agents: request['agents'] = ns.agents
            if ns.project: request['project'] = ns.project
            if ns.topic: request['topic'] = ns.topic
            if ns.equivalent_sources_file:
                request['equivalent_sources'] = json.loads(Path(ns.equivalent_sources_file).read_text(), object_pairs_hook=registry._no_duplicates)
            if ns.public_reuse_file:
                request['public_reuse'] = json.loads(Path(ns.public_reuse_file).read_text(), object_pairs_hook=registry._no_duplicates)
            request['selection'] = '暂不整理' if ns.decline else ns.selection or '按默认方案'
            if ns.retention_file: request['retentions'] = json.loads(Path(ns.retention_file).read_text(),object_pairs_hook=registry._no_duplicates)
        expected_scope = 'project' if ns.command=='organize-project-memory' else 'user'
        if request.get('scope','user') != expected_scope:
            _fail('approval_mismatch','批准作用域与命令不一致')
        if ns.project and str(Path(ns.project).resolve()) != str(Path(request.get('project', ns.project)).resolve()):
            _fail('approval_mismatch','批准项目与命令不一致')
        result = run_organize(request)
        if ns.selection_reference:
            if ns.approval_file or ns.selection is None or not ns.selection_reference.strip():
                _fail('approval_mismatch', '选择执行须绑定本次真实选择，不可混用批准文件')
            if not ns.selection_plan_file:
                _fail('approval_mismatch', '选择执行须提供已展示计划，防止沿用漂移后的编号')
            if result.get('approval_required') and not result['approval_plan'].get('view'):
                plan = result['approval_plan']
                shown = json.loads(Path(ns.selection_plan_file).read_text(), object_pairs_hook=registry._no_duplicates)
                if any(shown.get(k) != plan.get(k) for k in ('layout','observations','groups','agents','scope','project')):
                    _fail('drift', '现场或编号内容相对已展示计划变化，停止执行')
                evidence = {'confirmed_at': datetime.now(timezone.utc).isoformat().replace('+00:00','Z'),
                            'reference': ns.selection_reference}
                result = execute_organize(plan, dict(plan, **evidence), request=request)
            elif result.get('status') == 'completed' and result.get('fusion_status') != 'declined':
                result['fusion_status'] = 'unchanged'
        if expected_scope == 'user' and result.get('fusion_status') in ('completed','declined','unchanged'):
            from . import ck_install
            result = ck_install.tail(result, request)
    except (ValueError,OSError,KeyError,TypeError) as exc:
        result = _result(errors=[{'code':getattr(exc,'code','organize_failed'),'message':str(exc)}])
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result['status']=='viewed' else 2 if result['status'] in ('failed','recovery_required') else 5 if result.get('approval_required') or result.get('fusion_status')=='pending_selection' else 0
