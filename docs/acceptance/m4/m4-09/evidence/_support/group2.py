from collect import *

def v0(c):
    def seed():
        write(c.O/'memories/MEMORY.md','# 合成旧索引\n\n[主题](./主题.md) [手册](../references/手册.md) [旧失效](./missing.md)\n')
        write(c.O/'memories/主题.md','synthetic user text\r\n')
        write(c.O/'references/手册.md',b'handbook\xff\r\n')
        (c.O/'memories/relative').symlink_to('主题.md')
        for rel in ('skills/independent/SKILL.md','mcp/config.json','scripts/never-run.py','.sync-state.json'):
            write(c.O/rel,'synthetic excluded sentinel\n')
    c.mutate('v0-seed',seed)

def identity(c,kind):
    v0(c)
    if kind=='target-unknown':c.mutate(kind,lambda:write(c.R/'unknown','target sentinel'))
    inp={'app_directories':[]}
    if kind!='unanswered' and kind!='target-unknown':inp['legacy_identity']={'denied':'not_v0','uncertain':'unknown','confirmed':'confirmed_v0'}[kind]
    c.mutate('identity-request',lambda:dump(c.request,inp));c.preview();c.check()

def imported(c):
    v0(c);c.mutate('confirmed-v0',lambda:dump(c.request,{'app_directories':[],'legacy_identity':'confirmed_v0'}))
    c.install();c.preview('repeat-import-preview');c.check()

def devrefusal(c):
    c.install();d=json.loads(c.V.read_bytes());d['product']['product_code_version']='0.4.0-dev'
    c.mutate('development-version',lambda:dump(c.V,d));c.preview();c.check()
    c.block('§26 replaces pre-release P chain with development-version refusal. Real formal T0/later release identities are not frozen in this checkout; positive formal-upgrade subcase cannot execute.')

def future(c,kind):
    c.install();d=json.loads(c.V.read_bytes())
    if kind=='schema':d['schema_version']=99
    elif kind=='structure':d['product']['product_structure_version']=99
    elif kind=='code':d['product']['product_code_version']='99.0.0'
    elif kind=='unknown-predecessor':d['product']['source']['commit']='c'*40
    else:d['product']['source']['url']='fixture://unverifiable'
    c.mutate('future-'+kind,lambda:dump(c.V,d));c.preview();c.check()

def broken(c,kind):
    c.install();d=json.loads(c.V.read_bytes())
    if kind=='bad-json':raw=b'{broken\xff'
    elif kind=='duplicate':raw=c.V.read_bytes().replace(b'"schema_version": 3',b'"schema_version": 3, "schema_version": 3')
    else:
        if kind=='missing':d.pop('machine')
        elif kind=='type':d['projects']=[]
        elif kind=='identity':d['product']['product_id']='other'
        else:
            obj=next(o for o in d['machine']['objects'].values() if o['ownership']=='created')
            obj['backup_manifest']=None
        raw=json.dumps(d).encode()
    c.mutate('bad-ledger-'+kind,lambda:write(c.V,raw));c.preview();c.check()

def interrupted(c,kind):
    if kind=='unfinished-journal':
        c.mutate(kind,lambda:dump(c.home/'.mem-sharing-install-pending/journal.json',{'status':'running','product_id':'mem-sharing'}))
    elif kind=='lock':c.mutate(kind,lambda:(c.home/'.mem-sharing-install.lock').mkdir())
    elif kind=='staging':c.mutate(kind,lambda:write(c.home/'.mem-sharing-install-staging/target/file','pending'))
    else:
        c.install();j=next(c.home.glob('.mem-sharing-install-*/journal.json'));d=json.loads(j.read_bytes());d['status']='outputs_verified'
        c.mutate(kind,lambda:dump(j,d))
    c.preview();c.check()

def schema3(c):
    c.install();c.project_action();c.check()
    c.py('read-schema-and-plan',"import json,sys;print(json.dumps(json.load(open(sys.argv[2])),ensure_ascii=False))",str(c.V))

if __name__=='__main__':
    for kind in ('unanswered','denied','confirmed','uncertain','target-unknown'):
        run_case(4,'v0 身份边界',lambda c,k=kind:identity(c,k),kind)
    run_case(5,'v0 分离源一次复制',imported)
    run_case(6,'§26 开发版拒绝与正式前驱缺口',devrefusal)
    for kind in ('schema','structure','code','unknown-predecessor','unverifiable'):
        run_case(7,'未来与未知版本',lambda c,k=kind:future(c,k),kind)
    for kind in ('bad-json','duplicate','missing','type','identity','created-evidence'):
        run_case(8,'坏台账',lambda c,k=kind:broken(c,k),kind)
    for kind in ('unfinished-journal','lock','staging','committed-unclosed'):
        run_case(9,'中断普通入口',lambda c,k=kind:interrupted(c,k),kind)
    run_case(45,'schema 3 活动基线',schema3)
