"""Unified layout on real current kernels and synthetic six-agent detection."""
import copy
import json
from pathlib import Path
import shutil
import sys
import unittest
from unittest.mock import patch

sys.path[:0] = [str(Path(__file__).resolve().parents[2] / 'scripts'), str(Path(__file__).resolve().parent)]
from agm_core import user_entries, user_entry_layout as top, detect, paths, registry, uninstall, uninstall_recovery
from agm_core.entries import managed_span, sha256
from test_m404_install import InstallFixture, approved
from test_public_layout import _export_target


class ByteLayoutTests(unittest.TestCase):
    def test_opaque_remainder_and_bom(self):
        marker=user_entries.BASE_MARKER
        block=user_entries._wrap_block(marker,'public pointer and own rules')
        obj=dict(scope='machine',ownership='created',marker=marker,fingerprint=dict(value=sha256(block)))
        for private in [b'private',b'\xef\xbb\xbfprivate\r\n',b'<!-- context-keeper:start -->\r\n# memSharing\n@literal\n<!-- context-keeper:end -->\n',b'\n\r\nprivate without newline']:
            raw=private+block+b'\r\nfooter'
            final=top.arrange(raw,[(marker,block,obj)])
            bom=top.BOM if private.startswith(top.BOM) else b''
            remainder=private[len(bom):]+b'\r\nfooter'
            expected=bom+block+(b'' if remainder.startswith((b'\r',b'\n')) else b'\n')+remainder
            self.assertEqual(final,expected)
            self.assertEqual(top.arrange(final,[(marker,block,obj)]),final)

    def test_opaque_fragments_keep_all_original_whitespace(self):
        marker=user_entries.BASE_MARKER;block=user_entries._wrap_block(marker,'pointer and current agent')
        obj=dict(scope='machine',ownership='created',marker=marker,fingerprint=dict(value=sha256(block)))
        opaque=[b'private\r\n',b'<!-- context-keeper:start -->\r\n# Project rules @not-an-import\n<!-- context-keeper:end -->',b'\n\nprivate end without LF']
        for position in range(4):
            raw=b''.join(opaque[:position])+block+b''.join(opaque[position:])
            final=top.arrange(raw,[(marker,block,obj)])
            expected=block+b'\n'+b''.join(opaque)
            self.assertEqual(final,expected)

    def test_registered_reused_top_is_zero_write_without_new_rights(self):
        m=user_entries.BASE_MARKER;b=user_entries._wrap_block(m,'owned')
        obj=dict(scope='machine',ownership='reused',marker=m,fingerprint=dict(value=sha256(b)))
        raw=b+b'\nprivate'
        self.assertEqual(top.arrange(raw,[(m,b,obj)]),raw)
        self.assertEqual(obj['ownership'],'reused')
        with self.assertRaises(ValueError):top.arrange(b'private\n'+b,[(m,b,obj)])

    def test_unknown_duplicate_missing_and_drift_rejected(self):
        m=user_entries.BASE_MARKER;b=user_entries._wrap_block(m,'owned')
        obj=dict(scope='machine',ownership='created',marker=m,fingerprint=dict(value=sha256(b)))
        for raw,registered in [(b,None),(b+b,obj),(b'x',obj),(b.replace(b'owned',b'changed'),obj)]:
            with self.assertRaises(ValueError):top.arrange(raw,[(m,b,registered)])


class KernelLayoutFixture(InstallFixture):
    def setUp(self):
        super().setUp()
        shutil.rmtree(self.source);files=_export_target(self.source)
        self.request['source'].update(files=files)
        self.request['search_paths']=[];self.request['app_directories']=[]
        real=detect.detect_agents
        def installed(*args,**kwargs):
            result=real(*args,**kwargs)
            for fact in result['agents'].values():fact.update(status='installed',summary='synthetic detection only')
            return result
        self.addCleanup(patch.stopall)
        patch.object(detect,'detect_agents',side_effect=installed).start()
        self.original={}
        for agent,c in self.config.items():
            p=Path(paths.expand_path(c['user_entry'],home=str(self.home)));p.parent.mkdir(parents=True,exist_ok=True)
            raw=('private '+agent+'\r\n').encode()+b'<!-- context-keeper:start -->\nopaque @text\n<!-- context-keeper:end -->\r\nlast'
            p.write_bytes(raw);p.chmod(0o644);self.original[agent]=raw

    def assemble(self):
        request=dict(self.request,interactive=False);request.pop('source')
        preview=user_entries.run_user_entries(request)
        if preview['status']=='completed':return preview
        self.assertEqual(preview['status'],'approval_required',preview)
        approval=json.loads(preview['next_action']);approval.update(confirmed_at='2026-11-02T00:00:00Z',reference='synthetic top layout')
        return user_entries.run_user_entries(dict(request,approval=approval))

