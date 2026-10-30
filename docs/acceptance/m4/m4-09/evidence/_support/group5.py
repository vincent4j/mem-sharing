from collect import *
import plistlib

def wb(c):
    def seed():
        app=c.home/'Applications/WorkBuddy.app'
        write(app/'Contents/Info.plist',plistlib.dumps({'CFBundleName':'WorkBuddy','CFBundleIdentifier':'fixture.workbuddy','CFBundleExecutable':'WorkBuddy','CFBundleShortVersionString':'1.0'}))
        p=app/'Contents/MacOS/WorkBuddy';write(p,'#!/bin/sh\nexit 0\n');p.chmod(0o755)
        sig=c.bin/'codesign';write(sig,'#!/bin/sh\nif [ "$1" = "-d" ]; then printf "Identifier=fixture.workbuddy\\n" >&2; fi\nexit 0\n');sig.chmod(0o755)
    c.mutate('synthetic-workbuddy-static-signature-backend',seed)
    c.note('WorkBuddy bundle and codesign response are synthetic detector inputs, not an authentic signed application or native session.')

def onboard(c):
    c.install();c.mutate('existing-claude-user-body',lambda:write(c.home/'.claude/CLAUDE.md',b'private user body\xff\r\n'))
    c.signal('claude');c.check('check-before-explicit-onboard')
    p=c.preview('explicit-onboard-preview',('--agent','claude'))
    if 'approval_plan' in p:c.I('explicit-onboard-execute','--approval-file',c.approve(p['approval_plan']))
    p=c.preview('explicit-repeat-preview',('--agent','claude'))
    if 'approval_plan' in p:c.I('explicit-repeat-execute','--approval-file',c.approve(p['approval_plan']))

def absent(c,kind):
    c.signal('codex')
    if kind=='hint':c.mutate('claude-hint',lambda:(c.home/'.claude').mkdir())
    if kind=='unknown':
        def seed():
            p=c.bin/'claude';write(p,'#!/bin/sh\nexit 0\n');p.chmod(0o755)
        c.mutate('unverified-wrapper',seed)
    c.preview('explicit-claude',('--agent','claude'))
    p=c.preview('selected-codex',('--agent','codex'))
    if 'approval_plan' in p:c.I('selected-codex-apply','--approval-file',c.approve(p['approval_plan']))

def agents_life(c,kind):
    c.install();c.project_action();p=c.project/'AGENTS.md'
    def change():
        raw=p.read_bytes()
        if kind=='body':raw=raw.replace(b'# project',b'# Changed title')+b'\nUser body\xff\r\n'
        elif kind=='edit':raw=raw.replace('职责'.encode(),b'edited-role')
        elif kind=='duplicate':raw+=raw[raw.index(b'<!-- mem-sharing:project-experience:start -->'):]
        else:
            start=raw.index(b'<!-- mem-sharing:project-experience:start -->');end=raw.index(b'<!-- mem-sharing:project-experience:end -->')+len(b'<!-- mem-sharing:project-experience:end -->')
            raw=raw[:start]+raw[end:]
        write(p,raw)
    c.mutate('agents-'+kind,change);c.check();c.project_action('remove-memory',label='remove');c.check('post-remove-check')

def claude_life(c,kind):
    c.install(('codex','claude'))
    if kind=='existing-reference':c.mutate('existing-reference',lambda:write(c.project/'CLAUDE.md',b'@AGENTS.md\n'))
    c.project_action(extra=('--agent','claude'))
    if kind=='added-body':c.mutate('claude-user-body',lambda:write(c.project/'CLAUDE.md',(c.project/'CLAUDE.md').read_bytes()+b'private\xff\r\n'))
    if kind=='missing-creation-proof':
        def change():
            d=json.loads(c.V.read_bytes());o=next(o for o in d['projects'][str(c.project)]['checkouts'][str(c.project)]['objects'].values() if o['path']==str(c.project/'CLAUDE.md'))
            o.pop('lifecycle',None);o.update(ownership='reused',original_existed=True,backup_manifest=None)
            dump(c.V,d)
        c.mutate(kind,change)
    c.project_action('remove-memory',label='remove');c.check()

