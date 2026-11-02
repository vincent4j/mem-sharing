"""Real old installer + real historical public-layout Transaction; temporary HOME.

The historical append is produced by the actual ea553738 kernel, not hand-made
manifest JSON. The current test kernel is then explicitly staged (fixture only,
not an upgrade acceptance claim). Detection is synthetic; no real HOME/CK used.
"""
import copy
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2]/'scripts'))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from agm_core import legacy_reconcile as reconcile, paths, registry, policy_migration
from agm_core import entries, user_install, legacy_import as legacy
from agm_core.layout import resolve_layout
from test_public_layout import _export_release, _export_target
import agm

NOW = '2026-11-02T08:00:00Z'
OLD012 = '0f690ef7aabf747a23bacc7662c19bee34c4bf52'
OLD013 = 'ea553738f37a5cc5befb34bf241d12da33f07b21'


def approval(plan):
    return {'plan': reconcile.view(plan), 'confirmed_at': NOW,
            'reference': 'explicit synthetic reconciliation approval'}


def snapshot(home):
    rows = {}
    def visit(p):
        st = p.lstat()
        rows[str(p)] = (st.st_mode, st.st_mtime_ns,
                       os.readlink(p) if p.is_symlink() else p.read_bytes() if p.is_file() else None)
        if p.is_dir() and not p.is_symlink():
            for child in sorted(p.iterdir()): visit(child)
    visit(home)
    return rows


class ReconcileTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.area = Path(self.temp.name).resolve(); self.home = self.area/'home'; self.home.mkdir()
        self.runtime = resolve_layout(self.home); self.path = self.home/'.claude/CLAUDE.md'
        self.path.parent.mkdir()
        self.ckold = b'<!-- context-keeper:start -->\nold independent CK rules\n<!-- context-keeper:end -->'
        self.cknew = b'<!-- context-keeper:start -->\nnew independent CK rules with different length\n<!-- context-keeper:end -->'
        self.private = b'private prefix\r\n'
        self.path.write_bytes(self.private+self.ckold+b'\r\nprivate suffix\r\n')
        self.path.chmod(0o644)
        self.bin = self.area/'bin'; self.bin.mkdir()
        package = self.area/'package'; (package/'bin').mkdir(parents=True)
        exe = package/'bin/claude'; exe.write_bytes(b'#!/bin/sh\n'); exe.chmod(0o755)
        (package/'package.json').write_text(json.dumps({'name':'@anthropic-ai/claude-code','version':'1','bin':{'claude':'bin/claude'}}))
        (self.bin/'claude').symlink_to(exe)
        if getattr(self, 'codex_entry', False):
            cp=self.area/'codex-package';(cp/'bin').mkdir(parents=True)
            ce=cp/'bin/codex';ce.write_bytes(b'#!/bin/sh\n');ce.chmod(0o755)
            (cp/'package.json').write_text(json.dumps({'name':'@openai/codex','version':'1','bin':{'codex':'bin/codex'}}))
            (self.bin/'codex').symlink_to(ce)
            native=self.home/'.codex/AGENTS.md';native.parent.mkdir();native.write_bytes(b'private codex\r\n');native.chmod(0o644)
        self.request = self.area/'detect.json'
        self.request.write_text(json.dumps({'search_paths':[str(self.bin)],'app_directories':[]}))
        # Old kernels, actual Git bytes and subprocess installer approvals.
        self.old12 = self.area/'old12'; files12 = _export_release(self.old12,OLD012,'0.1.2')
        source12 = dict(root=str(self.old12),url='https://github.com/vincent4j/mem-sharing',commit=OLD012,version='0.1.2',files=files12)
        self.install(self.old12, source12, self.request, 'install-012')
        self.old13 = self.area/'old13'; files13 = _export_release(self.old13,OLD013,'0.1.3')
        source13 = dict(root=str(self.old13),url='https://github.com/vincent4j/mem-sharing',commit=OLD013,version='0.1.3',files=files13)
        checked12,_ = user_install._source({'source':source12}); checked13,_ = user_install._source({'source':source13})
        request13 = self.area/'conversion013.json'
        request13.write_text(json.dumps({'search_paths':[str(self.bin)],'app_directories':[], 'conversions':[{
            'before':dict(schema_version=3,product_structure_version=1,product_code_version='0.1.2',source={k:checked12[k] for k in ('url','commit','tree_sha256')}),
            'after':dict(schema_version=3,product_structure_version=1,product_code_version='0.1.3',source={k:checked13[k] for k in ('url','commit','tree_sha256')}),
            'direction':'upgrade','entries':{'type':'public-memory-layout-v1'}}]}))
        if getattr(self, 'new_topic', False):
            (self.runtime.root/'memories/topics/使用约定.md').write_bytes(policy_migration.legacy('topic',self.runtime))
        if getattr(self, 'missing_topic', False):
            (self.runtime.root/'memories/topics/使用约定.md').unlink()
        self.install(self.old13, source13, request13, 'history-013')
        self.history = self.runtime.backups/'migration-history-013/tx/manifest.json'
        self.assertEqual(json.loads(self.history.read_text())['status'],'committed')
        self.baseline = self.path.read_bytes()
        self.assertTrue(self.baseline.endswith(policy_migration.legacy('claude',self.runtime)))
        # Stage this worktree's current kernel in synthetic C. This is not a
        # release/version transition test and never modifies source constants.
        target = self.area/'current'; target_files = _export_target(target)
        source = dict(root=str(target),url='fixture://current',commit='c'*40,version='0.9.0',files=target_files)
        checked, files = user_install._source({'source':source})
        shutil.rmtree(self.runtime.code); shutil.copytree(target,self.runtime.code)
        data = json.loads(self.runtime.registry.read_bytes())
        data['product'].update(product_code_version='0.9.0',source={k:checked[k] for k in ('url','commit','tree_sha256')})
        allowed = paths.allowed_user_paths(policy_migration.config(),None,home=str(self.home))
        self.runtime.registry.write_bytes(registry.serialize_registry(data,allowed_user_paths=allowed))
        self.runtime.registry.chmod(0o600)
        (self.runtime.code/'.agm-code-manifest.json').write_bytes(legacy.encoded({'product_id':'mem-sharing','source':data['product']['source'],'files':files}))
        self.path.write_bytes(self.baseline.replace(self.ckold,self.cknew))
        self.path.chmod(0o644)

    def install(self, root, source, request, op):
        sf = self.area/(op+'-source.json'); sf.write_text(json.dumps(source))
        env = dict(os.environ,HOME=str(self.home),PYTHONDONTWRITEBYTECODE='1')
        argv = [sys.executable,'-B',str(root/'scripts/install.py'),'--source-manifest',str(sf),'--request-file',str(request),'--operation-id',op]
        if op == 'install-012':
            argv += ['--agent','claude']
            if getattr(self, 'codex_entry', False):argv += ['--agent','codex']
        preview = subprocess.run(argv,env=env,input='',text=True,capture_output=True)
        self.assertEqual(preview.returncode,5,preview.stdout+preview.stderr)
        plan = json.loads(preview.stdout)['approval_plan']; approve = dict(plan,confirmed_at=NOW,reference='actual historical producer in synthetic HOME')
        af = self.area/(op+'-approval.json'); af.write_text(json.dumps(approve))
        done = subprocess.run([sys.executable,'-B',str(root/'scripts/install.py'),'--approval-file',str(af)],env=env,input='',text=True,capture_output=True)
        self.assertEqual(done.returncode,0,done.stdout+done.stderr)

    def preview(self): return reconcile.preview(home=self.home)

    def rejected(self):
        before = snapshot(self.home)
        with self.assertRaises((ValueError,OSError)):
            self.preview()
        self.assertEqual(snapshot(self.home),before)

    def test_real_producer_chain_preview_execute_policy_and_noop(self):
        original = self.path.read_bytes(); before = snapshot(self.home)
        with self.assertRaisesRegex(ValueError,'Native import baseline drift'):
            policy_migration.preview(home=self.home)
        p=self.preview(); self.assertEqual(snapshot(self.home),before)
        self.assertEqual(len(p['evidence']),1)
        self.assertEqual(p['ck']['outside'],'byte_identical')
        self.assertFalse(p['noop'])
        view=reconcile.view(p); self.assertNotIn('after_hex',view); self.assertNotIn('private prefix',json.dumps(view))
        done=reconcile.execute(approval(p),home=self.home); self.assertEqual(done['status'],'completed')
        current=self.path.read_bytes(); self.assertIn(self.cknew,current); self.assertIn(self.private,current)
        oldspan=entries.managed_span(original,**user_entries_marker())
        newsp=entries.managed_span(current,**user_entries_marker())
        self.assertEqual(original[:oldspan[0]]+original[oldspan[1]:],current[:newsp[0]]+current[newsp[1]:])
        self.assertEqual(self.path.stat().st_mode & 0o777,0o644)
        self.assertEqual(json.loads(Path(done['manifest']).read_text())['status'],'committed')
        policy_migration.preview(home=self.home)  # ordinary whole-file guard now accepts
        noop=self.preview(); self.assertTrue(noop['noop']); before=snapshot(self.home)
        self.assertTrue(reconcile.execute(approval(noop),home=self.home)['noop'])
        self.assertEqual(snapshot(self.home),before)

    def test_negative_content_matrix_zero_write(self):
        raw=self.path.read_bytes(); line=('@'+str(self.runtime.root/'memories/MEMORY.md')).encode()
        mutations=[raw+b'outside edit',raw.replace(self.cknew,b''),raw+self.cknew,
                   raw.replace(b'context-keeper:end',b'context-keeper:bad'),
                   raw.replace(line,b'@/wrong'),raw+b'\n'+line+b'\n',
                   raw.replace(b'<!-- mem-sharing:claude-fallback:start -->',b'<!-- wrong:start -->'),
                   raw.replace(policy_migration.legacy('claude',self.runtime),policy_migration.legacy('claude',self.runtime)+b'X'),
                   raw.replace(b'private prefix',b'private altered')]
        # A change inside the registered owned block (not outside only).
        mutations.append(raw.replace(b'@AGENTS.md',b'@OTHER.md'))
        for mutation in mutations:
            with self.subTest(sha=entries.sha256(mutation)):
                self.path.write_bytes(mutation); self.rejected()
        self.path.write_bytes(raw)

    def test_history_schema_and_status_matrix(self):
        raw=self.history.read_bytes(); doc=json.loads(raw)
        for key,value in [('status','prepared'),('status','rolled_back'),('registry_path','/other/home/registry.json'),('operation','unknown-producer'),('schema_version',True),('error','unknown'),('extra',1)]:
            changed=copy.deepcopy(doc); changed[key]=value
            self.history.write_text(json.dumps(changed)); self.history.chmod(0o600)
            with self.subTest(field=key,value=value):self.rejected()
        self.history.write_bytes(raw)
        self.history.write_bytes(b'{"status":"committed",'+raw.lstrip()[1:])
        self.rejected();self.history.write_bytes(raw)

    def test_evidence_backups_symlinks_modes_hash_and_missing(self):
        doc=json.loads(self.history.read_text());index=next(ix for ix,e in enumerate(doc['entries']) if e['path']==str(self.path));f=self.history.parent/(str(index)+'.before');raw=f.read_bytes()
        f.write_bytes(raw+b'corrupt');self.rejected();f.write_bytes(raw)
        f.chmod(0o644);self.rejected();f.chmod(0o600)
        f.unlink();f.symlink_to(self.area/'missing');self.rejected();f.unlink();f.write_bytes(raw);f.chmod(0o600)
        hist=self.history.read_bytes();self.history.unlink();self.history.symlink_to(self.area/'missing');self.rejected();self.history.unlink();self.history.write_bytes(hist);self.history.chmod(0o600)
        tx=self.history.parent;renamed=tx.with_name('saved');tx.rename(renamed);tx.symlink_to(renamed);self.rejected();tx.unlink();renamed.rename(tx)
        self.history.unlink();self.rejected();self.history.write_bytes(hist);self.history.chmod(0o600)

    def test_wrong_home_and_current_symlink_and_lock(self):
        other=self.area/'otherhome';other.mkdir();before=snapshot(other)
        with self.assertRaises((OSError,ValueError)):reconcile.preview(home=other)
        self.assertEqual(snapshot(other),before)
        raw=self.path.read_bytes();self.path.unlink();self.path.symlink_to(self.area/'missing');self.rejected();self.path.unlink();self.path.write_bytes(raw);self.path.chmod(0o644)
        self.runtime.lock.mkdir();self.rejected();self.runtime.lock.rmdir()
        installer_lock=self.home/'.mem-sharing-install.lock'
        installer_lock.mkdir();self.rejected();installer_lock.rmdir()
        guard=self.home/'.mem-sharing-upgrade.json';guard.write_text('{}');self.rejected();guard.unlink()

    def test_approval_current_evidence_registry_and_kernel_drift(self):
        p=self.preview();a=approval(p)
        bad=copy.deepcopy(a);bad['reference']='<not a real confirmation>';before=snapshot(self.home)
        with self.assertRaises(ValueError):reconcile.execute(bad,home=self.home)
        self.assertEqual(snapshot(self.home),before)
        self.path.write_bytes(self.path.read_bytes()+b'user edit');before=snapshot(self.home)
        with self.assertRaises(ValueError):reconcile.execute(a,home=self.home)
        self.assertEqual(snapshot(self.home),before)
        self.path.write_bytes(bytes.fromhex(p['before_hex']))
        raw=self.history.read_bytes();self.history.write_bytes(raw+b'\n');before=snapshot(self.home)
        with self.assertRaises(ValueError):reconcile.execute(a,home=self.home)
        self.assertEqual(snapshot(self.home),before);self.history.write_bytes(raw)
        reg=self.runtime.registry.read_bytes();self.runtime.registry.write_bytes(reg+b'\n');before=snapshot(self.home)
        with self.assertRaises(ValueError):reconcile.execute(a,home=self.home)
        self.assertEqual(snapshot(self.home),before);self.runtime.registry.write_bytes(reg)
        module=self.runtime.code/'scripts/agm_core/legacy_reconcile.py';module.write_bytes(module.read_bytes()+b'\n');before=snapshot(self.home)
        with self.assertRaises(ValueError):reconcile.execute(a,home=self.home)
        self.assertEqual(snapshot(self.home),before)

    def test_registered_ownership_and_historical_after_negatives(self):
        raw=self.runtime.registry.read_bytes(); doc=json.loads(raw)
        imported=next(o for o in doc['machine']['objects'].values() if o['kind']=='import' and o['path']==str(self.path))
        oid=next(k for k,v in doc['machine']['objects'].items() if v is imported)
        for field,value in [('ownership','created'),('agents',['codex'])]:
            changed=copy.deepcopy(doc);changed['machine']['objects'][oid][field]=value
            self.runtime.registry.write_text(json.dumps(changed));self.rejected()
        self.runtime.registry.write_bytes(raw)
        hist=self.history.read_bytes(); changed=json.loads(hist)
        row=next(r for r in changed['entries'] if r['path']==str(self.path))
        row['after']['fingerprint']='0'*64
        self.history.write_text(json.dumps(changed));self.rejected();self.history.write_bytes(hist)

    def test_locked_evidence_change_prevents_target_writes(self):
        p=self.preview();before=self.path.read_bytes();ledger=self.runtime.registry.read_bytes()
        extra=self.history.parent/'unknown'
        def inject(event,path):
            if event=='before_write' and not extra.exists():extra.write_bytes(b'unknown evidence')
        with self.assertRaisesRegex(ValueError,'candidate set changed|evidence directory changed'):
            reconcile.execute(approval(p),home=self.home,hook=inject)
        self.assertEqual(self.path.read_bytes(),before)
        self.assertEqual(self.runtime.registry.read_bytes(),ledger)

    def rewrite_historical_journal(self, edit=None):
        """Mutations can recompute public digests, never an authenticity oracle."""
        jp=self.history.parent.parent/'journal.json';j=json.loads(jp.read_bytes())
        if edit:edit(j['plan'])
        body=dict(j['plan']);body.pop('plan_sha256')
        j['plan']['plan_sha256']=entries.sha256(legacy.encoded(body))
        j['approval']=dict(j['plan'],confirmed_at=NOW,reference='synthetic altered historical evidence')
        j['manifest_sha256']=entries.sha256(self.history.read_bytes())
        jp.write_bytes(legacy.encoded(j));jp.chmod(0o600)

    def test_foreign_scope_even_with_resealed_historical_plan(self):
        doc=json.loads(self.history.read_bytes());i=len(doc['entries'])-1
        row=copy.deepcopy(doc['entries'][0]);row['path']=str(self.home/'unrelated-private.txt')
        row['before']=dict(existed=False,kind='absent',mode=None,link_target=None,fingerprint=None,backup=None)
        row['after']=dict(existed=True,kind='file',mode=0o644,link_target=None,fingerprint='0'*64,backup=None)
        reg=doc['entries'][-1];(self.history.parent/reg['before']['backup']).rename(self.history.parent/(str(i+1)+'.before'))
        reg['before']['backup']=str(i+1)+'.before';doc['entries'].insert(i,row)
        self.history.write_bytes(legacy.encoded(doc))
        def edit(plan):
            plan['targets'].append(dict(kind='guide_topic',path=row['path'],before={'kind':'absent'},
                after=dict(kind='file',fingerprint='0'*64,mode=0o644),outside_fingerprint=None))
            plan['order'].insert(-1,row['path'])
        self.rewrite_historical_journal(edit);self.rejected()

    def test_registry_before_must_be_json_even_with_resealed_plan(self):
        doc=json.loads(self.history.read_bytes());r=doc['entries'][-1]
        blob=b'not a registry';(self.history.parent/r['before']['backup']).write_bytes(blob)
        r['before']['fingerprint']=entries.sha256(blob);self.history.write_bytes(legacy.encoded(doc))
        def edit(plan):
            plan['v1_registry_hex']=blob.hex();plan['v1_registry_sha256']=entries.sha256(blob)
            plan['observations'][str(self.runtime.registry)]['fingerprint']=entries.sha256(blob)
        self.rewrite_historical_journal(edit);self.rejected()

    def test_forged_known_after_even_with_resealed_plan(self):
        doc=json.loads(self.history.read_bytes());row=doc['entries'][1];row['after']['fingerprint']='0'*64
        self.history.write_bytes(legacy.encoded(doc))
        self.rewrite_historical_journal(lambda p:p['targets'][1]['after'].update(fingerprint='0'*64))
        self.rejected()

    def test_after_registry_scope_must_equal_producer_delta(self):
        doc=json.loads(self.history.read_bytes());jp=self.history.parent.parent/'journal.json'
        plan=json.loads(jp.read_bytes())['plan'];after=json.loads(bytes.fromhex(plan['v2_registry_hex']))
        imported=next(o for o in after['machine']['objects'].values() if o['kind']=='import')
        imported['fingerprint']['value']='0'*64
        blob=legacy.encoded(after);doc['entries'][-1]['after']['fingerprint']=entries.sha256(blob)
        self.history.write_bytes(legacy.encoded(doc))
        self.rewrite_historical_journal(lambda p:p.update(v2_registry_hex=blob.hex(),final_registry_sha256=entries.sha256(blob)))
        self.rejected()

    def test_new_prepared_candidate_at_before_write_is_rejected(self):
        p=self.preview();raw=self.path.read_bytes();ledger=self.runtime.registry.read_bytes()
        added=self.runtime.backups/'migration-new-uncommitted';injected=False
        def inject(event,path):
            nonlocal injected
            if event=='before_write' and not injected:
                injected=True;shutil.copytree(self.history.parent.parent,added)
                m=added/'tx/manifest.json';d=json.loads(m.read_bytes());d['status']='prepared';m.write_bytes(legacy.encoded(d))
        with self.assertRaisesRegex(ValueError,'candidate set changed'):
            reconcile.execute(approval(p),home=self.home,hook=inject)
        self.assertTrue(injected);self.assertEqual(self.path.read_bytes(),raw);self.assertEqual(self.runtime.registry.read_bytes(),ledger)

    def test_unselected_candidate_status_bound_and_approval_drift_zero_write(self):
        other=self.runtime.backups/'other-transaction';other.mkdir(mode=0o700)
        m=other/'manifest.json';m.write_bytes(legacy.encoded({'entries':[], 'status':'prepared'}));m.chmod(0o600)
        p=self.preview();m.write_bytes(legacy.encoded({'entries':[], 'status':'committed'}))
        before=snapshot(self.home)
        with self.assertRaises(ValueError):reconcile.execute(approval(p),home=self.home)
        self.assertEqual(snapshot(self.home),before)

    def test_later_public_files_are_not_historical_scene_dependencies(self):
        topic=self.runtime.root/'memories/topics/使用约定.md';index=self.runtime.root/'memories/MEMORY.md'
        topic.write_bytes(b'later separately governed topic\r\n');index.write_bytes(b'later separately governed index\n')
        before=(topic.read_bytes(),index.read_bytes())
        p=self.preview();reconcile.execute(approval(p),home=self.home)
        self.assertEqual((topic.read_bytes(),index.read_bytes()),before)
        self.assertIn(self.cknew,self.path.read_bytes())

    def test_existing_unselected_candidate_changes_at_write_are_rejected(self):
        other=self.runtime.backups/'other-transaction';other.mkdir(mode=0o700)
        m=other/'manifest.json';m.write_bytes(legacy.encoded({'entries':[], 'status':'prepared'}));m.chmod(0o600)
        p=self.preview();raw=self.path.read_bytes();ledger=self.runtime.registry.read_bytes()
        def inject(event,path):
            if event=='before_write':m.write_bytes(legacy.encoded({'entries':[], 'status':'committed'}))
        with self.assertRaisesRegex(ValueError,'candidate set changed'):
            reconcile.execute(approval(p),home=self.home,hook=inject)
        self.assertEqual(self.path.read_bytes(),raw);self.assertEqual(self.runtime.registry.read_bytes(),ledger)

    def test_resealed_toolkit_is_not_a_trust_root(self):
        jp=self.history.parent.parent/'journal.json';saved=jp.read_bytes();tools=self.history.parent.parent/'tools/agm_core'
        helper=tools/'registry.py';raw=helper.read_bytes()
        helper.write_bytes(raw+b'\n# changed helper\n')
        self.rewrite_historical_journal(lambda p:next(t for t in p['tools'] if t['path']=='registry.py').update(sha256=entries.sha256(helper.read_bytes())))
        self.rejected();helper.write_bytes(raw);jp.write_bytes(saved)
        extra=tools/'foreign_helper.py';extra.write_bytes(b'# foreign\n');extra.chmod(0o600)
        self.rewrite_historical_journal(lambda p:p['tools'].append(dict(path=extra.name,sha256=entries.sha256(extra.read_bytes()),mode=0o644)))
        self.rejected();extra.unlink();jp.write_bytes(saved)
        helper.unlink()
        self.rewrite_historical_journal(lambda p:p.update(tools=[t for t in p['tools'] if t['path']!='registry.py']))
        self.rejected();helper.write_bytes(raw);helper.chmod(0o600);jp.write_bytes(saved)
        self.rewrite_historical_journal(lambda p:next(t for t in p['tools'] if t['path']=='registry.py').update(mode=0o755))
        self.rejected();jp.write_bytes(saved)
        helper.chmod(0o644);self.rejected();helper.chmod(0o600)

    def remove_historical_output(self, name):
        doc=json.loads(self.history.read_bytes())
        blobs={row['path']:(self.history.parent/row['before']['backup']).read_bytes()
               for row in doc['entries'] if row['before']['backup'] is not None}
        for p in self.history.parent.glob('*.before'):p.unlink()
        doc['entries']=[row for row in doc['entries'] if row['path']!=name]
        for i,row in enumerate(doc['entries']):
            if row['before']['backup'] is not None:
                row['before']['backup']=str(i)+'.before'
                p=self.history.parent/row['before']['backup'];p.write_bytes(blobs[row['path']]);p.chmod(0o600)
        self.history.write_bytes(legacy.encoded(doc))
        def edit(p):
            p['targets']=[t for t in p['targets'] if t['path']!=name];p['order'].remove(name)
        self.rewrite_historical_journal(edit)

    def test_resealed_omitted_required_topic_rejected(self):
        self.remove_historical_output(str(self.runtime.root/'memories/topics/使用约定.md'));self.rejected()

    def test_resealed_omitted_required_index_rejected(self):
        self.remove_historical_output(str(self.runtime.root/'memories/MEMORY.md'));self.rejected()

    def test_executing_helper_must_match_installed_kernel(self):
        original=reconcile._file
        helper=Path(policy_migration.__file__).resolve()
        def changed(path,**kwargs):
            raw,fact=original(path,**kwargs)
            return (raw+b'\n',fact) if Path(path)==helper else (raw,fact)
        with patch.object(reconcile,'_file',side_effect=changed):
            self.rejected()

    def test_interruption_rolls_back_file_and_registry(self):
        p=self.preview();before=self.path.read_bytes();reg=self.runtime.registry.read_bytes()
        def fail(event,path):
            if event=='after_write' and path==self.path:raise RuntimeError('injected before registry commit')
        with self.assertRaises(ValueError):reconcile.execute(approval(p),home=self.home,hook=fail)
        self.assertEqual(self.path.read_bytes(),before);self.assertEqual(self.runtime.registry.read_bytes(),reg)
        committed=[q for q in self.runtime.backups.glob('*/manifest.json') if json.loads(q.read_text()).get('operation')==reconcile.COMMAND]
        self.assertEqual(len(committed),1);self.assertEqual(json.loads(committed[0].read_text())['status'],'rolled_back')

    def test_ck_crlf_and_nonregular_evidence(self):
        self.path.write_bytes(self.path.read_bytes().replace(self.cknew,self.cknew.replace(b'\n',b'\r\n')))
        p=self.preview();ck=bytes.fromhex(p['before_hex'])[slice(*p['ck']['current_span'])]
        reconcile.execute(approval(p),home=self.home)
        self.assertIn(ck,self.path.read_bytes());self.assertIn(self.private,self.path.read_bytes())
        # A separate regular-file reader check rejects FIFO without opening it.
        fifo=self.area/'fifo';os.mkfifo(fifo)
        with self.assertRaisesRegex(ValueError,'regular file'):reconcile._file(fifo)

    def test_no_drift_old_template_is_not_an_adoption_path(self):
        self.path.write_bytes(self.baseline);self.rejected()

    def test_cli_route_preview_no_private_text(self):
        with patch.dict(os.environ,HOME=str(self.home)):
            output=io.StringIO()
            with __import__('contextlib').redirect_stdout(output):
                code=reconcile.cli([reconcile.COMMAND,'--json'])
        self.assertEqual(code,5);value=json.loads(output.getvalue());self.assertEqual(value['status'],'approval_required')
        self.assertNotIn('private prefix',output.getvalue())
        output=io.StringIO();error=io.StringIO()
        # main's explicit runtime test seam routes to the same core command.
        with patch.dict(os.environ,HOME=str(self.home)):
            with __import__('contextlib').redirect_stdout(output):code=agm.main([reconcile.COMMAND,'--json'])
        self.assertEqual(code,5)


