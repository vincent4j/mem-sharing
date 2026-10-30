from collect import *
import re

ORG=r'''import sys,json
sys.path.insert(0,sys.argv[1])
from agm_core import user_rules_organize as org,paths
request=json.load(open(sys.argv[2]));request['platform_config']=paths.select_platform(paths.load_agents_table(),'darwin')
result=org.plan_organize(request)
if sys.argv[3]!='preview':
 approval=json.load(open(sys.argv[3]));plan={k:v for k,v in approval.items() if k not in ('confirmed_at','reference')}
 result=org.execute_organize(plan,approval,request=request)
print(json.dumps(result,ensure_ascii=False))
'''
def org_seed(c):
    c.install(('codex','claude'))
    def seed():
        write(c.R/'memories/communication.md','# 沟通\n\n## L1 概要\n\n回答应简洁明确。\n\n## L2 原文\n\n- 回答应简洁明确。\n')
        for agent,name in (('codex','AGENTS.md'),('claude','CLAUDE.md'),('workbuddy','MEMORY.md')):
            p=c.home/('.'+agent)/name
            raw=p.read_bytes() if p.exists() else b''
            write(p,raw+('\n\n- 提交信息请使用简体中文。\r\n- '+agent+' 专属：使用专用执行器路径。\r\n- 回答应简洁明确。\r\n- 未明确归属的 abc 约定。\r\n').encode())
    c.mutate('organizer-mixed-content',seed)
    req=c.area/'organize-request.json';c.mutate('organize-request',lambda:dump(req,{'home':str(c.home),'date':'2026-10-31'}))
    return req
def org_preview(c,req,label='organize-preview'):
    return c.py(label,ORG,str(req),'preview').get('json',{})
def organize(c):
    req=org_seed(c);p=org_preview(c,req)['approval_plan']
    decisions={i['item_id']:{'action':'keep'} for i in p['items'] if i['classification']=='疑似冗余'}
    c.mutate('decisions-before-approval',lambda:dump(req,{'home':str(c.home),'date':'2026-10-31','decisions':decisions}))
    revised=org_preview(c,req,'revised-decisions')['approval_plan']
    c.py('execute-central-approval',ORG,str(req),str(c.approve(revised,'central-approval')))
    org_preview(c,req,'repeat-organize')
def organize_reject(c,kind):
    req=org_seed(c)
    if kind=='blocked-wholefile':
        code=r'''import sys,json
from pathlib import Path
sys.path.insert(0,sys.argv[1])
from agm_core import registry,paths,entries
v=Path(sys.argv[2]);p=Path(sys.argv[3]);home=sys.argv[4];d=json.loads(v.read_bytes())
d['machine']['objects']['synthetic-old-import']={'kind':'import','path':str(p),'scope':'machine','agents':['codex'],'ownership':'reused','marker':None,'fingerprint':{'algorithm':'sha256','basis':'file_bytes','value':entries.sha256(p.read_bytes())},'original_existed':True,'link_target':None,'backup_manifest':None,'consumers':[]}
v.write_bytes(registry.serialize_registry(d,allowed_user_paths=paths.allowed_user_paths(paths.select_platform(paths.load_agents_table(),'darwin'),None,home=home)));print(json.dumps({'seeded':'old whole-file reused import'}))
'''
        c.py('seed-old-wholefile-import',code,str(c.V),str(c.home/'.codex/AGENTS.md'),str(c.home))
    p=org_preview(c,req)['approval_plan'];a=c.approve(p)
    if kind=='source-drift':c.mutate(kind,lambda:write(c.home/'.codex/AGENTS.md',(c.home/'.codex/AGENTS.md').read_bytes()+b'new source body\n'))
    elif kind=='changed-decisions':
        decisions={i['item_id']:{'action':'keep'} for i in p['items'] if i['classification']=='公共'}
        c.mutate(kind,lambda:dump(req,{'home':str(c.home),'date':'2026-10-31','decisions':decisions}))
        org_preview(c,req,'new-plan-after-decisions')
    elif kind=='missing-confirmation':
        d=json.loads(a.read_bytes());d.pop('reference');c.mutate(kind,lambda:dump(a,d))
    c.py('organize-rejected-execution',ORG,str(req),str(a))

