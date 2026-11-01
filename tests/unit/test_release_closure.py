"""Release manifest closure: every clickable local link in shipped docs resolves
inside the manifest checkout_source would package. Static only; no install runs."""
import importlib.util
import re
import subprocess
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('release_install', REPO/'scripts/install.py')
cli = importlib.util.module_from_spec(spec); spec.loader.exec_module(cli)

LINK = re.compile(r'\[[^\]]*\]\(([^)#\s]+)(?:#[^)\s]*)?\)')
REMOTE = ('http://', 'https://', 'mailto:')


def shipped_doc_links(doc):
    """Clickable local markdown links outside fenced code blocks."""
    inside = False
    for number, line in enumerate((REPO/doc).read_text(encoding='utf-8').splitlines(), 1):
        if line.lstrip().startswith('```'):
            inside = not inside
            continue
        if inside:
            continue
        for target in LINK.findall(line):
            if not target.startswith(REMOTE):
                yield number, target


def _manifest_names():
    """当前 payload 的受管文件名:tracked + untracked(未 commit 的新模块不得漏包)。"""
    names = subprocess.run(
        ['git', '-C', str(REPO), 'ls-files', '--cached', '--others', '--exclude-standard', '-z'],
        capture_output=True, text=True, check=True).stdout.split('\0')
    return {name for name in names if name and (REPO/name).is_file() and cli._managed_source(name)}


class ReleaseClosureTests(unittest.TestCase):
    def test_manifest_contains_live_core_and_documents(self):
        manifest = _manifest_names()
        # Current source payload adds the shared release resolver to the 31 files.
        self.assertIn('scripts/agm_core/public_layout.py', manifest)
        self.assertIn('scripts/agm_core/plugin_release.py', manifest)
        for name in ('uninstall','uninstall_recovery','policy_migration'):
            self.assertIn('scripts/agm_core/'+name+'.py',manifest)
        self.assertNotIn('scripts/agm_core/remove.py',manifest)
        self.assertTrue(set(cli.SHIPPED_DOCS)<=manifest)
        existing={str(p.relative_to(REPO)) for p in (REPO/'scripts').rglob('*') if p.is_file() and p.suffix in ('.py','.json') and cli._managed_source(str(p.relative_to(REPO)))}
        self.assertEqual(manifest,existing|set(cli.SHIPPED_DOCS))

    def test_shipped_doc_links_stay_inside_manifest(self):
        manifest = _manifest_names()
        for doc in cli.SHIPPED_DOCS:
            for number, target in shipped_doc_links(doc):
                with self.subTest(link=f'{doc}:{number} -> {target}'):
                    resolved = (REPO/doc).parent.joinpath(target).resolve()
                    rel = str(resolved.relative_to(REPO.resolve()))
                    self.assertIn(rel, manifest)


if __name__ == '__main__':
    unittest.main()
