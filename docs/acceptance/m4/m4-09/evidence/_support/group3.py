from collect import *
from group2 import v0, imported

def conflict(c,kind):
    v0(c)
    if kind=='same-bytes':
        c.mutate('target-same',lambda:write(c.R/'references/same.md',b'handbook\xff\r\n'))
    elif kind=='different-bytes':c.mutate('target-different',lambda:write(c.R/'references/same.md','different'))
    elif kind=='type':c.mutate('target-type',lambda:write(c.R/'memories','file-instead-of-directory'))
    else:c.mutate('occupied-package',lambda:write(c.R/'memories/legacy-v0-fixed/occupied','reserved'))
    c.preview();c.check()
    if kind=='same-bytes':c.block('§23 new nonempty R without V is an unexplained scene: legacy same-byte positive reuse cannot reach the import planner. Raw rejection collected; no invented bypass.')

def drift(c,kind):
    v0(c);c.signal('codex');p=c.preview()['approval_plan'];a=c.approve(p)
    def change():
        if kind=='old-modify':write(c.O/'memories/主题.md','changed')
        elif kind=='old-add':write(c.O/'references/added','added')
        elif kind=='old-delete':(c.O/'memories/主题.md').unlink()
        elif kind=='source-modify':write(c.source/'scripts/agm.py','print("changed source")\n')
        elif kind=='source-delete':(c.source/'scripts/agm.py').unlink()
        else:write(c.source/'scripts/new-file.py','print("unlisted")\n')
    c.mutate(kind,change);c.I('apply-stale-approval','--approval-file',a)
    c.note('Source uses frozen export manifest. Added unlisted source files are outside that manifest; this branch is recorded independently from checkout cleanliness.')

def links(c,kind):
    v0(c);sentinel=c.area/'outside/sentinel';c.mutate('outside-sentinel',lambda:write(sentinel,b'outside\xff\r\n'))
    targets={'external':'../../../outside/sentinel','absolute':str(sentinel),'dangling':'missing',
      'internal':'../references/手册.md','escape-reentry':'../../.agents-group/references/手册.md'}
    c.mutate('link-'+kind,lambda:(c.O/'memories/link').symlink_to(targets[kind]))
    p=c.preview()
    if kind=='internal' and 'approval_plan' in p:
        c.I('allowed-internal-apply','--approval-file',c.approve(p['approval_plan']))
    c.check()

def special(c,kind):
    if kind in ('independent-code','dirty-code','foreign-code'):
        if kind=='independent-code':c.mutate(kind,lambda:write(c.C/'README.md','independent checkout sentinel'))
        else:
            c.install()
            if kind=='dirty-code':c.mutate(kind,lambda:write(c.C/'scripts/agm.py','print("user edit")\n'))
            else:
                m=c.C/'.agm-code-manifest.json';d=json.loads(m.read_bytes());d['product_id']='other'
                c.mutate(kind,lambda:dump(m,d))
    elif kind in ('case-collision','unicode-collision','traversal'):
        info=copy.deepcopy(c.source_info)
        if kind=='traversal':info['files']['../outside']=sha(b'never dereference')
        else:
            name='scripts/AGM.py' if kind=='case-collision' else 'scripts/e\u0301.py'
            original='scripts/agm.py' if kind=='case-collision' else 'scripts/é.py'
            c.mutate('collision-original',lambda:write(c.source/original,'# same\n'))
            c.mutate('collision-name',lambda:write(c.source/name,'# same\n'))
            info['files'][original]=sha((c.source/original).read_bytes());info['files'][name]=sha((c.source/name).read_bytes())
        c.mutate('unsafe-manifest',lambda:dump(c.manifest,info))
    else:
        v0(c)
        if kind=='cycle':
            c.mutate(kind,lambda:((c.O/'memories/a').symlink_to('b'),(c.O/'memories/b').symlink_to('a')))
        else:c.mutate(kind,lambda:os.mkfifo(c.O/'memories/pipe'))
    c.preview()

if __name__=='__main__':
    run_case(14,'同名索引、相对链接与旧失效链接',imported)
    for k in ('same-bytes','different-bytes','type','occupied-package'):
        run_case(15,'目标冲突',lambda c,k=k:conflict(c,k),k)
    for k in ('old-modify','old-add','old-delete','source-modify','source-add','source-delete'):
        run_case(16,'批准后源漂移',lambda c,k=k:drift(c,k),k)
    for k in ('external','absolute','dangling','internal','escape-reentry'):
        run_case(17,'链接边界',lambda c,k=k:links(c,k),k)
    for k in ('cycle','fifo','case-collision','unicode-collision','traversal','independent-code','dirty-code','foreign-code'):
        run_case(18,'特殊路径和源码占位',lambda c,k=k:special(c,k),k)
