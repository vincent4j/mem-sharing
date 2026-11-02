"""Bounded independent compatibility tests with real historical producers."""
import json
from pathlib import Path
import sys
import unittest
sys.path[:0]=[str(Path(__file__).resolve().parents[2]/'scripts'),str(Path(__file__).resolve().parent)]
from agm_core import uninstall_compat as compat,uninstall,uninstall_recovery as recovery
import test_legacy_import_reconcile as historical
import test_m407_upgrade as upgrades
import test_uninstall as original

class CompatTests(unittest.TestCase):
    def migration(self):
        f=historical.ReconcileTests();f.setUp();self.addCleanup(f.doCleanups)
        return f
    def upgrade(self):
        f=upgrades.UpgradeFixture();f.setUp();self.addCleanup(f.doCleanups);f.execute_upgrade()
        return f
    def test_real_migration_producer_complete_closure(self):
        f=self.migration();root=f.history.parent.parent
        before=recovery.tree(f.home);observed=compat.verify_public_layout_backup(f.runtime,root)
        self.assertEqual(recovery.tree(f.home),before);self.assertEqual(set(observed),set(recovery.tree(root)))
    def test_changed_historical_helper_rejected(self):
        f=self.migration();root=f.history.parent.parent;p=root/'tools/agm_core/public_layout.py';p.write_bytes(p.read_bytes()+b'\n# foreign')
        with self.assertRaises(ValueError):compat.verify_public_layout_backup(f.runtime,root)
    def test_external_extra_helper_rejected(self):
        f=self.migration();root=f.history.parent.parent;(root/'tools/agm_core/foreign.py').write_bytes(b'foreign')
        with self.assertRaises(ValueError):compat.verify_public_layout_backup(f.runtime,root)
    def test_prepared_migration_rejected(self):
        f=self.migration();root=f.history.parent.parent;p=root/'journal.json';j=json.loads(p.read_bytes());j['status']='prepared';p.write_text(json.dumps(j))
        with self.assertRaises(ValueError):compat.verify_public_layout_backup(f.runtime,root)
    def test_real_upgrade_archive_and_unknown_child_rejected(self):
        f=self.upgrade();root=f.runtime.backups/'upgrade-fixture-m407'
        before=recovery.tree(f.home);observed=compat.verify_upgrade_backup(f.runtime,root)
        self.assertEqual(recovery.tree(f.home),before);self.assertIn(str(root/'registry-before.json'),observed)
        (root/'foreign').write_bytes(b'foreign')
        with self.assertRaises(ValueError):compat.verify_upgrade_backup(f.runtime,root)
    def test_upgrade_corrupt_before_rejected(self):
        f=self.upgrade();root=f.runtime.backups/'upgrade-fixture-m407';p=root/'registry-before.json';p.chmod(0o600);p.write_bytes(b'foreign')
        with self.assertRaises(ValueError):compat.verify_upgrade_backup(f.runtime,root)
    def test_independent_engine_return_and_restore(self):
        f=original.UninstallTests();f.setUp();self.addCleanup(f.doCleanups)
        before=recovery.tree(f.home);identity={'root':'/synthetic-reviewed-tool','commit':'a'*40}
        plan=uninstall.preview(home=f.home,backup_dir=f.backup,tool_identity=identity)
        self.assertEqual(plan['independent_tool'],identity)
        result=uninstall.execute(original.approval(recovery.summary(plan)),home=f.home,backup_dir=f.backup,tool_identity=identity)
        self.assertEqual(result['status'],'completed')
        rp=recovery.recover(f.backup/'manifest.json')
        done=recovery.recover(f.backup/'manifest.json',approval=original.approval(rp['plan']))
        self.assertEqual(done['status'],'restored');self.assertEqual(recovery.tree(f.home),before)


