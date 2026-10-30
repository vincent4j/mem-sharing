from collect import *
from group5 import wb
from group6 import ORG,org_preview

def organizer_unblocked(c):
    c.install()
    def seed():
        write(c.R/'memories/communication.md','# 沟通\n\n## L1 概要\n\n回答应简洁明确。\n\n## L2 原文\n\n- 回答应简洁明确。\n')
        for a,n in (('codex','AGENTS.md'),('claude','CLAUDE.md'),('workbuddy','MEMORY.md')):
            p=c.home/('.'+a)/n;raw=p.read_bytes() if p.exists() else b''
            write(p,raw+('\n\n- 提交信息请使用简体中文。\r\n- '+a+' 专属：使用专用执行器路径。\r\n- 回答应简洁明确。\r\n').encode())
    c.mutate('three-private-files-without-registered-wholefile-import',seed)
    req=c.area/'organize-request.json';c.mutate('organize-request',lambda:dump(req,{'home':str(c.home),'date':'2026-10-31'}))
    original=org_preview(c,req)['approval_plan']
    decisions={i['item_id']:{'action':'keep'} for i in original['items'] if i['classification']=='疑似冗余'}
    c.mutate('reviewed-decisions',lambda:dump(req,{'home':str(c.home),'date':'2026-10-31','decisions':decisions}))
    revised=org_preview(c,req,'reviewed-plan')['approval_plan']
    c.py('execute-reviewed-central-approval',ORG,str(req),str(c.approve(revised,'central-approval')))
    org_preview(c,req,'repeat-plan')
    c.note('Original 37 also preserved a genuine whole-file Claude-import conflict. This separate fixture has only a Codex machine registration; Claude/WB private rule files are synthetic unregistered preexisting content, so their full-file import gate is not present.')

def batch_partial(c):
    c.install();scan=c.area/'partial-scan';scan.mkdir()
    for name in ('a','b','c'):c.cmd('git-init-'+name,['/usr/bin/git','init','-q',scan/name])
    args=['enable-memory-batch','--directory',str(scan)]
    p=c.A('partial-batch-preview',*args);plan=json.loads(p['next_action'])
    a=c.approve({k:v for k,v in plan.items() if k not in ('confirmed_at','reference')},'batch-approval')
    code=r'''import sys
sys.path.insert(0,sys.argv[1])
import agm
from agm_core import detect,transaction
detect.STANDARD_APP_DIRECTORIES=()
original=transaction._apply
def fail_b(path,snapshot,**kwargs):
 if str(path).endswith('/b/AGENTS.md'):raise OSError('M4-09 synthetic second-project write failure')
 return original(path,snapshot,**kwargs)
transaction._apply=fail_b
raise SystemExit(agm.main(sys.argv[2:]))
'''
    c.py('partial-batch-execute',code,*args,'--approval-file',str(a))
    c.A('partial-batch-readback',*args)
    c.note('Second-project failure injected in one subprocess only; first-project and not-started third-project raw states remain in output. No cross-project atomicity claim.')

def three_templates(c):
    wb(c);c.install(('codex','claude'));c.project_action()
    c.cmd('read-three-user-entries-and-protocol',['/bin/cat',c.home/'.codex/AGENTS.md',c.home/'.claude/CLAUDE.md',c.home/'.workbuddy/MEMORY.md',c.project/'AGENTS.md',c.R/'memories/MEMORY.md',c.R/'memories/topics/使用约定.md'])

def keep_auto_rules(c):
    c.install();c.project_action()
    p=c.project/'AGENTS.md'
    c.mutate('preexisting-unmanaged-ck-auto-instructions',lambda:write(p,p.read_bytes()+'\n用户保留的旧 CK 自动规则：阶段完成后自动保存项目经历。\r\n'.encode()))
    c.project_action(extra=('--no-memory',),label='disable-with-existing-auto-text')
    c.A('default-reenter','enable-memory','--project',c.project);c.check()
    c.note('Synthetic unmanaged automatic-recording paragraph is retained. Whether a real agent obeys the higher-priority denial guard needs M4-10; this record proves only file/ledger behavior.')

if __name__=='__main__':
    run_case(37,'无整文件占用的三家私有规则集中审批',organizer_unblocked,'unblocked-three-private-files')
    run_case(39,'第二项目故障与先前项目保留',batch_partial,'injected-second-project-failure')
    run_case(32,'三家合成用户入口与短协议原文',three_templates,'three-synthetic-executors')
    run_case(49,'保留旧自动记录正文后显式停用',keep_auto_rules,'preexisting-auto-rule-body')
