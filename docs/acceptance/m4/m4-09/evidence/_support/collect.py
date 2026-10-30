"""M4-09 raw collection only. No assertions, verdicts, or acceptance predicates.

Fixture operations and child commands are recorded separately. Every child has
an allowlisted environment, independent synthetic HOME, full stdout/stderr and
lstat snapshots. Content-addressed blobs preserve exact bytes, including binary
and invalid UTF-8 data. This is an evidence recorder, not a test runner.
"""
import base64, copy, difflib, hashlib, io, json, os, platform, shutil, stat
import subprocess, sys, tarfile, tempfile, time, traceback
from datetime import datetime, timezone
from pathlib import Path

REPO=Path(__file__).resolve().parents[6]
EVID=Path(__file__).resolve().parent.parent
PYTHON=Path(sys.executable).resolve()
BASELINE='de9cc4fdd0c7c5088267b9ff3bf0ff10ad52a40b'
REFERENCE='M4-09 synthetic-only execution authorization: user message dff17160-5380-4d37-a388-9b63b30e3968'
START=time.monotonic()
def utc(): return datetime.now(timezone.utc).isoformat().replace('+00:00','Z')
def sha(raw): return hashlib.sha256(raw).hexdigest()
def dump(path,obj):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(obj,ensure_ascii=False,indent=2,default=str)+'\n')
def write(path,raw):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    path.write_bytes(raw.encode() if isinstance(raw,str) else raw)
def synthetic_approval(plan):
    p=copy.deepcopy(plan);p['confirmed_at']=utc();p['reference']=REFERENCE
    return p

