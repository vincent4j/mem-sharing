from collect import *

def cold(c):
    c.I('install-help','--help');c.A('agm-help','--help');c.check()
    c.preview()
    code="import json,sys;sys.path.insert(0,sys.argv[1]);import agm_core.user_install,agm_core.upgrade;from agm_core import detect,paths;print(json.dumps(detect.detect_agents(paths.select_platform(paths.load_agents_table(),'darwin'),None,home=sys.argv[2],search_paths=[],app_directories=[])))"
    c.py('imports-and-detection',code,str(c.home))
def fresh(c):
    c.install();c.check()
def noop(c):
    c.install();p=c.preview('same-preview');a=c.approve(p['approval_plan'],'same-approval')
    c.I('same-execute','--approval-file',a);c.preview('same-repeat');c.check()
def uninstalled(c):
    c.A('missing-enable','enable-memory','--project',c.project)
    c.A('missing-remove','remove-memory','--project',c.project);c.check()
    c.signal('codex');p=c.preview()['approval_plan']
    for kind in ('operation_id','source','scene_sha256','requested_agents','changes','confirmed_at','reference'):
        a=synthetic_approval(p)
        if kind=='source':a[kind]['commit']='f'*40
        elif kind=='requested_agents':a[kind]=['claude']
        elif kind=='changes':a[kind]=[]
        elif kind in ('confirmed_at','reference'):a.pop(kind)
        else:a[kind]='wrong-binding'
        path=c.area/(kind+'.json');c.mutate('wrong-'+kind,lambda path=path,a=a:dump(path,a))
        c.I('reject-'+kind,'--approval-file',path)
if __name__=='__main__':
    for n,name,fn in [(1,'冷启动只读',cold),(34,'批准绑定及未安装命令',uninstalled),(2,'全新安装',fresh),(3,'同版零写',noop)]:
        run_case(n,name,fn)
