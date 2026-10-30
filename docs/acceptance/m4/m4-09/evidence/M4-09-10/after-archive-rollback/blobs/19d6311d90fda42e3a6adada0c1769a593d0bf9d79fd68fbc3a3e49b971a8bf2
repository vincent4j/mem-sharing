"""Development ledgers are refused rather than silently upgraded to schema 3."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_m403_migrate import MigrationFixture
from agm_core import upgrade, legacy_import as legacy, user_install as install


class LegacyUpgradeTests(MigrationFixture):
    def test_old_schema_upgrade_routes_refuse_and_preserve_all_source_bytes(self):
        source = self.area / 'target'; (source / 'scripts/agm_core').mkdir(parents=True)
        for rel, raw in {'SKILL.md': b'# product\n', 'scripts/agm.py': b'print("fixture")\n',
                         'scripts/agm_core/__init__.py': b''}.items():
            (source / rel).write_bytes(raw)
        request = {'home': str(self.home), 'platform_config': self.config, 'search_paths': [], 'app_directories': [],
                   'source': {'root': str(source), 'url': 'fixture://formal', 'commit': 'c'*40, 'version': '0.4.0',
                   'files': {str(p.relative_to(source)): legacy.digest(p.read_bytes()) for p in source.rglob('*') if p.is_file()}},
                   'legacy_registries': [str(self.old)]}
        before = self.snapshot()
        self.assertEqual(install.inspect_machine(request)['scene'], 'unsupported')
        with self.assertRaises(ValueError): install.plan_install(request)
        with self.assertRaises(ValueError): upgrade.plan_upgrade(request)
        self.assertEqual(before, self.snapshot())