class KernelLayoutTests(KernelLayoutFixture):
    def test_fresh_six_top_idempotent_and_uninstall_restore(self):
        self.execute()
        saved={}
        for a,c in self.config.items():
            p=Path(paths.expand_path(c['user_entry'],home=str(self.home)));raw=p.read_bytes();saved[a]=raw
            if a=='claude':
                line=('@'+str(self.runtime.root/'memories/MEMORY.md')).encode()
                block=user_entries._wrap_block(user_entries.CLAUDE_FALLBACK_MARKER,user_entries.CLAUDE_FALLBACK_TEXT)
                self.assertEqual(raw,line+b'\n'+block+b'\n'+self.original[a])
            else:
                span=managed_span(raw,**user_entries.BASE_MARKER);self.assertEqual(span[0],0)
                self.assertEqual(raw[span[1]:],b'\n'+self.original[a])
            self.assertEqual(p.stat().st_mode&0o777,0o644)
        self.assertEqual(self.assemble()['status'],'completed')
        for a,c in self.config.items():self.assertEqual(Path(paths.expand_path(c['user_entry'],home=str(self.home))).read_bytes(),saved[a])
        backup=self.area/'recovery';plan=uninstall.preview(home=self.home,backup_dir=backup)
        approval=dict(plan=uninstall_recovery.summary(plan),confirmed_at='2026-11-02T00:00:00Z',reference='synthetic uninstall')
        uninstall.execute(approval,home=self.home,backup_dir=backup)
        for a,c in self.config.items():self.assertIn(self.original[a],Path(paths.expand_path(c['user_entry'],home=str(self.home))).read_bytes())
        restored=uninstall_recovery.recover(backup/'manifest.json')
        uninstall_recovery.recover(backup/'manifest.json',approval=dict(plan=restored['plan'],confirmed_at='2026-11-02T00:00:00Z',reference='synthetic restore'))
        for a,c in self.config.items():self.assertEqual(Path(paths.expand_path(c['user_entry'],home=str(self.home))).read_bytes(),saved[a])


    def test_shared_alias_is_not_a_relocation_grant(self):
        self.execute()
        ledger=json.loads(self.runtime.registry.read_bytes())
        p=self.home/'.codex/AGENTS.md';obj=copy.deepcopy(ledger['machine']['objects'][str(p)+'#public-source'])
        obj.update(scope='user',ownership='reused',original_existed=True,backup_manifest=None)
        ledger['shared_objects']['synthetic-shared-alias']=obj
        allowed=paths.allowed_user_paths(self.config,None,home=str(self.home))
        before=(p.read_bytes(),self.runtime.registry.read_bytes())
        with self.assertRaisesRegex(ValueError,'duplicate machine unit'):
            registry.serialize_registry(ledger,allowed_user_paths=allowed)
        self.assertEqual((p.read_bytes(),self.runtime.registry.read_bytes()),before)

    def test_fresh_bom_preserved_for_all_six(self):
        for a,c in self.config.items():
            p=Path(paths.expand_path(c['user_entry'],home=str(self.home)))
            self.original[a]=top.BOM+self.original[a]
            p.write_bytes(self.original[a])
        self.execute()
        for a,c in self.config.items():
            raw=Path(paths.expand_path(c['user_entry'],home=str(self.home))).read_bytes()
            self.assertEqual(raw.count(top.BOM),1)
            self.assertTrue(raw.startswith(top.BOM))
            self.assertTrue(raw.endswith(self.original[a][len(top.BOM):]))
            self.assertTrue(user_entries.top_layout_intact(raw,a,self.runtime.root/'memories/MEMORY.md'))
        self.assertEqual(self.assemble()['status'],'completed')


