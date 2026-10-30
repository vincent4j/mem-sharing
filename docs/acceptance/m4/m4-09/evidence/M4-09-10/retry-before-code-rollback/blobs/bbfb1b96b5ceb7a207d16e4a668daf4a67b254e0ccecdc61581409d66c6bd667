"""Raw command/metadata recorder only. No acceptance, comparisons, rollback, or init."""
import os, json, hashlib, stat, subprocess, sys
from pathlib import Path
from datetime import datetime, timezone
R=Path('/Users/vincent4j/Tools/Source/agent-group-memory')
S=Path('/Users/vincent4j/Tools/Source/context-keeper')
E=Path(__file__).parent
RUN=E.name
AUTH='paseo message 4c4c4df3-3f6c-4ed5-ba98-fbb213cbbac1; prior 7b6244d9-426f-4681-9d22-b94566ae21f1'
def now(): return datetime.now(timezone.utc).isoformat().replace('+00:00','Z')
def sha(b): return hashlib.sha256(b).hexdigest()
def write(p,d): p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n')
def snap(p):
 p=Path(p); d={'path':str(p),'exists':os.path.lexists(p)}
 if not d['exists']: return d
 s=p.lstat(); d.update(mode=oct(stat.S_IMODE(s.st_mode)),mtime_ns=s.st_mtime_ns)
 if p.is_symlink(): d.update(type='symlink',target=os.readlink(p),resolved=str(p.resolve()),sha256=sha(str(p.resolve()).encode()),sha256_basis='resolved_link_target_utf8')
 elif p.is_file():
  b=p.read_bytes(); d.update(type='file',bytes=len(b),sha256=sha(b))
 elif p.is_dir(): d.update(type='directory')
 return d
paths=[R/'AGENTS.md',R/'CLAUDE.md',*[R/x/'skills/context-keeper' for x in ['.agents','.codex','.claude','.workbuddy']],R/'.workbuddy/memory/MEMORY.md',R/'scripts/registry.json',*[Path.home()/x for x in ['.codex/AGENTS.md','.claude/CLAUDE.md','.workbuddy/MEMORY.md']],*[S/x for x in ['SKILL.md','scripts/install.py','scripts/context_keeper_probe.py']],R/'templates/workbuddy-bridge.md',R/'context-keeper.json',R/'docs/context-keeper',*sorted((R/'docs/context-keeper').rglob('*'))]
def record(label,argv,affected=(),bucket='m1-03',ownership=None):
 folder=R/'docs/acceptance'/bucket/RUN
 before=[snap(p) for p in paths]
 mp=None
 if affected:
  bd=R/'scripts/backups'/(RUN+'-'+label); bd.mkdir(mode=0o700)
  entries=[]
  for i,p in enumerate(affected):
   p=Path(p); row={'before':snap(p),'path':str(p),'backup_file':None}
   if p.is_file() and not p.is_symlink():
    dest=bd/(str(i)+'.bin'); dest.write_bytes(p.read_bytes()); dest.chmod(0o600); row['backup_file']=str(dest)
   entries.append(row)
  mp=bd/'manifest.json'; manifest={'operation':label,'authorization':AUTH,'observed_at':now(),'objects':entries,'recovery':'not-run; round3 no-rollback protocol'}; write(mp,manifest)
 started=now(); result=subprocess.run(argv,capture_output=True)
 after=[snap(p) for p in paths]
 receipt={'argv':argv,'started_at':started,'finished_at':now(),'rc':result.returncode,'stdout':result.stdout.decode('utf-8'),'stderr':result.stderr.decode('utf-8'),'before':before,'after':after,'ownership':ownership,'backup_manifest':str(mp) if mp else None,'acceptance':'reserved for main agent'}
 write(folder/(label+'.json'),receipt)
 (folder/(label+'.stdout')).write_bytes(result.stdout); (folder/(label+'.stderr')).write_bytes(result.stderr)
 if mp:
  for row in entries: row['after']=snap(row['path'])
  write(mp,manifest)
 print(json.dumps({'receipt':str(folder/(label+'.json')),'rc':result.returncode,'stdout':receipt['stdout'],'stderr':receipt['stderr'],'backup_manifest':str(mp) if mp else None},ensure_ascii=False))
 return result.returncode
