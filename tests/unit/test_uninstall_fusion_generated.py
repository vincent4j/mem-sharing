"""Real fusion producer through six native uninstall returns; synthetic HOME only."""
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parent))
from test_m404_install import InstallFixture, approved
from test_uninstall import approval
from agm_core import detect, paths, user_rules_organize as fusion, uninstall
from agm_core import uninstall_memory as memory, uninstall_recovery as recovery


class FusionReturnTests(unittest.TestCase):
    def setUp(self):
        f=InstallFixture();f.setUp();self.addCleanup(f.doCleanups);self.f=f
        self.common='完整用户原文：提交说明使用中文，保留全部条件。\n'.encode()
        self.ck=b'<!-- context-keeper:start -->\nSynthetic CK opaque.\n<!-- context-keeper:end -->\n'
        self.private={}
        for agent,config in f.config.items():
            p=Path(paths.expand_path(config['user_entry'],home=str(f.home)))
            p.parent.mkdir(parents=True,exist_ok=True)
            own=('# 用户个人标题\n\n'+agent+' 私有原文。[用户自有链接](https://example.invalid/user-rules.md)\n\n').encode()
            p.write_bytes(own+self.common+b'\n'+self.ck);p.chmod(0o640)
            self.private[agent]=(p,own)
        real=detect.detect_agents
        def installed(*args,**kwargs):
            result=real(*args,**kwargs)
            for row in result['agents'].values():row.update(status='installed',summary='synthetic installed executable')
            return result
        self.patch=patch.object(detect,'detect_agents',side_effect=installed);self.patch.start();self.addCleanup(self.patch.stop)
        self.assertEqual(f.execute()['status'],'completed')
        self.req={k:v for k,v in f.request.items() if k in ('home','platform_config','agents','search_paths','app_directories')}
        self.run_fusion()
        self.index=f.runtime.root/'memories/MEMORY.md'
        self.topic=f.runtime.root/'memories/user-rules.md'

    def run_fusion(self, include_optional=False):
        self.req.pop('selection',None)
        preview=fusion.plan_organize(self.req)
        if include_optional:
            self.req['selection']='共享 '+'、'.join(map(str,preview['approval_plan']['optional_numbers']))
            preview=fusion.plan_organize(self.req)
        self.assertEqual(preview['status'],'approval_required',preview)
        plan=preview['approval_plan']
        result=fusion.execute_organize(plan,approved(plan),request=self.req)
        self.assertEqual(result['status'],'completed',result)
        self.manifest=Path(result['manifest'])
        return plan

    def test_real_creation_public_body_and_six_returns_preserve_originals(self):
        self.assertTrue(self.topic.read_bytes().startswith('# 用户规则\n'.encode()))
        original=memory.public_sources(self.f.runtime)
        body=memory.public_body(self.f.runtime,original)
        self.assertIn(self.common,body)
        self.assertNotIn(memory.FUSION_GENERATED_PREFIX,body)
        self.assertNotIn('- 用户记忆：user-rules.md'.encode(),body)
        # Wrapper recognition never changes arbitrary native user text.
        self.assertEqual(memory.strip_generated(memory.FUSION_GENERATED_PREFIX,self.f.runtime),memory.FUSION_GENERATED_PREFIX)
        before={str(p):(p.stat().st_ino,p.stat().st_mode&0o777) for p,_ in self.private.values()}
        backup=self.f.area/'uninstall-backup'
        plan=uninstall.preview(home=self.f.home,backup_dir=backup)
        result=uninstall.execute(approval(recovery.summary(plan)),home=self.f.home,backup_dir=backup)
        self.assertEqual(result['status'],'completed')
        for agent,(p,own) in self.private.items():
            raw=p.read_bytes()
            self.assertIn(own,raw,agent);self.assertIn(self.common,raw,agent);self.assertIn(self.ck,raw,agent)
            self.assertNotIn(memory.FUSION_GENERATED_PREFIX,raw,agent)
            self.assertNotIn('当前有效结论：以下记忆经完整清单确认后共享'.encode(),raw,agent)
            self.assertNotIn('- 用户记忆：user-rules.md'.encode(),raw,agent)
            self.assertEqual((p.stat().st_ino,p.stat().st_mode&0o777),before[str(p)])

    def test_unknown_custom_duplicate_and_missing_proof_fail_closed(self):
        original=self.topic.read_bytes()
        for kind in ('custom','duplicate','missing'):
            with self.subTest(kind=kind):
                saved=self.manifest.read_bytes()
                if kind=='custom':self.topic.write_bytes(original.replace(self.common,b'changed source\n'))
                if kind=='duplicate':self.topic.write_bytes(memory.FUSION_GENERATED_PREFIX+original)
                if kind=='missing':self.manifest.unlink()
                try:
                    with self.assertRaises(ValueError):
                        uninstall.preview(home=self.f.home,backup_dir=self.f.area/('blocked-'+kind))
                finally:
                    self.topic.write_bytes(original)
                    self.manifest.write_bytes(saved)

    def test_normal_second_fusion_history_and_broken_chain(self):
        # Legitimate later content follows a complete committed topic chain.
        more='另一条完整公共用户原文：修改后说明验证结果。\n'.encode()
        for agent,(p,_) in self.private.items():
            if agent!='claude':p.write_bytes(p.read_bytes()+b'\n'+more)
        self.run_fusion(include_optional=True)
        self.assertIn(more,self.topic.read_bytes())
        third='第三条完整用户原文：保留用户自有链接。\n'.encode()
        for agent,(p,_) in self.private.items():
            if agent!='claude':p.write_bytes(p.read_bytes()+b'\n'+third)
        self.run_fusion(include_optional=True)
        before=recovery.tree(self.f.home)
        body=memory.public_body(self.f.runtime,memory.public_sources(self.f.runtime))
        self.assertIn(more,body);self.assertIn(self.common,body)
        self.assertNotIn(memory.FUSION_GENERATED_PREFIX,body)
        self.assertIn(third,body)
        saved_manifest=self.manifest.read_bytes()
        data=json.loads(saved_manifest)
        row=next(r for r in data['entries'] if r['path']==str(self.topic))
        row['before']['fingerprint']='0'*64
        self.manifest.write_text(json.dumps(data))
        with self.assertRaises(ValueError):
            uninstall.preview(home=self.f.home,backup_dir=self.f.area/'broken-proof')
        self.manifest.write_bytes(saved_manifest)
        backup=self.f.area/'after-three-fusions'
        plan=uninstall.preview(home=self.f.home,backup_dir=backup)
        result=uninstall.execute(approval(recovery.summary(plan)),home=self.f.home,backup_dir=backup)
        self.assertEqual(result['status'],'completed')
        for agent,(p,own) in self.private.items():
            raw=p.read_bytes()
            for fragment in (own,self.common,self.ck):self.assertIn(fragment,raw)
            if agent!='claude':
                for fragment in (more,third):self.assertIn(fragment,raw)
            self.assertNotIn(memory.FUSION_GENERATED_PREFIX,raw)

if __name__=='__main__':unittest.main()