class LegacyUpgradeTests(KernelLayoutFixture):
    def install_old(self):
        import os,subprocess
        from test_public_layout import _export_release
        old=self.area/'old-016'
        files=_export_release(old,'ef742a2843edb3961d7bf3c71e8ca9cc921c5d1d','0.1.6')
        source=dict(root=str(old),url='https://github.com/vincent4j/mem-sharing',commit='eb31607bcd5fb1c2e5a6332e9e67682cd0cf956b',version='0.1.6',files=files)
        sf=self.area/'old-source.json';sf.write_text(json.dumps(source));rf=self.area/'detect.json';rf.write_text(json.dumps(dict(search_paths=[],app_directories=[])))
        boot="""import sys,runpy;sys.path.insert(0,sys.argv[1]);from agm_core import detect;detect.STANDARD_APP_DIRECTORIES=();real=detect.detect_agents

def synthetic(*a,**k):
 r=real(*a,**k)
 for f in r['agents'].values():f.update(status='installed',summary='synthetic detection only')
 return r

detect.detect_agents=synthetic;sys.argv=sys.argv[2:];runpy.run_path(sys.argv[0],run_name='__main__')"""
        env=dict(os.environ,HOME=str(self.home),TMPDIR=str(self.area),PYTHONDONTWRITEBYTECODE='1')
        base=[sys.executable,'-B','-c',boot,str(old/'scripts'),str(old/'scripts/install.py')]
        child=subprocess.run(base+['--source-manifest',str(sf),'--request-file',str(rf),'--operation-id','old-016'],capture_output=True,text=True,env=env)
        self.assertEqual(child.returncode,5,child.stdout+child.stderr)
        plan=json.loads(child.stdout)['approval_plan'];af=self.area/'old-approval.json';af.write_text(json.dumps(approved(plan)))
        done=subprocess.run(base+['--approval-file',str(af)],capture_output=True,text=True,env=env)
        self.assertEqual(done.returncode,0,done.stdout+done.stderr)
        return plan

    def candidate(self):
        import importlib.util
        from agm_core import user_install,upgrade
        source=self.request['source'];source.update(version='0.9.0',commit='c'*40)
        target,_=user_install._source(self.request)
        ledger=json.loads(self.runtime.registry.read_bytes())
        before=dict(schema_version=3,product_structure_version=1,product_code_version='0.1.6',source=ledger['product']['source'])
        after=dict(schema_version=3,product_structure_version=1,product_code_version='0.9.0',source={k:target[k] for k in ('url','commit','tree_sha256')})
        self.request['conversions']=[dict(before=before,after=after,direction='upgrade',entries=upgrade.UNIFIED_ENTRY_CONVERSION)]
        spec=importlib.util.spec_from_file_location('layout_installer',Path(__file__).resolve().parents[2]/'scripts/install.py');cli=importlib.util.module_from_spec(spec);spec.loader.exec_module(cli)
        return cli

    def test_frozen_after_rejects_rehashed_source_and_running_candidate(self):
        import importlib
        from agm_core import upgrade
        from test_release_014_upgrade import _load_old_kernel
        self.install_old();self.candidate()
        expected = upgrade.UNIFIED_ENTRY_AFTER
        self.assertEqual(set(expected), {'scripts/agents.json', 'scripts/agm_core/user_entries.py',
            'scripts/agm_core/user_entry_layout.py', 'scripts/agm_core/entry_layout.py'})
        before = uninstall_recovery.tree(self.home)
        for name,digest in expected.items():
            path=self.source/name;raw=path.read_bytes()
            self.assertEqual(sha256(raw),digest)
            try:
                path.write_bytes(raw+b'\n')
                req=copy.deepcopy(self.request);req['source']['files'][name]=sha256(path.read_bytes())
                alias=_load_old_kernel(self.source)
                kernel=importlib.import_module(alias+'.user_install')
                altered=importlib.import_module(alias+'.upgrade')
                checked,_=kernel._source(req)
                req['conversions'][0]['after']['source']={k:checked[k] for k in ('url','commit','tree_sha256')}
                with self.subTest(module=name):
                    with self.assertRaisesRegex(ValueError,'frozen after contract'):
                        altered.plan_upgrade(req)
                    self.assertEqual(uninstall_recovery.tree(self.home),before)
            finally:path.write_bytes(raw)
        # Pristine source plus a separately imported altered running kernel:
        # no mocked digest, security gate or __file__ substitution.
        running=self.area/'altered-running-kernel';shutil.copytree(self.source,running)
        helper=running/'scripts/agm_core/user_entry_layout.py';helper.write_bytes(helper.read_bytes()+b'\n')
        alias=_load_old_kernel(running);altered=importlib.import_module(alias+'.upgrade')
        with self.assertRaisesRegex(ValueError,'source/running bytes'):
            altered._unified_after_contract(self.request['source'])
        self.assertEqual(uninstall_recovery.tree(self.home),before)

    def test_real_016_to_candidate_single_outer_approval(self):
        self.install_old();cli=self.candidate()
        plan=cli.plan_machine(self.request);self.assertTrue(plan['entry_plan']['changes'])
        done=cli.execute_machine(plan,approved(plan),request=self.request)
        self.assertEqual(done['status'],'completed',done)
        for a,c in self.config.items():
            raw=Path(paths.expand_path(c['user_entry'],home=str(self.home))).read_bytes()
            self.assertIn(self.original[a],raw)
            marker=user_entries.CLAUDE_FALLBACK_MARKER if a=='claude' else user_entries.BASE_MARKER
            self.assertLess(managed_span(raw,**marker)[0],len(raw)-len(self.original[a]))
            self.assertTrue(raw.startswith(b'@' if a=='claude' else b'<!-- mem-sharing:rules:start -->'))
        same=cli.plan_machine(self.request)
        self.assertTrue(same['plan']['noop']);self.assertFalse(same['entry_plan'])

    def test_explicit_cli_binding_drift_rollback_and_migration(self):
        import io,contextlib
        from agm_core import entry_layout,upgrade,transaction
        self.install_old()
        request=self.area/'layout-detect.json';request.write_text(json.dumps(dict(search_paths=[],app_directories=[])))
        def cli(approval=None,home=None):
            argv=[entry_layout.COMMAND,'--request-file',str(request),'--json']
            if approval:argv+=['--approval-file',str(approval)]
            output=io.StringIO()
            with contextlib.redirect_stdout(output):code=entry_layout.cli(argv,home=home or self.home)
            return code,json.loads(output.getvalue())
        before={p:p.read_bytes() for p in self.home.rglob('*') if p.is_file()}
        self.assertEqual(cli()[0],2)  # Uninstalled checkout cannot act on old C.
        self.assertTrue(all(p.read_bytes()==v for p,v in before.items()))
        wrong=self.area/'wrong-home';wrong.mkdir();self.assertEqual(cli(home=wrong)[0],2);self.assertEqual(list(wrong.iterdir()),[])
        self.candidate();plan=upgrade.plan_upgrade(self.request)
        upgrade.execute_upgrade(plan,approved(plan),request=self.request)
        code,result=cli();self.assertEqual(code,5,result)
        approval=json.loads(result['next_action']);approval.update(confirmed_at='2026-11-02T00:00:00Z',reference='synthetic explicit layout')
        af=self.area/'layout-approval.json';af.write_text(json.dumps(approval))
        bad=dict(approval,reference='<confirmation placeholder>');badfile=self.area/'bad-approval.json';badfile.write_text(json.dumps(bad))
        self.assertEqual(cli(badfile)[0],2)
        codex=self.home/'.codex/AGENTS.md';old=codex.read_bytes()
        codex.chmod(0o600);self.assertEqual(cli(af)[0],5);self.assertEqual(codex.stat().st_mode&0o777,0o600);codex.chmod(0o644)
        codex.write_bytes(old+b'private after approval')
        snapshot={p:p.read_bytes() for p in self.home.rglob('*') if p.is_file()}
        self.assertEqual(cli(af)[0],5);self.assertTrue(all(p.read_bytes()==v for p,v in snapshot.items()))
        codex.write_bytes(old)
        before={p:p.read_bytes() for p in [self.runtime.registry,*[Path(paths.expand_path(c['user_entry'],home=str(self.home))) for c in self.config.values()]]}
        real=transaction.Transaction.run
        fired=[]
        def run(tx,*a,**k):
            def fail(event,path):
                if event=='after_write' and not fired:
                    fired.append(True);raise RuntimeError('synthetic layout write interruption')
            tx.hook=fail
            return real(tx,*a,**k)
        with patch.object(transaction.Transaction,'run',run):self.assertEqual(cli(af)[0],2)
        self.assertTrue(fired);self.assertTrue(all(p.read_bytes()==v for p,v in before.items()))
        code,result=cli(af);self.assertEqual(code,0,result)
        self.assertEqual(cli()[0],0)
        for a,c in self.config.items():
            raw=Path(paths.expand_path(c['user_entry'],home=str(self.home))).read_bytes()
            self.assertTrue(user_entries.top_layout_intact(raw,a,self.runtime.root/'memories/MEMORY.md'))
            self.assertIn(self.original[a],raw)
