"""M4-06: strict command-specific approval wiring; no real HOME operations."""
import copy
import unittest
from test_cli import agm, _approval_data


class LifecycleApprovalTests(unittest.TestCase):
    def plan(self):
        return _approval_data(installation={a: {'status': 'installed', 'fingerprint': 'a' * 64}
                                           for a in ('codex', 'claude', 'workbuddy')}, native_pending=[])

    def validate(self, data, command='enable-memory'):
        return agm.validate_approval(data, command=command,
                                    agents=['codex', 'claude', 'workbuddy'], memory_choice=None)

    def rebuild(self):
        data = self.plan()
        data['rebuild'] = {
            'classification': 'registry_project_corrupt', 'reason': 'damaged project',
            'registry_sha256': 'b' * 64, 'registry_bytes': 1200, 'project_count': 1,
            'removed_projects': [{'main_checkout': '/projects/a', 'record_sha256': 'c' * 64}],
            'removed_shared_objects': [],
            'scope': 'reset all project registrations and shared consumer indexes; preserve machine identity and all user files'}
        data['rebuild_confirmation'] = {'registry_sha256': 'b' * 64,
            'confirmed_at': data['confirmed_at'], 'reference': 'separate rebuild authorization'}
        return data

    def test_enable_accepts_installed_facts_and_native_pending(self):
        data = self.plan(); data['native_pending'] = ['workbuddy']
        self.assertEqual(self.validate(data), data)

    def test_default_effective_subset_and_empty_revocation(self):
        data = self.plan(); data['installation']['claude']['status'] = 'absent'
        data['installation']['workbuddy']['status'] = 'unknown'; data['agents'] = ['codex']
        self.validate(data)
        for fact in data['installation'].values(): fact['status'] = 'absent'
        data['agents'] = []; data['memory_authorization'] = 'no'
        data['memory_transition'] = {'before': 'yes', 'after': 'no',
            'scope': 'all registered project agents', 'affected_agents': ['codex'], 'reused_conflicts': []}
        self.validate(data)
        data.pop('memory_transition')
        with self.assertRaises(agm.CliError): self.validate(data)

    def test_enable_transition_with_reused_conflict(self):
        data = self.plan(); data['memory_authorization'] = 'no'
        data['memory_transition'] = {'before': 'yes', 'after': 'no',
            'scope': 'all registered project agents', 'affected_agents': ['codex'],
            'reused_conflicts': [{'path': '/projects/a/AGENTS.md', 'ownership': 'reused',
                                 'action': 'preserve bytes; explicit denial guard'}]}
        self.validate(data)
        data['memory_transition']['after'] = 'yes'
        with self.assertRaises(agm.CliError): self.validate(data)

    def test_rebuild_requires_independent_exact_hash_binding_and_valid_evidence(self):
        data = self.rebuild(); self.validate(data)
        for field, value in [('registry_sha256', 'd' * 64), ('confirmed_at', '2026-02-30T00:00:00Z'), ('reference', '')]:
            bad = copy.deepcopy(data); bad['rebuild_confirmation'][field] = value
            with self.subTest(field=field), self.assertRaises(agm.CliError): self.validate(bad)
        for field in ('rebuild', 'rebuild_confirmation'):
            bad = copy.deepcopy(data); bad.pop(field)
            with self.subTest(missing=field), self.assertRaises(agm.CliError): self.validate(bad)

    def test_remove_rejects_each_enable_extension_check_rejects_approval(self):
        data = self.rebuild(); data['memory_transition'] = {}
        for field in agm._ENABLE_APPROVAL_FIELDS:
            bad = _approval_data(command='remove-memory', memory_authorization=None)
            bad[field] = data[field]
            with self.subTest(field=field), self.assertRaises(agm.CliError): self.validate(bad, 'remove-memory')
        self.validate(_approval_data(command='remove-memory', memory_authorization=None), 'remove-memory')
        with self.assertRaises(agm.CliError): self.validate(_approval_data(command='check-memory'), 'check-memory')

    def test_unknown_or_malformed_extension_rejected(self):
        mutations = [('unexpected', True), ('installation', {}), ('native_pending', ['codex']),
                     ('memory_transition', {}), ('rebuild', {})]
        for name, value in mutations:
            bad = self.plan(); bad[name] = value
            with self.subTest(name=name), self.assertRaises(agm.CliError): self.validate(bad)
        data = self.plan(); data['installation']['codex']['extra'] = True
        with self.assertRaises(agm.CliError): self.validate(data)

    def test_default_request_preserves_none_for_installed_filter(self):
        ns = agm.build_parser().parse_args(['enable-memory'])
        table = agm.agm_paths.load_agents_table()
        request = agm.build_request('enable-memory', ns, agents=['codex', 'claude', 'workbuddy'],
            approval=None, table=table, platform_key='darwin', platform_config=table['platforms']['darwin'],
            table_path=None, interactive=False, home='/fixture-home')
        self.assertIsNone(request['agents'])
        ns.agent = ['codex']
        request = agm.build_request('enable-memory', ns, agents=['codex'], approval=None, table=table,
            platform_key='darwin', platform_config=table['platforms']['darwin'], table_path=None,
            interactive=False, home='/fixture-home')
        self.assertEqual(request['agents'], ['codex'])
