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


class ReleaseClosureTests(unittest.TestCase):
    def test_manifest_is_thirty_files(self):
        tracked = subprocess.run(['git', '-C', str(REPO), 'ls-files', '-z'],
                                 capture_output=True, text=True, check=True).stdout.split('\0')
        manifest = {name for name in tracked if name and cli._managed_source(name)}
        self.assertEqual(len(manifest), 30, sorted(manifest))

    def test_shipped_doc_links_stay_inside_manifest(self):
        tracked = subprocess.run(['git', '-C', str(REPO), 'ls-files', '-z'],
                                 capture_output=True, text=True, check=True).stdout.split('\0')
        manifest = {name for name in tracked if name and cli._managed_source(name)}
        for doc in cli.SHIPPED_DOCS:
            for number, target in shipped_doc_links(doc):
                with self.subTest(link=f'{doc}:{number} -> {target}'):
                    resolved = (REPO/doc).parent.joinpath(target).resolve()
                    rel = str(resolved.relative_to(REPO.resolve()))
                    self.assertIn(rel, manifest)


if __name__ == '__main__':
    unittest.main()
