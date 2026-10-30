from pathlib import Path
import json, hashlib, os
from datetime import datetime, timezone
R=Path.cwd(); S=Path('/Users/vincent4j/Tools/Source/context-keeper'); E=Path('/Users/vincent4j/Tools/Source/agent-group-memory/docs/acceptance/m1-03/20261029T110112Z-round3')
t=datetime.now(timezone.utc).isoformat().replace('+00:00','Z')
auth={'confirmed_at':t,'reference':'paseo message 4c4c4df3-3f6c-4ed5-ba98-fbb213cbbac1; prior 7b6244d9-426f-4681-9d22-b94566ae21f1'}
sha=lambda b:hashlib.sha256(b).hexdigest()
def fact(status,ev): return {'status':status,'observed_at':t,'evidence':str(ev)}
def obj(kind,p,agents,ownership,existed,marker=None,manifest=None):
 if kind=='skill_symlink': basis='link_target'; value=sha(str(p.resolve()).encode())
 elif marker:
  b=p.read_bytes(); a,z=[x.encode() for x in marker]; basis='block_bytes'; value=sha(b[b.index(a):b.index(z)+len(z)])
 else: basis='file_bytes'; value=sha(p.read_bytes())
 return {'kind':kind,'path':str(p),'scope':'project','agents':agents,'ownership':ownership,'marker':dict(zip(['start','end'],marker)) if marker else None,'fingerprint':{'algorithm':'sha256','basis':basis,'value':value},'original_existed':existed,'link_target':str(p.resolve()) if p.is_symlink() else None,'backup_manifest':str(manifest) if manifest else None,'consumers':[str(R)]}
objects={}; marker=['<!-- context-keeper:start -->','<!-- context-keeper:end -->']
for name,agent,step in [('AGENTS.md','codex','04-codex-approved'),('CLAUDE.md','claude','07-claude-approved')]:
 p=R/name; m=R/'scripts/backups'/(E.name+'-'+step)/'manifest.json'
 objects[str(p)+'#base']=obj('file',p,[agent],'reused',True,manifest=m)
 objects[str(p)+'#keeper']=obj('block',p,[agent],'created',False,marker,m)
for alias,agent in [('.agents','codex'),('.codex','codex'),('.claude','claude'),('.workbuddy','workbuddy')]:
 p=R/alias/'skills/context-keeper'; objects[str(p)]=obj('skill_symlink',p,[agent],'created',False,manifest=R/'scripts/backups'/(E.name+'-01-create-links')/'manifest.json')
p=R/'CLAUDE.md'; objects[str(p)+'#import']=obj('import',p,['claude'],'reused',True)
states={'source_available':fact('ready',E/'00-preflight.json'),'skill_installed':{a:fact('ready',E/'01-create-links.json') for a in ['codex','claude','workbuddy']},'bridge_assembled':{'codex':fact('ready',E/'04-codex-approved.json'),'claude':fact('ready',E/'07-claude-approved.json'),'workbuddy':fact('missing','M1-04 not yet executed in round3')},'store_authorized_ready':fact('ready',str(E/'00-preflight.json')+'; reused prior actual init/status: '+str(E.parent/'20261029T105740Z-retry/status.json'))}
assembly={'git_common_dir':str(R/'.git'),'agents':['codex','claude','workbuddy'],'states':states,'store':{'path':str(R/'docs/context-keeper'),'location_approved':True,'approval_evidence':auth},'objects':objects,'shared_object_ids':[],'runtime_acceptance':{'status':'pending','evidence_path':None}}
reg={'schema_version':1,'projects':{str(R):{'main_checkout':str(R),'memory_authorization':'yes','authorization_evidence':auth,'provider_source':str(S),'checkouts':{str(R):assembly}}},'shared_objects':{}}
p=R/'scripts/registry.json'; tmp=p.with_suffix('.json.tmp'); tmp.write_text(json.dumps(reg,ensure_ascii=False,indent=2)+'\n'); os.replace(tmp,p)
print('Created schema_version=1 registry; WorkBuddy bridge missing until M1-04; runtime pending; state facts are operational bookkeeping, acceptance reserved for main agent.')
