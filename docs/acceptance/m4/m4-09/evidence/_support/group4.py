from collect import *

LEGACY_SEED=r'''import sys,json
from pathlib import Path
sys.path.insert(0,sys.argv[1])
from agm_core import registry
path=Path(sys.argv[2]);schema=int(sys.argv[3]);path.parent.mkdir(parents=True,exist_ok=True)
if schema==1:d={'schema_version':1,'projects':{},'shared_objects':{}}
else:
 d=registry.empty_registry();d['schema_version']=2
 d['product']={'product_id':'agent-group-memory','installation_id':'old-development-machine','product_structure_version':1,'product_code_version':'0.4.0','source':{'url':'fixture://old-development','commit':'a'*40,'tree_sha256':'b'*64},'installation_status':'complete','last_operation_id':'old-op'}
path.write_text(json.dumps(d));print(json.dumps({'fixture_ledger':str(path),'raw':d}))
'''
DIAG=r'''import sys,json
sys.path.insert(0,sys.argv[1])
from agm_core import registry,paths
print(json.dumps(registry.load_diagnostic_registry(sys.argv[2],allowed_user_paths=paths.allowed_user_paths(paths.select_platform(paths.load_agents_table(),'darwin'),None,home=sys.argv[3]))))
'''

def old(c,schema=1,active=False):
    path=c.V if active else c.area/'old-product/scripts/registry.json'
    c.py('seed-legacy-ledger',LEGACY_SEED,str(path),str(schema))
    c.mutate('old-body-sentinel',lambda:write(c.area/'old-product/memories/body.md',b'old user bytes\xff\r\n'))
    if not active:c.mutate('old-request',lambda:dump(c.request,{'app_directories':[],'legacy_registries':[str(path)],'legacy_source_commits':{str(path):'a'*40}}))
    return path

def diagnostic(c,schema,bad=False):
    path=old(c,schema,True)
    if bad:c.mutate('bad-old-fields',lambda:dump(path,{'schema_version':schema,'projects':[]}))
    c.py('diagnostic-old-ledger',DIAG,str(path),str(c.home));c.preview();c.check()
    c.note('§25/§26 replacement: strict read-only diagnosis and refused development-ledger writes. No pre-release schema conversion is claimed.')

def retired(c,n):
    path=old(c,1);c.py('diagnostic',DIAG,str(path),str(c.home))
    c.preview();c.check()
    code=r'''import sys,json
sys.path.insert(0,sys.argv[1])
from agm_core import migrate
from agm_core.layout import resolve_layout
try:
 result=migrate.plan_migration(resolve_layout(sys.argv[2]),[sys.argv[3]])
 print(json.dumps(result))
except Exception as e:
 print(json.dumps({'error_type':type(e).__name__,'code':getattr(e,'code',None),'message':str(e)}));sys.exit(2)
'''
    c.py('explicit-migration-request',code,str(c.home),str(path))
    if n==21:
        c.mutate('old-source-drift',lambda:write(path,path.read_bytes()+b'\n'))
        c.preview('drifted-development-rejected')
        c.note('§26 retires tombstone/old-writer handoff. No concurrent old writer command or lock-transfer success is asserted.')
    if n==22:
        journal=c.area/'old-journal.json';c.mutate('old-journal',lambda:dump(journal,{'schema_version':1,'plan':{'command':'migrate-machine'},'status':'running'}))
        for action in ('continue','rollback'):c.I('old-recovery-'+action,'--recover',journal,'--action',action)
    c.note('§26 replaces old migration promises for cases 19–22. Old development ledgers and journals preserved; no conversion/tombstone chain executed.')

def dual(c,kind):
    c.install();path=old(c,1)
    if kind=='half-migration':
        d=json.loads(c.V.read_bytes());d['migration']={'status':'half','mapping':{}}
        c.mutate(kind,lambda:dump(c.V,d))
    c.preview();c.check()
    c.note('§26 replacement keeps conflict diagnosis and byte preservation; no mtime winner or migration is selected by the collector.')

def formal_gap(c,n):
    c.install();c.check()
    if n==47:
        code=r'''import sys,json,copy
sys.path.insert(0,sys.argv[1])
from agm_core import registry
d=json.load(open(sys.argv[2]))
try:print(json.dumps(registry.validate_registry_v1(d)))
except Exception as e:
 print(json.dumps({'code':getattr(e,'code',None),'type':type(e).__name__,'message':str(e)}));sys.exit(2)
'''
        c.py('old-schema-reader-new-ledger',code,str(c.V))
    c.block('Formal T0/later release identities and approved positive upgrade/rollback pair are not frozen. §26 forbids using development P as substitute; positive formal-release subcases remain blocked. Generic phase/file recovery is separately captured in 10–12.')

if __name__=='__main__':
    for n in (19,21,22):run_case(n,'§26 开发旧账只读与拒绝写入',lambda c,n=n:retired(c,n))
    for k in ('dual-regular','half-migration'):run_case(20,'双账及半迁移冲突',lambda c,k=k:dual(c,k),k)
    for s in (1,2):
        for bad in (False,True):run_case(46,'旧 schema 诊断与升级拒绝',lambda c,s=s,b=bad:diagnostic(c,s,b),f'v{s}-'+('bad-fields' if bad else 'legal'))
    run_case(13,'正式已安装版本主动回退前置缺口',lambda c:formal_gap(c,13))
    run_case(47,'正式前驱与逆 schema 前置缺口',lambda c:formal_gap(c,47))
