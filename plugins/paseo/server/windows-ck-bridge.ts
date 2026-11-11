// Calls the verified upstream installer; no Context Keeper source is bundled.
// Shares the preview writer lock and rebases only its two native rule snapshots.
export const WINDOWS_CK_BRIDGE = String.raw`
import sys,json,os,io,importlib.util,contextlib,uuid
from pathlib import Path
request=json.load(sys.stdin)
sys.path.insert(0,sys.argv[1])
from agm_core import windows_preview as p
home=p.absolute(request['home']);source=Path(request['ck_source'])
if sys.platform!='win32': raise ValueError('Windows Host required')
p.guard(home);p.guard(source)
spec=importlib.util.spec_from_file_location('verified_ck_installer',source/'scripts/install.py')
ck=importlib.util.module_from_spec(spec);spec.loader.exec_module(ck)
class MemoryFile:
 def __init__(self,raw): self.raw=raw;self.parent=self
 def exists(self): return self.raw is not None
 def read_bytes(self): return self.raw
 def write_bytes(self,raw): self.raw=raw
 def mkdir(self,**kwargs): pass
def rendered(raw,agent):
 f=MemoryFile(raw);ck._upsert_bridge(f,agent);return f.raw
# Windows volume identities can exceed JavaScript safe integers. Keep them
# as decimal strings across the Python -> RPC -> Python approval boundary.
def alias(path):
 # A CK target may be a junction, but its parents must remain real directories.
 p.guard(path.parent)
 if not os.path.lexists(path): return {'kind':'absent'}
 if ck._is_alias(path) and path.resolve()==source.resolve():
  s=path.lstat();return {'kind':'alias','target':str(path.resolve()),'ino':str(s.st_ino),'dev':str(s.st_dev)}
 raise ValueError('Context Keeper target belongs to another source: '+str(path))
def operations_root():
 root=home/'.mem-sharing-ck-operations';p.guard(root)
 if root.exists():
  for node in root.iterdir():
   p.guard(node);journal=node/'journal.json';p.guard(journal)
   if not journal.is_file() or json.loads(journal.read_bytes()).get('status') not in ('committed','rolled_back'):
    raise ValueError('Context Keeper operation needs inspection: '+str(node))
 return root
def plan(run_id):
 operations_root();p.exit_plan(home)
 receipt,before=p.load_receipt(home)
 if receipt['source_files']!=p.source_manifest(Path(sys.argv[1]).parent): raise ValueError('Preview source changed')
 parser=ck.build_parser();flags={x for a in parser._actions for x in a.option_strings}
 agents=['zcode','workbuddy'];supported=[a for a in agents if '--'+a in flags];skipped=[a for a in agents if a not in supported]
 if not supported: raise ValueError('Upstream installer supports neither client')
 args=['--'+a for a in supported];out=io.StringIO()
 with contextlib.redirect_stdout(out): rc=ck.main(args)
 preview=json.loads(out.getvalue())
 if rc!=0 or preview.get('approval_required') is not True: raise ValueError('Invalid upstream preview')
 expected_skills=sorted({str(r/'context-keeper') for a in supported for r in ck._skill_roots(a,home,None)})
 rules={str(ck._bridge_path(a,home,user=True)):a for a in supported}
 allowed_rules={str(home/'.zcode/AGENTS.md'),str(home/'.workbuddy/MEMORY.md')}
 allowed_skills={str(home/n/'context-keeper') for n in ('.zcode/skills','.agents/skills','.workbuddy/skills')}
 if set(rules)-allowed_rules or set(expected_skills)-allowed_skills: raise ValueError('Upstream target scope changed')
 if sorted(preview['skill_entries'])!=expected_skills or set(preview['rule_files'])!=set(rules): raise ValueError('Upstream preview targets differ')
 links={name:alias(Path(name)) for name in expected_skills};files={};originals={}
 for name,agent in rules.items():
  f=Path(name);snap=p.snap(f);after=rendered(snap.data,agent)
  rel=f.relative_to(home).as_posix();meta=receipt['native'][rel]
  old=p.unpacked(meta['before']);new_original=rendered(old.data,agent)
  files[name]={'before':p.packed(snap),'after':p.packed(p.file_snapshot(after,snap))}
  originals[rel]={'before':p.packed(p.file_snapshot(new_original,old)),'installed_sha256':p.digest(after)}
 updated=json.loads(json.dumps(receipt));updated['native'].update(originals)
 files[str(home/p.RECEIPT)]={'before':p.packed(before),'after':p.packed(p.file_snapshot(p.encoded(updated),before))}
 # All existing ancestors are in the exact scene; aliases themselves were checked separately.
 parents={}
 for name in [*links,*files]:
  for parent in Path(name).parents:
   if parent==home: break
   p.guard(parent)
   if parent.exists():
    st=parent.lstat();parents[str(parent)]={'dev':str(st.st_dev),'ino':str(st.st_ino)}
   else: parents[str(parent)]=None
 return {'run_id':run_id,'home':str(home),'ck_source':str(source),'agents':supported,'skipped':skipped,
  'links':links,'files':files,'parents':parents,'public_sha256':p.snap(home/p.PUBLIC).fingerprint,
  'backup_root':str(home/'.mem-sharing-ck-operations'/run_id)}
def save(file,data):
 raw=p.encoded(data);before=p.snap(file);p.tx._atomic_file(file,raw,0o600,expected=before)
def execute(approved):
 root=operations_root();p.guard(home/p.LOCK)
 with p.tx.write_lock(home/p.LOCK):
  if plan(approved['run_id'])!=approved: raise ValueError('Context Keeper plan drift; preview again')
  target=root/approved['run_id'];p.guard(target);target.mkdir(parents=True,exist_ok=False)
  journal=target/'journal.json';record={'status':'running','plan':approved};save(journal,record)
  try:
   output=io.StringIO()
   with contextlib.redirect_stdout(output): rc=ck.main(['--'+a for a in approved['agents']]+['--approved'])
   if rc!=0: raise ValueError('Upstream installation failed')
   result=json.loads(output.getvalue())
   if set(result['installed'])!=set(approved['links']): raise ValueError('Upstream installed target mismatch')
   for name in approved['links']:
    if alias(Path(name))['kind']!='alias': raise ValueError('Context Keeper installed link missing: '+name)
   for name,item in approved['files'].items():
    if name==str(home/p.RECEIPT): continue
    if p.snap(Path(name))!=p.unpacked(item['after']): raise ValueError('Rule readback mismatch')
   item=approved['files'][str(home/p.RECEIPT)];p.guard(home/p.RECEIPT)
   p.tx._atomic_file(home/p.RECEIPT,p.unpacked(item['after']).data,p.unpacked(item['before']).mode,expected=p.unpacked(item['before']))
   if p.snap(home/p.PUBLIC).fingerprint!=approved['public_sha256']: raise ValueError('Public memory changed')
   p.exit_plan(home) # CK-aware exit remains valid without deleting CK entries.
   record['status']='committed';save(journal,record)
   return {'status':'committed','action':'ck_install','agents':approved['agents'],'skipped':approved['skipped'],
    'source':str(source),'backup':str(journal),'installed':list(approved['links']),'public_memory_unchanged':True}
  except BaseException:
   errors=[]
   for name,item in reversed(list(approved['files'].items())):
    try:
     current=p.snap(Path(name));before=p.unpacked(item['before']);after=p.unpacked(item['after'])
     if current==before: continue
     if current!=after: raise ValueError('Foreign rule edit preserved')
     if before.kind=='absent': Path(name).unlink()
     else: p.tx._atomic_file(Path(name),before.data,before.mode,expected=current)
    except BaseException: errors.append(name)
   for name,before in approved['links'].items():
    try:
     if before['kind']=='absent' and os.path.lexists(name): alias(Path(name));ck._unlink_alias(Path(name))
    except BaseException: errors.append(name)
   record['status']='recovery_required' if errors else 'rolled_back';record['recovery_paths']=errors;save(journal,record)
   raise
try:
 if request['action']=='plan':
  value=plan(request['run_id'])
  print(json.dumps({'status':'approval_required','plan':value},ensure_ascii=False))
 elif request['action']=='confirm': print(json.dumps(execute(request['plan']),ensure_ascii=False))
 else: raise ValueError('Unsupported Context Keeper action')
except Exception as e:
 print(json.dumps({'status':'failed','message':str(e)},ensure_ascii=False));sys.exit(2)
`;
