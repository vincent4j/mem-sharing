from pathlib import Path
import json,hashlib,os
from datetime import datetime,timezone
R=Path.cwd(); E=Path('/Users/vincent4j/Tools/Source/agent-group-memory/docs/acceptance/m1-03/20261029T110112Z-round3'); p=R/'scripts/registry.json'; reg=json.loads(p.read_text()); a=reg['projects'][str(R)]['checkouts'][str(R)]; t=datetime.now(timezone.utc).isoformat().replace('+00:00','Z')
def owned(kind,p,scope,ownership,existed,marker,label):
 b=p.read_bytes(); start,end=[v.encode() for v in marker]; block=b[b.index(start):b.index(end)+len(end)]
 return {'kind':kind,'path':str(p),'scope':scope,'agents':['workbuddy'],'ownership':ownership,'marker':{'start':marker[0],'end':marker[1]},'fingerprint':{'algorithm':'sha256','basis':'block_bytes','value':hashlib.sha256(block).hexdigest()},'original_existed':existed,'link_target':None,'backup_manifest':str(R/'scripts/backups'/(E.name+'-'+label)/'manifest.json'),'consumers':[str(R)]}
wb=R/'.workbuddy/memory/MEMORY.md'; user=Path.home()/'.workbuddy/MEMORY.md'
a['objects'][str(wb)+'#keeper']=owned('block',wb,'project','created',False,['<!-- context-keeper:workbuddy:start -->','<!-- context-keeper:workbuddy:end -->'],'09-workbuddy-project')
key=str(user)+'#keeper-exception'; reg['shared_objects'][key]=owned('user_convention',user,'user','created',False,['<!-- agent-group-memory:keeper-exception:start -->','<!-- agent-group-memory:keeper-exception:end -->'],'10-workbuddy-user')
basekey=str(user)+'#base'; reg['shared_objects'][basekey]={'kind':'file','path':str(user),'scope':'user','agents':['workbuddy'],'ownership':'reused','marker':None,'fingerprint':{'algorithm':'sha256','basis':'file_bytes','value':hashlib.sha256(user.read_bytes()).hexdigest()},'original_existed':True,'link_target':None,'backup_manifest':str(R/'scripts/backups'/(E.name+'-10-workbuddy-user')/'manifest.json'),'consumers':[str(R)]}
a['shared_object_ids']=[key,basekey]; a['states']['bridge_assembled']['workbuddy']={'status':'ready','observed_at':t,'evidence':str(R/'docs/acceptance/m1-04'/E.name/'09-workbuddy-project.json')+'; '+str(R/'docs/acceptance/m1-04'/E.name/'10-workbuddy-user.json')}
tmp=p.with_suffix('.json.tmp'); tmp.write_text(json.dumps(reg,ensure_ascii=False,indent=2)+'\n'); os.replace(tmp,p)
print('Updated WorkBuddy object/state bookkeeping; runtime_acceptance remains pending; acceptance decision reserved for main agent.')
