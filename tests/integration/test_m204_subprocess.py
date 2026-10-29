"""Real subprocess/file-system integration against a disposable Keeper checkout stub."""
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "unit"))
from test_m204_enable import EnableFixture
from agm_core import enable

INSTALL_STUB = r'''import json, sys
from pathlib import Path
BRIDGE_START = "<!-- context-keeper:start -->"
BRIDGE_END = "<!-- context-keeper:end -->"
BRIDGE = f"{BRIDGE_START}\nKeeper rules\n{BRIDGE_END}\n"
args = sys.argv[1:]
def value(name): return args[args.index(name)+1]
source = Path(__file__).resolve().parents[1]
if '--ensure-bridge' in args:
    root = Path(value('--root'))
    bridge = root / ('AGENTS.md' if '--codex' in args else 'CLAUDE.md')
    assert BRIDGE.rstrip() in bridge.read_text()
    print(json.dumps(dict(scope='project', bridge=str(bridge), action='unchanged')))
else:
    root = Path(value('--project'))
    links, rules = [], []
    for agent, roots, entry in [('codex', ['.agents', '.codex'], 'AGENTS.md'), ('claude', ['.claude'], 'CLAUDE.md'), ('workbuddy', ['.workbuddy'], None)]:
        if '--'+agent not in args: continue
        links += [str(root / base / 'skills/context-keeper') for base in roots]
        if entry: rules.append(str(root / entry))
    if '--approved' not in args:
        print(json.dumps(dict(approval_required=True, skill_entries=links, rule_files=rules)))
    else:
        for link in links:
            assert Path(link).is_symlink() and Path(link).resolve() == source
        for rule in rules:
            assert BRIDGE.rstrip() in Path(rule).read_text()
        print(json.dumps(dict(scope='project', project=str(root))))
'''

PROBE_STUB = r'''import json, sys
from pathlib import Path
args = sys.argv[1:]
def value(name): return args[args.index(name)+1]
root, store = Path(value('--root')), Path(value('--store-dir'))
source = Path(__file__).resolve().parents[1]
modefile = source / 'mode'
mode = modefile.read_text() if modefile.exists() else ''
if mode == 'migration': sys.exit(3)
if '--approved' not in args:
    sys.exit(0 if (store / 'memory-keeper.md').exists() else 5)
store.mkdir(parents=True, exist_ok=True)
(store / 'memory-keeper.md').write_text('# keeper store\n')
if mode == 'partial': sys.exit(2)
for name in ('plans', 'worklogs', 'evolution'):
    (store / name).mkdir(exist_ok=True)
if store != root / 'docs/context-keeper':
    (root / 'context-keeper.json').write_text(json.dumps(dict(directory=str(store))))
print('store ready')
'''