def git_worktree(c,scan):
    base=scan/'linked-main';linked=scan/'linked-worktree'
    c.cmd('init-worktree-base',['/usr/bin/git','init','-q',base])
    c.cmd('fetch-local-frozen-object',['/usr/bin/git','-C',base,'fetch','--quiet','--depth=1',REPO,BASELINE])
    c.cmd('read-tree-local-frozen-object',['/usr/bin/git','-C',base,'reset','--quiet','--hard','FETCH_HEAD'])
    c.cmd('create-linked-worktree',['/usr/bin/git','-C',base,'worktree','add','--quiet','--detach',linked,'FETCH_HEAD'])
    return linked
def batch(c):
    c.install();scan=c.area/'scan';scan.mkdir()
    for name in ('new-a','new-b','already-enabled','drifted'):
        c.cmd('init-'+name,['/usr/bin/git','init','-q',scan/name])
    c.mutate('non-git-and-unselected',lambda:(write(scan/'not-git/readme','not git'),write(c.area/'unselected/sentinel','outside scan')))
    old=c.project
    for name in ('already-enabled','drifted'):
        c.project=scan/name;c.project_action(label='pre-enable-'+name)
    drifted=scan/'drifted/AGENTS.md';c.mutate('registered-project-drift',lambda:write(drifted,drifted.read_bytes().replace('职责'.encode(),b'changed')))
    c.project=old;git_worktree(c,scan)
    args=['enable-memory-batch','--directory',str(scan)]
    p=c.A('batch-preview',*args)
    if p.get('approval_required'):
        plan=json.loads(p['next_action']);a=c.approve({k:v for k,v in plan.items() if k not in ('confirmed_at','reference')},'batch-approval')
        c.A('batch-apply',*args,'--approval-file',a)
    c.A('batch-readback',*args)

def default_scope(c,kind):
    c.install()
    if kind=='existing-body':c.mutate(kind,lambda:write(c.project/'AGENTS.md',b'project user body\xff\r\n'))
    if kind=='non-git':c.project=c.cwd
    elif kind=='worktree':c.project=git_worktree(c,c.area/'worktree-scan')
    c.project_action();c.A('reenter','enable-memory','--project',c.project);c.check()
    c.status='not_in_scope';c.note('Synthetic explicit kernel calls captured; automatic default-enable trigger in real Agent session is M4-10 scope. No new Agent session was started.')

def ck_activation(c,kind):
    c.install()
    if kind=='custom-store':c.mutate(kind,lambda:write(c.project/'custom-ck-store/worklogs/old.md',b'existing custom data\xff\r\n'))
    if kind=='user-presence':c.mutate(kind,lambda:write(c.home/'.agents/skills/context-keeper/SKILL.md','synthetic user presence only'))
    c.project_action();c.check()
    c.block('memSharing enable/check collected. Real first /context-keeper activation needs CK own frozen source/interaction; upstream is outside this write set and real-session activation stays M4-10. No substitute CK initialization performed.')

def docs(c,n):
    c.cmd('documentation-map-read',['/bin/cat',c.source/'llms.txt'])
    code=r'''import sys,re,json,hashlib
from pathlib import Path
root=Path(sys.argv[2]);raw=(root/'llms.txt').read_text()
for target in re.findall(r'\]\(([^)]+)\)',raw):
 p=root/target
 if p.is_file():
  data=p.read_bytes();print(json.dumps({'path':target,'length':len(data),'sha256':hashlib.sha256(data).hexdigest(),'body':data.decode('utf-8','replace')},ensure_ascii=False))
 else:print(json.dumps({'path':target,'exists':p.exists(),'is_file':False}))
'''
    c.py('read-map-every-linked-file',code,str(c.source))
    if n==44:
        for name in ('README.md','INSTALL.md','SKILL.md','docs/acceptance/m4/m4-09/cases.md','docs/plan/decisions-m4.md'):
            c.cmd('read-'+name.replace('/','-'),['/bin/cat',c.source/name])
        c.note('Current §24–§26 and DESIGN v1.14 supersede old v1.13 expectations. Full raw document bodies supplied; no automated semantic acceptance verdict.')

def templates(c):
    c.install(('codex','claude'));c.project_action()
    c.cmd('read-installed-templates',['/bin/cat',c.R/'memories/MEMORY.md',c.R/'memories/topics/使用约定.md',c.home/'.codex/AGENTS.md',c.home/'.claude/CLAUDE.md',c.project/'AGENTS.md'])
    c.note('Two verified synthetic package installations. WorkBuddy static template is available in source blobs; three real native executors/new sessions were not invoked.')

