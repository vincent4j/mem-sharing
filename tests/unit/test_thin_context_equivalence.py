"""Explicit one-plan context judgments; no real user content in fixtures."""
import copy,json,os,sys,tempfile,unittest,subprocess
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'scripts'))
from agm_core import memory_share as ms,paths
from agm_core.uninstall_recovery import tree
RULES=[('- Synthetic global rule %d; preserve its complete bytes.\n'%n).encode() for n in range(1,7)]
AGENTS=['codex','claude','workbuddy','dsh','zcode','opencode']

def approved(plan):return dict(plan,confirmed_at='2026-11-06T05:00:00Z',reference='synthetic precise test selection')

class ThinContextTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.area=Path(self.tmp.name).resolve();self.home=self.area/'home';self.home.mkdir();self.config=paths.select_platform(paths.load_agents_table(),'darwin');self.native={}
  for agent in AGENTS:
   p=Path(paths.expand_path(self.config[agent]['user_entry'],home=str(self.home)));p.parent.mkdir(parents=True,exist_ok=True)
   heading='User rules' if agent not in ('workbuddy','opencode') else 'Private WorkBuddy notes' if agent=='workbuddy' else 'General rules'
   p.write_bytes(('# '+heading+'\n\n').encode()+b'\n'.join(RULES));p.chmod(0o640);self.native[agent]=p
  self.req={'home':str(self.home),'platform_config':self.config,'agents':AGENTS};self.topic=self.home/'.mem-sharing/memories/user-rules.md'
 def proposal(self,agents=None,proof=True):
  req=dict(self.req,agents=agents or AGENTS);scan=ms.plan_share(req);self.assertEqual(scan['status'],'completed',scan);groups=[];declarations=[]
  for rule in RULES:
   items=[s for s in scan['segments'] if s['text'].encode()==rule];self.assertEqual(len(items),len(req['agents']))
   groups.append({'summary':'Complete global constraint','same_content':True,'items':[{'agent':i['agent'],'start':i['start'],'end':i['end']} for i in items]})
   if len(items)>1:declarations.append({'sources':[{'source':i['source'],'start':i['start'],'end':i['end'],'context':i['context'],'text_sha256':i['sha256'],'basis':scan['basis'][i['source']]} for i in items],'canonical_context':items[0]['context'],'reason':'Agent read all originals; these synthetic constraints have equal cross-Agent scope.'})
  p={'schema_version':1,'basis':scan['basis'],'groups':groups}
  if proof:p['equivalent_sources']=declarations
  return req,p
 def plan(self,req,p,selection='共享 1、2、3、4、5、6'):
  result=ms.plan_share(dict(req,proposal=p,selection=selection));self.assertNotEqual(result['status'],'failed',result);return result['approval_plan']
 def execute(self,req,p):
  plan=self.plan(req,p);done=ms.execute_share(plan,approved(plan),request=req);self.assertEqual(done['status'],'completed',done);return done
 def test_old_conservative_three_copies_and_explicit_one_copy_36_contexts(self):
  req,p=self.proposal(proof=False);old=self.plan(req,p);body=bytes.fromhex(next(c for c in old['changes'] if c['path']==str(self.topic))['after_hex'])
  self.assertEqual([body.count(r) for r in RULES],[3]*6);self.assertTrue(all(not g['same_scope'] for g in old['groups']))
  req,p=self.proposal();plan=self.plan(req,p);self.assertEqual(plan['default_numbers'],list(range(1,7)))
  self.execute(req,p);body=self.topic.read_bytes();self.assertEqual([body.count(r) for r in RULES],[1]*6);records=list(ms._available_migrations(ms._runtime(req)).values());self.assertEqual(len(records),36)
  original={(s['source'],s['start'],s['end']):s['context'] for proof in p['equivalent_sources'] for s in proof['sources']}
  for record in records:self.assertEqual(record['context'],original[(record['path'],record['start'],record['end'])])
  self.assertEqual(body.count('# 用户记忆'.encode()),1)
 def test_invalid_proofs_fail_zero_write_and_project_not_widened(self):
  req,p=self.proposal()
  for mode in ('partial','context','basis','hash','overlap','canonical','unknown'):
   candidate=copy.deepcopy(p);proof=candidate['equivalent_sources'][0]
   if mode=='partial':proof['sources'].pop()
   elif mode=='context':proof['sources'][0]['context']=[]
   elif mode=='basis':proof['sources'][0]['basis']='0'*64
   elif mode=='hash':proof['sources'][0]['text_sha256']='0'*64
   elif mode=='overlap':proof['sources'].append(copy.deepcopy(proof['sources'][0]))
   elif mode=='canonical':proof['canonical_context']=[[1,'invented',1]]
   else:candidate['unknown']=True
   before=tree(self.home);result=ms.plan_share(dict(req,proposal=candidate));self.assertEqual(result['status'],'failed',(mode,result));self.assertEqual(tree(self.home),before)
 def test_omitted_same_scope_occurrence_and_one_proof_across_groups_reject(self):
  req,p=self.proposal()
  omitted=copy.deepcopy(p);omitted['groups'][0]['items'].pop();omitted['equivalent_sources'][0]['sources'].pop()
  before=tree(self.home);result=ms.plan_share(dict(req,proposal=omitted));self.assertEqual(result['status'],'failed',result);self.assertEqual(tree(self.home),before)
  crossed=copy.deepcopy(p);crossed['equivalent_sources'][0]['sources'].append(copy.deepcopy(crossed['equivalent_sources'][1]['sources'][0]))
  result=ms.plan_share(dict(req,proposal=crossed));self.assertEqual(result['status'],'failed',result);self.assertEqual(tree(self.home),before)
 def test_view_decline_and_drift_zero_write(self):
  req,p=self.proposal();before=tree(self.home)
  for choice in ('查看 1','暂不整理'):
   plan=self.plan(req,p,choice);self.assertEqual(plan['changes'],[]);self.assertEqual(tree(self.home),before)
  plan=self.plan(req,p);self.native['workbuddy'].write_bytes(self.native['workbuddy'].read_bytes()+b'new private text\n');before=tree(self.home)
  self.assertEqual(ms.execute_share(plan,approved(plan),request=req)['status'],'failed');self.assertEqual(tree(self.home),before)
 def reused(self):
  first=AGENTS[:-1];req,p=self.proposal(first);self.execute(req,p);public=self.topic.read_bytes();metadata=(self.topic.stat().st_mode,self.topic.stat().st_mtime_ns,self.topic.stat().st_ino)
  req,p=self.proposal(['opencode']);records=list(ms._available_migrations(ms._runtime(req)).values());proofs=[]
  scan=ms.plan_share(req)
  for item in scan['segments']:
   target=next((r for r in records if bytes.fromhex(r['text_hex'])==item['text'].encode()),None)
   if target:proofs.append({'source':item['source'],'start':item['start'],'end':item['end'],'source_context':item['context'],'source_basis':scan['basis'][item['source']],'public_basis':ms.entries.sha256(public),'public_start':target['public_offset'],'public_end':target['public_end'],'public_context':target['context'],'text_sha256':item['sha256'],'equivalent':True,'reason':'Agent read existing public and new native context; same global rule.'})
  p['public_reuse']=proofs;return req,p,public,metadata
 def test_public_reuse_zero_write_and_last_reference_return(self):
  req,p,public,metadata=self.reused();self.execute(req,p);self.assertEqual(self.topic.read_bytes(),public);self.assertEqual((self.topic.stat().st_mode,self.topic.stat().st_mtime_ns,self.topic.stat().st_ino),metadata)
  runtime=ms._runtime(req);available=ms._available_migrations(runtime);self.assertEqual(len(available),36)
  def return_agents(agents):
   current=self.topic.read_bytes();items=[]
   for ref,r in available.items():
    if r['agent'] in agents:items.append({'ref':ref[0],'migration':ref[1],'public_span':{'start':r['public_offset'],'end':r['public_end'],'text_hex':current[r['public_offset']:r['public_end']].hex()},'target':{'path':r['path'],'mode':'insert_at','insert_at':len(Path(r['path']).read_bytes())}})
   proposal={'schema_version':1,'basis':{str(self.topic):ms.entries.sha256(current)},'items':items};request=dict(self.req,agents=agents,return_plan=proposal);plan=ms.build_return_plan(request,proposal);result=ms.run_return(dict(request,approval=approved(plan)));self.assertEqual(result['status'],'completed',result)
  return_agents(['opencode']);self.assertEqual(self.topic.read_bytes(),public);self.assertEqual((self.topic.stat().st_mode,self.topic.stat().st_mtime_ns,self.topic.stat().st_ino),metadata)
  alien={('other-topic',n):dict(record,topic=str(self.topic.parent/'other.md')) for n,record in enumerate(available.values())}
  with patch.object(ms,'_available_migrations',return_value=dict(available,**{}) | alien):return_agents(AGENTS[:-1])
  self.assertTrue(all(r not in self.topic.read_bytes() for r in RULES))
 def test_reuse_wrong_binding_and_public_edit_reject(self):
  req,p,public,_=self.reused()
  for mode in ('partial','source_context','source_basis','public_basis','text_sha256','public_start','public_context'):
   bad=copy.deepcopy(p)
   if mode=='partial':bad['public_reuse'].append(copy.deepcopy(bad['public_reuse'][0]))
   else:bad['public_reuse'][0][mode]=[] if mode.endswith('context') else 1 if mode=='public_start' else '0'*64
   before=tree(self.home);result=ms.plan_share(dict(req,proposal=bad,selection='共享 1、2、3、4、5、6'));self.assertEqual(result['status'],'failed',(mode,result));self.assertEqual(tree(self.home),before)
  plan=self.plan(req,p);self.topic.write_bytes(public+b'new public text\n');before=tree(self.home);self.assertEqual(ms.execute_share(plan,approved(plan),request=req)['status'],'failed');self.assertEqual(tree(self.home),before)

