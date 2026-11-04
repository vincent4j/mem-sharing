"""Synthetic HOME only: direct return, generated provenance and no-new-file execution."""
import json
import os
import sys
from pathlib import Path
import unittest
from unittest.mock import patch

from test_m404_install import InstallFixture
from test_uninstall import approval
from agm_core import detect, paths, uninstall, uninstall_memory as memory
from agm_core import uninstall_recovery as recovery


class NativeReturnTests(unittest.TestCase):
    def fixture(self, keeper_content=b'opaque CK'):
        f=InstallFixture();f.setUp();self.addCleanup(f.doCleanups)
        opaque=b'\xef\xbb\xbf# '+ '公共记忆'.encode()+b'\r\nuser original\x00\xff\r\n<!-- context-keeper:start -->\r\n'+keeper_content+b'\r\n<!-- context-keeper:end -->\r\nno final LF'
        f.private={}
        for a,c in f.config.items():
            p=Path(paths.expand_path(c['user_entry'],home=str(f.home)))
            p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(opaque);p.chmod(0o640)
            f.private[a]=(p,opaque)
        real=detect.detect_agents
        def installed(*args,**kw):
            report=real(*args,**kw)
            for r in report['agents'].values():r.update(status='installed',summary='synthetic installed native executable')
            return report
        with patch.object(detect,'detect_agents',side_effect=installed):f.execute()
        index=f.runtime.root/'memories/MEMORY.md'
        f.fact=b'# Preferences\r\n\r\ncomplete first paragraph\r\n\r\ncomplete second paragraph\r\n'
        topic=f.runtime.root/'memories/topics/facts.md';topic.parent.mkdir(exist_ok=True);topic.write_bytes(f.fact)
        index.write_bytes(index.read_bytes()+b'\n[all facts](topics/facts.md)\n')
        f.backup=f.area/'restore-only'
        return f

    def test_six_direct_complete_return_no_new_file_outside_backup_and_restore(self):
        f=self.fixture();before=recovery.tree(f.home)
        plan=uninstall.preview(home=f.home,backup_dir=f.backup)
        self.assertEqual(plan['memory_return'],'native-direct-v1')
        self.assertEqual(plan['agents'],list(paths.AGENT_ORDER))
        self.assertFalse(any('memsharing-return' in c['path'] for c in plan['changes']))
        # Production execution cannot fall back to temp-file writer or locks.
        audit_state={'active':True};created=[]
        def monitor(event,args):
            if not audit_state['active']:return
            if event=='open' and len(args)>2 and isinstance(args[0],(str,bytes)) and args[2]&os.O_CREAT:
                path=Path(os.fsdecode(args[0]));created.append(str(path))
                if not path.is_relative_to(f.backup):raise AssertionError('new file outside backup: '+str(path))
            if event=='os.mkdir':
                path=Path(os.fsdecode(args[0]))
                if not path.is_relative_to(f.backup):raise AssertionError('new directory outside backup: '+str(path))
        sys.addaudithook(monitor)
        try:
            with patch.object(recovery,'write_file',side_effect=AssertionError('atomic temp forbidden')),patch.object(recovery,'locks',side_effect=AssertionError('new writer lock forbidden')):
                result=uninstall.execute(approval(recovery.summary(plan)),home=f.home,backup_dir=f.backup,hook=lambda *args:None)
        finally:audit_state['active']=False
        self.assertEqual(set(created),{str(f.backup/'manifest.json'),str(f.backup/'recover.py')})
        self.assertEqual(result['status'],'completed')
        after=recovery.tree(f.home)
        self.assertFalse(set(after)-set(before))
        for a,(p,opaque) in f.private.items():
            raw=p.read_bytes();self.assertIn(opaque.removeprefix(b'\xef\xbb\xbf'),raw,a);self.assertTrue(raw.startswith(b'\xef\xbb\xbf'))
            self.assertIn(f.fact,raw,a)
            self.assertNotIn(b'memsharing-return',raw);self.assertNotIn(b'.mem-sharing',raw)
            self.assertEqual(p.stat().st_mode&0o777,0o640)
            self.assertIn(b'<!-- context-keeper:start -->\r\nopaque CK\r\n<!-- context-keeper:end -->',raw)
        self.assertEqual(set(p.name for p in f.backup.iterdir()),{'manifest.json','recover.py'})
        preview=recovery.recover(f.backup/'manifest.json')
        done=recovery.recover(f.backup/'manifest.json',approval=approval(preview['plan']))
        self.assertEqual(done['status'],'restored');self.assertEqual(recovery.tree(f.home),before)

    def test_entire_generated_governance_without_product_word_removed(self):
        f=self.fixture();p=f.runtime.root/'memories/MEMORY.md'
        p.write_bytes(p.read_bytes()+b'\n'+memory.LEGACY_GENERATED_GOVERNANCE+b'\n')
        plan=uninstall.preview(home=f.home,backup_dir=f.backup)
        for c in plan['changes']:
            if c['stage']=='detach' and c['after']['kind']=='file':
                raw=bytes.fromhex(c['after']['hex'])
                for line in memory.LEGACY_GENERATED_GOVERNANCE.splitlines()[2:]:self.assertNotIn(line,raw)
                self.assertIn(b'opaque CK',raw)
                self.assertEqual(raw.count('# 公共记忆'.encode()),1)
                self.assertNotIn('中枢已初始化'.encode(),raw)

    def test_same_named_user_heading_and_context_keeper_are_opaque(self):
        f=self.fixture();p,raw=f.private['codex']
        plan=uninstall.preview(home=f.home,backup_dir=f.backup)
        c=next(c for c in plan['changes'] if c['path']==str(p))
        self.assertIn(raw.removeprefix(b'\xef\xbb\xbf'),bytes.fromhex(c['after']['hex']));self.assertTrue(bytes.fromhex(c['after']['hex']).startswith(b'\xef\xbb\xbf'))
        self.assertEqual(memory.strip_generated(raw,f.runtime),raw)

    def test_unproven_similar_governance_requires_review(self):
        f=self.fixture();p=f.runtime.root/'memories/MEMORY.md'
        p.write_bytes(p.read_bytes()+b'\n'+memory.LEGACY_GENERATED_GOVERNANCE.replace('独立管理。'.encode(),'独立管理但有定制。'.encode()))
        before=recovery.tree(f.home)
        with self.assertRaisesRegex(ValueError,'review'):uninstall.preview(home=f.home,backup_dir=f.backup)
        self.assertEqual(recovery.tree(f.home),before)

    def test_missing_escape_symlink_and_cycle_reject(self):
        for target in ('missing.md','../../outside.md','topics/loop.md','topics/link.md'):
            with self.subTest(target=target):
                f=self.fixture();index=f.runtime.root/'memories/MEMORY.md'
                index.write_bytes(index.read_bytes()+('\n[x](%s)\n'%target).encode())
                if target=='topics/loop.md':
                    (f.runtime.root/'memories/topics/loop.md').write_bytes(b'[loop](../MEMORY.md)')
                if target=='topics/link.md':
                    (f.runtime.root/'memories/topics/link.md').symlink_to('/outside/private')
                with self.assertRaises(ValueError):uninstall.preview(home=f.home,backup_dir=f.backup)
                self.assertFalse(f.backup.exists())

    def test_drift_and_replaced_inode_refuse_without_backup(self):
        f=self.fixture();plan=uninstall.preview(home=f.home,backup_dir=f.backup)
        p,_=f.private['codex'];raw=p.read_bytes();p.unlink();p.write_bytes(raw);p.chmod(0o640)
        with self.assertRaises(ValueError):uninstall.execute(approval(recovery.summary(plan)),home=f.home,backup_dir=f.backup)
        self.assertFalse(f.backup.exists())

    def test_exact_complete_dedup_and_idempotent_transform(self):
        opaque=b'user\x00\r\n';body=b'first\n\nsecond'
        once=memory.merge_native(opaque,body)
        self.assertEqual(memory.merge_native(once,body),once)
        self.assertTrue(once.startswith(opaque))

    def test_unknown_legacy_return_directory_and_missing_native_reject(self):
        f=self.fixture();p,_=f.private['codex'];(p.parent/'memsharing-return').mkdir()
        with self.assertRaises(ValueError):uninstall.preview(home=f.home,backup_dir=f.backup)
        (p.parent/'memsharing-return').rmdir();p.unlink()
        with self.assertRaises(ValueError):uninstall.preview(home=f.home,backup_dir=f.backup)

    def test_fault_recovery_and_independently_verified_backup_removal(self):
        f=self.fixture();before=recovery.tree(f.home)
        plan=uninstall.preview(home=f.home,backup_dir=f.backup)
        def fail(event,index,change):
            if event=='after_write':raise RuntimeError('synthetic interruption')
        with self.assertRaises(RuntimeError):
            uninstall.execute(approval(recovery.summary(plan)),home=f.home,backup_dir=f.backup,hook=fail)
        self.assertTrue(f.backup.exists())
        preview=recovery.recover(f.backup/'manifest.json')
        recovery.recover(f.backup/'manifest.json',approval=approval(preview['plan']))
        self.assertEqual(recovery.tree(f.home),before)
        # Backup retirement is performed by the independent verifier, not an
        # automatic successful-writer claim. No extra receipt is introduced.
        for p in [f.backup/'recover.py',f.backup/'manifest.json']:p.unlink()
        f.backup.rmdir();self.assertFalse(f.backup.exists())

    def test_unknown_ownership_and_active_lock_are_zero_write(self):
        f=self.fixture();r=json.loads(f.runtime.registry.read_text())
        obj=next(o for o in r['machine']['objects'].values() if o['kind']=='block')
        obj['ownership']='reused';f.runtime.registry.write_text(json.dumps(r))
        before=recovery.tree(f.home)
        with self.assertRaises(ValueError):uninstall.preview(home=f.home,backup_dir=f.backup)
        self.assertEqual(recovery.tree(f.home),before)
        self.assertFalse(f.backup.exists())

    def test_explicit_dsh_conversion_retains_context_keeper_and_rejects_unknown(self):
        from agm_core.uninstall_compat import detach_dsh_reference
        f=self.fixture();p=f.private['dsh'][0]
        line='开始任务前读取并遵守 '.encode()+str(f.runtime.root/'memories/MEMORY.md').encode()+'；读不到就说明。'.encode()+b'\r\n'
        opaque=b'<!-- context-keeper:start -->\r\nopaque user protocol\r\n<!-- context-keeper:end -->\r\n'
        after,proof=detach_dsh_reference(f.runtime,p,line+opaque,line+opaque,0o640)
        self.assertEqual(after,opaque);self.assertEqual(proof['ownership_transition'],'none')
        for raw in [line+line,opaque.replace(b'opaque user protocol',line),line.replace('；读不到就说明。'.encode(),'；private user text'.encode())]:
            with self.assertRaises(ValueError):detach_dsh_reference(f.runtime,p,raw,raw,0o640)

    def test_writer_appearing_after_hook_rejects_before_native_write(self):
        f=self.fixture();plan=uninstall.preview(home=f.home,backup_dir=f.backup)
        before={str(p):p.read_bytes() for p,raw in f.private.values()}
        def inject(event,index,change):
            if event=='before_write':
                (f.home/'.mem-sharing-install.lock').mkdir()
        with self.assertRaisesRegex(ValueError,'lock'):
            uninstall.execute(approval(recovery.summary(plan)),home=f.home,backup_dir=f.backup,hook=inject)
        for name,raw in before.items():self.assertEqual(Path(name).read_bytes(),raw)
        self.assertTrue(f.runtime.code.exists());self.assertTrue(f.backup.exists())

    def test_legacy_plan_cannot_be_relabelled_to_create_return_paths(self):
        f=self.fixture();plan=uninstall.preview(home=f.home,backup_dir=f.backup)
        plan['changes'][0]['stage']='return';recovery.seal(plan)
        with self.assertRaisesRegex(ValueError,'relabelled'):recovery.verify_plan(plan)
        plan['changes'][0]['stage']='detach';plan.pop('native_identities');recovery.seal(plan)
        with self.assertRaisesRegex(ValueError,'identities'):recovery.verify_plan(plan)

    def test_generated_source_title_retired_with_contract_after_user_prefix(self):
        f=self.fixture();p=f.runtime.root/'memories/MEMORY.md'
        user=b'public user fact before generated template\r\n'
        p.write_bytes(user+p.read_bytes())
        plan=uninstall.preview(home=f.home,backup_dir=f.backup)
        for a,(native,opaque) in f.private.items():
            after=bytes.fromhex(next(c['after']['hex'] for c in plan['changes'] if c['path']==str(native)))
            self.assertIn(user,after)
            self.assertEqual(after.count('# 公共记忆'.encode()),1)  # User's opaque heading only.
            self.assertNotIn('中枢已初始化'.encode(),after)

    def test_exact_governance_in_unproven_user_topic_is_not_claimed(self):
        f=self.fixture();p=f.runtime.root/'references/MEMORY.md'
        p.write_bytes(memory.LEGACY_GENERATED_GOVERNANCE)
        before=recovery.tree(f.home)
        with self.assertRaisesRegex(ValueError,'outside producer scope'):
            uninstall.preview(home=f.home,backup_dir=f.backup)
        self.assertEqual(recovery.tree(f.home),before);self.assertFalse(f.backup.exists())

    def test_product_looking_signature_inside_context_keeper_is_opaque(self):
        from agm_core.layout import RuntimeLayout
        runtime=RuntimeLayout(Path('/synthetic-home'))
        raw=b'<!-- context-keeper:start -->\r\n'+memory.LEGACY_GENERATED_GOVERNANCE+b'\r\n<!-- context-keeper:end -->\r\n'
        self.assertEqual(memory.strip_generated(raw,runtime,historical_proof=True),raw)
        outside=memory.LEGACY_GENERATED_GOVERNANCE+b'\n'+raw
        self.assertEqual(memory.strip_generated(outside,runtime,historical_proof=True),b'\n'+raw)

    def protected_chain(self,f,protected):
        before=recovery.tree(f.home)
        plan=uninstall.preview(home=f.home,backup_dir=f.backup)
        for a,(p,_) in f.private.items():
            state=next(c['after'] for c in plan['changes'] if c['path']==str(p))
            self.assertIn(protected,bytes.fromhex(state['hex']),a)
        result=uninstall.execute(approval(recovery.summary(plan)),home=f.home,backup_dir=f.backup,hook=lambda *args:None)
        self.assertEqual(result['status'],'completed')
        for a,(p,_) in f.private.items():self.assertIn(protected,p.read_bytes(),a)
        rp=recovery.recover(f.backup/'manifest.json')
        done=recovery.recover(f.backup/'manifest.json',approval=approval(rp['plan']))
        self.assertEqual(done['status'],'restored');self.assertEqual(recovery.tree(f.home),before)

    def test_review_legacy_cleanup_protected_sentence_full_chain(self):
        f=self.fixture()
        protected=b'<!-- context-keeper:start -->\r\n'+'公共源修改后运行同步工具。'.encode()+b'\r\n<!-- context-keeper:end -->'
        p=f.runtime.root/'memories/legacy-v0-review/memories/MEMORY.md';p.parent.mkdir(parents=True)
        p.write_bytes(memory.LEGACY_GENERATED_GOVERNANCE+b'\n'+protected)
        self.protected_chain(f,protected)

    def test_review_signature_only_topic_and_public_index_full_chain(self):
        protected=b'<!-- context-keeper:start -->\r\n'+memory.LEGACY_GENERATED_GOVERNANCE+b'\r\n<!-- context-keeper:end -->'
        for relative in ('memories/topics/facts.md','memories/MEMORY.md','memories/topics/使用约定.md'):
            with self.subTest(source=relative):
                f=self.fixture();p=f.runtime.root/relative
                if not p.exists():
                    p.parent.mkdir(parents=True, exist_ok=True)
                    from agm_core import user_entries
                    p.write_bytes(user_entries.usage_convention_topic_text(f.runtime.code).encode())
                p.write_bytes(p.read_bytes()+b'\r\n'+protected)
                self.protected_chain(f,protected)

    def test_native_installed_protected_signature_full_chain(self):
        protected=b'<!-- context-keeper:start -->\r\n'+memory.LEGACY_GENERATED_GOVERNANCE+b'\r\n<!-- context-keeper:end -->'
        f=self.fixture(keeper_content=memory.LEGACY_GENERATED_GOVERNANCE)
        self.protected_chain(f,protected)

    def test_protected_paths_are_not_automatically_inert(self):
        for kind in ('bare','relative_import','markdown','tilde','symlink'):
            with self.subTest(kind=kind):
                f=self.fixture();p=f.runtime.root/'memories/topics/facts.md'
                payload={'bare':str(f.runtime.root/'memories/MEMORY.md').encode(),
                         'relative_import':b'@../MEMORY.md',
                         'markdown':b'[active](../MEMORY.md)',
                         'tilde':b'@~/.mem-sharing/memories/MEMORY.md'}.get(kind,b'')
                if kind=='symlink':p.unlink();p.symlink_to('../MEMORY.md')
                else:p.write_bytes(b'<!-- context-keeper:start -->\r\n'+payload+b'\r\n<!-- context-keeper:end -->')
                before=recovery.tree(f.home)
                with self.assertRaises(ValueError):uninstall.preview(home=f.home,backup_dir=f.backup)
                self.assertEqual(recovery.tree(f.home),before);self.assertFalse(f.backup.exists())

    def test_invalid_protected_boundaries_are_zero_write(self):
        for kind in ('missing_end','nested','reversed'):
            with self.subTest(kind=kind):
                f=self.fixture();p=f.private['codex'][0];raw=p.read_bytes()
                if kind=='missing_end':raw=raw.replace(b'<!-- context-keeper:end -->',b'')
                elif kind=='nested':raw=raw.replace(b'opaque CK',b'<!-- context-keeper:start -->nested<!-- context-keeper:end -->')
                else:raw=raw.replace(b'<!-- context-keeper:start -->',b'TEMP').replace(b'<!-- context-keeper:end -->',b'<!-- context-keeper:start -->').replace(b'TEMP',b'<!-- context-keeper:end -->')
                p.write_bytes(raw);before=recovery.tree(f.home)
                with self.assertRaises(ValueError):uninstall.preview(home=f.home,backup_dir=f.backup)
                self.assertEqual(recovery.tree(f.home),before);self.assertFalse(f.backup.exists())

    def test_new_schema_cannot_be_confused_with_legacy_recovery(self):
        f=self.fixture();plan=uninstall.preview(home=f.home,backup_dir=f.backup)
        plan['memory_return']='unknown-direct-v2';recovery.seal(plan)
        with self.assertRaisesRegex(ValueError,'schema'):recovery.verify_plan(plan)


if __name__=='__main__':unittest.main()