class DshRedirectTests(unittest.TestCase):
    def fixture(self):
        f=original.UninstallTests();f.setUp();self.addCleanup(f.doCleanups);return f
    def direct(self,raw,*,planned=True):
        f=self.fixture();path=f.home/'.dsh/AGENTS.md';index=path.parent/'memsharing-return/memories/MEMORY.md'
        token=str(f.runtime.root/'memories/MEMORY.md').encode();raw=raw.replace(b'OLD',token)
        active={'memories/MEMORY.md':{'kind':'file','hex':b'complete public memory'.hex(),'mode':0o600}}
        changes={str(index):{'stage':'return','before':{'kind':'absent'},'after':active['memories/MEMORY.md']}} if planned else {}
        return f,path,index,token,raw,active,changes
    def test_exact_single_token_crlf_context_keeper_and_mode(self):
        f,p,index,old,raw,active,changes=self.direct('开始任务前读取并遵守 OLD；其余原文'.encode()+b'\r\n<!-- context-keeper:start -->\r\nprivate\x00opaque\r\n<!-- context-keeper:end -->\r\nno-final-newline')
        after,proof=compat.redirect_dsh_reference(f.runtime,p,raw,raw,0o640,index,changes,active,[])
        self.assertEqual(after,raw.replace(old,str(index).encode(),1));self.assertEqual(proof['before_mode'],proof['after_mode']);self.assertEqual(proof['ownership_transition'],'none')
    def test_duplicate_reference_rejected(self):
        f,p,index,old,raw,active,changes=self.direct('开始任务前读取并遵守 OLD；OLD'.encode())
        with self.assertRaises(ValueError):compat.redirect_dsh_reference(f.runtime,p,raw,raw,0o600,index,changes,active,[])
    def test_context_keeper_reference_rejected(self):
        f,p,index,old,raw,active,changes=self.direct(b'<!-- context-keeper:start -->\n'+'开始任务前读取并遵守 OLD；原文'.encode()+b'\n<!-- context-keeper:end -->')
        with self.assertRaises(ValueError):compat.redirect_dsh_reference(f.runtime,p,raw,raw,0o600,index,changes,active,[])
    def test_missing_planned_return_rejected(self):
        f,p,index,old,raw,active,changes=self.direct('开始任务前读取并遵守 OLD；原文'.encode(),planned=False)
        with self.assertRaises(ValueError):compat.redirect_dsh_reference(f.runtime,p,raw,raw,0o600,index,changes,active,[])
    def test_unrecognized_prefix_rejected(self):
        f,p,index,old,raw,active,changes=self.direct(b'opaque OLD')
        with self.assertRaises(ValueError):compat.redirect_dsh_reference(f.runtime,p,raw,raw,0o600,index,changes,active,[])
    def engine_fixture(self):
        from agm_core import registry,policy_migration,paths
        f=self.fixture();config=policy_migration.config();p=Path(paths.expand_path(config['dsh']['user_entry'],home=str(f.home)))
        p.parent.mkdir(parents=True,exist_ok=True)
        raw='开始任务前读取并遵守 '.encode()+str(f.runtime.root/'memories/MEMORY.md').encode()+'；用户原文'.encode()+b'\r\n<!-- context-keeper:start -->\r\nindependent protocol\r\n<!-- context-keeper:end -->\r\nno-final-newline'
        p.write_bytes(raw);p.chmod(0o640)
        identity={'root':'/synthetic-reviewed-tool','commit':'a'*40,'user_conversions':{'dsh_reference':'explicit-single-path-to-return-v1'}}
        return f,p,raw,identity
    def test_engine_return_and_independent_restore_preserves_dsh(self):
        f,p,raw,identity=self.engine_fixture();before=recovery.tree(f.home)
        plan=uninstall.preview(home=f.home,backup_dir=f.backup,tool_identity=identity)
        proof=plan['user_reference_redirects'][0];self.assertEqual(proof['agent'],'dsh')
        result=uninstall.execute(original.approval(recovery.summary(plan)),home=f.home,backup_dir=f.backup,tool_identity=identity)
        self.assertEqual(result['status'],'completed')
        self.assertEqual(p.read_bytes(),raw.replace(str(f.runtime.root/'memories/MEMORY.md').encode(),proof['new_token'].encode(),1))
        self.assertEqual(p.stat().st_mode&0o777,0o640);self.assertTrue((p.parent/'memsharing-return/memories/MEMORY.md').is_file())
        preview=recovery.recover(f.backup/'manifest.json');done=recovery.recover(f.backup/'manifest.json',approval=original.approval(preview['plan']))
        self.assertEqual(done['status'],'restored');self.assertEqual(recovery.tree(f.home),before)
    def test_approved_dsh_drift_zero_write(self):
        f,p,raw,identity=self.engine_fixture();plan=uninstall.preview(home=f.home,backup_dir=f.backup,tool_identity=identity)
        p.write_bytes(raw+b'user edit');after_edit=recovery.tree(f.home)
        with self.assertRaises(ValueError):uninstall.execute(original.approval(recovery.summary(plan)),home=f.home,backup_dir=f.backup,tool_identity=identity)
        self.assertFalse(f.backup.exists());self.assertEqual(recovery.tree(f.home),after_edit)

if __name__=='__main__':unittest.main()
