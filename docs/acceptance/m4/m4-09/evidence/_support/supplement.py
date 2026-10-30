from collect import *
from group5 import agents_life,claude_life

def acquisition_partial(c):
    c.signal('codex')
    cfg=c.area/'local-transport.gitconfig'
    c.mutate('local-only-git-rewrite',lambda:write(cfg,'[url "'+str(REPO)+'"]\n\tinsteadOf = https://github.com/vincent4j/mem-sharing\n'))
    c.env['GIT_CONFIG_GLOBAL']=str(cfg)
    stage=c.area/'acquired-source'
    r=c.I('acquire-preview','--acquire','--staging',stage,'--commit',BASELINE,'--version','0.4.0').get('json',{})
    if 'approval_plan' not in r:c.block('Acquisition preview did not produce plan; inspect raw output.');return
    c.I('acquire-execute','--approval-file',c.approve(r['approval_plan'],'acquisition-approval'))
    checkout=stage/'checkout'
    r=c.I('acquired-install-preview','--source',checkout,'--commit',BASELINE,'--version','0.4.0','--request-file',c.request).get('json',{})
    if 'approval_plan' not in r:c.block('Acquired source did not produce installation plan.');return
    a=c.approve(r['approval_plan'],'main-approval')
    code=r'''import sys,json
sys.path.insert(0,sys.argv[1])
import install
from agm_core import transaction
original=transaction._apply
def controlled_failure(path,snapshot,**kwargs):
 if str(path).endswith('/.codex/AGENTS.md'):
  raise OSError('M4-09 controlled synthetic executor-entry write failure')
 return original(path,snapshot,**kwargs)
transaction._apply=controlled_failure
raise SystemExit(install.main(sys.argv[2:]))
'''
    c.py('acquired-then-entry-failure',code,'--approval-file',str(a))
    c.note('Git insteadOf forces the official acquisition URL to the existing local frozen repository; no network, remote webpage, real credential or Git commit is used. Mid-entry failure is injected only in this child process; source code remains unchanged.')
    c.block('Acquisition/partial underlying reports now executed. Full outer user-facing conversation remains unavailable as documented in 40; no success dialogue fabricated.')

if __name__=='__main__':
    for k in ('edit','duplicate','missing'):
        run_case(25,'AGENTS 漂移拒绝后完整采集重跑',lambda c,k=k:agents_life(c,k),'retry-'+k)
    run_case(26,'CLAUDE 缺创建证据后完整采集重跑',lambda c:claude_life(c,'missing-creation-proof'),'retry-missing-creation-proof')
    run_case(33,'本地获取成功后入口故障原始报告',acquisition_partial,'acquisition-then-entry-failure')