class Case:
    def __init__(self,n,name,variant=None):
        self.id=f'M4-09-{n:02d}';self.name=name
        self.out=EVID/self.id
        if variant:self.out=self.out/variant
        self.out.mkdir(parents=True,exist_ok=True)
        self.area=Path(tempfile.mkdtemp(prefix=self.id+'-',dir='/private/tmp')).resolve()
        self.home=self.area/'home';self.home.mkdir(mode=0o700)
        self.cwd=self.area/'cwd';self.cwd.mkdir()
        self.tmp=self.area/'tmp';self.tmp.mkdir()
        self.source=self.area/'source';self.source.mkdir()
        self.project=self.area/'project';self.project.mkdir()
        self.bin=self.area/'bin';self.bin.mkdir()
        (self.bin/'git').symlink_to('/usr/bin/git')
        self.env={'HOME':str(self.home),'PATH':str(self.bin)+':/usr/bin:/bin:/usr/sbin:/sbin',
          'TMPDIR':str(self.tmp),'PYTHONDONTWRITEBYTECODE':'1','PYTHONNOUSERSITE':'1',
          'GIT_CONFIG_NOSYSTEM':'1','GIT_CONFIG_GLOBAL':'/dev/null','GIT_OPTIONAL_LOCKS':'0',
          'LC_ALL':'en_US.UTF-8'}
        # Export actual baseline tracked bytes, without a live repo dependency.
        raw=subprocess.run(['/usr/bin/git','-C',str(REPO),'archive',BASELINE],env=self.env,cwd=self.cwd,capture_output=True,check=True).stdout
        with tarfile.open(fileobj=io.BytesIO(raw)) as archive:
            members=archive.getmembers() if n in (31,44) else [m for m in archive.getmembers()
              if m.name in ('SKILL.md','README.md','INSTALL.md','llms.txt') or m.name.startswith('scripts/')]
            archive.extractall(self.source,members=members)
        files={str(p.relative_to(self.source)):sha(p.read_bytes()) for p in self.source.rglob('*')
          if p.is_file() and (str(p.relative_to(self.source)) in ('SKILL.md','README.md','INSTALL.md','llms.txt')
          or str(p.relative_to(self.source)).startswith('scripts/'))}
        self.source_info={'root':str(self.source),'url':'https://github.com/vincent4j/mem-sharing',
          'commit':BASELINE,'version':'0.4.0','files':files}
        self.manifest=self.area/'source.json';dump(self.manifest,self.source_info)
        self.request=self.area/'request.json';dump(self.request,{'app_directories':[]})
        self.steps=[];self.notes=[];self.status='executed';self.index=0
        self.R=self.home/'.mem-sharing';self.C=self.home/'.local/share/mem-sharing'
        self.V=self.R/'var/registry.json';self.O=self.home/'.agents-group'
        self.cmd('fixture-git-init',['/usr/bin/git','init','-q',str(self.project)])
        self.note('Source contains exact baseline git-archive product bytes (scripts and four root documents; documentation cases retain full archive); source-manifest route is used. Synthetic SemVer 0.4.0 is an exercise identity, not a frozen formal release.')
        dump(self.out/'fixture.json',{'case':self.id,'name':name,'area':self.area,'home':self.home,
          'project':self.project,'source':self.source_info,'python':str(PYTHON),
          'platform':platform.platform(),'python_version':sys.version,'started_utc':utc(),
          'environment':self.env,'isolation':'env allowlist; synthetic HOME/PATH packages; install request app_directories=[]; project CLI launcher disables STANDARD_APP_DIRECTORIES',
          'not_isolated':'same uid/kernel/filesystem; no sandbox VM, real Agent session, account, browser or credential access',
          'authorization':REFERENCE})
    def note(self,text): self.notes.append(text)
    def block(self,text): self.status='blocked';self.note(text)
    def snapshot(self):
        result={}
        def visit(p):
            s=p.lstat();rel=str(p.relative_to(self.area)) or '.'
            meta={'mode':s.st_mode,'permissions':oct(stat.S_IMODE(s.st_mode)),
              'mtime_ns':s.st_mtime_ns,'size':s.st_size}
            if stat.S_ISLNK(s.st_mode): meta.update(kind='symlink',target=os.readlink(p))
            elif stat.S_ISREG(s.st_mode):
                raw=p.read_bytes();h=sha(raw);meta.update(kind='file',sha256=h)
                blob=self.out/'blobs'/h
                if not blob.exists(): write(blob,raw)
            elif stat.S_ISDIR(s.st_mode): meta['kind']='directory'
            elif stat.S_ISFIFO(s.st_mode): meta['kind']='fifo'
            else: meta['kind']='special'
            result[rel]=meta
            if meta['kind']=='directory':
                for child in sorted(p.iterdir()):visit(child)
        visit(self.area);return result
    def record(self,label,fn,argv=None):
        self.index+=1;d=self.out/f'{self.index:03d}-{label}';d.mkdir()
        before=self.snapshot();dump(d/'before-tree.json',before)
        started=utc();tick=time.monotonic();result=fn()
        after=self.snapshot();dump(d/'after-tree.json',after)
        changes=[];textdiff=[]
        for rel in sorted(before.keys()|after.keys()):
            b=before.get(rel);a=after.get(rel)
            if a==b:continue
            changes.append({'path':rel,'before':b,'after':a})
            if (b or {}).get('sha256')!=(a or {}).get('sha256') and any((m or {}).get('kind')=='file' for m in (a,b)):
                rb=(self.out/'blobs'/b['sha256']).read_bytes() if (b or {}).get('kind')=='file' else b''
                ra=(self.out/'blobs'/a['sha256']).read_bytes() if (a or {}).get('kind')=='file' else b''
                try:textdiff.extend(difflib.unified_diff(rb.decode('utf-8').splitlines(True),ra.decode('utf-8').splitlines(True),fromfile='before/'+rel,tofile='after/'+rel))
                except UnicodeDecodeError:textdiff.append(f'Binary delta {rel}: exact bytes in blobs; before={sha(rb)} after={sha(ra)}\n')
        dump(d/'changes.json',changes);write(d/'bytes.diff',''.join(textdiff))
        meta={'label':label,'argv':argv,'cwd':str(self.cwd),'environment':self.env,
          'started_utc':started,'ended_utc':utc(),'duration_seconds':time.monotonic()-tick,**result}
        dump(d/'command.json',meta);self.steps.append({'path':d.name,'label':label,'exit_code':meta.get('exit_code')})
        dump(self.out/'index.json',{'case':self.id,'status':self.status,'steps':self.steps,'notes':self.notes})
        return result
    def cmd(self,label,argv,stdin=b'',env=None):
        argv=[str(a) for a in argv]
        def run():
            try:
                p=subprocess.run(argv,cwd=self.cwd,env=env or self.env,input=stdin,capture_output=True,timeout=90)
                r={'exit_code':p.returncode,'stdin_base64':base64.b64encode(stdin).decode()}
                write(self.out/f'{self.index:03d}-{label}'/'stdout.bin',p.stdout)
                write(self.out/f'{self.index:03d}-{label}'/'stderr.bin',p.stderr)
                try:r['json']=json.loads(p.stdout)
                except (ValueError,UnicodeDecodeError):pass
                return r
            except subprocess.TimeoutExpired as exc:
                return {'exit_code':None,'timeout':90,'stdout_base64':base64.b64encode(exc.stdout or b'').decode(),'stderr_base64':base64.b64encode(exc.stderr or b'').decode()}
        return self.record(label,run,argv)
    def mutate(self,label,fn):
        def apply():
            value=fn()
            return {'fixture_operation':label,'returned':repr(value)}
        return self.record('fixture-'+label,apply,['fixture-operation',label])
    def py(self,label,code,*args):return self.cmd(label,[PYTHON,'-B','-c',code,str(self.source/'scripts'),*args])
    def I(self,label='install-preview',*args):
        return self.cmd(label,[PYTHON,'-B',self.source/'scripts/install.py',*args])
    def preview(self,label='install-preview',extra=()):
        return self.I(label,'--source-manifest',self.manifest,'--request-file',self.request,*extra).get('json',{})
    def approve(self,plan,label='approval'):
        p=self.area/f'{label}-{self.index}.json'
        self.mutate(label,lambda:dump(p,synthetic_approval(plan)))
        return p
    def install(self,agents=('codex',)):
        for a in agents:self.signal(a)
        report=self.preview()
        if 'approval_plan' not in report:
            self.block('Installation precondition unavailable; see raw preview.');return None
        approval=self.approve(report['approval_plan'])
        return self.I('install-execute','--approval-file',approval).get('json',{})
    def signal(self,agent):
        def seed():
            package=self.area/'packages'/agent
            exe=package/'bin'/agent;write(exe,'#!/bin/sh\nexit 0\n');exe.chmod(0o755)
            dump(package/'package.json',{'name':{'codex':'@openai/codex','claude':'@anthropic-ai/claude-code'}[agent],
              'version':'1.0.0','bin':{agent:'bin/'+agent}})
            (self.bin/agent).symlink_to(exe)
        self.mutate('synthetic-'+agent+'-package',seed)
    def A(self,label,*args):
        # Same bounded launcher as tests/unit/runtime_fixture.py, made explicit.
        code="import runpy,sys;from pathlib import Path;sys.path.insert(0,str(Path(sys.argv[1]).parent));from agm_core import detect;detect.STANDARD_APP_DIRECTORIES=();sys.argv=sys.argv[1:];runpy.run_path(sys.argv[0],run_name='__main__')"
        script=(self.C if self.C.exists() else self.source)/'scripts/agm.py'
        return self.cmd(label,[PYTHON,'-B','-c',code,script,*args]).get('json',{})
    def project_action(self,command='enable-memory',extra=(),label='project'):
        args=[command,'--project',str(self.project),*extra]
        p=self.A(label+'-preview',*args)
        if p.get('approval_required'):
            try:plan=json.loads(p['next_action'])
            except (ValueError,KeyError,TypeError):
                # remove-memory has a deliberate noninteractive front gate;
                # obtain its frozen kernel plan, never invent CLI fields.
                if command!='remove-memory':return p
                script="import sys,json;sys.path.insert(0,sys.argv[1]);from agm_core import remove,paths;print(json.dumps(remove.run({'home':sys.argv[2],'project':sys.argv[3],'platform_config':paths.select_platform(paths.load_agents_table(),'darwin'),'interactive':False})))"
                r=self.py(label+'-kernel-preview',script,str(self.home),str(self.project)).get('json',{})
                try:plan=json.loads(r['next_action'])
                except (ValueError,KeyError,TypeError):
                    if r.get('status') not in ('failed','gaps','recovery_required'):
                        self.block('remove preview has no exact approval template; see raw output')
                    return r
            approval=self.approve({k:v for k,v in plan.items() if k not in ('confirmed_at','reference')},label+'-approval')
            return self.A(label+'-execute',*args,'--approval-file',approval)
        return p
    def check(self,label='check'):return self.A(label,'check-memory','--project',str(self.project))
    def end(self):
        dump(self.out/'index.json',{'case':self.id,'name':self.name,'status':self.status,'area':self.area,
          'steps':self.steps,'notes':self.notes,'ended_utc':utc(),
          'recovery_locations':[str(p) for p in self.home.rglob('*') if p.name in ('journal.json','manifest.json','recover.py')],
          'verdict':'Not evaluated; primary Agent must judge raw evidence.'})
        write(self.out/'README.md',f'# {self.id} {self.name}\n\nExecution status: {self.status}. No acceptance verdict.\n\nSynthetic fixture preserved at `{self.area}`.\n\n'+''.join('- '+n+'\n' for n in self.notes)+'\nSee index.json, per-command raw stdout/stderr, trees, byte diffs and content-addressed blobs.\n')
        print(self.id,self.status,len(self.steps),'steps',flush=True)

def run_case(n,name,fn,variant=None):
    c=Case(n,name,variant)
    try:fn(c)
    except Exception as exc:
        c.block('Collector/precondition exception; not a product verdict: '+repr(exc))
        write(c.out/'collector-exception.txt',traceback.format_exc())
    finally:c.end()
    return c
