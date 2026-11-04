"""Precise current producer navigation; user markdown and fenced examples survive."""
import sys,tempfile,unittest
from pathlib import Path
sys.path[:0]=[str(Path(__file__).resolve().parents[2]/'scripts'),str(Path(__file__).parent)]
from runtime_fixture import seed_runtime
from agm_core import uninstall_memory as memory,user_entries

class NavigationTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.home=Path(self.tmp.name).resolve();self.runtime=seed_runtime(self.home)
        self.root=self.runtime.root/'memories';self.root.mkdir()
        self.index=self.root/'MEMORY.md';self.topic=self.root/'user-rules.md'
        self.rules='# 用户规则\n\n1. 合成原规则，保持原字节。\n\n'.encode()
        self.topic.write_bytes(self.rules)
        self.prefix=('# 公共记忆\n\n'+user_entries.public_memory_contract_text(self.runtime.code)+'\n').encode()
        self.navigation='\n## 用户记忆\n\n- [user-rules.md](user-rules.md)\n'.encode()
    def body(self):return memory.public_body(self.runtime,memory.public_sources(self.runtime))
    def test_exact_current_index_inlines_only_body(self):
        self.index.write_bytes(self.prefix+self.navigation)
        self.assertEqual(self.body(),self.rules)
    def test_multiple_topics_preserve_each_body_and_order(self):
        other=b'# Other topic\n\n- Original.\r\n';(self.root/'preferences.md').write_bytes(other)
        self.index.write_bytes(self.prefix+self.navigation+b'- [preferences.md](preferences.md)\n')
        self.assertEqual(self.body(),self.rules+b'\n\n'+other)
    def test_custom_same_heading_and_filename_remain(self):
        custom='## 用户记忆\n\n自定义索引说明。\n\n- [user-rules.md](user-rules.md)\n'.encode()
        self.index.write_bytes(custom)
        body=self.body();self.assertIn('## 用户记忆'.encode(),body);self.assertIn(b'- user-rules.md\n',body);self.assertIn(self.rules,body)
    def test_custom_label_in_producer_index_remains(self):
        self.index.write_bytes(self.prefix+'\n## 用户记忆\n\n- [用户亲写标签](user-rules.md)\n'.encode())
        self.assertIn('## 用户记忆\n\n- 用户亲写标签\n'.encode(),self.body())
    def test_fenced_navigation_is_literal_not_expanded(self):
        fence=b'```markdown\n'+self.navigation+b'```\n'
        self.index.write_bytes(self.prefix+fence)
        body=self.body();self.assertIn(fence,body);self.assertEqual(body.count(self.rules),1)
    def test_duplicate_generated_navigation_rejected(self):
        self.index.write_bytes(self.prefix+self.navigation+b'- [user-rules.md](user-rules.md)\n')
        with self.assertRaisesRegex(ValueError,'Duplicate generated'):self.body()

    def test_formal_uninstall_inline_return_and_restore(self):
        from unittest.mock import patch
        from test_m404_install import InstallFixture
        from test_uninstall import approval
        from agm_core import detect,paths,uninstall,uninstall_recovery as recovery
        f=InstallFixture();f.setUp();self.addCleanup(f.doCleanups)
        originals={}
        for agent,cfg in f.config.items():
            path=Path(paths.expand_path(cfg['user_entry'],home=str(f.home)))
            path.parent.mkdir(parents=True,exist_ok=True);private=(agent+' original bytes\r\n').encode();path.write_bytes(private);originals[agent]=(path,private)
        real=detect.detect_agents
        def installed(*a,**k):
            data=real(*a,**k)
            for row in data['agents'].values():row['status']='installed'
            return data
        with patch.object(detect,'detect_agents',side_effect=installed):f.execute()
        index=f.runtime.root/'memories/MEMORY.md';topic=index.parent/'user-rules.md'
        prefix=('# 公共记忆\n\n'+user_entries.public_memory_contract_text(f.runtime.code)+'\n').encode()
        index.write_bytes(prefix+self.navigation);topic.write_bytes(self.rules)
        before=recovery.tree(f.home);backup=f.area/'return-backup'
        plan=uninstall.preview(home=f.home,backup_dir=backup)
        self.assertEqual(uninstall.execute(approval(recovery.summary(plan)),home=f.home,backup_dir=backup)['status'],'completed')
        for path,private in originals.values():
            raw=path.read_bytes();self.assertIn(private,raw);self.assertEqual(raw.count(self.rules),1);self.assertNotIn('## 用户记忆'.encode(),raw);self.assertNotIn(b'- user-rules.md',raw)
        restore=recovery.recover(backup/'manifest.json')
        self.assertEqual(recovery.recover(backup/'manifest.json',approval=approval(restore['plan']))['status'],'restored')
        self.assertEqual(recovery.tree(f.home),before)
