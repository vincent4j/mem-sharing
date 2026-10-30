"""Retired migration is refused in a fresh process with a synthetic HOME."""
import json
import os
from pathlib import Path
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).parents[1] / 'unit'))
from test_m403_migrate import MigrationFixture


class MigrationProcessTests(MigrationFixture):
    def test_old_journal_cannot_replay_in_fresh_process(self):
        journal = self.area / 'journal.json'; journal.write_text(json.dumps(self.plan))
        before = self.snapshot()
        script = '''import sys
from agm_core import migrate
try: migrate.plan_recovery(sys.argv[1], action=sys.argv[2])
except migrate.MigrationError as e:
 print(e.code); sys.exit(2)
'''
        for action in ('continue', 'rollback'):
            result = subprocess.run([sys.executable, '-B', '-c', script, str(journal), action],
                env=dict(os.environ, HOME=str(self.home), PYTHONDONTWRITEBYTECODE='1',
                         PYTHONPATH=str(Path(__file__).resolve().parents[2] / 'scripts')),
                capture_output=True, text=True)
            self.assertEqual(result.returncode, 2, result.stderr)
            self.assertEqual(result.stdout.strip(), 'migration_unsupported')
            self.assertEqual(before, self.snapshot())