def workbuddy(c):
    wb(c);c.install();c.project_action(extra=('--agent','workbuddy'))
    c.mutate('synthetic-native-directory-appears',lambda:write(c.project/'.workbuddy/memory/MEMORY.md',b'native user body\xff\r\n'))
    c.project_action(extra=('--agent','workbuddy'),label='native-pointer');c.check()
    c.mutate('native-reset',lambda:write(c.project/'.workbuddy/memory/MEMORY.md',b'reset native body\xff\r\n'))
    c.check('check-reset');c.project_action(extra=('--agent','workbuddy'),label='reset-repair')
    c.project_action('remove-memory',label='remove');c.check('check-after-remove')
    c.note('Native directory appearance/reset is explicitly a synthetic filesystem event. Real WorkBuddy actual-use trigger/new-session verification is not_in_scope for M4-10.')

def data(c):
    c.mutate('existing-ck-data',lambda:write(c.project/'docs/context-keeper/worklogs/existing.md',b'preserved CK data\xff\r\n'))
    c.mutate('existing-user-ck-install',lambda:write(c.home/'.agents/skills/context-keeper/SKILL.md','synthetic CK user-level presence; never executed\n'))

def disabled(c,action='disable'):
    c.install();data(c);c.project_action()
    if action=='disable':c.project_action(extra=('--no-memory',),label='disable')
    else:c.project_action('remove-memory',label='remove')
    c.A('default-reenter','enable-memory','--project',c.project);c.check()

def defaults(c,present):
    c.install()
    if present:c.mutate('synthetic-user-ck-presence',lambda:write(c.home/'.agents/skills/context-keeper/SKILL.md','synthetic presence only'))
    c.project_action();c.A('default-repeated','enable-memory','--project',c.project);c.check()

def restore(c):
    c.install();c.project_action();c.project_action(extra=('--no-memory',),label='disable')
    args=['enable-memory','--project',str(c.project),'--memory']
    p=c.A('restore-missing-approval',*args)
    plan=json.loads(p['next_action']);base={k:v for k,v in plan.items() if k not in ('confirmed_at','reference')}
    bad=synthetic_approval(base);bad['main_checkout']=str(c.cwd)
    path=c.area/'wrong-project-approval.json';c.mutate('wrong-project-approval',lambda:dump(path,bad))
    c.A('wrong-project-restore',*args,'--approval-file',path)
    c.A('valid-exact-restore',*args,'--approval-file',c.approve(base,'restore-approval'));c.check()

def native_reference(c,kind):
    c.install(('codex','claude'));c.project_action(extra=('--agent','codex'))
    if kind=='existing-body':c.mutate('existing-claude-body',lambda:write(c.project/'CLAUDE.md',b'custom body\xff\r\n'))
    elif kind=='existing-reference':c.mutate('existing-claude-reference',lambda:write(c.project/'CLAUDE.md',b'custom body\r\n@AGENTS.md\n'))
    c.project_action(extra=('--agent','claude'),label='synthetic-explicit-claude-use')
    c.A('repeated-explicit-claude','enable-memory','--project',c.project,'--agent','claude');c.check()
    c.status='not_in_scope';c.note('Explicit CLI kernel behavior collected. A real Claude first-use/new-session trigger is reserved for M4-10; no synthetic CLI call proves the trigger ran.')

def actual_use(c):
    wb(c);c.install(('codex','claude'));c.project_action(extra=('--agent','codex'))
    c.project_action(extra=('--agent','workbuddy'),label='wb-before-native')
    c.mutate('synthetic-native-appearance',lambda:write(c.project/'.workbuddy/memory/MEMORY.md',b'WB body\xff\r\n'))
    c.project_action(extra=('--agent','workbuddy'),label='wb-after-native');c.check()
    c.status='not_in_scope';c.note('Synthetic explicit CLI demonstrates gated outputs only. Actual execution identity and first-use trigger require M4-10 sessions.')

