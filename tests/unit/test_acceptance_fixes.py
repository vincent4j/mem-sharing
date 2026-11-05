"""Regression shapes from the real Codex acceptance; synthetic HOME only."""
import io
import json
import os
import subprocess
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch
from test_m404_install import InstallFixture, approved
from test_m408_installer import cli
from test_uninstall import approval
from agm_core import detect, user_rules_organize as org, uninstall
from agm_core import uninstall_recovery as recovery

class AcceptanceFixes(InstallFixture):
    def setUp(self):
        super().setUp()
        real = detect.detect_agents
        def installed(*args, **kwargs):
            result = real(*args, **kwargs)
            for row in result['agents'].values(): row['status'] = 'installed'
            return result
        mock = patch.object(detect, 'detect_agents', side_effect=installed)
        mock.start(); self.addCleanup(mock.stop)

    def install(self, agents=None):
        self.request['agents'] = agents
        plan = cli.plan_machine(self.request)
        return cli.execute_machine(plan, approved(plan), request=self.request)

    def test_core_version_fresh_checkout_without_version_and_conflict(self):
        for args in [('init',), ('add','.'), ('-c','user.name=Fixture','-c','user.email=fixture@example.invalid','commit','-m','fixture')]:
            subprocess.run(['git','-C',str(self.source),*args],capture_output=True,check=True)
        self.assertEqual(cli.checkout_version(self.source), '0.1.7')
        with self.assertRaises(cli.InstallError): cli.checkout_version(self.source,'9.0.0')
        output=io.StringIO()
        with patch.dict(os.environ, HOME=str(self.home)), patch.object(cli,'__file__',str(self.source/'scripts/install.py')), redirect_stdout(output):
            rc=cli.main(['--agent','codex'])
        result=json.loads(output.getvalue())
        self.assertEqual(rc,5,result)
        self.assertEqual(result['approval_plan']['source']['version'],'0.1.7')
        self.assertIn('scripts/core-version.json',result['approval_plan']['source']['files'])
        self.assertFalse(self.runtime.root.exists())
        (self.source/'scripts/core-version.json').unlink()
        subprocess.run(['git','-C',str(self.source),'add','-u'],check=True,capture_output=True)
        self.assertEqual(cli.checkout_version(self.source,'0.1.6'),'0.1.6')
        with self.assertRaises(cli.InstallError): cli.checkout_version(self.source)

    def test_natural_six_rules_offsets_incremental_uninstall_and_restore(self):
        native=self.home/'.codex/AGENTS.md'; native.parent.mkdir()
        rules=[('%d. **规则%d**：保留原文。\n'%(i,i)).encode() for i in range(1,7)]
        native.write_bytes('# 用户规则\n\n'.encode()+b'\n'.join(rules))
        self.install(['codex'])
        req={k:v for k,v in self.request.items() if k in ('home','platform_config','agents','search_paths','app_directories')}
        req['selection']='共享 1、2、3、4、5、6'
        plan=org.plan_organize(req)['approval_plan'];done=org.execute_organize(plan,approved(plan),request=req)
        topic=self.runtime.root/'memories/user-rules.md'; body=topic.read_bytes()
        self.assertNotIn('## 用户规则'.encode(),body)
        self.assertEqual([body.index(x) for x in rules],sorted(body.index(x) for x in rules))
        meta=json.loads(Path(done['manifest']).read_text())['operation_metadata']['share_user_memory']
        for row in meta['migrations']:
            self.assertEqual(body[row['public_offset']:row['public_end']],bytes.fromhex(row['text_hex']))
        native.write_bytes(native.read_bytes()+'\n# 其他语境\n\n- 新增规则。\n'.encode())
        req['selection']='共享 1'
        inc=org.plan_organize(req)['approval_plan'];org.execute_organize(inc,approved(inc),request=req)
        self.assertTrue(topic.read_bytes().startswith(body))
        before=recovery.tree(self.home); backup=self.area/'exit'
        plan=uninstall.preview(home=self.home,backup_dir=backup)
        uninstall.execute(approval(recovery.summary(plan)),home=self.home,backup_dir=backup)
        for rule in rules:self.assertEqual(native.read_bytes().count(rule),1)
        proposal=recovery.recover(backup/'manifest.json')
        result=recovery.recover(backup/'manifest.json',approval=approval(proposal['plan']))
        self.assertEqual(result['status'],'restored');self.assertEqual(recovery.tree(self.home),before)

    def test_same_title_distinct_context_and_literal_fence_are_preserved(self):
        native=self.home/'.codex/AGENTS.md';native.parent.mkdir()
        literal='```md\n# 用户规则\n- 代码示例。\n```\n'.encode()
        native.write_bytes('# 用户规则\n\n- 第一个语境。\n\n# 用户规则\n\n- 第二个语境。\n\n'.encode()+literal)
        self.install(['codex'])
        req={k:v for k,v in self.request.items() if k in ('home','platform_config','agents','search_paths','app_directories')}
        req['selection']='共享 1、2'
        plan=org.plan_organize(req)['approval_plan']
        self.assertNotEqual(plan['groups'][0]['sources'][0]['context'],plan['groups'][1]['sources'][0]['context'])
        org.execute_organize(plan,approved(plan),request=req)
        body=(self.runtime.root/'memories/user-rules.md').read_bytes()
        self.assertEqual(body.count('## 用户规则'.encode()),1)
        self.assertIn(literal,native.read_bytes());self.assertNotIn('代码示例'.encode(),body)

    def test_created_native_directories_removed_and_restored(self):
        self.install()
        before=recovery.tree(self.home);backup=self.area/'exit'
        plan=uninstall.preview(home=self.home,backup_dir=backup)
        dirs=[Path(o['path']).parent for oid,o in json.loads(self.runtime.registry.read_text())['machine']['objects'].items() if oid.endswith('#native-skill')]
        self.assertEqual(len(dirs),6)
        for directory in dirs:self.assertIn(str(directory),plan['guard_roots'])
        uninstall.execute(approval(recovery.summary(plan)),home=self.home,backup_dir=backup)
        for directory in dirs:self.assertFalse(directory.exists())
        proposed=recovery.recover(backup/'manifest.json')
        recovery.recover(backup/'manifest.json',approval=approval(proposed['plan']))
        self.assertEqual(recovery.tree(self.home),before)

    def test_preexisting_or_unknown_child_directories_not_removed(self):
        old=self.home/'.codex/skills/mem-sharing';old.mkdir(parents=True)
        self.install(['codex','claude'])
        unknown=self.home/'.claude/skills/mem-sharing/private.txt';unknown.write_bytes(b'user private')
        plan=uninstall.preview(home=self.home,backup_dir=self.area/'exit')
        for directory in (old,unknown.parent):
            self.assertNotIn(str(directory),[r['path'] for r in plan['changes']])
        uninstall.execute(approval(recovery.summary(plan)),home=self.home,backup_dir=self.area/'exit')
        self.assertTrue(old.is_dir());self.assertEqual(unknown.read_bytes(),b'user private')

    def test_unrelated_receipt_cannot_claim_preexisting_directory(self):
        directory=self.home/'.codex/skills/mem-sharing';directory.mkdir(parents=True)
        self.install(['codex'])
        ledger=json.loads(self.runtime.registry.read_text())
        obj=ledger['machine']['objects'][str(directory/'SKILL.md')+'#native-skill']
        actual=Path(obj['backup_manifest']);receipt=json.loads(actual.read_text())
        receipt['created_directories'].append(str(directory));actual.write_text(json.dumps(receipt))
        self.assertFalse(uninstall._created_native_directory(self.runtime,obj,directory/'SKILL.md'))
        # A matching hash and created_directories claim outside the actual producer is insufficient.
        fake=self.runtime.backups/'unrelated';fake.mkdir()
        (fake/'manifest.json').write_text(json.dumps({'status':'committed','operation':'user-entries',
            'created_directories':[str(directory)],'entries':[{'path':str(directory/'SKILL.md'),
            'before':{'kind':'absent'},'after':{'kind':'file','fingerprint':obj['fingerprint']['value']},'attempted':True}]}))
        self.assertFalse(uninstall._created_native_directory(self.runtime,obj,directory/'SKILL.md'))
        alternate=dict(obj,backup_manifest=str(fake/'manifest.json'))
        self.assertFalse(uninstall._created_native_directory(self.runtime,alternate,directory/'SKILL.md'))

    def test_lock_time_new_native_child_refuses_zero_write(self):
        self.install(['codex']);backup=self.area/'exit'
        plan=uninstall.preview(home=self.home,backup_dir=backup)
        extra=self.home/'.codex/skills/mem-sharing/unknown';extra.write_bytes(b'new')
        before=recovery.tree(self.home)
        with self.assertRaises(ValueError):uninstall.execute(approval(recovery.summary(plan)),home=self.home,backup_dir=backup)
        self.assertEqual(recovery.tree(self.home),before)