class ThinInstalledCliTests(unittest.TestCase):
 def test_installed_actual_CLI_equivalence_uninstall_external_restore(self):
  from test_m404_install import InstallFixture
  from agm_core import detect
  from agm_core.layout import resolve_layout
  t=ThinContextTests();t.setUp();self.addCleanup(t.doCleanups)
  f=InstallFixture();f.setUp();self.addCleanup(f.doCleanups)
  f.home=t.home;f.runtime=resolve_layout(t.home);f.request['home']=str(t.home);f.request['agents']=AGENTS
  real=detect.detect_agents
  def installed(*a,**kw):
   kw.update(search_paths=[],app_directories=[]);facts=real(*a,**kw)
   for row in facts['agents'].values():row['status']='installed'
   return facts
  with patch.object(detect,'detect_agents',side_effect=installed):self.assertEqual(f.execute()['status'],'completed')
  req,proposal=t.proposal();file=t.area/'proposal.json';file.write_text(json.dumps(proposal));tool=f.runtime.code/'scripts/memory_share.py'
  def run(args):
   out=subprocess.run([sys.executable,'-B',str(tool),*args],capture_output=True,text=True,env=dict(os.environ,HOME=str(t.home)));self.assertTrue(out.stdout.strip(),(out.returncode,out.stderr));return out.returncode,json.loads(out.stdout)
  flags=['--agent',AGENTS[0]]
  for a in AGENTS[1:]:flags+=['--agent',a]
  argv=['share-user-memory',*flags,'--proposal-file',str(file)]
  rc,view=run(argv);self.assertEqual(rc,5,view);shown=t.area/'shown.json';shown.write_text(json.dumps(view['approval_plan']))
  before=tree(t.home)
  for flags2 in (['--selection','查看 1'],['--decline']):
   rc,out=run(argv+flags2);self.assertEqual(rc,0,out);self.assertEqual(tree(t.home),before)
  rc,out=run(argv+['--selection','1、2、3、4、5、6','--selection-plan-file',str(shown),'--selection-reference','synthetic actual CLI user selection']);self.assertEqual(rc,0,out)
  self.assertEqual([t.topic.read_bytes().count(r) for r in RULES],[1]*6);self.assertEqual(len(ms._available_migrations(f.runtime)),36)
  private=t.native['workbuddy'];private.write_bytes(private.read_bytes()+b'private follow-up stays\n');before_exit=tree(t.home);backup=t.area/'exit';agm=f.runtime.code/'scripts/agm.py'
  cmd=[sys.executable,'-B',str(agm),'uninstall-machine','--backup-dir',str(backup)];env=dict(os.environ,HOME=str(t.home))
  p=subprocess.run(cmd,capture_output=True,text=True,env=env);self.assertEqual(p.returncode,5,p.stdout);self.assertEqual(tree(t.home),before_exit)
  approval=t.area/'exit-approval.json';approval.write_text(json.dumps({'plan':json.loads(p.stdout)['plan'],'confirmed_at':'2026-11-06T05:00:00Z','reference':'synthetic formal exit approval'}));p=subprocess.run(cmd+['--approval-file',str(approval)],capture_output=True,text=True,env=env);self.assertEqual(p.returncode,0,p.stdout)
  for native in t.native.values():self.assertEqual([native.read_bytes().count(r) for r in RULES],[1]*6)
  self.assertIn(b'private follow-up stays',private.read_bytes())
  recover=[sys.executable,'-I','-S','-B',str(backup/'recover.py'),'--manifest',str(backup/'manifest.json'),'--action','restore'];p=subprocess.run(recover,capture_output=True,text=True,env=env);self.assertEqual(p.returncode,5,p.stdout)
  approval.write_text(json.dumps({'plan':json.loads(p.stdout)['plan'],'confirmed_at':'2026-11-06T05:00:00Z','reference':'synthetic external restore approval'}));p=subprocess.run(recover+['--approval-file',str(approval)],capture_output=True,text=True,env=env);self.assertEqual(p.returncode,0,p.stdout);self.assertEqual(tree(t.home),before_exit)
