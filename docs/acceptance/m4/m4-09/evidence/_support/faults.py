from collect import *

PLAN_CODE=r'''import json,sys
from pathlib import Path
sys.path.insert(0,sys.argv[1])
from agm_core import paths,user_install,upgrade
home=Path(sys.argv[2]);manifest=Path(sys.argv[3]);out=Path(sys.argv[4])
req={'home':str(home),'platform_config':paths.select_platform(paths.load_agents_table(),'darwin'),
 'source':json.loads(manifest.read_bytes()),'app_directories':[],'operation_id':'synthetic-fault-upgrade'}
old=json.loads((home/'.mem-sharing/var/registry.json').read_bytes())['product']
target,_=user_install._source(req)
req['conversions']=[{'before':{'schema_version':3,'product_structure_version':1,'product_code_version':old['product_code_version'],'source':old['source']},
 'after':{'schema_version':3,'product_structure_version':1,'product_code_version':target['version'],'source':{k:target[k] for k in ('url','commit','tree_sha256')}},'direction':'upgrade','entries':'preserve'}]
plan=upgrade.plan_upgrade(req)
(out.parent/'upgrade-request.json').write_text(json.dumps(req))
out.write_text(json.dumps(plan));print(json.dumps(plan))
'''
CRASH_CODE=r'''import json,sys,os
sys.path.insert(0,sys.argv[1])
from agm_core import upgrade
plan=json.load(open(sys.argv[2]));approval=json.load(open(sys.argv[3]))
event=sys.argv[4];suffix=sys.argv[5]
def hook(stage,path):
 print(json.dumps({'event':stage,'path':str(path),'pid':os.getpid()}),flush=True)
 if stage==event and (not suffix or str(path).endswith(suffix)):os._exit(86)
from pathlib import Path
req=json.loads((Path(sys.argv[2]).parent/'upgrade-request.json').read_bytes())
print(json.dumps(upgrade.execute_upgrade(plan,approval,request=req,hook=hook)))
'''

def upgrade_plan(c):
    c.install()
    target=c.area/'target-source'
    c.mutate('synthetic-target-source',lambda:shutil.copytree(c.source,target))
    c.mutate('synthetic-target-delta',lambda:(write(target/'README.md',(target/'README.md').read_bytes()+b'\nSynthetic fault-window revision.\n'),write(target/'scripts/agm_core/evidence_revision.py','REVISION = "synthetic-fault-target"\n')))
    info=copy.deepcopy(c.source_info);info.update(root=str(target),version='0.4.1',commit=sha(b'synthetic-fault-target')[:40])
    info['files']={rel:sha((target/rel).read_bytes()) for rel in info['files']}
    info['files']['scripts/agm_core/evidence_revision.py']=sha((target/'scripts/agm_core/evidence_revision.py').read_bytes())
    manifest=c.area/'target.json';c.mutate('target-manifest',lambda:dump(manifest,info))
    planpath=c.area/'upgrade-plan.json'
    result=c.py('kernel-upgrade-plan',PLAN_CODE,str(c.home),str(manifest),str(planpath))
    c.note('§26 generic recovery exercise only: original baseline code plus an explicitly synthetic README/module delta, exact manifest conversion injected to the existing upgrade kernel. Synthetic commit is not a Git release identity and this is not evidence for a frozen T0→release upgrade.')
    return result.get('json'),planpath

def crash(c,event,suffix=''):
    p,path=upgrade_plan(c)
    if not p:raise RuntimeError('No upgrade plan in raw output')
    a=c.approve(p,'fault-approval')
    c.py('hard-exit-'+event.replace(':','-'),CRASH_CODE,str(path),str(a),event,suffix)
    return p

def recovery(c,p,action,fixed=False):
    j=p['journal']
    if fixed:
        script=Path(p['bootstrap'])/'recover.py'
        preview=c.cmd('fixed-recovery-preview',[PYTHON,'-B',script,'preview',j,action]).get('json',{})
        if 'command' in preview:
            a=c.approve(preview,'recovery-approval')
            c.cmd('fixed-recovery-apply',[PYTHON,'-B',script,'apply',a])
    else:
        r=c.I('recover-preview','--recover',j,'--action',action).get('json',{})
        if 'approval_plan' in r:
            a=c.approve(r['approval_plan'],'recovery-approval')
            c.I('recover-apply','--recover',j,'--action',action,'--approval-file',a)

def phase(c,event,action):
    p=crash(c,event);c.preview('ordinary-after-crash');c.check('check-after-crash')
    recovery(c,p,action);c.check('check-after-recovery')

def window(c,event,suffix):
    p=crash(c,event,suffix)
    c.mutate('make-original-sources-inaccessible',lambda:((c.area/'source').rename(c.area/'source-unavailable'),(c.area/'target-source').rename(c.area/'target-unavailable')))
    recovery(c,p,'continue',fixed=True)
    c.note('Original source paths renamed inside this synthetic area; fixed bootstrap tool uses its own copied dependency tree. Preserved sources are at source-unavailable and target-unavailable.')

def refusal(c,kind):
    p=crash(c,'after_registry_commit' if kind=='committed-mixed' else 'after_phase:code')
    if kind in ('third-state','committed-mixed'):
        c.mutate(kind,lambda:write(c.C/'README.md','external third state'))
    elif kind=='backup':
        path=Path(p['archive'])/'registry-before.json';c.mutate(kind,lambda:(path.chmod(0o600),write(path,'broken backup')))
    elif kind=='toolkit':
        path=Path(p['bootstrap'])/'tools/agm_core/upgrade.py';c.mutate(kind,lambda:write(path,'# toolkit drift\n'))
    elif kind in ('active-pid','unknown-owner'):
        path=c.home/'.mem-sharing-install.lock/migration-owner.json'
        def change():
            d=json.loads(path.read_bytes())
            if kind=='active-pid':d['pid']=os.getpid()
            else:d.pop('pid')
            dump(path,d)
        c.mutate(kind,change)
    c.preview('ordinary-refusal');recovery(c,p,'continue')
    if kind=='missing-approval':c.I('recover-without-approval','--recover',p['journal'],'--action','continue')

if __name__=='__main__':
    mode=sys.argv[1] if len(sys.argv)>1 else 'phase'
    if mode=='phase':
        for stage in ('prepare','archive','inventory','code','verify','commit'):
            for when in ('before','after'):
                for action in ('continue','rollback'):
                    event=when+'_phase:'+stage
                    run_case(10,'六阶段独立硬退出与恢复',lambda c,e=event,a=action:phase(c,e,a),'retry-'+when+'-'+stage+'-'+action)
    elif mode=='window':
        windows=[('before_version_rename',''),('after_version_rename',''),('before_registry_commit',''),('after_registry_commit','')]
        for rel in ('.agm-code-manifest.json','README.md','scripts/agm_core/evidence_revision.py'):
            windows.extend((event,rel) for event in ('before_code_replace','after_code_replace'))
        for i,(event,suffix) in enumerate(windows,1):
            run_case(11,'库存 rename、逐文件替换、V 提交窗口',lambda c,e=event,s=suffix:window(c,e,s),f'{i:02d}-{event}')
    else:
        for k in ('third-state','backup','toolkit','active-pid','unknown-owner','committed-mixed','missing-approval'):
            run_case(12,'恢复拒绝与批准锁',lambda c,k=k:refusal(c,k),k)
