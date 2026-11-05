"""Current-main acquisition uses a local Git remote, never the user's installation."""
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from agm_core import ck_install as ck


class MainSourceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()
        self.remote = self.root/'upstream'
        self.remote.mkdir()
        self.git(self.remote, 'init', '-b', 'main')
        (self.remote/'scripts').mkdir()
        (self.remote/'SKILL.md').write_text('first')
        (self.remote/'scripts/install.py').write_text('import argparse\np=argparse.ArgumentParser()\np.add_argument("--codex")\n')
        self.commit()
        self.home = self.root/'home'; self.home.mkdir()
        self.request = {'home':str(self.home)}
        self.addCleanup(patch.stopall)
        patch.object(ck, 'OFFICIAL', str(self.remote)).start()
        patch.object(ck, '_durable_source').start()

    def git(self, root, *args):
        return subprocess.run(['git','-C',str(root),*args],check=True,capture_output=True,text=True).stdout.strip()

    def commit(self):
        self.git(self.remote,'add','.')
        self.git(self.remote,'-c','user.name=test','-c','user.email=test@example.invalid','commit','-m','update')
        return self.git(self.remote,'rev-parse','HEAD')

    def test_each_request_fetches_current_main_and_preserves_dirty_source(self):
        source = Path(ck.prepare_source(self.request))
        self.assertEqual(source, self.home/'.local/share/context-keeper/source')
        old = self.git(source,'rev-parse','HEAD')
        (self.remote/'SKILL.md').write_text('second')
        new = self.commit(); self.assertNotEqual(old,new)
        self.assertEqual(ck.prepare_source(self.request), str(source))
        self.assertEqual(self.git(source,'rev-parse','HEAD'),new)
        self.git(source,'update-index','--assume-unchanged','SKILL.md')
        (source/'SKILL.md').write_text('private edit')
        with self.assertRaises(ck.CKError): ck.prepare_source(self.request)
        self.assertEqual((source/'SKILL.md').read_text(),'private edit')

    def test_divergent_checkout_is_not_reset(self):
        source=Path(ck.prepare_source(self.request))
        (source/'SKILL.md').write_text('local commit')
        self.git(source,'add','.')
        self.git(source,'-c','user.name=test','-c','user.email=test@example.invalid','commit','-m','local')
        local=self.git(source,'rev-parse','HEAD')
        (self.remote/'SKILL.md').write_text('remote commit');self.commit()
        with self.assertRaises(subprocess.CalledProcessError): ck.prepare_source(self.request)
        self.assertEqual(self.git(source,'rev-parse','HEAD'),local)
        self.assertEqual((source/'SKILL.md').read_text(),'local commit')

    def test_capabilities_follow_fetched_main(self):
        source=Path(ck.prepare_source(self.request))
        self.assertEqual(ck.supported_agents({'root':str(source)}), ['codex'])
        (self.remote/'scripts/install.py').write_text('import argparse\np=argparse.ArgumentParser()\n'+''.join('p.add_argument("--'+a+'")\n' for a in ck.UPSTREAM_ORDER))
        self.commit();ck.prepare_source(self.request)
        self.assertEqual(ck.supported_agents({'root':str(source)}),list(ck.UPSTREAM_ORDER))

    def test_failed_fetch_never_falls_back_to_old_checkout(self):
        source=Path(ck.prepare_source(self.request))
        before=(source/'SKILL.md').read_bytes()
        original=ck._git
        def offline(root, *args):
            if args[0]=='fetch':
                raise subprocess.CalledProcessError(128, ['git','fetch'])
            return original(root,*args)
        with patch.object(ck, '_git', side_effect=offline):
            with self.assertRaises(subprocess.CalledProcessError): ck.prepare_source(self.request)
        self.assertEqual((source/'SKILL.md').read_bytes(), before)
