"""Installed C/V -> actual fusion CLI -> repeat -> formal exit, temporary HOME."""
import copy
import io
import json
import os
import sys
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).parent))
import test_m404_install as fixture
from runtime_fixture import seed_project_executors
from test_m408_installer import cli as install_cli
from agm_core import detect, user_rules_organize as org, memory_share as share, uninstall, uninstall_recovery as restore
from agm_core import registry, user_entries, fusion_recovery

class InstalledSelectionTests(unittest.TestCase):
    def setUp(self):
        f=fixture.InstallFixture(); f.setUp(); self.addCleanup(f.doCleanups); self.f=f
        f.request.update(seed_project_executors(f.home)); f.request['agents']=['codex','claude']
        self.native={}
        for agent,name in [('codex','AGENTS.md'),('claude','CLAUDE.md')]:
            p=f.home/('.'+agent)/name; p.parent.mkdir(exist_ok=True)
            p.write_text('# 用户规则\n\n- 提交信息使用中文。\n')
            self.native[agent]=p
        self.assertEqual(f.execute()['status'],'completed')
        # Reproduce the exact historical fusion-owned entry alongside the installed rules entry.
        old=share._entry_bytes('codex',f.runtime)
        self.native['codex'].write_bytes(self.native['codex'].read_bytes()+b'\n'+old)
        self.req={k:v for k,v in f.request.items() if k in ('home','platform_config','agents','search_paths','app_directories','detect_runner')}

    def invoke(self, selection, shown):
        f=self.f; path=f.area/'displayed-plan.json'; path.write_text(json.dumps(shown))
        out=io.StringIO()
        with patch.dict(os.environ, HOME=str(f.home), PATH=os.pathsep.join(f.request['search_paths'])), patch.object(detect,'STANDARD_APP_DIRECTORIES',()), redirect_stdout(out):
            rc=org.cli(['organize-user-memory','--agent','codex','--agent','claude',
                '--selection',selection,'--selection-plan-file',str(path),'--selection-reference','用户选择：'+selection],home=f.home)
        return rc,json.loads(out.getvalue())

    def test_install_cli_cleanup_repeat_uninstall_restore_keeps_V_closed(self):
        f=self.f; shown=org.plan_organize(self.req)['approval_plan']
        before_v=json.loads(f.runtime.registry.read_bytes())
        rc,result=self.invoke('按默认方案',shown)
        self.assertEqual(rc,0,result);self.assertEqual(result['fusion_status'],'completed')
        for p in self.native.values(): self.assertNotIn('# 用户规则'.encode(),p.read_bytes())
        self.assertNotIn(share.ENTRY_MARKER['start'],self.native['codex'].read_bytes())
        self.assertEqual(share._entry_state('codex',self.native['codex'].read_bytes(),f.runtime),1)
        after_v=json.loads(f.runtime.registry.read_bytes()); expected=copy.deepcopy(before_v)
        imports=[o for o in expected['machine']['objects'].values() if o['kind']=='import']
        for obj in imports:obj['fingerprint']['value']=org.entries.sha256(self.native['claude'].read_bytes())
        self.assertEqual(after_v,expected)
        repeat=install_cli.plan_machine(f.request)
        self.assertEqual(repeat['changes'],[])
        self.assertEqual(install_cli.execute_machine(repeat,fixture.approved(repeat),request=f.request)['changes'],[])
        before=restore.tree(f.home)
        plan=uninstall.preview(home=f.home,backup_dir=f.area/'exit-backup')
        self.assertEqual(restore.tree(f.home),before)
        from test_uninstall import approval
        done=uninstall.execute(approval(restore.summary(plan)),home=f.home,backup_dir=f.area/'exit-backup')
        self.assertEqual(done['status'],'completed')
        recovery=restore.recover(f.area/'exit-backup/manifest.json')
        restored=restore.recover(f.area/'exit-backup/manifest.json',approval=approval(recovery['plan']))
        self.assertEqual(restored['status'],'restored');self.assertEqual(restore.tree(f.home),before)
