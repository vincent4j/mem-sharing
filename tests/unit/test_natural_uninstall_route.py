"""Real installed reading chains in temporary HOME; no model-session claim."""
import hashlib
import json
from pathlib import Path
import re
import shlex
import subprocess
import sys
from unittest.mock import patch

from test_m404_install import InstallFixture
from test_uninstall import approval
from agm_core import detect, legacy_import, paths, plugin_release, policy_migration
from agm_core import public_layout, uninstall, uninstall_recovery as recovery, user_entries

REPO = Path(__file__).resolve().parents[2]


class NaturalUninstallRouteTests(InstallFixture):
    def setUp(self):
        super().setUp()
        # Copy real shipped kernel/docs, never a stub SKILL or CLI target.
        for source in (REPO/'scripts').rglob('*'):
            if source.is_file() and source.suffix in ('.py','.json'):
                target=self.source/source.relative_to(REPO)
                target.parent.mkdir(parents=True,exist_ok=True)
                target.write_bytes(source.read_bytes())
        for rel in plugin_release.SHIPPED_DOCS:
            target=self.source/rel;target.parent.mkdir(parents=True,exist_ok=True)
            target.write_bytes((REPO/rel).read_bytes())
        self.request['source']['files']={str(p.relative_to(self.source)):legacy_import.digest(p.read_bytes())
            for p in self.source.rglob('*') if p.is_file()}
        self.index=self.runtime.root/'memories/MEMORY.md'
        self.topic=self.runtime.root/'memories/topics/使用约定.md'
        self.claude=self.home/'.claude/CLAUDE.md'
        self.claude.parent.mkdir();self.private=b'private Claude\r\n\xff no final newline'
        self.claude.write_bytes(self.private)
        remember_mode(self, self.claude)

    def install_agents(self, agents=None):
        self.request['agents']=agents
        real=detect.detect_agents
        def installed(*args,**kwargs):
            report=real(*args,**kwargs)
            for record in report['agents'].values():record.update(status='installed',summary='synthetic fixture')
            return report
        with patch.object(detect,'detect_agents',side_effect=installed):self.execute()

    def old_public(self):
        self.topic.parent.mkdir(parents=True,exist_ok=True)
        self.index.write_bytes('# 公共记忆\n\n'.encode()+policy_migration.legacy('pre_route_contract',self.runtime)+b'\n[my topic](topics/private.md)\r\nprivate tail\xff')
        self.topic.write_bytes(policy_migration.legacy('pre_route_topic',self.runtime))
        (self.topic.parent/'private.md').write_bytes(b'# Private\r\nmy complete topic\xff')

    def test_installed_six_native_entries_resolve_one_shared_route_and_real_cli_preview(self):
        self.install_agents()
        index=self.index.read_text();skill_path=self.runtime.code/'SKILL.md'
        self.assertIn(str(skill_path),index)
        self.assertFalse(self.topic.exists())
        self.assertIn('docs/uninstall-design.md',skill_path.read_text())
        route=user_entries.natural_language_uninstall_text(self.runtime.code)
        self.assertNotIn(route,index)
        for agent, config in self.config.items():
            entry=Path(paths.expand_path(config['user_entry'],home=str(self.home)))
            raw=entry.read_bytes()
            self.assertIn(str(self.index).encode(),raw,agent)
            self.assertNotIn(route.encode(),raw,agent)
        assert_opaque(self, self.claude.read_bytes(), self.private, index=self.runtime.root/"memories/MEMORY.md", path=self.claude)
        for link in re.findall(r'\]\(<([^>]+)>\)',route):
            path=Path(link);self.assertTrue(path.is_absolute());self.assertTrue(path.is_file(),link)
        self.assertEqual((self.runtime.code/'SKILL.md').read_bytes(),(REPO/'SKILL.md').read_bytes())
        self.assertIn('自然语言要求',index)
        command=re.search(r'```sh\n([^\n]+)\n```',route).group(1)
        argv=shlex.split(command)
        self.assertEqual(argv[:4],['python3','-B',str(self.runtime.code/'scripts/agm.py'),'uninstall-machine'])
        backup=self.area/'not-created-external'
        argv[argv.index('--backup-dir')+1]=str(backup)
        # Bound test HOME, real installed entry point, unrelated cwd. Standalone
        # scope is deliberately declared by this fixture; no real host operation.
        import os
        env=dict(os.environ,HOME=str(self.home),PYTHONDONTWRITEBYTECODE='1')
        before=recovery.tree(self.home)
        result=subprocess.run(argv,cwd=self.area,env=env,capture_output=True,text=True)
        self.assertEqual(result.returncode,5,result.stderr+result.stdout)
        output=json.loads(result.stdout)
        self.assertEqual(output['status'],'approval_required')
        self.assertEqual(output['plan']['agents'],list(paths.AGENT_ORDER))
        self.assertEqual(recovery.tree(self.home),before)
        self.assertFalse(backup.exists())

    def test_only_connected_entries_created_and_route_safety_contract(self):
        self.install_agents(['codex'])
        for name in ('workbuddy','dsh','zcode','opencode'):
            self.assertFalse(Path(paths.expand_path(self.config[name]['user_entry'],home=str(self.home))).exists())
        self.assertEqual(self.claude.read_bytes(),self.private)
        route=user_entries.natural_language_uninstall_text(self.runtime.code)
        for phrase in ('卸载 memSharing','卸载 mem-sharing','不想用这个共享记忆工具了，帮我卸载',
                       '卸载这个项目','停用项目记忆','仅澄清','不得删除项目',
                       '自然语言请求不批准尚未展示的精确删除计划','预览前不 mkdir',
                       '--host-obligation paseo','不能默认 standalone','不自动重装',
                       '默认保留','不能复用主卸载批准'):
            self.assertIn(phrase,route)
        self.assertLess(route.index('先展示完整归还'),route.index('用户批准该计划后'))
        self.assertLess(route.index('声明范围全部成功后'),route.index('单独征询'))
        # Shell identity survives spaces in installation path.
        spaced=user_entries.natural_language_uninstall_text('/tmp/code with space')
        self.assertEqual(shlex.split(re.search(r'```sh\n([^\n]+)',spaced).group(1))[2],'/tmp/code with space/scripts/agm.py')

    def test_frozen_predecessor_migrates_private_bytes_and_second_run_zero_write(self):
        self.install_agents();self.old_public()
        for name,expected in {'pre_route_contract':'07f91c75c63ac8e387b345dbe02314b7a7cd4c3fafca1805a524282dc8d27dc8',
                              'pre_route_topic':'d6f650046ebf78e798e171913efd03575683cf05ffef3ef16e59604d11d91c9c'}.items():
            self.assertEqual(hashlib.sha256(user_entries.PRE_UNINSTALL_ROUTE_TEMPLATES[name].encode()).hexdigest(),expected)
        native=self.claude.read_bytes();private=(self.topic.parent/'private.md').read_bytes()
        before=recovery.tree(self.home)
        plan=policy_migration.preview(home=self.home)
        self.assertEqual(recovery.tree(self.home),before)
        policy_migration.execute(approval(policy_migration.view(plan)),home=self.home)
        self.assertEqual(self.claude.read_bytes(),native)
        self.assertTrue(self.index.read_bytes().endswith(b'private tail\xff'))
        self.assertEqual((self.topic.parent/'private.md').read_bytes(),private)
        self.assertEqual(self.topic.read_text(),user_entries.usage_convention_topic_text(self.runtime.code))
        again=policy_migration.preview(home=self.home)
        self.assertEqual(again['files'],{})
        before=recovery.tree(self.home)
        self.assertEqual(policy_migration.execute(approval(policy_migration.view(again)),home=self.home)['changes'],[])
        self.assertEqual(recovery.tree(self.home),before)

    def test_unknown_custom_topic_refuses_and_preserves_all_bytes(self):
        self.install_agents();self.old_public()
        self.topic.write_bytes(self.topic.read_bytes()+b'\nunknown custom control')
        before=recovery.tree(self.home)
        with self.assertRaisesRegex(ValueError,'Unknown/customized'):policy_migration.preview(home=self.home)
        self.assertEqual(recovery.tree(self.home),before)

    def test_old_and_new_generated_routes_retire_in_active_but_original_and_user_topic_survive(self):
        self.install_agents()
        for generation in ('old','new'):
            with self.subTest(generation=generation):
                self.old_public()
                if generation=='new':
                    plan=policy_migration.preview(home=self.home)
                    policy_migration.execute(approval(policy_migration.view(plan)),home=self.home)
                before=recovery.tree(self.home)
                original,active=uninstall._standalone_memory(self.runtime)
                for path in (self.index,self.topic,self.topic.parent/'private.md'):
                    self.assertEqual(bytes.fromhex(original[str(path)]['hex']),path.read_bytes())
                topic=bytes.fromhex(active['memories/topics/使用约定.md']['hex'])
                index=bytes.fromhex(active['memories/MEMORY.md']['hex'])
                self.assertNotIn('自然语言卸载'.encode(),topic)
                self.assertNotIn(b'SKILL.md',topic+index)
                self.assertNotIn(b'uninstall-machine',topic+index)
                self.assertNotIn('卸载 memSharing'.encode(),topic+index)
                self.assertNotIn('按需操作指南'.encode(),index)
                self.assertEqual(bytes.fromhex(active['memories/topics/private.md']['hex']),b'# Private\r\nmy complete topic\xff')
                self.assertEqual(recovery.tree(self.home),before)

    def assert_actual_return(self, generation):
        self.install_agents();self.old_public()
        if generation=='new':
            plan=policy_migration.preview(home=self.home)
            policy_migration.execute(approval(policy_migration.view(plan)),home=self.home)
        topic_before=self.topic.read_bytes();index_before=self.index.read_bytes()
        backup=self.area/'external-backup'
        plan=uninstall.preview(home=self.home,backup_dir=backup)
        uninstall.execute(approval(recovery.summary(plan)),home=self.home,backup_dir=backup)
        self.assertFalse(self.runtime.code.exists())
        self.assertFalse(self.runtime.root.exists())
        saved=json.loads((backup/'manifest.json').read_text())['plan']
        for source,expected in ((self.topic,topic_before),(self.index,index_before)):
            state=next(c['before'] for c in saved['changes'] if c['path']==str(source))
            self.assertEqual(bytes.fromhex(state['hex']),expected)
        expected_public=b'\nmy topic\n# Private\r\nmy complete topic\xff\r\nprivate tail\xff'
        for agent,config in self.config.items():
            entry=Path(paths.expand_path(config['user_entry'],home=str(self.home)))
            raw=entry.read_bytes()
            self.assertFalse((entry.parent/'memsharing-return').exists(),agent)
            self.assertTrue(raw.endswith(expected_public),agent)
            prefix=raw[:-len(expected_public)]
            if agent=='claude':
                self.assertIn(prefix,(self.private+b'\n\n',b'\n'+self.private+b'\n\n',b'\n\n'+self.private+b'\n\n'))
                self.assertEqual(entry.stat().st_mode&0o777,self._opaque_modes[str(entry)])
            else:self.assertEqual(prefix.strip(b'\r\n'),b'',agent)
            for token in (b'SKILL.md',b'uninstall-machine','卸载 memSharing'.encode(),'自然语言卸载'.encode(),
                          str(self.runtime.root).encode(),b'memsharing-return',b'<!-- mem-sharing:'):
                self.assertNotIn(token,raw,agent)

    def test_actual_old_public_return_six_copies_retire_route(self):
        self.assert_actual_return('old')

    def test_actual_new_public_return_six_copies_retire_route(self):
        self.assert_actual_return('new')

    def test_valid_install_with_real_historical_skill_cannot_receive_new_guide(self):
        # Actual historical SKILL bytes from the existing immutable baseline,
        # installed through the real source/manifest/ledger lifecycle. No dirty
        # C forgery or dependence on mutable main-workspace files.
        historical=subprocess.run(['git','show','8ffb66f:SKILL.md'],cwd=REPO,
                                  capture_output=True,check=True).stdout
        self.assertNotEqual(historical,(REPO/'SKILL.md').read_bytes())
        (self.source/'SKILL.md').write_bytes(historical)
        self.request['source']['files']={str(p.relative_to(self.source)):legacy_import.digest(p.read_bytes())
            for p in self.source.rglob('*') if p.is_file()}
        self.install_agents();self.old_public()
        from agm_core import user_install,registry
        ledger=registry.load_registry(self.runtime.registry,
            allowed_user_paths=paths.allowed_user_paths(self.config,None,home=str(self.home)))
        user_install._code_matches(self.runtime,ledger['product'])
        self.assertEqual((self.runtime.code/'SKILL.md').read_bytes(),historical)
        before=recovery.tree(self.home)
        with self.assertRaisesRegex(ValueError,'Installed code cannot carry') as raised:
            policy_migration.preview(home=self.home)
        self.assertEqual(raised.exception.code,'route_code_incompatible')
        self.assertEqual(recovery.tree(self.home),before)
        self.assertEqual(self.topic.read_bytes(),policy_migration.legacy('pre_route_topic',self.runtime))

    def test_approved_route_migration_binds_installed_code_and_drift_zero_writes(self):
        self.install_agents();self.old_public()
        plan=policy_migration.preview(home=self.home)
        target=self.runtime.code/'scripts/agm_core/uninstall.py'
        self.assertIn(str(target),plan['observations'])
        target.write_bytes(target.read_bytes()+b'\n# external edit after approval\n')
        before=recovery.tree(self.home)
        with self.assertRaises(ValueError):
            policy_migration.execute(approval(policy_migration.view(plan)),home=self.home)
        self.assertEqual(recovery.tree(self.home),before)

    def test_public_layout_exact_pre_route_header_migration_preserves_private_tail(self):
        code=self.runtime.code
        old='# 公共记忆\n\n'.encode()+policy_migration.legacy('pre_route_contract',self.runtime)+b'\nprivate bytes\r\n\xff'
        updated,head=public_layout.migrate_index_bytes(old,code)
        self.assertGreater(head,0)
        self.assertEqual(updated,'# 公共记忆\n\n'.encode()+public_layout.new_contract_bytes()+b'private bytes\r\n\xff')
        self.assertEqual(public_layout.migrate_index_bytes(updated,code),(updated,0))
        self.assertEqual(public_layout.migrate_index_bytes(old.replace('读取契约'.encode(),b'custom'),code),(None,0))

from entry_opaque_fixture import assert_opaque, remember_mode