def naming(c,kind):
    c.install();c.project_action()
    if kind=='old-product-id':
        d=json.loads(c.V.read_bytes());d['product']['product_id']='agent-group-memory';c.mutate(kind,lambda:dump(c.V,d))
    elif kind=='old-markers':c.mutate(kind,lambda:write(c.project/'AGENTS.md',(c.project/'AGENTS.md').read_bytes()+b'\n<!-- agent-group-memory:old:start -->\n'))
    elif kind=='old-ledger':
        c.mutate(kind,lambda:write(c.source/'scripts/registry.json','{"schema_version":1,"projects":{},"shared_objects":{}}'))
    c.preview('naming-install-preview');c.A('naming-enable-preview','enable-memory','--project',c.project);c.check()

def runtimes(c,n,kind):
    if n==29:
        (c.bin/'git').unlink();env=dict(c.env,PATH=str(c.bin))
        c.cmd('missing-git-diagnostic',[PYTHON,'-B',c.source/'scripts/install.py','--source-manifest',c.manifest,'--request-file',c.request],env=env)
        c.block('PATH-only missing-Git branch collected. INSTALL assigns package-manager installation to outer Agent orchestration; no frozen isolated OS/package-manager route. Real macOS dependency/permission scenarios not executed.')
    else:
        if kind=='current':c.preview('current-compatible-python')
        elif kind in ('3.9','3.8'):
            code="import sys;sys.path.insert(0,sys.argv[1]);import install;sys.version_info="+repr((3,int(kind.split('.')[1]),0))+";raise SystemExit(install.main(sys.argv[2:]))"
            c.py('simulated-version-'+kind,code,'--source-manifest',str(c.manifest),'--request-file',str(c.request))
        else:c.cmd('path-without-python',['/bin/sh','-c','command -v python3'],env=dict(c.env,PATH=str(c.bin)))
        c.block('Only current interpreter and controlled version/PATH branch simulation collected. No separate real Python 3.9/older/missing-OS interpreter environment or outer package-manager installation is frozen; cannot claim real runtime coverage.')

def dialogue(c):
    c.install();c.check()
    c.cmd('read-outer-dialogue-contract',['/bin/cat',c.source/'INSTALL.md'])
    c.block('Outer first-sentence/environment-summary/one-confirmation dialogue is an Agent procedure in INSTALL, not a frozen executable harness. CLI EOF installation output collected; no real user dialogue or dependency-install flow invented.')

def reports(c,kind):
    if kind=='no-installed':c.install(())
    elif kind=='static-success':c.install()
    else:
        c.signal('codex')
        c.mutate('entry-conflict',lambda:write(c.home/'.codex/AGENTS.md','<!-- mem-sharing:public-source:start -->\nambiguous\n'))
        c.preview('entry-conflict-preview')
        c.block('Entry preflight conflict output collected. Acquisition-success then mid-onboarding-failure outer conversation needs the separate acquisition fixture; no download or success dialogue fabricated.')

if __name__=='__main__':
    run_case(37,'用户规则整理集中审批',organize)
    for k in ('blocked-wholefile','source-drift','missing-confirmation','changed-decisions'):run_case(38,'整理向导拒绝边界',lambda c,k=k:organize_reject(c,k),k)
    run_case(39,'批量扫描和批准执行',batch)
    for k in ('empty','existing-body','non-git','worktree'):run_case(35,'默认启用合成内核与真实触发边界',lambda c,k=k:default_scope(c,k),k)
    for k in ('absent','user-presence','custom-store'):run_case(42,'CK 按需激活前置边界',lambda c,k=k:ck_activation(c,k),k)
    run_case(31,'LLM 文档地图原文',lambda c:docs(c,31))
    run_case(32,'分层索引和规则模板',templates)
    for k in ('no-installed','static-success','entry-failure'):run_case(33,'底层安装与用户报告边界',lambda c,k=k:reports(c,k),k)
    for k in ('fresh','old-product-id','old-markers','old-ledger'):run_case(43,'新标识与旧现场拒绝',lambda c,k=k:naming(c,k),k)
    run_case(44,'文档合同原始材料',lambda c:docs(c,44))
    run_case(29,'缺 Git 诊断及外层安装缺口',lambda c:runtimes(c,29,'missing'))
    for k in ('3.9','current','3.8','missing'):run_case(30,'Python 版本和运行时环境',lambda c,k=k:runtimes(c,30,k),k)
    run_case(40,'安装对话与外层执行边界',dialogue)
