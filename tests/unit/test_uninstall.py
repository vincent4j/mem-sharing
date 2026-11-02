"""Synthetic HOME acceptance: byte preservation, detach order, independent restore."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from test_m404_install import InstallFixture
from agm_core import uninstall, uninstall_recovery as recovery
from agm_core import detect, registry, paths


def approval(view):
    return {'plan':view,'reference':'explicit synthetic approval','confirmed_at':'2026-11-01T00:00:00Z'}


class UninstallTests(InstallFixture):
    def setUp(self):
        super().setUp()
        self.codex()
        self.execute()
        self.backup = self.area/'independent-backup'
        self.entry = self.home/'.codex/AGENTS.md'
        self.entry.write_bytes(b'private\x00\r\n'+self.entry.read_bytes()+b'\nprivate footer\r\n')

    def plan_uninstall(self):
        return uninstall.preview(home=self.home,backup_dir=self.backup)

    def apply_uninstall(self, hook=None):
        plan = self.plan_uninstall()
        return uninstall.execute(approval(recovery.summary(plan)),home=self.home,backup_dir=self.backup,hook=hook)

    def test_preview_zero_write_and_exact_approval(self):
        before = recovery.tree(self.home)
        plan = self.plan_uninstall()
        self.assertEqual(recovery.tree(self.home),before)
        self.assertFalse(self.backup.exists())
        with self.assertRaises(ValueError):
            uninstall.execute({},home=self.home,backup_dir=self.backup)
        self.assertFalse(self.backup.exists())
        self.assertEqual(plan['agents'],['codex'])

    def test_complete_return_private_bytes_and_standalone_restore(self):
        before = recovery.tree(self.home)
        original = (self.runtime.root/'memories/MEMORY.md').read_bytes()
        result = self.apply_uninstall()
        self.assertEqual(result['status'],'completed')
        self.assertFalse(self.runtime.root.exists())
        self.assertFalse(self.runtime.code.exists())
        returned = self.entry.parent/'memsharing-return'
        self.assertEqual((returned/'original/memories/MEMORY.md').read_bytes(),original)
        self.assertTrue(self.entry.read_bytes().startswith(b'private\x00\r\n'))
        self.assertIn(b'private footer\r\n',self.entry.read_bytes())
        self.assertNotIn(str(self.runtime.root).encode(),self.entry.read_bytes())
        manifest = self.backup/'manifest.json'
        preview = recovery.recover(manifest)
        approved = self.area/'restore-approval.json'
        approved.write_text(json.dumps(approval(preview['plan'])))
        child = subprocess.run([sys.executable,'-B',str(self.backup/'recover.py'),'--manifest',str(manifest),
                                '--approval-file',str(approved)],capture_output=True,text=True,timeout=30)
        self.assertEqual(child.returncode,0,child.stdout+child.stderr)
        # Existing user containers remain; newly introduced return directories
        # are removed, all original product/user bytes and modes restored.
        self.assertEqual(recovery.tree(self.home),before)

    def test_drift_rejects_before_backup(self):
        plan = self.plan_uninstall()
        self.entry.write_bytes(self.entry.read_bytes()+b'user changed')
        with self.assertRaises(ValueError):
            uninstall.execute(approval(recovery.summary(plan)),home=self.home,backup_dir=self.backup)
        self.assertFalse(self.backup.exists())

    def test_partial_failure_resume_and_restore_drift_protection(self):
        count = []
        def crash(event,index,change):
            if event=='after_write':
                count.append(index)
                if len(count)==3: raise RuntimeError('interruption')
        with self.assertRaises(RuntimeError):self.apply_uninstall(crash)
        manifest = self.backup/'manifest.json'
        preview = recovery.recover(manifest,action='resume')
        result = recovery.recover(manifest,action='resume',approval=approval(preview['plan']))
        self.assertEqual(result['status'],'completed')
        self.entry.write_bytes(self.entry.read_bytes()+b'new private edit')
        with self.assertRaises(ValueError):recovery.recover(manifest)
        self.assertIn(b'new private edit',self.entry.read_bytes())

    def test_unknown_code_and_public_root_stop(self):
        (self.runtime.code/'foreign.txt').write_bytes(b'private')
        with self.assertRaises(ValueError):self.plan_uninstall()
        (self.runtime.code/'foreign.txt').unlink()
        (self.runtime.root/'foreign.txt').write_bytes(b'private')
        with self.assertRaises(ValueError):self.plan_uninstall()

    def test_occupied_destination_and_backup_inside_product_stop(self):
        with self.assertRaises(ValueError):
            uninstall.preview(home=self.home,backup_dir=self.runtime.root/'recovery')
        (self.entry.parent/'memsharing-return').mkdir()
        with self.assertRaises(ValueError):self.plan_uninstall()

    def test_external_references_closure_and_original_bytes(self):
        reference = self.runtime.root/'references/private.md'
        reference.write_bytes(b'private reference\r\n')
        index = self.runtime.root/'memories/MEMORY.md'
        index.write_bytes(index.read_bytes()+b'\n[reference](../references/private.md)\n')
        self.apply_uninstall()
        self.assertEqual((self.entry.parent/'memsharing-return/references/private.md').read_bytes(),reference.read_bytes() if reference.exists() else b'private reference\r\n')

    def test_missing_link_blocks_deletion(self):
        index = self.runtime.root/'memories/MEMORY.md'
        index.write_bytes(index.read_bytes()+b'\n[missing](missing.md)\n')
        with self.assertRaises(ValueError):self.plan_uninstall()
        self.assertTrue(self.runtime.registry.exists())

    def test_absolute_public_links_remapped_and_unknown_asset_blocks(self):
        reference=self.runtime.root/'references/private.md'
        reference.write_bytes(b'original reference')
        index=self.runtime.root/'memories/MEMORY.md'
        index.write_bytes(index.read_bytes()+('\n[absolute](%s)\n'%reference).encode())
        plan=self.plan_uninstall()
        target=self.entry.parent/'memsharing-return/memories/MEMORY.md'
        raw=next(bytes.fromhex(c['after']['hex']) for c in plan['changes'] if c['path']==str(target))
        self.assertIn(b'[absolute](../references/private.md)',raw)
        assets=self.runtime.code.parent/'mem-sharing-runtimes'
        assets.mkdir();(assets/'unknown-private').write_bytes(b'must preserve')
        with self.assertRaisesRegex(ValueError,'ownership/lease'):self.plan_uninstall()
        self.assertEqual((assets/'unknown-private').read_bytes(),b'must preserve')

    def test_historical_journal_retention_is_explicit_and_pending_journal_blocks(self):
        plan=self.plan_uninstall()
        self.assertEqual(len(plan['retained_evidence']),1)
        row=plan['retained_evidence'][0]
        self.assertEqual(row['non_active_evidence']['status'],'committed')
        self.assertIn(row,recovery.summary(plan)['retained_evidence'])
        journal=self.home/'.mem-sharing-install-fixture-m404/journal.json'
        data=json.loads(journal.read_text());data['status']='applying';journal.write_text(json.dumps(data))
        with self.assertRaises(ValueError):self.plan_uninstall()

    def test_new_return_child_blocks_restore_before_mutation(self):
        self.apply_uninstall()
        private=self.entry.parent/'memsharing-return/new-private.md'
        private.write_bytes(b'new content after uninstall')
        before=self.entry.read_bytes()
        with self.assertRaises(ValueError):recovery.recover(self.backup/'manifest.json')
        self.assertEqual(self.entry.read_bytes(),before)

    def test_independent_probe_failure_leaves_all_original_roots_untouched(self):
        before=recovery.tree(self.home)
        plan=self.plan_uninstall()
        with patch.object(uninstall.subprocess,'run',return_value=SimpleNamespace(returncode=1,stdout='probe failed',stderr='')):
            with self.assertRaisesRegex(ValueError,'probe failed'):
                uninstall.execute(approval(recovery.summary(plan)),home=self.home,backup_dir=self.backup)
        self.assertEqual(recovery.tree(self.home),before)
        self.assertTrue(self.runtime.registry.exists())
        self.assertEqual(json.loads((self.backup/'manifest.json').read_text())['status'],'recovery_required')

    def test_private_runtime_hash_lease_and_bundle_identity(self):
        import socket
        root=self.runtime.code.parent/'mem-sharing-runtimes'
        directory=root/'fixture-python'/'arm64';payload=directory/'payload'
        (payload/'bin').mkdir(parents=True)
        exe=payload/'bin/python3';exe.write_bytes(b'synthetic interpreter bytes');exe.chmod(0o755)
        marker=directory/'asset.json'
        marker.write_text(json.dumps({'schema':1,'id':'fixture-python','sha256':'a'*64,'home':str(root),
                                      'host':socket.gethostname(),'verified':True}))
        asset={'id':'fixture-python','arch':'arm64','sha256':'a'*64,'treeSha256':uninstall._runtime_digest(payload),'bytes':1}
        with patch.object(uninstall,'RUNTIME_ASSETS',[asset]):
            uninstall._verify_runtime_assets(root)
            for field,value in (('schema',True),('verified',1)):
                raw=json.loads(marker.read_text());raw[field]=value;marker.write_text(json.dumps(raw))
                before=recovery.tree(self.home)
                with self.assertRaises(ValueError):self.plan_uninstall()
                self.assertEqual(recovery.tree(self.home),before)
                raw[field]=1 if field=='schema' else True;marker.write_text(json.dumps(raw))
            root_link=payload/'root-link';root_link.symlink_to('.')
            with self.assertRaises(ValueError):uninstall._runtime_digest(payload)
            root_link.unlink()
            (directory/'lease.json').write_bytes(b'{}')
            with self.assertRaisesRegex(ValueError,'lease'):self.plan_uninstall()
            (directory/'lease.json').unlink()
            with patch.object(uninstall.sys,'executable',str(exe)):
                plan=self.plan_uninstall()
            self.assertEqual(plan['recovery_runtime']['kind'],'bundled')
            self.backup.mkdir()
            recovery.write_file(self.backup/'recover.py',Path(recovery.__file__).read_bytes())
            recovery.write_file(self.backup/'manifest.json',recovery.encoded({'plan':plan,'status':'prepared'}))
            # Synthetic bundle validates copying/binding; it does not claim
            # official CPython relocation or execute these fixture bytes.
            with patch.object(uninstall.subprocess,'run',return_value=SimpleNamespace(returncode=5,stdout='{"status":"approval_required"}')) as run:
                uninstall._prepare_interpreter(plan)
                self.assertEqual(run.call_args.args[0][1:4],['-I','-S','-B'])
                self.assertEqual(run.call_args.args[0][0],plan['recovery_runtime']['interpreter'])
            copied=Path(plan['recovery_runtime']['interpreter'])
            self.assertEqual(copied.read_bytes(),exe.read_bytes())
            copied.write_bytes(b'drift')
            with self.assertRaises(ValueError):recovery.verify_interpreter(plan)
            exe.write_bytes(b'drift')
            with self.assertRaises(ValueError):uninstall._verify_runtime_assets(root)

    def test_keeper_product_dependency_blocks_without_deleting_keeper(self):
        from agm_core import entries
        from agm_core.project import resolve_project
        project=self.area/'project';project.mkdir()
        subprocess.run(['git','init','-q',str(project)],check=True)
        identity=resolve_project(project)
        link=project/'.agents/skills/context-keeper';link.parent.mkdir(parents=True)
        link.symlink_to(self.runtime.code)
        ledger=registry.load_registry(self.runtime.registry,
            allowed_user_paths=paths.allowed_user_paths(self.config,None,home=str(self.home)))
        record=registry.new_project(identity,['codex']);ledger['projects'][str(project)]=record
        record['checkouts'][str(project)]['objects']['legacy-keeper']={
            'kind':'skill_symlink','path':str(link),'scope':'project','agents':['codex'],'ownership':'reused',
            'marker':None,'fingerprint':{'algorithm':'sha256','basis':'link_target','value':entries.link_fingerprint(self.runtime.code)},
            'original_existed':True,'link_target':str(self.runtime.code),'backup_manifest':None,'consumers':[str(project)]}
        self.runtime.registry.write_bytes(registry.serialize_registry(ledger,
            allowed_user_paths=paths.allowed_user_paths(self.config,None,home=str(self.home))))
        before=recovery.tree(self.home)
        with self.assertRaisesRegex(ValueError,'Keeper depends on product'):self.plan_uninstall()
        self.assertEqual(recovery.tree(self.home),before)
        self.assertTrue(link.is_symlink())
        marker={'start':'<!-- context-keeper:start -->','end':'<!-- context-keeper:end -->'}
        raw=entries.render_block(b'',(marker['start']+'\n'+str(self.runtime.code)+'\n'+marker['end']).encode(),**marker)
        obj={'path':str(project/'AGENTS.md'),'marker':marker,'link_target':None}
        with self.assertRaises(ValueError):uninstall._preserve_ck(obj,[self.runtime.code],raw)

    def test_empty_directories_modes_and_internal_directory_link_preserved(self):
        empty=self.runtime.root/'references/empty-dir';empty.mkdir();empty.chmod(0o500)
        link=self.runtime.root/'memories/empty-link';link.symlink_to('../references/empty-dir')
        plan=self.plan_uninstall()
        uninstall.execute(approval(recovery.summary(plan)),home=self.home,backup_dir=self.backup)
        root=self.entry.parent/'memsharing-return'
        for base in (root,root/'original'):
            self.assertTrue((base/'references/empty-dir').is_dir())
            self.assertEqual((base/'references/empty-dir').stat().st_mode&0o777,0o500)
            self.assertTrue((base/'memories/empty-link').is_symlink())
            self.assertEqual((base/'memories/empty-link').resolve(),base/'references/empty-dir')
        preview=recovery.recover(self.backup/'manifest.json')
        recovery.recover(self.backup/'manifest.json',approval=approval(preview['plan']))
        self.assertEqual(empty.stat().st_mode&0o777,0o500)

    def test_unreadable_symlink_chains_block_before_any_write(self):
        root=self.runtime.root/'memories'
        (self.home/'outside-public-assets').write_bytes(b'not a public reading asset')
        for name,links in (('self',{'a':'a'}),('cycle',{'a':'b','b':'a'}),
                           ('missing',{'a':'b','b':'missing'}),
                           ('escape',{'a':'b','b':'../../outside-public-assets'})):
            with self.subTest(name=name):
                for path,target in links.items():(root/path).symlink_to(target)
                before=recovery.tree(self.home)
                with self.assertRaises(ValueError):self.plan_uninstall()
                self.assertEqual(recovery.tree(self.home),before)
                self.assertFalse(self.backup.exists())
                for path in links:(root/path).unlink()

    def test_independent_executor_ignores_pythonpath_and_user_site(self):
        poison=self.area/'poison';poison.mkdir()
        signal=self.area/'startup-executed'
        (poison/'sitecustomize.py').write_text('from pathlib import Path\nPath(%r).write_text("unsafe")\n'%str(signal))
        with patch.dict('os.environ',{'PYTHONPATH':str(poison),'PYTHONUSERBASE':str(poison)}):
            result=self.apply_uninstall()
        self.assertEqual(result['status'],'completed')
        self.assertFalse(signal.exists())


class LegacyUninstallTests(InstallFixture):
    def test_v0_cross_reference_closure_readonly_backup_and_exact_restore(self):
        originals=self.v0();self.codex();self.execute()
        before=recovery.tree(self.home)
        backup=self.area/'independent-backup'
        plan=uninstall.preview(home=self.home,backup_dir=backup)
        uninstall.execute(approval(recovery.summary(plan)),home=self.home,backup_dir=backup)
        returned=self.home/'.codex/memsharing-return'
        legacy=returned/'memories/legacy-v0-fixture-m404'
        self.assertEqual((legacy/'references/ops.md').read_bytes(),originals['references/ops.md'])
        self.assertEqual((returned/'original/memories/legacy-v0-fixture-m404/memories/MEMORY.md').read_bytes(),originals['memories/MEMORY.md'])
        preview=recovery.recover(backup/'manifest.json')
        recovery.recover(backup/'manifest.json',approval=approval(preview['plan']))
        self.assertEqual(recovery.tree(self.home),before)


class DurableExportUninstallTests(unittest.TestCase):
    def setUp(self):
        fixture=UninstallTests();fixture.setUp();self.addCleanup(fixture.doCleanups)
        self.home=fixture.home;self.backup=fixture.backup;self.plan_uninstall=fixture.plan_uninstall

    def test_real_export_receipt_is_inventoried_and_drift_rejected(self):
        from test_plugin_release import ReleaseFixture,approved
        from agm_core import plugin_release
        fixture=ReleaseFixture();fixture.setUp();self.addCleanup(fixture.doCleanups)
        exported=plugin_release.plan_export(fixture.plugin(),self.home,'uninstall-export-fixture')
        plugin_release.execute_export(exported,approved(exported))
        directory=Path(exported['destination'])
        plan=self.plan_uninstall()
        self.assertIn(str(directory.parents[1]),plan['delete_roots'])
        self.assertTrue(any(c['path']==str(directory/'acquisition.json') for c in plan['changes']))
        before=recovery.tree(self.home)
        target=directory/'core/SKILL.md';target.write_bytes(target.read_bytes()+b'foreign drift')
        changed=recovery.tree(self.home)
        with self.assertRaises(ValueError):self.plan_uninstall()
        with self.assertRaises(ValueError):uninstall.execute(approval(recovery.summary(plan)),home=self.home,backup_dir=self.backup)
        self.assertEqual(recovery.tree(self.home),changed)
        self.assertNotEqual(before,changed)
        self.assertFalse(self.backup.exists())


class MultiAgentUninstallTests(InstallFixture):
    def setUp(self):
        super().setUp()
        self.backup = self.area/'independent-backup'
        self.claude = self.home/'.claude/CLAUDE.md'
        self.claude.parent.mkdir()
        self.private = b'private before\r\n\xff\x00\nprivate tail without final newline'
        self.claude.write_bytes(self.private)
        remember_mode(self, self.claude)
        real_detect = detect.detect_agents
        def synthetic_installed(*args,**kwargs):
            report = real_detect(*args,**kwargs)
            for record in report['agents'].values():
                record.update(status='installed',summary='synthetic installation fixture')
            return report
        with patch.object(detect,'detect_agents',side_effect=synthetic_installed):
            self.execute()

    def test_six_independent_copies_and_no_current_installed_filter(self):
        original = self.claude.read_bytes()
        with patch.object(detect,'detect_agents',side_effect=AssertionError('Uninstall must not filter installed')):
            plan = uninstall.preview(home=self.home,backup_dir=self.backup)
            self.assertEqual(plan['agents'],list(paths.AGENT_ORDER))
            uninstall.execute(approval(recovery.summary(plan)),home=self.home,backup_dir=self.backup)
        for agent, config in self.config.items():
            entry = Path(paths.expand_path(config['user_entry'],home=str(self.home)))
            returned = entry.parent/'memsharing-return'
            self.assertTrue((returned/'memories/MEMORY.md').is_file(),agent)
            self.assertTrue((returned/'original/memories/MEMORY.md').is_file(),agent)
        raw = self.claude.read_bytes()
        assert_opaque(self, raw, self.private, index=self.claude.parent/"memsharing-return/memories/MEMORY.md", path=self.claude)
        self.assertEqual(raw.count(b'@'),1)
        self.assertNotIn(str(self.runtime.root).encode(),raw)

    def test_redirect_preserves_non_token_bytes_and_rejects_ambiguity(self):
        old = self.runtime.root/'memories/MEMORY.md'
        new = self.claude.parent/'memsharing-return/memories/MEMORY.md'
        raw = b'private\r\n  @'+str(old).encode()+b' \r\ntail without LF'
        obj = {'kind':'import','marker':None,'ownership':'reused',
               'fingerprint':{'value':recovery.digest(raw)}}
        expected = raw.replace(str(old).encode(),str(new).encode())
        self.assertEqual(uninstall._redirect_import(raw,obj,old,new),expected)
        no_lf = b'@'+str(old).encode()
        obj['fingerprint']['value'] = recovery.digest(no_lf)
        self.assertEqual(uninstall._redirect_import(no_lf,obj,old,new),b'@'+str(new).encode())
        for bad in (raw+b'\n@'+str(old).encode(),b'private only'):
            obj['fingerprint']['value']=recovery.digest(bad)
            with self.assertRaises(ValueError):uninstall._redirect_import(bad,obj,old,new)
        obj['fingerprint']['value']=recovery.digest(raw)
        with self.assertRaises(ValueError):uninstall._redirect_import(raw+b'changed',obj,old,new)
        obj['kind']='file'
        with self.assertRaises(ValueError):uninstall._redirect_import(raw,obj,old,new)


if __name__ == '__main__':unittest.main()

from entry_opaque_fixture import assert_opaque, remember_mode