def bridge(c,kind):
    c.install();c.project_action();p=c.project/'AGENTS.md'
    if kind=='created':
        code=r'''import sys,json
from pathlib import Path
sys.path.insert(0,sys.argv[1])
from agm_core import enable,entries,registry,paths
v=Path(sys.argv[2]);root=Path(sys.argv[3]);home=sys.argv[4]
d=json.loads(v.read_bytes());a=d['projects'][str(root)]['checkouts'][str(root)]
o=next(o for o in a['objects'].values() if o['marker']==enable.KEEPER_MARKER)
old=enable._block(enable.LEGACY_KEEPER_MARKER,'synthetic old CK protocol')
p=root/'AGENTS.md';p.write_bytes(p.read_bytes().replace(enable._block(enable.KEEPER_MARKER,enable.EXPERIENCE_TEXT),old))
o['marker']=enable.LEGACY_KEEPER_MARKER;o['fingerprint']['value']=entries.sha256(old);o['lifecycle']['unit_hex']=old.hex()
v.write_bytes(registry.serialize_registry(d,allowed_user_paths=paths.allowed_user_paths(paths.select_platform(paths.load_agents_table(),'darwin'),None,home=home)))
print(json.dumps({'fixture':'registered created legacy unit, existing original creation-manifest retained; same seed method as test_registered_created_legacy_retired_with_explicit_plan','object':o}))
'''
        c.py('seed-owned-old-bridge',code,str(c.V),str(c.project),str(c.home))
    else:
        old=b'<!-- context-keeper:start -->\nsynthetic reused old CK\n<!-- context-keeper:end -->'
        c.mutate('unregistered-old-bridge',lambda:write(p,p.read_bytes()+b'\nuser prefix\xff\r\n'+old+b'\nuser suffix\r\n'))
        if kind=='duplicate':c.mutate('duplicate-old-bridge',lambda:write(p,p.read_bytes()+b'\n'+old))
        elif kind=='boundary':c.mutate('malformed-old-boundary',lambda:write(p,p.read_bytes().replace(b'<!-- context-keeper:end -->',b'<!-- unclosed -->')))
        elif kind=='retired-product':c.mutate('retired-product-marker',lambda:write(p,p.read_bytes()+b'\n<!-- agent-group-memory:old:start -->\n'))
    if kind in ('created','reused'):c.project_action(label='explicit-old-bridge-retire')
    elif kind=='drift-after-preview':
        r=c.A('old-bridge-plan','enable-memory','--project',c.project);plan=json.loads(r['next_action'])
        a=c.approve({k:v for k,v in plan.items() if k not in ('confirmed_at','reference')})
        c.mutate('old-bridge-drift',lambda:write(p,p.read_bytes().replace(b'synthetic reused old CK',b'changed old CK')))
        c.A('stale-bridge-apply','enable-memory','--project',c.project,'--approval-file',a)
    else:c.A('whole-plan-stop','enable-memory','--project',c.project)
    c.check()

def restart(c):
    disabled(c,'remove')
    c.project_action(extra=('--memory',),label='explicit-restart');c.check('restarted-check')

if __name__=='__main__':
    run_case(23,'显式后装另一执行器',onboard)
    for k in ('absent','hint','unknown'):run_case(24,'absent unknown 与显式选择',lambda c,k=k:absent(c,k),k)
    for k in ('body','edit','duplicate','missing'):run_case(25,'AGENTS 生命周期',lambda c,k=k:agents_life(c,k),k)
    for k in ('pure-created','added-body','existing-reference','missing-creation-proof'):run_case(26,'CLAUDE 生命周期',lambda c,k=k:claude_life(c,k),k)
    run_case(27,'WorkBuddy 合成原生目录与重置',workbuddy)
    for k in ('disable','remove'):run_case(28,'最后消费者停用与保留数据',lambda c,k=k:disabled(c,k),k)
    for present in (False,True):run_case(48,'缺省 follow_ck 幂等',lambda c,p=present:defaults(c,p),'ck-present' if present else 'ck-absent')
    run_case(49,'显式停用后缺省重进',disabled)
    run_case(50,'显式恢复批准边界',restore)
    run_case(56,'created 旧桥接显式替换',lambda c:bridge(c,'created'))
    run_case(57,'reused 旧桥接精确展示与确认',lambda c:bridge(c,'reused'))
    for k in ('duplicate','boundary','retired-product','drift-after-preview'):run_case(58,'旧桥接整停',lambda c,k=k:bridge(c,k),k)
    for k in ('missing','existing-body','existing-reference'):run_case(36,'Claude 实际使用保留至 M4-10',lambda c,k=k:native_reference(c,k),k)
    run_case(59,'已有 Claude 正文补引用内核',lambda c:native_reference(c,'existing-body'))
    run_case(60,'实际使用触发与 CLI 边界',actual_use)
    run_case(61,'菜单停用 remove-memory 路由',lambda c:disabled(c,'remove'))
    run_case(62,'停用层次与显式重启',restart)
