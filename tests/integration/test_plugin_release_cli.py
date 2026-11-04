"""Cold generated plugin -> durable installer; synthetic Git and HOME only."""
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'unit'))
from test_plugin_release import ReleaseFixture
from agm_core import legacy_import as legacy


class ReleaseCLIProcessTests(ReleaseFixture):
    def cold(self, installer, *args):
        child = subprocess.run([sys.executable,'-B',str(installer),*args], cwd=self.area,
            env=dict(os.environ, HOME=str(self.home), PYTHONDONTWRITEBYTECODE='1'),
            capture_output=True, text=True)
        self.assertEqual(child.stderr, '', child.stderr)
        return child.returncode, json.loads(child.stdout)

    def test_generated_plugin_hands_off_to_durable_installer_without_parent_imports(self):
        installer = self.repo/'plugins/paseo/payload/core/scripts/install.py'
        request = self.area/'release-request.json'; request.write_bytes(legacy.encoded(self.plugin()))
        before = self.snapshot()
        code, preview = self.cold(installer,'--release-request',str(request))
        self.assertEqual(code,5,preview); self.assertEqual(before,self.snapshot())
        code, exported = self.cold(installer,'--approval-file',self.approval_file(preview['approval_plan']))
        self.assertEqual(code,0,exported); self.assertEqual(exported['source']['commit'],self.s)
        durable = Path(exported['source']['root'])/'scripts/install.py'
        inputs = self.area/'inputs.json'; inputs.write_text(json.dumps({'search_paths':[],'app_directories':[]}))
        shutil.rmtree(self.repo/'plugins')
        code, preview = self.cold(durable,'--source-manifest',exported['source_manifest'],'--request-file',str(inputs))
        self.assertEqual(code,5,preview); self.assertEqual(preview['approval_plan']['command'],'install-machine-cli')
        code, installed = self.cold(durable,'--approval-file',self.approval_file(preview['approval_plan']))
        self.assertEqual(code,0,installed); self.assertEqual(installed['status'],'completed')
        self.assertEqual(installed['source']['commit'],self.s)
        self.assertFalse((self.home/'.local/share/mem-sharing/scripts').is_symlink())
        active = json.loads((self.home/'.mem-sharing/var/registry.json').read_bytes())
        self.assertEqual(active['product']['source']['commit'],self.s)
        self.assertNotEqual(active['product']['source']['commit'],self.r)
        self.assertEqual(list(self.home.rglob('__pycache__')),[])

    def test_active_bare_agent_reconnect_is_readonly_and_source_drift_rejected(self):
        exported = self.export()
        package = self.area/'codex-package'
        (package/'bin').mkdir(parents=True)
        executable = package/'bin/codex'
        executable.write_text('#!/bin/sh\n'); executable.chmod(0o755)
        (package/'package.json').write_text(json.dumps({'name':'@openai/codex','version':'1.0', 'bin':{'codex':'bin/codex'}}))
        inputs = self.area/'inputs.json'
        inputs.write_text(json.dumps({'search_paths':[str(package/'bin')], 'app_directories':[]}))
        durable = Path(exported['source']['root'])/'scripts/install.py'
        code, preview = self.cold(durable, '--source-manifest',exported['source_manifest'], '--request-file',str(inputs),'--agent','codex')
        self.assertEqual(code,5,preview)
        code, installed = self.cold(durable,'--approval-file',self.approval_file(preview['approval_plan']))
        self.assertEqual(code,0,installed)
        active = Path(installed['layout']['code'])/'scripts/install.py'
        before = self.snapshot()
        code,nonactive=self.cold(durable,'--agent','codex','--request-file',str(inputs))
        self.assertEqual(code,2,nonactive);self.assertEqual(before,self.snapshot())
        code, again = self.cold(active,'--agent','codex','--request-file',str(inputs))
        self.assertEqual(code,0,again)
        self.assertEqual(again['status'],'completed')
        self.assertFalse(again['approval_required']); self.assertIsNone(again['approval_plan'])
        self.assertEqual(again['agents']['connected'],['codex'])
        self.assertEqual(again['changes'],[]); self.assertIsNone(again['fusion'])
        self.assertEqual(before,self.snapshot())
        # A newly discovered target must still receive a complete, exact entry approval.
        claude=package/'bin/claude'
        claude.write_text('#!/bin/sh\n');claude.chmod(0o755)
        claude_package=self.area/'claude-package'
        (claude_package/'bin').mkdir(parents=True)
        shutil.move(str(claude),str(claude_package/'bin/claude'))
        (claude_package/'package.json').write_text(json.dumps({'name':'@anthropic-ai/claude-code','version':'1.0','bin':{'claude':'bin/claude'}}))
        inputs.write_text(json.dumps({'search_paths':[str(package/'bin'),str(claude_package/'bin')], 'app_directories':[]}))
        before=self.snapshot()
        code,new_target=self.cold(active,'--agent','claude','--request-file',str(inputs))
        self.assertEqual(code,5,new_target)
        self.assertIsNotNone(new_target['approval_plan']['entry_plan'])
        self.assertTrue(new_target['changes']);self.assertEqual(before,self.snapshot())
        altered=dict(new_target['approval_plan']);altered['requested_agents']=['codex']
        code,rejected=self.cold(active,'--approval-file',self.approval_file(altered))
        self.assertEqual(code,2,rejected);self.assertEqual(before,self.snapshot())
        # An actual missing entry still needs the full exact approval, never the no-op shortcut.
        native=self.home/'.codex/AGENTS.md'
        original_native=native.read_bytes()
        native.write_bytes(b'Native content preserved; managed reference removed.\n')
        before=self.snapshot()
        code, drift=self.cold(active,'--agent','codex','--request-file',str(inputs))
        self.assertNotEqual(code,0,drift);self.assertEqual(before,self.snapshot())
        native.write_bytes(original_native)
        # A missing durable receipt cannot trigger acquisition or any write.
        receipt=Path(exported['source_manifest'])
        receipt_raw=receipt.read_bytes();receipt.unlink()
        before=self.snapshot()
        code,missing=self.cold(active,'--agent','codex','--request-file',str(inputs))
        self.assertEqual(code,2,missing);self.assertEqual(before,self.snapshot())
        receipt.write_bytes(receipt_raw);receipt.chmod(0o600)
        # A durable source change must not be inferred as another source/version.
        source_file=Path(exported['source']['root'])/'SKILL.md'
        source_raw=source_file.read_bytes()
        source_file.write_bytes(source_raw+b'\ndrift\n')
        before=self.snapshot()
        code, bad=self.cold(active,'--agent','codex','--request-file',str(inputs))
        self.assertEqual(code,2,bad);self.assertEqual(before,self.snapshot())
        source_file.write_bytes(source_raw)
        # Active C must also match V; never infer from a drifted installed copy.
        active_skill=active.parents[1]/'SKILL.md'
        active_skill.write_bytes(active_skill.read_bytes()+b'\nactive drift\n')
        before=self.snapshot()
        code,bad_active=self.cold(active,'--agent','codex','--request-file',str(inputs))
        self.assertEqual(code,2,bad_active);self.assertEqual(before,self.snapshot())
