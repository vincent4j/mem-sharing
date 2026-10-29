"""AGM delegates WorkBuddy to the upstream protocol without a private template."""
import subprocess
import unittest
from pathlib import Path
from test_m204_enable import EnableFixture
from agm_core import enable


class WorkBuddyProtocolTests(EnableFixture):
    def test_upstream_template_is_used_and_existing_block_is_reused(self):
        self.request['agents'] = ['workbuddy']
        alias = self.root / '.workbuddy/skills/context-keeper'
        alias.parent.mkdir(parents=True)
        alias.symlink_to(self.source)
        bridge = self.root / '.workbuddy/memory/MEMORY.md'
        bridge.parent.mkdir(parents=True)
        block = enable._bridge_template(self.source, 'workbuddy')
        self.assertIn(b'Upstream WorkBuddy rules', block)
        bridge.write_bytes(block + b'\n\n# existing notes\r\n')
        before = bridge.read_bytes(), bridge.stat().st_mtime_ns
        self.apply('yes', True)
        self.assertEqual((bridge.read_bytes(), bridge.stat().st_mtime_ns), before)
        obj = self.load()['projects'][str(self.root)]['checkouts'][str(self.root)]['objects'][str(bridge) + '#keeper']
        self.assertEqual(obj['ownership'], 'reused')
        calls = [c for c in self.calls if '--ensure-bridge' in c]
        self.assertEqual(len(calls), 1)
        self.assertIn('--workbuddy', calls[0])

    def test_workbuddy_drift_stops_before_upstream_call(self):
        self.apply('yes', True)
        bridge = self.root / '.workbuddy/memory/MEMORY.md'
        bridge.write_bytes(bridge.read_bytes().replace(b'Upstream WorkBuddy rules', b'External change'))
        before = bridge.read_bytes()
        self.calls.clear()
        self.request['approval'] = None
        result = enable.run(self.request)
        self.assertEqual(result['errors'][0]['code'], 'drift')
        self.assertEqual(self.calls, [])
        self.assertEqual(bridge.read_bytes(), before)

    def test_missing_upstream_template_fails_closed_without_fallback(self):
        source = self.source / 'scripts/install.py'
        source.write_text(source.read_text().replace('WORKBUDDY_BRIDGE =', 'OLD_WORKBUDDY_BRIDGE ='))
        self.request.update(memory_choice='yes', approval={'provider_source': str(self.source), 'memory_authorization': 'yes'})
        result = enable.run(self.request)
        self.assertEqual(result['status'], 'failed', result)
        self.assertEqual(self.calls, [])
        self.assertFalse((self.root / '.workbuddy/memory/MEMORY.md').exists())

    def test_workbuddy_ensure_wrong_path_rolls_back(self):
        original = self.runner
        def wrong_workbuddy(argv, **kwargs):
            result = original(argv, **kwargs)
            if '--ensure-bridge' in argv and '--workbuddy' in argv:
                return subprocess.CompletedProcess(argv, 0,
                    '{"scope":"project","bridge":"wrong","action":"unchanged"}', '')
            return result
        self.request['runner'] = wrong_workbuddy
        plan = self.preview('yes', True)
        self.request['approval'] = plan
        result = enable.run(self.request)
        self.assertEqual(result['errors'][0]['code'], 'provider_scope_mismatch', result)
        self.assertFalse((self.root / '.workbuddy/memory/MEMORY.md').exists())
        self.assertFalse((self.install / 'registry.json').exists())


if __name__ == '__main__':
    unittest.main()
