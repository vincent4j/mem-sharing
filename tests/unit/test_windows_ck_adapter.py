"""Semantic bridge tests with a tiny upstream API fixture, not Windows evidence."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import uuid

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
from agm_core import windows_preview as p

# Only the documented call shape is modeled. Actual upstream and Windows
# junction behavior are verified separately on their respective hosts.
UPSTREAM = r'''
import argparse,json,os
from pathlib import Path
SOURCE=Path(__file__).resolve().parents[1]
def build_parser():
 p=argparse.ArgumentParser();p.add_argument('--zcode',action='store_true');p.add_argument('--workbuddy',action='store_true');p.add_argument('--approved',action='store_true');return p
def _skill_roots(a,h,project):return [h/n for n in (['.zcode/skills','.agents/skills'] if a=='zcode' else ['.workbuddy/skills'])]
def _bridge_path(a,h,user=False):return h/('.zcode/AGENTS.md' if a=='zcode' else '.workbuddy/MEMORY.md')
def _upsert_bridge(f,a):
 raw=f.read_bytes() if f.exists() else b'';block=('CK-'+a+'\n').encode();f.parent.mkdir(parents=True,exist_ok=True)
 if block not in raw:f.write_bytes(block+raw)
def _is_alias(f):return f.is_symlink()
def _unlink_alias(f):f.unlink()
def main(args):
 args=build_parser().parse_args(args);h=Path(os.environ['HOME']);agents=[a for a in ['zcode','workbuddy'] if getattr(args,a)]
 links=[r/'context-keeper' for a in agents for r in _skill_roots(a,h,None)];rules=[_bridge_path(a,h,True) for a in agents]
 if not args.approved:print(json.dumps({'approval_required':True,'skill_entries':list(map(str,links)),'rule_files':list(map(str,rules))}));return 0
 for f in links:
  f.parent.mkdir(parents=True,exist_ok=True)
  if not f.exists():f.symlink_to(SOURCE,target_is_directory=True)
 for a,f in zip(agents,rules):_upsert_bridge(f,a)
 if (SOURCE/'fail').exists():raise RuntimeError('fixture failure after writes')
 if (SOURCE/'lose-link').exists():links[0].unlink()
 print(json.dumps({'installed':list(map(str,links))}));return 0
'''


class WindowsCkAdapterTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='ms-ck-bridge-')
        self.area = Path(self.tmp.name).resolve()
        self.home = self.area / 'home'; self.home.mkdir()
        self.ck = self.area / 'ck'; (self.ck / 'scripts').mkdir(parents=True)
        (self.ck / 'scripts/install.py').write_text(UPSTREAM)
        self.originals = {'.zcode/AGENTS.md': b'Z private\r\n', '.workbuddy/MEMORY.md': b'WB private\r\n'}
        for rel, data in self.originals.items():
            f = self.home / rel; f.parent.mkdir(parents=True, exist_ok=True); f.write_bytes(data)
        plan = p.install_plan(self.home, ROOT); p.execute(plan, p.digest(p.encoded(plan)))
        self.public = (self.home / p.PUBLIC).read_bytes()
        self.before = {name: (self.home / name).read_bytes() for name in [*p.NATIVE, p.RECEIPT, p.PUBLIC]}
        self.bridge = (ROOT / 'plugins/paseo/server/windows-ck-bridge.ts').read_text().split('String.raw`', 1)[1].rsplit('`;', 1)[0]
        self.assertIn("if sys.platform!='win32': raise ValueError('Windows Host required')", self.bridge)
        self.bridge = self.bridge.replace("if sys.platform!='win32': raise ValueError('Windows Host required')", '')

    def tearDown(self):
        self.tmp.cleanup()

    def call(self, **request):
        proc = subprocess.run([sys.executable, '-I', '-S', '-B', '-X', 'utf8', '-c', self.bridge, str(ROOT / 'scripts')],
                              input=json.dumps(dict(request, home=str(self.home), ck_source=str(self.ck))),
                              env=dict(os.environ, HOME=str(self.home), USERPROFILE=str(self.home)), text=True, capture_output=True)
        self.assertTrue(proc.stdout, proc.stderr)
        return json.loads(proc.stdout)

    def plan(self):
        value = self.call(action='plan', run_id=str(uuid.uuid4()))
        self.assertEqual(value['status'], 'approval_required', value)
        return value['plan']

    def test_preview_and_install_preserve_public_then_exit_keeps_ck(self):
        plan = self.plan()
        for name, raw in self.before.items(): self.assertEqual((self.home / name).read_bytes(), raw)
        self.assertFalse((self.home / '.mem-sharing-ck-operations').exists())
        result = self.call(action='confirm', plan=plan)
        self.assertEqual(result['status'], 'committed', result)
        self.assertEqual((self.home / p.PUBLIC).read_bytes(), self.public)
        p.add_plan(self.home, 'new item')
        exit_plan = p.exit_plan(self.home); result = p.execute(exit_plan, p.digest(p.encoded(exit_plan)))
        self.assertEqual(Path(result['export']['path']).read_bytes(), self.public)
        for rel, raw in self.originals.items():
            data = (self.home / rel).read_bytes(); self.assertIn(raw, data); self.assertIn(b'CK-', data); self.assertNotIn(p.START.encode(), data)
        for rel in ['.zcode/skills/context-keeper', '.agents/skills/context-keeper', '.workbuddy/skills/context-keeper']:
            self.assertEqual((self.home / rel).resolve(), self.ck)

    def test_windows_large_volume_identity_survives_javascript_approval_roundtrip(self):
        self.bridge = self.bridge.replace("'dev':str(st.st_dev),'ino':str(st.st_ino)",
                                          "'dev':str(18026235495889856457),'ino':str(18026235495889856459)")
        plan = self.plan()
        for identity in plan['parents'].values():
            if identity:
                self.assertEqual(identity['dev'], '18026235495889856457')
                self.assertEqual(identity['ino'], '18026235495889856459')
        roundtrip = subprocess.run(['node', '-e',
            'let s="";process.stdin.on("data",b=>s+=b);process.stdin.on("end",()=>process.stdout.write(JSON.stringify(JSON.parse(s))))'],
            input=json.dumps(plan), text=True, capture_output=True, check=True)
        approved = json.loads(roundtrip.stdout)
        self.assertEqual(self.call(action='confirm', plan=approved)['status'], 'committed')
        self.assertEqual((self.home / p.PUBLIC).read_bytes(), self.public)

    def test_rule_drift_rejects_before_installer_writes(self):
        plan = self.plan(); (self.home / '.zcode/AGENTS.md').write_bytes(b'foreign edit')
        result = self.call(action='confirm', plan=plan); self.assertEqual(result['status'], 'failed')
        self.assertEqual((self.home / '.zcode/AGENTS.md').read_bytes(), b'foreign edit')
        self.assertFalse((self.home / '.agents/skills/context-keeper').exists())

    def test_upstream_failure_restores_rules_receipt_and_only_own_aliases(self):
        (self.ck / 'fail').write_text('fail')
        plan = self.plan(); result = self.call(action='confirm', plan=plan)
        self.assertEqual(result['status'], 'failed')
        for name, raw in self.before.items(): self.assertEqual((self.home / name).read_bytes(), raw)
        self.assertFalse((self.home / '.agents/skills/context-keeper').exists())
        journal = self.home / '.mem-sharing-ck-operations' / plan['run_id'] / 'journal.json'
        self.assertEqual(json.loads(journal.read_bytes())['status'], 'rolled_back')
        p.exit_plan(self.home)

    def test_missing_installed_alias_rejects_commit_and_restores_own_writes(self):
        (self.ck / 'lose-link').write_text('simulate disappearance after installer writes')
        plan = self.plan()
        result = self.call(action='confirm', plan=plan)
        self.assertEqual(result['status'], 'failed', result)
        self.assertIn('installed link missing', result['message'])
        for name, raw in self.before.items():
            self.assertEqual((self.home / name).read_bytes(), raw)
        for rel in ['.zcode/skills/context-keeper', '.agents/skills/context-keeper', '.workbuddy/skills/context-keeper']:
            self.assertFalse(os.path.lexists(self.home / rel))
        journal = self.home / '.mem-sharing-ck-operations' / plan['run_id'] / 'journal.json'
        self.assertEqual(json.loads(journal.read_bytes())['status'], 'rolled_back')
        p.exit_plan(self.home)

    def test_foreign_alias_and_incomplete_journal_fail_closed(self):
        root = self.home / '.zcode/skills/context-keeper'; root.symlink_to(self.area, target_is_directory=True)
        self.assertEqual(self.call(action='plan', run_id=str(uuid.uuid4()))['status'], 'failed')
        self.assertEqual(root.resolve(), self.area); root.unlink()
        op = self.home / '.mem-sharing-ck-operations' / str(uuid.uuid4()); op.mkdir(parents=True)
        (op / 'journal.json').write_text('{"status":"running"}')
        self.assertEqual(self.call(action='plan', run_id=str(uuid.uuid4()))['status'], 'failed')
        for name, raw in self.before.items(): self.assertEqual((self.home / name).read_bytes(), raw)
