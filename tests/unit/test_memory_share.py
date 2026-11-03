"""Skill-first memory sharing full chain, synthetic two-agent HOME trees.

Covers the approved disposition review: identical bytes share one public copy
with every source span recorded; format variants keep one copy each; same-name
headings inside one file with different context are never auto-grouped;
original duplicates keep their counts; CK blocks stay untouched; the second
share succeeds positively; public edits/additions and native drift are handled
by explicit Agent return plans over current bytes; hook failure and a real
subprocess crash recover through the existing Transaction.
"""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'scripts'))
from agm_core import paths
from agm_core import memory_share as ms

CODEX_TEXT = (
    '# 约定\n'
    '\n'
    '- 提交信息使用中文。\n'
    '- 修改后运行相关测试。\n'
    '\n'
    '<!-- context-keeper:start -->\n'
    '私有经历，不参与共享。\n'
    '<!-- context-keeper:end -->\n'
    '\n'
    '# 备选\n'
    '\n'
    '- 只走海运。\n'
    '- 提交信息使用中文。\n'
    '\n'
    '# 备选\n'
    '\n'
    '- 只走空运。\n'
    '- 提交信息使用中文。\n'
    '- 提交信息使用中文。\n'
)
CLAUDE_TEXT = (
    '# 约定\n'
    '\n'
    '- 提交信息使用中文。\n'
    '* 修改后运行相关测试。\n'
    '- 表达简洁，先给结论。\n'
)
CK_BLOCK = ('<!-- context-keeper:start -->\n私有经历，不参与共享。\n'
            '<!-- context-keeper:end -->\n')


class MemoryShareChainTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name).resolve() / 'home'
        self.home.mkdir()
        self.config = paths.select_platform(paths.load_agents_table(), 'darwin')
        self.codex = self.home / '.codex' / 'AGENTS.md'
        self.claude = self.home / '.claude' / 'CLAUDE.md'
        self.codex.parent.mkdir(parents=True)
        self.claude.parent.mkdir(parents=True)
        self.codex.write_text(CODEX_TEXT)
        self.claude.write_text(CLAUDE_TEXT)
        self.req = {'home': str(self.home), 'platform_config': self.config,
                    'agents': ['codex', 'claude']}
        self.memories = self.home / '.mem-sharing' / 'memories'
        self.topic = self.memories / 'user-rules.md'

    # ---- helpers ----------------------------------------------------------

    def preview(self, **kw):
        result = ms.plan_share(dict(self.req, **kw))
        self.assertEqual(result['status'], 'completed', result)
        return result

    def proposal(self, groups):
        basis = self.preview()['basis']
        return {'schema_version': 1, 'basis': basis, 'groups': groups}

    def segment(self, preview_result, agent, text):
        matches = [s for s in preview_result['segments']
                   if s['agent'] == agent and s['text'] == text]
        self.assertTrue(matches, 'segment not found: %s %r' % (agent, text))
        return matches

    def plan_for(self, proposal, selection='按默认方案'):
        result = ms.plan_share(dict(self.req, proposal=proposal, selection=selection))
        self.assertIn(result['status'], ('approval_required', 'completed'), result)
        return result

    def approve_and_execute(self, result, hook=None):
        plan = result['approval_plan']
        approval = dict(plan, confirmed_at='2026-11-03T13:10:00Z',
                        reference='synthetic user confirmation')
        outcome = ms.execute_share(plan, approval, request=self.req, hook=hook)
        self.assertEqual(outcome['status'], 'completed', outcome)
        return outcome

    def standard_proposal(self):
        preview = self.preview()
        zh = '- 提交信息使用中文。\n'
        return {'schema_version': 1, 'basis': preview['basis'], 'groups': [
            {'summary': '两家都在 # 约定 下要求中文提交信息', 'same_content': True,
             'items': [{'agent': 'codex', 'start': s['start'], 'end': s['end']}
                       for s in self.segment(preview, 'codex', zh)[:1]]
                   + [{'agent': 'claude', 'start': s['start'], 'end': s['end']}
                      for s in self.segment(preview, 'claude', zh)]},
            {'summary': '两家都要求修改后运行测试（列表符号不同）', 'same_content': True,
             'items': [{'agent': 'codex', 'start': s['start'], 'end': s['end']}
                       for s in self.segment(preview, 'codex', '- 修改后运行相关测试。\n')]
                   + [{'agent': 'claude', 'start': s['start'], 'end': s['end']}
                      for s in self.segment(preview, 'claude', '* 修改后运行相关测试。\n')]},
            {'summary': '两处同名 # 备选 下的中文提交偏好（上下文不同）', 'same_content': True,
             'items': [{'agent': 'codex', 'start': s['start'], 'end': s['end']}
                       for s in self.segment(preview, 'codex', zh)[1:]]},
        ]}

    def first_share(self, selection='共享 3'):
        proposal = self.standard_proposal()
        result = self.plan_for(proposal, selection)
        return self.approve_and_execute(result)

    def migrations(self, manifest_path):
        data = json.loads(Path(manifest_path).read_text())
        return data['operation_metadata']['share_user_memory']['migrations']

    # ---- preview and grouping --------------------------------------------

    def test_preview_reads_full_text_protects_ck_and_unknown_not_empty(self):
        preview = self.preview()
        by_agent = {a: [s['text'] for s in preview['segments'] if s['agent'] == a]
                    for a in ('codex', 'claude')}
        self.assertNotIn('私有经历，不参与共享。\n', by_agent['codex'])
        self.assertEqual(by_agent['codex'].count('- 提交信息使用中文。\n'), 4)
        self.assertEqual(preview['participants'][str(self.codex)]['status'], 'ok')
        self.assertEqual(preview['basis'][str(self.codex)],
                         ms.entries.sha256(self.codex.read_bytes()))
        self.claude.write_bytes(b'\xff')
        broken = self.preview()
        self.assertEqual(broken['participants'][str(self.claude)]['status'], 'unknown')

    def test_blocks_scopes_and_stable_numbers(self):
        result = self.plan_for(self.standard_proposal())
        plan = result['approval_plan']
        self.assertEqual(plan['default_numbers'], [1, 2])
        self.assertEqual(plan['single_numbers'], [3])
        group3 = next(g for g in plan['groups'] if g['number'] == 3)
        self.assertEqual(len(group3['items']), 3)  # 同名两标题 + 原有重复，计数保留
        self.assertEqual([g['number'] for g in plan['groups']], [1, 2, 3])
        # 同文不同作用域（# 约定 vs # 备选）不能合入默认组：单独提案验证
        mixed = self.proposal([{'summary': '跨作用域同文', 'same_content': True,
                                'items': [{'agent': s['agent'], 'start': s['start'], 'end': s['end']}
                                          for s in self.preview()['segments']
                                          if s['text'] == '- 提交信息使用中文。\n']}])
        mixed_plan = self.plan_for(mixed)['approval_plan']
        self.assertEqual(mixed_plan['default_numbers'], [])
        self.assertEqual(mixed_plan['optional_numbers'], [1])

    def test_view_is_zero_write(self):
        before = (self.codex.read_bytes(), self.claude.read_bytes())
        result = ms.plan_share(dict(self.req, proposal=self.standard_proposal(),
                                    selection='查看 1'))
        self.assertEqual(result['status'], 'viewed')
        self.assertEqual(result['view']['sources'][0]['text'], '- 提交信息使用中文。\n')
        self.assertEqual(len(result['view']['sources']), 2)
        self.assertEqual((self.codex.read_bytes(), self.claude.read_bytes()), before)
        self.assertFalse(self.topic.exists())

    # ---- first share: exact bytes, entries, metadata ----------------------

    def test_first_share_exact_bytes_entries_and_metadata(self):
        outcome = self.first_share()
        share = outcome['operation_metadata']['share_user_memory']
        public = self.topic.read_bytes()
        self.assertEqual(public, ('# 用户记忆\n'
                                  '\n'
                                  '- 提交信息使用中文。\n'
                                  '\n- 修改后运行相关测试。\n'
                                  '\n* 修改后运行相关测试。\n'
                                  '\n'
                                  '- 提交信息使用中文。\n').encode())
        # 每处来源→公共段可逐字节回验；同字节一份、格式变体逐份
        records = share['migrations']
        self.assertEqual(len(records), 7)
        topic_after = bytes.fromhex(
            next(c['after_hex'] for c in outcome['changes']
                 if c['path'] == str(self.topic)))
        for record in records:
            raw = bytes.fromhex(record['text_hex'])
            self.assertEqual(topic_after[record['public_offset']:record['public_end']],
                             raw)
        zh_spans = [r for r in records if r['text_hex'] == '- 提交信息使用中文。\n'.encode().hex()]
        self.assertEqual(len(zh_spans), 5)  # codex 4 处 + claude 1 处
        self.assertEqual(len({(r['public_offset'], r['public_end']) for r in zh_spans[:2]}), 1)
        self.assertEqual(share['source_after'][str(self.codex)],
                         ms.entries.sha256(self.codex.read_bytes()))
        # 原生剩余字节：标题、空白、CK、独有逐字节保留 + 新入口
        expected_codex = ('# 约定\n\n\n' + CK_BLOCK +
                          '\n# 备选\n\n- 只走海运。\n\n# 备选\n\n- 只走空运。\n').encode()
        codex_now = self.codex.read_bytes()
        self.assertTrue(codex_now.startswith(expected_codex))
        self.assertIn(ms.ENTRY_MARKER['start'], codex_now)
        self.assertEqual(codex_now.count(ms.ENTRY_MARKER['start']), 1)
        index_abs = str(self.memories / 'MEMORY.md')
        self.assertIn(('开工先读公共记忆：' + index_abs + '。').encode(), codex_now)
        claude_now = self.claude.read_bytes()
        self.assertTrue(claude_now.startswith('# 约定\n\n- 表达简洁，先给结论。\n'.encode()))
        self.assertEqual(sum(1 for line in claude_now.splitlines()
                             if line == ('@' + index_abs).encode()), 1)
        self.assertEqual((self.memories / 'MEMORY.md').read_text(),
                         '# 公共记忆\n\n- 用户记忆：[user-rules.md](user-rules.md)\n')
        self.assertEqual([e['kind'] for e in share['entries_created']],
                         ['memory_index_block', 'at_import'])

    def test_share_manifest_persists_metadata_before_writes(self):
        observed = []
        def inspect(event, path):
            if event == 'before_write' and not observed:
                manifests = list((self.home / '.mem-sharing' / 'backups').glob('*/manifest.json'))
                self.assertEqual(len(manifests), 1)
                data = json.loads(manifests[0].read_text())
                self.assertEqual(data['status'], 'applying')
                self.assertEqual(len(data['operation_metadata']['share_user_memory']['migrations']), 7)
                self.assertFalse(self.topic.exists())
                observed.append(True)
        outcome = self.approve_and_execute(self.plan_for(self.standard_proposal(), '共享 3'),
                                            hook=inspect)
        self.assertEqual(observed, [True])
        data = json.loads(Path(outcome['manifest']).read_text())
        self.assertIn('operation_metadata', data)
        self.assertEqual(data['status'], 'committed')

    # ---- second share must be positively usable ---------------------------

    def test_second_share_succeeds(self):
        self.first_share()
        codex_add = '- 新增依赖前先确认。\n'
        self.codex.write_bytes(self.codex.read_bytes() + codex_add.encode())
        self.claude.write_bytes(self.claude.read_bytes() + codex_add.encode())
        preview = self.preview()
        new_items = [s for s in preview['segments'] if s['text'] == codex_add]
        self.assertEqual(len(new_items), 2)
        proposal = {'schema_version': 1, 'basis': preview['basis'], 'groups': [
            {'summary': '两家新增的依赖确认要求', 'same_content': True,
             'items': [{'agent': s['agent'], 'start': s['start'], 'end': s['end']}
                       for s in new_items]}]}
        result = self.plan_for(proposal, '共享 1')
        plan = result['approval_plan']
        self.assertEqual(plan['default_numbers'], [])  # 作用域不同→待选
        self.approve_and_execute(result)
        self.assertIn(codex_add, self.topic.read_text())
        self.assertNotIn(codex_add, self.codex.read_text())
        self.assertNotIn(codex_add, self.claude.read_text())
        self.assertIn('- 提交信息使用中文。', self.topic.read_text())

    # ---- return over current bytes ---------------------------------------

    def test_return_after_public_edit_addition_and_native_drift(self):
        outcome = self.first_share()
        records = self.migrations(outcome['manifest'])
        edited = '- 提交信息使用中文（含 merge commit）。\n'
        addition = '- 深色主题优先。\n'
        topic_now = self.topic.read_text()
        topic_now = topic_now.replace('- 提交信息使用中文。\n', edited, 1)
        self.topic.write_text(topic_now + addition)
        self.codex.write_bytes(self.codex.read_bytes() + '- 各仓库单独配置。\n'.encode())
        public_bytes = self.topic.read_bytes()
        # 当前 Agent 依据当前正文生成归还计划（这里由测试模拟该判断）
        def span(text):
            start = public_bytes.index(text.encode())
            return {'start': start, 'end': start + len(text.encode()),
                    'text_hex': text.encode().hex()}
        zh_records = [r for r in records if r['text_hex'] == '- 提交信息使用中文。\n'.encode().hex()]
        test_record = next(r for r in records
                           if r['text_hex'] == '- 修改后运行相关测试。\n'.encode().hex())
        star_record = next(r for r in records
                           if r['text_hex'] == '* 修改后运行相关测试。\n'.encode().hex())
        codex_now = self.codex.read_bytes()
        claude_now = self.claude.read_bytes()
        after_codex_rule = codex_now.index('- 各仓库单独配置。\n'.encode()) \
            + len('- 各仓库单独配置。\n'.encode())
        codex_tail = len(codex_now)
        claude_inplace = next(r for r in zh_records if r['agent'] == 'claude')
        items = [
            # 修改后的 G1 回两家：claude 原位（未漂移）、codex 明确插入新独有规则之后
            {'ref': claude_inplace['manifest'] if 'manifest' in claude_inplace
             else Path(outcome['manifest']).parent.name,
             'migration': records.index(claude_inplace),
             'public_span': span(edited),
             'target': {'path': str(self.claude), 'mode': 'in_place'}},
            {'ref': Path(outcome['manifest']).parent.name,
             'migration': records.index(next(r for r in zh_records if r['agent'] == 'codex'
                                             and r['group'] == 1)),
             'public_span': span(edited),
             'target': {'path': str(self.codex), 'mode': 'insert_at',
                        'insert_at': after_codex_rule}},
        ]
        # 备选区剩余两处按明确位置归还（第二个 # 备选 内两处）
        alt_records = [r for r in zh_records if r['agent'] == 'codex' and r['group'] == 3]
        second_alt = self.codex.read_text().index('# 备选', 10)
        anchor = codex_now.index('- 只走空运。\n'.encode()) + len('- 只走空运。\n'.encode())
        first_alt_anchor = codex_now.index('- 只走海运。\n'.encode()) + len('- 只走海运。\n'.encode())
        items += [
            {'ref': Path(outcome['manifest']).parent.name,
             'migration': records.index(alt_records[1]),
             'public_span': span('- 提交信息使用中文。\n'),
             'target': {'path': str(self.codex), 'mode': 'insert_at', 'insert_at': anchor}},
            {'ref': Path(outcome['manifest']).parent.name,
             'migration': records.index(alt_records[2]),
             'public_span': span('- 提交信息使用中文。\n'),
             'target': {'path': str(self.codex), 'mode': 'insert_at', 'insert_at': anchor}},
            {'ref': Path(outcome['manifest']).parent.name,
             'migration': records.index(alt_records[0]),
             'public_span': span('- 提交信息使用中文。\n'),
             'target': {'path': str(self.codex), 'mode': 'insert_at',
                        'insert_at': first_alt_anchor}},
            {'ref': Path(outcome['manifest']).parent.name,
             'migration': records.index(test_record),
             'public_span': span('- 修改后运行相关测试。\n'),
             'target': {'path': str(self.codex), 'mode': 'insert_at',
                        'insert_at': codex_now.index('\n\n' .encode())}},
            {'ref': Path(outcome['manifest']).parent.name,
             'migration': records.index(star_record),
             'public_span': span('* 修改后运行相关测试。\n'),
             'target': {'path': str(self.claude), 'mode': 'in_place'}},
        ]
        agent_plan = {
            'schema_version': 1,
            'basis': {str(self.topic): ms.entries.sha256(public_bytes),
                      str(self.codex): ms.entries.sha256(codex_now),
                      str(self.claude): ms.entries.sha256(claude_now)},
            'items': items,
            'additions': [
                {'start': len(public_bytes) - len(addition.encode()),
                 'end': len(public_bytes), 'text_hex': addition.encode().hex(),
                 'action': 'move', 'target': {'path': str(self.claude),
                                              'insert_at': len(claude_now)}},
                {'start': 0, 'end': len('# 用户记忆\n'.encode()),
                 'text_hex': '# 用户记忆\n'.encode().hex(), 'action': 'keep_public'},
            ],
            'remove_entries': True,
        }
        result = ms.run_return(dict(self.req, return_plan=agent_plan))
        self.assertEqual(result['status'], 'approval_required', result)
        plan = result['approval_plan']
        approval = dict(plan, confirmed_at='2026-11-03T13:12:00Z',
                        reference='synthetic user confirmation')
        done = ms.run_return(dict(self.req, approval=approval,
                                  return_plan=agent_plan))
        self.assertEqual(done['status'], 'completed', done)
        # codex：修改后偏好回两家、备选区 3 处原数恢复、新独有规则保留、入口移除
        codex_final = self.codex.read_bytes()
        self.assertEqual(codex_final.count(edited.encode()), 1)
        self.assertEqual(codex_final.count('- 提交信息使用中文。\n'.encode()), 3)
        self.assertIn('- 各仓库单独配置。\n'.encode(), codex_final)
        self.assertNotIn(ms.ENTRY_MARKER['start'], codex_final)
        self.assertIn(CK_BLOCK.encode(), codex_final)
        self.assertEqual(codex_final.count('- 只走海运。\n'.encode()), 1)
        # claude：修改后偏好 + * 变体 + 独有 + 公共新增目标，@入口移除
        claude_final = self.claude.read_bytes()
        self.assertEqual(claude_final.count(edited.encode()), 1)
        self.assertIn('* 修改后运行相关测试。\n'.encode(), claude_final)
        self.assertIn('- 表达简洁，先给结论。\n'.encode(), claude_final)
        self.assertIn('- 深色主题优先。\n'.encode(), claude_final)
        self.assertNotIn(b'\n@', claude_final)
        self.assertFalse(claude_final.strip().startswith(b'@'))
        # 公共只剩保留项
        self.assertEqual(self.topic.read_bytes(), '# 用户记忆\n\n\n\n\n'.encode())
        # 双重归还被拒；未迁移的独有内容没有归还记录可引用
        agent_plan['basis'] = {str(self.topic): ms.entries.sha256(self.topic.read_bytes())}
        again = ms.run_return(dict(self.req, return_plan=agent_plan))
        self.assertEqual(again['status'], 'failed')
        self.assertIn('已被先前归还消费', again['errors'][0]['message'])

    def test_return_rejects_never_migrated_content(self):
        outcome = self.first_share()
        records = self.migrations(outcome['manifest'])
        bogus = {'schema_version': 1,
                 'basis': {str(self.topic): ms.entries.sha256(self.topic.read_bytes())},
                 'items': [{'ref': Path(outcome['manifest']).parent.name,
                            'migration': len(records),
                            'public_span': {'start': 0, 'end': 5, 'text_hex': '00'},
                            'target': {'path': str(self.claude), 'mode': 'in_place'}}],
                 'additions': []}
        result = ms.run_return(dict(self.req, return_plan=bogus))
        self.assertEqual(result['status'], 'failed')

    def cli_call(self, *args):
        command = [sys.executable, '-B', str(Path(__file__).resolve().parents[2]
                   / 'scripts' / 'memory_share.py'), *args, '--home', str(self.home)]
        done = subprocess.run(command, capture_output=True, text=True)
        return done, json.loads(done.stdout)

    def test_plain_cli_normal_share_and_return_chain(self):
        # No fault hook or crash fixture: public entry point itself must work.
        proposal = self.standard_proposal()
        proposal_file = Path(self.tmp.name) / 'proposal.json'
        approval_file = Path(self.tmp.name) / 'approval.json'
        proposal_file.write_text(json.dumps(proposal))
        done, preview = self.cli_call('share-user-memory', '--agent', 'codex',
                                     '--agent', 'claude', '--proposal-file', str(proposal_file))
        self.assertEqual(done.returncode, 5, done.stdout + done.stderr)
        plan = preview['approval_plan']
        self.assertEqual(plan['selected_numbers'], [1, 2])
        approval_file.write_text(json.dumps(dict(plan, confirmed_at='2026-11-03T13:35:00Z',
                                                reference='synthetic CLI confirmation')))
        done, shared = self.cli_call('share-user-memory', '--approval-file', str(approval_file))
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertEqual(shared['status'], 'completed')
        records = self.migrations(shared['manifest'])
        current = self.topic.read_bytes()
        agent_plan = {'schema_version': 1,
                      'basis': {str(self.topic): ms.entries.sha256(current)},
                      'items': [{'ref': Path(shared['manifest']).parent.name,
                                 'migration': i,
                                 'public_span': {'start': r['public_offset'], 'end': r['public_end'],
                                                 'text_hex': r['text_hex']},
                                 'target': {'path': r['path'], 'mode': 'in_place'}}
                                for i, r in enumerate(records)],
                      'remove_entries': True}
        return_file = Path(self.tmp.name) / 'return.json'
        return_file.write_text(json.dumps(agent_plan))
        done, preview = self.cli_call('return-user-memory', '--agent', 'codex', '--agent', 'claude',
                                     '--return-plan-file', str(return_file))
        self.assertEqual(done.returncode, 5, done.stdout + done.stderr)
        approval_file.write_text(json.dumps(dict(preview['approval_plan'],
            confirmed_at='2026-11-03T13:35:10Z', reference='synthetic CLI return confirmation')))
        done, returned = self.cli_call('return-user-memory', '--return-plan-file', str(return_file),
                                       '--approval-file', str(approval_file))
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertEqual(returned['status'], 'completed')
        # Only added entry separators remain; all original bytes/counts/CK retained.
        self.assertEqual(self.codex.read_bytes(), CODEX_TEXT.encode() + b'\n')
        self.assertEqual(self.claude.read_bytes(), CLAUDE_TEXT.encode() + b'\n')
        self.assertEqual(self.topic.read_bytes(), '# 用户记忆\n\n\n\n'.encode())

    def test_unrelated_claude_imports_survive_share_and_return_exactly(self):
        unrelated = b'@/other/rules.md\n@relative/private.md\n'
        self.claude.write_bytes(unrelated + CLAUDE_TEXT.encode())
        proposal = self.standard_proposal()
        result = self.plan_for(proposal)  # G3 remains native, never migrated.
        outcome = self.approve_and_execute(result)
        records = self.migrations(outcome['manifest'])
        self.assertNotIn(3, {r['group'] for r in records})
        self.assertEqual(self.claude.read_bytes(), unrelated +
                         '# 约定\n\n- 表达简洁，先给结论。\n\n'.encode() +
                         ms._entry_bytes('claude', ms._runtime(self.req)))
        public = self.topic.read_bytes()
        rp = {'schema_version': 1, 'basis': {str(self.topic): ms.entries.sha256(public)},
              'items': [{'ref': Path(outcome['manifest']).parent.name, 'migration': i,
                         'public_span': {'start': r['public_offset'], 'end': r['public_end'],
                                         'text_hex': r['text_hex']},
                         'target': {'path': r['path'], 'mode': 'in_place'}}
                        for i, r in enumerate(records)], 'remove_entries': True}
        preview = ms.run_return(dict(self.req, return_plan=rp))
        self.assertEqual(preview['status'], 'approval_required', preview)
        approved = dict(preview['approval_plan'], confirmed_at='2026-11-03T13:36:00Z',
                        reference='synthetic exact bytes return')
        result = ms.run_return(dict(self.req, return_plan=rp, approval=approved))
        self.assertEqual(result['status'], 'completed', result)
        self.assertEqual(self.claude.read_bytes(), unrelated + CLAUDE_TEXT.encode() + b'\n')
        self.assertEqual(self.codex.read_bytes(), CODEX_TEXT.encode() + b'\n')

    def test_wrong_targets_are_not_connected(self):
        runtime = ms._runtime(self.req)
        self.assertEqual(ms._entry_state('claude', b'@/wrong/MEMORY.md\n', runtime), 0)
        bad = ms._entry_bytes('codex', runtime).replace(str(self.home).encode(), b'/wrong')
        self.codex.write_bytes(CODEX_TEXT.encode() + bad)
        result = ms.plan_share(self.req)
        self.assertEqual(result['status'], 'failed', result)
        self.assertEqual(result['errors'][0]['code'], 'entry_conflict')
        self.assertFalse(self.topic.exists())

    def test_default_exclusion_and_decline_are_zero_write(self):
        proposal = self.standard_proposal()
        result = self.plan_for(proposal, '按默认方案')
        self.assertEqual(result['approval_plan']['selected_numbers'], [1, 2])
        result = self.plan_for(proposal, '共享 3，不共享 2')
        self.assertEqual(result['approval_plan']['selected_numbers'], [1, 3])
        result = self.plan_for(proposal, '暂不整理')
        self.assertEqual(result['approval_plan']['changes'], [])
        self.assertFalse(self.topic.exists())

    def test_partial_return_keeps_shared_copy_until_last_alias(self):
        outcome = self.first_share(selection='不共享 2')
        records = self.migrations(outcome['manifest'])
        self.assertEqual(len(records), 2)
        original_public = self.topic.read_bytes()
        ref = Path(outcome['manifest']).parent.name
        def proposal(index, mode='in_place'):
            r = records[index]
            current = self.topic.read_bytes()
            start = current.index(bytes.fromhex(r['text_hex']))
            return {'schema_version': 1, 'basis': {str(self.topic): ms.entries.sha256(current)},
                    'items': [{'ref': ref, 'migration': index,
                               'public_span': {'start': start, 'end': start + len(bytes.fromhex(r['text_hex'])),
                                               'text_hex': r['text_hex']},
                               'target': {'path': r['path'], 'mode': mode}}]}
        def apply(rp):
            preview = ms.run_return(dict(self.req, return_plan=rp))
            self.assertEqual(preview['status'], 'approval_required', preview)
            done = ms.run_return(dict(self.req, return_plan=rp,
                approval=dict(preview['approval_plan'], confirmed_at='2026-11-03T13:39:00Z',
                              reference='synthetic partial return')))
            self.assertEqual(done['status'], 'completed', done)
        apply(proposal(0))
        self.assertEqual(self.topic.read_bytes(), original_public)
        self.assertTrue(ms._entry_ok('claude', self.claude.read_bytes(), ms._runtime(self.req)))
        apply(proposal(1))
        self.assertEqual(self.topic.read_bytes(), '# 用户记忆\n\n'.encode())
        consumed = ms._consumed_index(ms._runtime(self.req))
        self.assertEqual(consumed, {(ref, 0), (ref, 1)})

    def test_unplanned_public_addition_blocks_entry_removal(self):
        outcome = self.first_share(selection='不共享 2')
        self.topic.write_bytes(self.topic.read_bytes() + '- 新增仍须读取。\n'.encode())
        records = self.migrations(outcome['manifest'])
        rp = {'schema_version': 1, 'basis': {str(self.topic): ms.entries.sha256(self.topic.read_bytes())},
              'items': [{'ref': Path(outcome['manifest']).parent.name, 'migration': i,
                         'public_span': {'start': r['public_offset'], 'end': r['public_end'],
                                         'text_hex': r['text_hex']},
                         'target': {'path': r['path'], 'mode': 'in_place'}}
                        for i, r in enumerate(records)], 'remove_entries': True}
        before = (self.topic.read_bytes(), self.codex.read_bytes(), self.claude.read_bytes())
        result = ms.run_return(dict(self.req, return_plan=rp))
        self.assertEqual(result['status'], 'failed', result)
        self.assertIn('新增内容', result['errors'][0]['message'])
        self.assertEqual((self.topic.read_bytes(), self.codex.read_bytes(), self.claude.read_bytes()), before)

    # ---- failure handling -------------------------------------------------

    def test_hook_failure_rolls_back_everything(self):
        before = (self.codex.read_bytes(), self.claude.read_bytes())
        proposal = self.standard_proposal()
        result = self.plan_for(proposal, '共享 3')
        seen = []

        def fault(event, path):
            if event == 'after_write':
                seen.append(path)
                if len(seen) == 5:
                    raise ms.TransactionError('synthetic failure mid-chain')
        outcome = ms.execute_share(result['approval_plan'],
                                   dict(result['approval_plan'],
                                        confirmed_at='2026-11-03T13:14:00Z',
                                        reference='synthetic user confirmation'),
                                   request=self.req, hook=fault)
        self.assertEqual(outcome['status'], 'failed', outcome)
        self.assertEqual(outcome['errors'][0]['code'], 'transaction_failed')
        self.assertTrue(outcome['errors'][0]['manifest'])
        self.assertEqual((self.codex.read_bytes(), self.claude.read_bytes()), before)
        self.assertFalse(self.topic.exists())

    def test_real_subprocess_crash_recovers_after_stale_lock_inspection(self):
        import tempfile as tf
        approval_dir = Path(tf.mkdtemp())
        self.addCleanup(lambda: (approval_file.unlink(missing_ok=True),
                                 approval_dir.rmdir()))
        proposal = self.standard_proposal()
        result = self.plan_for(proposal, '共享 3')
        approval_file = approval_dir / 'approval.json'
        approval_file.write_text(json.dumps(
            dict(result['approval_plan'], confirmed_at='2026-11-03T13:15:00Z',
                 reference='synthetic user confirmation'), ensure_ascii=False))
        fixture = Path(__file__).with_name('memory_share_crash_fixture.py')
        crash = subprocess.run(
            [sys.executable, '-B', str(fixture), str(approval_file)],
            capture_output=True, text=True)
        self.assertEqual(crash.returncode, 70, crash.stderr)
        manifests = list((self.home / '.mem-sharing' / 'backups').glob('*/manifest.json'))
        self.assertEqual(len(manifests), 1)
        data = json.loads(manifests[0].read_text())
        self.assertIn(data['status'], ('applying', 'prepared'))
        self.assertIn('operation_metadata', data)
        self.assertTrue(self.topic.exists())  # 已写公共，未删源
        self.assertIn('- 提交信息使用中文。', self.codex.read_text())
        tx_lock = self.home / '.mem-sharing' / 'var' / '.agm.lock' / 'transaction'
        self.assertTrue(tx_lock.exists())
        # 恢复先撞锁（不自动清锁），操作员检查后移除陈旧锁，再按批准回滚
        preview = ms.run_recover({'home': str(self.home), 'platform_config': self.config,
                                  'manifest': str(manifests[0])})
        self.assertEqual(preview['status'], 'approval_required', preview)
        recovery = ms.run_recover({'home': str(self.home), 'platform_config': self.config,
                                   'manifest': str(manifests[0]),
                                   'approval': {**preview['approval_plan'],
                                                'confirmed_at': '2026-11-03T13:16:00Z',
                                                'reference': 'operator inspected stale lock'}})
        self.assertEqual(recovery['status'], 'recovery_required', recovery)
        self.assertEqual(recovery['errors'][0]['code'], 'lock_conflict')
        tx_lock.rmdir()
        tx_lock.parent.rmdir()
        recovery = ms.run_recover({'home': str(self.home), 'platform_config': self.config,
                                   'manifest': str(manifests[0]),
                                   'approval': {**preview['approval_plan'],
                                                'confirmed_at': '2026-11-03T13:16:30Z',
                                                'reference': 'operator inspected stale lock'}})
        self.assertEqual(recovery['status'], 'completed', recovery)
        self.assertEqual(recovery['recovery_status'], 'rolled_back')
        self.assertEqual(self.codex.read_text(), CODEX_TEXT)
        self.assertEqual(self.claude.read_text(), CLAUDE_TEXT)
        self.assertFalse(self.topic.exists())


if __name__ == '__main__':
    unittest.main()
