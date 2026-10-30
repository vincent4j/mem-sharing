"""Optional, explicit user-rule organization; classifications are suggestions.

No imports trigger IO. Public memories are content, not V-managed objects.
One recoverable transaction edits entries and content; V is never modified.
The cooperative machine lock serializes AGM writers, not arbitrary editors.
"""
from __future__ import annotations

import copy
import json
import re
from datetime import datetime, timezone
from difflib import SequenceMatcher
from pathlib import Path

from . import entries, layout, paths, registry
from .transaction import Change, Snapshot, Transaction, TransactionError, read_snapshot, write_lock

COMMAND = 'organize-user-rules'
_COMMON = re.compile(r'中文|语言|简洁|简体|繁体|提交|commit|风格|流程|偏好|批准|确认|测试|核验|验证|证据|先规划|先分析|先计划|勿|不要|禁止|不得|format|concise|approval|language', re.I)
_SPECIFIC = re.compile(r'codex|claude|workbuddy|cursor|paseo|openai|anthropic|mcp|skills?|执行器专属|专属|agent专用|\.codex|\.claude|\.workbuddy|[~/$][\w./-]+|`[^`]+`|\b(?:npm|npx|uvx|python\d*|git|bash|zsh)\s+[-\w]', re.I)
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


def _normal(text):
    return re.sub(r'[\W_]+', '', re.sub(r'^\s*(?:[-*+]\s+|\d+[.)]\s+)', '', text), flags=re.UNICODE).casefold()


def _classify(text, public):
    if _SPECIFIC.search(text) or text.lstrip().startswith(('```','~~~','@')):
        return '独有', '含执行器名称、专属工具/命令/路径或代码；保守原地保留。', None
    normal=_normal(text)
    best=None;score=0
    for candidate in public:
        other=_normal(candidate['text'])
        if len(normal)<6 or len(other)<6:
            continue
        ratio=SequenceMatcher(None,normal,other).ratio()
        if ratio>score:
            best=candidate;score=ratio
    if score>=0.86:
        return '疑似冗余', '与公共源条目词面相近（%.2f）；仅为语义重复建议，须人工逐项核对。'%score, best
    if _COMMON.search(text):
        return '公共', '通用语言、风格或工作流程约定；建议跨执行器共享，仍需人工确认。', None
    return '独有', '缺乏跨执行器通用证据；归属不明，保守原地保留，可人工重审。', None


def _context(request):
    runtime=layout.from_request(request)
    # HOME's own ancestry may be an environment alias (/var -> /private/var on
    # macOS). Anchor actual transaction paths canonically, after the shared
    # resolver has rejected links inside the managed chain below HOME.
    runtime=layout.resolve_layout(runtime.home.resolve())
    runtime.validate_paths()
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


