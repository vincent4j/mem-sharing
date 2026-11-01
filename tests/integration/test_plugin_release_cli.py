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
