from collect import *
import ast

def synthetic_ck(c):
    # Copy only the frozen repository's already-published synthetic upstream
    # fixture literal. Do not run test setUp(), create a Git commit, or read CK
    # from the user's installed source.
    tree=ast.parse((REPO/'tests/unit/test_ck_install.py').read_text())
    code=ast.literal_eval(next(n.value for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='UPSTREAM' for t in n.targets)))
    root=c.area/'synthetic-ck-source'
    c.mutate('synthetic-ck-source',lambda:(write(root/'SKILL.md','name: context-keeper\n'),write(root/'scripts/install.py',code)))
    c.note('CK fixture is the existing UPSTREAM literal from tests/unit/test_ck_install.py. No upstream real source or real HOME is read/executed. No temporary Git commit is created. Production CK source rejects OS-temp locations; no monkeypatch of source trust gates is used.')
    return root

def route(c):
    c.install(('codex','claude'));source=synthetic_ck(c)
    c.I('ck-route-preview','--context-keeper','--ck-source',source)
    c.I('ck-discovery-without-source','--context-keeper')
    c.check()
    c.block('Positive CK independent-plan/execution cannot be constructed under temp-only synthetic source + no Git commits: production _durable_source rejects OS-temp, then requires its fixed clean pinned checkout. Exact source-gate refusal recorded; no fictional CK envelope or source-trust override.')

def wrong_envelope(c):
    c.signal('codex');main=c.preview()['approval_plan'];a=c.approve(main)
    c.I('main-envelope-to-ck','--context-keeper','--approval-file',a)
    c.I('main-install','--approval-file',a)
    # A deliberately invalid wrong-command envelope is a negative-input fixture,
    # never represented as a real generated CK plan or real user consent.
    wrong=c.area/'invalid-ck-envelope.json'
    c.mutate('wrong-command-negative-fixture',lambda:dump(wrong,{'command':'install-context-keeper','agents':['claude'],'confirmed_at':utc(),'reference':REFERENCE}))
    c.I('ck-envelope-to-main','--approval-file',wrong)
    c.I('ck-target-mismatch-negative','--context-keeper','--approval-file',wrong)
    c.block('Both wrong-command routes exercised. Exact generated CK-plan target-mismatch subcase blocked by temp/pin source gate; invalid negative fixture is explicitly not a generated CK approval.')

def prefill(c):
    c.signal('codex');p=c.preview()['approval_plan'];a=synthetic_approval(p)
    a['context_keeper_consent']=True;path=c.area/'prefilled-main.json'
    c.mutate('prefilled-future-consent',lambda:dump(path,a))
    c.I('prefill-main-rejection','--approval-file',path)
    c.I('valid-main-install','--approval-file',c.approve(p))
    invalid=c.area/'unconfirmed-ck.json';c.mutate('unconfirmed-ck-negative-fixture',lambda:dump(invalid,{'command':'install-context-keeper'}))
    c.I('unconfirmed-ck-route','--context-keeper','--approval-file',invalid)
    c.block('Main future-consent injection exercised. Valid CK-plan missing-confirmation variant cannot get past unavailable durable pinned synthetic source; no real confirmation was fabricated.')

TAIL=r'''import sys,json
sys.path.insert(0,sys.argv[1])
from agm_core import ck_install,paths
request={'home':sys.argv[2],'platform_config':paths.select_platform(paths.load_agents_table(),'darwin')}
print(json.dumps(ck_install.tail({'status':'completed'},request),ensure_ascii=False))
'''
def tty_command(c,label,data):
    # A real OS PTY feeds only a controlled synthetic input. It does not turn
    # this generated keystroke into a human's real CK authorization.
    import pty,select,errno
    argv=[str(PYTHON),'-B','-c',TAIL,str(c.source/'scripts'),str(c.home)]
    def child():
        master,slave=pty.openpty()
        proc=subprocess.Popen(argv,stdin=slave,stdout=subprocess.PIPE,stderr=subprocess.PIPE,cwd=c.cwd,env=c.env)
        os.close(slave)
        os.write(master,data)
        out,err=proc.communicate(timeout=30);os.close(master)
        step=c.out/f'{c.index:03d}-{label}';write(step/'stdout.bin',out);write(step/'stderr.bin',err)
        result={'exit_code':proc.returncode,'pty_stdin_base64':base64.b64encode(data).decode(),'input_origin':'machine-fed synthetic PTY input, not real human confirmation'}
        try:result['json']=json.loads(out)
        except ValueError:pass
        return result
    c.record(label,child,argv)

def consent(c,kind):
    c.install()
    if kind=='noninteractive-empty':c.py('noninteractive-empty',TAIL,str(c.home))
    elif kind=='noninteractive-newline':c.cmd('noninteractive-newline',[PYTHON,'-B','-c',TAIL,c.source/'scripts',c.home],stdin=b'\n')
    else:tty_command(c,'pty-'+kind,{'enter':b'\n','n':b'n\n','eof':b'\x04'}[kind])
    c.check()
    if kind=='enter':
        c.block('OS-PTY newline branch was actually exercised with generated input; real-human confirmation and CK execution remain unproven because the durable pinned source is unavailable. No synthetic newline is represented as real user CK consent.')

def fail_isolation(c,kind):
    c.install(('codex','claude'));source=synthetic_ck(c)
    c.I('ck-source-gate-failure','--context-keeper','--ck-source',source);c.check()
    c.block('Main installation and source-unavailable CK failure isolation captured. Injected upstream/partial-agent failure after a valid CK plan is blocked by durable pinned-source gate; no replacement source validator or fabricated success plan.')

if __name__=='__main__':
    run_case(41,'CK 用户级尾步与固定源门禁',route)
    run_case(51,'CK 独立封皮路由与源门禁',route)
    run_case(52,'主安装/CK 错封皮路由',wrong_envelope)
    run_case(53,'预填未来同意与无确认封皮',prefill)
    for k in ('enter','n','eof','noninteractive-empty','noninteractive-newline'):
        run_case(54,'PTY 与非交互同意分支',lambda c,k=k:consent(c,k),k)
    for k in ('source-unavailable','partial-upstream-unavailable'):
        run_case(55,'CK 失败与主产品保留',lambda c,k=k:fail_isolation(c,k),k)