def _build(request):
    runtime,ledger,vsnap,memories,topic=_context(request)
    selected=paths.resolve_agents(request.get('agents'))
    objects=_objects(ledger)
    observations={str(runtime.registry):_meta(vsnap)}
    snapshots={};public=[];public_listing=[]
    for path in sorted(memories.rglob('*')):
        if path.is_symlink():
            _fail('path_conflict','Public content symlink; no dereference: '+str(path))
        public_listing.append(str(path.relative_to(memories)))
        if path.is_file() and path.suffix.lower()=='.md':
            snap=_file(path);snapshots[str(path)]=snap;observations[str(path)]=_meta(snap)
            # Imported rule blocks are also compared as paragraphs; their marker
            # lines themselves are never rule candidates.
            metadata=[];offset=0
            for line in snap.data.splitlines(keepends=True):
                if line.lstrip().startswith((b'<!--', '> 迁自'.encode())):
                    metadata.append((offset,offset+len(line)))
                offset+=len(line)
            for a,b in _segments(snap.data,metadata):
                text=snap.data[a:b].decode()
                if text.lstrip().startswith(('<!--','> 迁自')):
                    continue
                public.append({'path':str(path),'start':a,'end':b,'text':text,'sha256':entries.sha256(snap.data[a:b])})
    index=memories/'MEMORY.md'
    for path in (index,topic):
        if str(path) not in snapshots:
            snap=_file(path,optional=True);snapshots[str(path)]=snap;observations[str(path)]=_meta(snap)
    items=[];blocked=[];protected_report=[]
    decisions=request.get('decisions',{})
    if not isinstance(decisions,dict):_fail('invalid_request','decisions must be an item-id mapping')
    for agent in selected:
        path=Path(paths.expand_path(request['platform_config'][agent]['user_entry'],home=str(runtime.home)))
        if not path.is_relative_to(runtime.home):_fail('path_conflict','User entry must remain below HOME')
        snap=_file(path,optional=True);snapshots[str(path)]=snap;observations[str(path)]=_meta(snap)
        if snap.kind=='absent':continue
        spans=_protected(snap.data,path,runtime,objects)
        protected_report.extend({'path':str(path),'start':a,'end':b,'sha256':entries.sha256(snap.data[a:b])} for a,b in spans)
        legacy=[o for o in objects if o['path']==str(path) and o['kind'] in ('file','import')]
        if legacy:
            blocked.append({'path':str(path),'reason':'旧整文件受管记录覆盖入口正文；V 不得被整理向导修改。',
                            'record_types':sorted({o['kind'] for o in legacy}),
                            'conversion':'先由产品生命周期转换将旧整文件记录转为精确受管单元，再重新预览；不要手删台账。'})
        for left,right in _segments(snap.data,spans):
            raw=snap.data[left:right];text=raw.decode();fingerprint=entries.sha256(raw)
            item_id=entries.sha256(_encoded([str(path),left,right,fingerprint]))
            classification,reason,match=_classify(text,public)
            action={'公共':'move','独有':'keep','疑似冗余':'delete'}[classification]
            choice=decisions.get(item_id,{})
            if not isinstance(choice,dict) or set(choice)-{'action','replacement'}:
                _fail('invalid_request','Each decision accepts only action/replacement')
            action=choice.get('action',action)
            if action not in ('move','keep','delete','modify'):
                _fail('invalid_request','Unknown item action')
            if classification=='独有' and action!='keep':
                _fail('exclusive_rule_protected','Executor-specific/uncertain items must remain untouched')
            if action=='modify' and (not isinstance(choice.get('replacement'),str) or not choice['replacement'].strip()):
                _fail('invalid_request','modify requires nonempty replacement text')
            if action!='modify' and 'replacement' in choice:
                _fail('invalid_request','replacement is only for modify')
            items.append({'item_id':item_id,'agent':agent,'source':str(path),'start':left,'end':right,
                'text':text,'sha256':fingerprint,'classification':classification,'reason':reason,
                'comparison':match,'action':action,'suggested_action':{'公共':'move','独有':'keep','疑似冗余':'delete'}[classification],
                'replacement':choice.get('replacement'), 'target':str(topic) if action=='move' else None,
                'removes_or_modifies_source':action!='keep'})
    if set(decisions)-{i['item_id'] for i in items}:
        _fail('stale_decision','Decision item absent or changed since scan')
    outputs={};moved=[i for i in items if i['action']=='move']
    for source in {i['source'] for i in items if i['action']!='keep'}:
        raw=snapshots[source].data
        for item in sorted((i for i in items if i['source']==source and i['action']!='keep'),key=lambda i:i['start'],reverse=True):
            replacement=item['replacement'].encode() if item['action']=='modify' else b''
            original=raw[item['start']:item['end']]
            if replacement and original.endswith(b'\n') and not replacement.endswith(b'\n'):
                replacement+=b'\r\n' if original.endswith(b'\r\n') else b'\n'
            raw=raw[:item['start']]+replacement+raw[item['end']:]
        outputs[source]=raw
    stamp=request.get('date') or datetime.now(timezone.utc).strftime('%Y-%m-%d')
    try:datetime.strptime(stamp,'%Y-%m-%d')
    except (TypeError,ValueError):_fail('invalid_request','date must be YYYY-MM-DD')
    l0=None
    if moved:
        original=snapshots[str(topic)]
        if original.kind=='file':
            content=original.data
            if not re.search(rb'^## L1 ',content,re.M):
                _fail('content_conflict','Existing target topic has no L1 summary; select a new topic')
        else:
            content=('# 用户公共规则\n\n## L1 概要\n\n当前有效结论：以下通用约定经完整计划集中确认后由各执行器共享。\n待办：规则变化时手写更新本概要及索引结论。\n\n## L2 原文与来源\n').encode()
        for item in moved:
            marker={'start':'<!-- mem-sharing:organized-'+item['item_id']+':start -->',
                    'end':'<!-- mem-sharing:organized-'+item['item_id']+':end -->'}
            origin='~/'+str(Path(item['source']).relative_to(runtime.home))
            block=(marker['start']+'\n'+item['text'].rstrip('\r\n')+'\n\n> 迁自 '+origin+
                   '('+stamp+', 原段 sha256 '+item['sha256'][:16]+')\n'+marker['end']).encode()
            content=entries.render_block(content,block,**marker)
        outputs[str(topic)]=content
        l0='- 用户公共规则：通用约定已按集中批准计划归位，独有内容仍留原入口。['+topic.name+']('+topic.name+')\n'
        original_index=snapshots[str(index)]
        index_raw=original_index.data or ('# 公共记忆\n\n读取契约：L0 恒读 → 需要时读主题 L1 概要 → 仍不足才读 L2 全文。\n\n').encode()
        existing=[line for line in index_raw.splitlines(keepends=True) if ('('+topic.name+')').encode() in line]
        if existing and existing != [l0.encode()]:
            _fail('content_conflict','Index already links the target with different wording; preserve it and select another topic')
        if not existing:index_raw += (b'' if index_raw.endswith(b'\n') else b'\n')+l0.encode()
        if len(index_raw)>25*1024 or len(index_raw.splitlines())>200:
            _fail('content_conflict','L0 index limit exceeded; no automatic compaction')
        outputs[str(index)]=index_raw
    changes=[]
    for path,raw in sorted(outputs.items()):
        snap=snapshots[path]
        if snap.data==raw:continue
        changes.append({'path':path,'before':_meta(snap),'after_sha256':entries.sha256(raw),'after_hex':raw.hex()})
    plan={'schema_version':1,'command':COMMAND,'layout':runtime.describe(), 'date':stamp,
          'request':{k:copy.deepcopy(request[k]) for k in ('home','platform_config','agents','topic','decisions') if k in request},
          'items':items,'blocked_entries':blocked,'protected_units':protected_report,
          'observations':observations,'public_listing':public_listing,'l0_draft':l0,
          'changes':changes,'metadata_scope':str(runtime.backups), 'registry_policy':'unchanged; content is not a V object'}
    plan['request']['date']=stamp
    plan['request']['home']=str(runtime.home)
    plan['plan_sha256']=entries.sha256(_encoded(plan))
    return plan,snapshots


