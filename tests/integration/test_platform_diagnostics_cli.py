"""Portable safe slice only. Never executes an installer or reads real memory."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


class PlatformDiagnosticCliTests(unittest.TestCase):
    def test_cold_cli_zero_write_in_explicit_synthetic_root(self):
        source = Path(__file__).resolve().parents[2] / 'scripts'
        with tempfile.TemporaryDirectory(prefix='memsharing-platform-') as tmp:
            root = Path(tmp)
            scripts = root / 'source' / 'scripts'
            shutil.copytree(source, scripts, ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
            home = root / 'synthetic-home'
            home.mkdir()
            marker = home / 'synthetic-memory.txt'
            marker.write_bytes(b'\xef\xbb\xbfSYNTHETIC ONLY\r\n')
            def snapshot():
                return {str(p.relative_to(root)): (
                            p.lstat().st_mode, p.lstat().st_mtime_ns,
                            p.lstat().st_ino, p.read_bytes() if p.is_file() else None)
                        for p in [root, *root.rglob('*')]}
            before = snapshot()
            env = {'PATH': os.defpath, 'HOME': str(home), 'USERPROFILE': str(home),
                   'PYTHONDONTWRITEBYTECODE': '1'}
            # Native Windows interpreter startup needs SystemRoot. Do not copy
            # arbitrary environment/configuration/credentials into this process.
            if 'SystemRoot' in os.environ:
                env['SystemRoot'] = os.environ['SystemRoot']
            for args, expected in (([], 0), (['--windows-path', 'C:\\中文 用户\\规则.md'], 0),
                                   (['--windows-path', 'C:\\NUL.txt'], 1)):
                proc = subprocess.run([sys.executable, '-B', str(scripts / 'agm.py'),
                                       'diagnose-platform', '--json'] + args,
                                      cwd=root, env=env, capture_output=True, text=True,
                                      encoding='utf-8', timeout=30)
                self.assertEqual(proc.returncode, expected, proc.stderr)
                result = json.loads(proc.stdout)
                self.assertEqual(result['changes'], [])
                self.assertFalse(result['windows']['production_write_enabled'])
                self.assertNotIn('SYNTHETIC ONLY', proc.stdout)
                self.assertNotIn(str(home), proc.stdout)
                self.assertEqual(snapshot(), before)


if __name__ == '__main__':
    unittest.main()