class SubprocessTests(EnableFixture):
    def setUp(self):
        super().setUp()
        (self.source / 'scripts/install.py').write_text(INSTALL_STUB)
        (self.source / 'scripts/context_keeper_probe.py').write_text(PROBE_STUB)
        self.request.pop('runner')

    def test_full_subprocess_install_and_registry_last(self):
        events = []
        self.request['transaction_hook'] = lambda event, path: events.append((event, path))
        result = self.apply('yes', True)
        self.assertEqual(result['status'], 'completed')
        writes = [p for event, p in events if event == 'before_write']
        self.assertEqual(writes[-1], self.install / 'registry.json')
        self.assertTrue((self.install / '.agm.lock').exists() is False)
        self.assertFalse(list(self.source.rglob('__pycache__')))
        manifests = list((self.install / 'backups').rglob('manifest.json'))
        self.assertEqual(len(manifests), 1)
        self.assertEqual(json.loads(manifests[0].read_text())['status'], 'committed')
        self.request['approval'] = None
        self.assertEqual(enable.run(self.request)['changes'], [])

    def test_real_subprocess_partial_store_kept_configs_restored(self):
        plan = self.preview('yes', True)
        (self.source / 'mode').write_text('partial')
        self.request['approval'] = plan
        result = enable.run(self.request)
        self.assertEqual(result['status'], 'failed', result)
        self.assertTrue((self.root / 'docs/context-keeper/memory-keeper.md').exists())
        self.assertFalse((self.root / 'AGENTS.md').exists())
        self.assertFalse((self.install / 'registry.json').exists())
        manifest = json.loads(next((self.install / 'backups').rglob('manifest.json')).read_text())
        self.assertEqual(manifest['status'], 'rolled_back')

    def test_migration_no_record_readback_or_extra_provider_call(self):
        plan = self.preview('yes', True)
        (self.source / 'mode').write_text('migration')
        self.request['approval'] = plan
        result = enable.run(self.request)
        self.assertEqual(result['status'], 'migration_required', result)
        self.assertFalse((self.root / 'docs').exists())
        self.assertFalse((self.install / 'backups').exists())

    def test_config_fault_rolls_back_and_preserves_old_registry(self):
        self.apply()
        before = (self.install / 'registry.json').read_bytes()
        self.request['approval'] = None
        plan = self.preview('yes', True)
        self.request['approval'] = plan
        def fail(event, path):
            if event == 'before_write' and path == self.root / 'CLAUDE.md':
                raise OSError('injected write failure')
        self.request['transaction_hook'] = fail
        result = enable.run(self.request)
        self.assertEqual(result['status'], 'failed', result)
        self.assertEqual((self.install / 'registry.json').read_bytes(), before)
        self.assertNotIn(b'context-keeper:start', (self.root / 'AGENTS.md').read_bytes())

    def test_rollback_failure_has_recovery_manifest(self):
        plan = self.preview()
        self.request['approval'] = plan
        def fail(event, path):
            if event == 'after_write':
                raise OSError('fail after write')
            if event == 'before_restore':
                raise OSError('fail rollback')
        self.request['transaction_hook'] = fail
        result = enable.run(self.request)
        self.assertEqual(result['status'], 'recovery_required', result)
        self.assertTrue(Path(result['errors'][0]['recovery']).is_file())
        self.assertFalse((self.install / 'registry.json').exists())

    def test_source_changed_before_transaction_is_rejected(self):
        plan = self.preview('yes', True)
        self.request['approval'] = plan
        called = []
        def mutate(event, path):
            if event == 'after_write' and not called:
                called.append(True)
                (self.source / 'SKILL.md').write_text('foreign source change')
        self.request['transaction_hook'] = mutate
        result = enable.run(self.request)
        self.assertEqual(result['status'], 'approval_required', result)
        self.assertFalse((self.install / 'registry.json').exists())

    def test_group_then_keeper_existing_objects_reused(self):
        self.apply()
        self.request['approval'] = None
        self.apply('yes', True)
        assembly = self.load()['projects'][str(self.root)]['checkouts'][str(self.root)]
        alias = str(self.root / '.agents/skills/context-keeper')
        self.assertEqual(assembly['objects'][alias]['ownership'], 'reused')
        base = assembly['objects'][str(self.root / 'AGENTS.md') + '#base']
        self.assertEqual(base['ownership'], 'created')

    def test_keeper_first_adopts_correct_bridges_as_reused(self):
        block = enable._bridge_template(self.source)
        (self.root / 'AGENTS.md').write_bytes(b'old project rules\r\n' + block)
        (self.root / 'CLAUDE.md').write_bytes(b'@AGENTS.md\n' + block)
        self.apply('yes', True)
        objects = self.load()['projects'][str(self.root)]['checkouts'][str(self.root)]['objects']
        self.assertEqual(objects[str(self.root / 'AGENTS.md') + '#keeper']['ownership'], 'reused')
        self.assertTrue((self.root / 'AGENTS.md').read_bytes().startswith(b'old project rules\r\n'))


if __name__ == '__main__':
    unittest.main()