def user_entries_marker():
    from agm_core.user_entries import CLAUDE_FALLBACK_MARKER
    return CLAUDE_FALLBACK_MARKER


class MetadataTests(unittest.TestCase):
    def test_frozen_producer_constants_match_git_pin(self):
        import ast,hashlib
        repo=Path(__file__).resolve().parents[2];pin=OLD013
        records=subprocess.check_output(['git','ls-tree','-rz',pin,'scripts/agm_core'],cwd=repo).decode().split('\0')
        expected=[]
        for record in records:
            if not record:continue
            meta,name=record.split('\t');mode,kind,blob=meta.split()
            self.assertEqual(mode,'100644');self.assertTrue(name.endswith('.py'))
            raw=subprocess.check_output(['git','cat-file','blob',blob],cwd=repo)
            expected.append((name.rsplit('/',1)[1],hashlib.sha256(raw).hexdigest()))
        self.assertEqual(tuple(expected),reconcile.HISTORICAL_TOOLS)
        source=subprocess.check_output(['git','show',pin+':scripts/agm_core/public_layout.py'],cwd=repo)
        launcher=next(ast.literal_eval(n.value) for n in ast.parse(source).body if isinstance(n,ast.Assign)
                      and any(isinstance(t,ast.Name) and t.id=='LAUNCHER' for t in n.targets))
        self.assertEqual(hashlib.sha256(launcher).hexdigest(),reconcile.HISTORICAL_LAUNCHER_SHA256)

    def test_absent_requires_real_boolean(self):
        data = dict(existed=False, kind='absent', mode=None, link_target=None,
                    fingerprint=None, backup=None)
        reconcile._metadata(data, before=True, index=0)
        data['existed'] = 0
        with self.assertRaises(ValueError):
            reconcile._metadata(data, before=True, index=0)


class AbsentTopicTests(unittest.TestCase):
    def test_real_producer_with_absent_historical_topic(self):
        case=ReconcileTests('test_real_producer_chain_preview_execute_policy_and_noop')
        case.missing_topic=True
        try:
            case.setUp()
            case.test_real_producer_chain_preview_execute_policy_and_noop()
        finally:
            case.doCleanups()


class HistoricalBranchTests(unittest.TestCase):
    def run_branch(self, **flags):
        case=ReconcileTests('test_real_producer_chain_preview_execute_policy_and_noop')
        for key,value in flags.items():setattr(case,key,value)
        try:
            case.setUp();case.test_real_producer_chain_preview_execute_policy_and_noop()
        finally:case.doCleanups()

    def test_canonical_new_topic_noop_is_supported(self):
        self.run_branch(new_topic=True)

    def test_real_codex_and_claude_historical_outputs(self):
        self.run_branch(codex_entry=True)