def _result(**fields):
    result={'command':COMMAND,'status':'failed','approval_required':False,'next_action':None,
            'errors':[],'changes':[],'blocked_entries':[]}
    result.update(fields);return result


def plan_organize(request):
    """Read-only request→result; full plan contains unredacted user text locally."""
    try:
        plan,_=_build(request)
        if not plan['changes']:
            return _result(status='completed',approval_plan=plan,blocked_entries=plan['blocked_entries'])
        preview=dict(plan,confirmed_at='<UTC timestamp>',reference='<real user confirmation>')
        return _result(status='approval_required',approval_required=True,approval_plan=plan,
                       changes=plan['changes'],blocked_entries=plan['blocked_entries'],
                       next_action=json.dumps(preview,ensure_ascii=False))
    except (ValueError,OSError,KeyError,TypeError) as exc:
        return _result(errors=[{'code':getattr(exc,'code','organize_failed'),'message':str(exc)}])


def execute_organize(plan,approval,*,request=None,hook=None):
    """One approval of the full itemized plan, re-plan under cooperative lock."""
    try:
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
        if not plan['changes']:return _result(status='completed',blocked_entries=plan['blocked_entries'])
        runtime=_context(request)[0]
        with write_lock(runtime.lock):
            current,snapshots=_build(request)
            if current!=plan:_fail('drift','Scene changed while acquiring machine lock')
            changes=[Change.file(c['path'],bytes.fromhex(c['after_hex']),expected=snapshots[c['path']]) for c in plan['changes']]
            tx=Transaction(lock_path=runtime.transaction_lock,backup_root=runtime.backups,
                           allowed_roots=[runtime.home,runtime.root],operation=COMMAND,hook=hook)
            def guarded(event,path):
                if hook:hook(event,path)
                # V and all untouched evidence stay bound through the final write.
                if event in ('before_write','after_write'):
                    for name,meta in plan['observations'].items():
                        if name not in editing and _meta(read_snapshot(name))!=meta:
                            _fail('drift','Unedited evidence drift: '+name)
                    memories=runtime.root/'memories'
                    additions={str(Path(c['path']).relative_to(memories)) for c in plan['changes']
                               if Path(c['path']).is_relative_to(memories) and c['before']['kind']=='absent'}
                    listing={str(p.relative_to(memories)) for p in memories.rglob('*')}
                    if listing-additions!=set(plan['public_listing']):
                        _fail('drift','Public content listing changed during transaction')
            tx.hook=guarded
            result=tx.run(changes)
        return _result(status='completed',changes=plan['changes'],manifest=result['manifest'],
                       blocked_entries=plan['blocked_entries'],provenance='transaction manifest + in-content source lines; V unchanged')
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
