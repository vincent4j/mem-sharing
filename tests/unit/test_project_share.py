"""Project memory mainline on synthetic Git main checkouts.

Contracts locked here (per 2026-11-03 re-review): participation counts every
independent file including AGENTS (only-latter-files same content is optional,
never default); in_agents dedup requires byte-identical AGENTS occurrence under
the same immediate heading, format variants each keep a complete public copy;
pure dedup executes with AGENTS unchanged; real phase order is public AGENTS ->
all necessary entries individually verified -> precise source deletion, with
timing assertions at the first deletion; unregistered-but-valid registries are
allowed while corrupt/unknown ones fail closed.
"""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'scripts'))
from agm_core import project_share as ps

ZH = '- 提交信息使用中文。\n'
TESTS = '- 修改后运行相关测试。\n'
AGENTS_TEXT = ('# 约定\n\n' + ZH + '\n# 其他\n\n- 仅用标准库。\n')
CLAUDE_TEXT = '# 约定\n\n' + ZH + TESTS + '- 表达简洁，先给结论。\n'
WB_TEXT = '# 约定\n\n' + ZH + TESTS + '- 只走海运。\n'


def git(repo, *args):
    done = subprocess.run(['git', '-C', str(repo), *args], capture_output=True,
                          text=True)
    assert done.returncode == 0, done.stderr
    return done.stdout


class ProjectShareTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name).resolve() / 'home'
        self.home.mkdir()
        self.repo = Path(self.tmp.name).resolve() / 'repo'
        self.repo.mkdir()
        git(self.repo, 'init')
        git(self.repo, 'config', 'user.email', 't@t')
        git(self.repo, 'config', 'user.name', 't')
        self.agents = self.repo / 'AGENTS.md'
        self.claude = self.repo / 'CLAUDE.md'
        self.wb = self.repo / '.workbuddy' / 'memory' / 'MEMORY.md'
        self.wb.parent.mkdir(parents=True)
        for path, text in ((self.agents, AGENTS_TEXT), (self.claude, CLAUDE_TEXT),
                           (self.wb, WB_TEXT)):
            path.write_text(text)
        git(self.repo, 'add', '-A')
        git(self.repo, 'commit', '-m', 'init')
        self.req = {'home': str(self.home), 'project': str(self.repo)}
        self.originals = {p: p.read_bytes() for p in (self.agents, self.claude, self.wb)}

    def cli(self, *args):
        done = subprocess.run([sys.executable, '-B',
                               str(Path(__file__).resolve().parents[2]
                                   / 'scripts' / 'memory_share.py'), *args],
                              capture_output=True, text=True)
        return done, json.loads(done.stdout or 'null')

    def preview(self):
        result = ps.plan_share(dict(self.req))
        self.assertEqual(result['status'], 'completed', result)
        return result

    def proposal(self):
        preview = self.preview()
        def seg(name, text):
            match = [s for s in preview['segments']
                     if s['source'] == name and s['text'] == text]
            self.assertTrue(match, (name, text))
            return match[0]
        return {'schema_version': 1, 'basis': preview['basis'], 'groups': [
            {'summary': 'AGENTS 已有中文提交要求，默认整理重复', 'same_content': True,
             'items': [{'file': f, 'start': seg(f, ZH)['start'], 'end': seg(f, ZH)['end']}
                       for f in ('claude', 'workbuddy')]},
            {'summary': '两份独立文件都要求修改后运行测试', 'same_content': True,
             'items': [{'file': f, 'start': seg(f, TESTS)['start'], 'end': seg(f, TESTS)['end']}
                       for f in ('claude', 'workbuddy')]},
            {'summary': '仅 CLAUDE 的简洁要求', 'same_content': True,
             'items': [{'file': 'claude', 'start': seg('claude', '- 表达简洁，先给结论。\n')['start'],
                        'end': seg('claude', '- 表达简洁，先给结论。\n')['end']}]},
        ]}

    def do_share(self, hook=None, selection='共享 1、2', proposal=None):
        result = ps.plan_share(dict(self.req, proposal=proposal or self.proposal(),
                                    selection=selection))
        self.assertEqual(result['status'], 'approval_required', result)
        plan = result['approval_plan']
        return ps.execute_share(plan, dict(plan, confirmed_at='2026-11-03T15:10:00Z',
                                           reference='synthetic project confirmation'),
                                request=self.req, hook=hook)

    def migrations(self, manifest):
        data = json.loads(Path(manifest).read_text())
        return data['operation_metadata']['project_share_memory']['migrations']

    def return_plan(self, shared, remove_entries=True):
        records = self.migrations(shared['manifest'])
        agents_bytes = self.agents.read_bytes()

        def span_of(record):
            if record['in_agents']:
                start = agents_bytes.index(bytes.fromhex(record['text_hex']))
                end = start + len(bytes.fromhex(record['text_hex']))
            else:
                start, end = record['public_offset'], record['public_end']
            return {'start': start, 'end': end,
                    'text_hex': agents_bytes[start:end].hex()}
        return {'schema_version': 1,
                'basis': {str(self.agents): ps.entries.sha256(agents_bytes)},
                'items': [{'ref': Path(shared['manifest']).parent.name,
                           'migration': i, 'public_span': span_of(r),
                           'target': {'path': r['path'], 'mode': 'in_place'}}
                          for i, r in enumerate(records)],
                'remove_entries': remove_entries}

    # ---- share chain -------------------------------------------------------

    def test_cli_share_blocks_dedup_default_and_optional_coverage(self):
        proposal_file = Path(self.tmp.name) / 'p.json'
        approval_file = Path(self.tmp.name) / 'a.json'
        proposal_file.write_text(json.dumps(self.proposal(), ensure_ascii=False))
        done, preview = self.cli('share-project-memory', '--project', str(self.repo),
                                 '--home', str(self.home),
                                 '--proposal-file', str(proposal_file),
                                 '--selection', '共享 1、2')
        self.assertEqual(done.returncode, 5, done.stdout + done.stderr)
        plan = preview['approval_plan']
        # 参与集合含 AGENTS 共三份独立文件：仅后两家同文的组是待选，不是默认。
        self.assertEqual(plan['default_numbers'], [1])
        self.assertEqual(plan['optional_numbers'], [2])
        self.assertEqual(plan['selected_numbers'], [1, 2])
        self.assertIn(1, plan['in_agents_numbers'])
        self.assertNotIn(2, plan['in_agents_numbers'])
        approval_file.write_text(json.dumps(dict(
            plan, confirmed_at='2026-11-03T15:11:00Z',
            reference='synthetic CLI project confirmation'), ensure_ascii=False))
        done, shared = self.cli('share-project-memory', '--project', str(self.repo),
                                '--home', str(self.home), '--approval-file',
                                str(approval_file))
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        records = self.migrations(shared['manifest'])
        # AGENTS 原字节保全：dedup 组不写 AGENTS；新共享组完整原文追加一次。
        self.assertEqual(self.agents.read_bytes(),
                         AGENTS_TEXT.encode() + b'\n' + TESTS.encode())
        self.assertEqual(len(records), 4)
        self.assertEqual(sum(1 for r in records if r['in_agents']), 2)
        for record in records:
            if record['in_agents']:
                span = record['agents_span']
                self.assertEqual(self.agents.read_bytes()[span['start']:span['end']],
                                 bytes.fromhex(record['text_hex']))
        # 删源前已建立并核验必要项目入口；迁空桥保留文件与入口。
        self.assertEqual(self.claude.read_bytes(),
                         '# 约定\n\n- 表达简洁，先给结论。\n\n@AGENTS.md\n'.encode())
        self.assertEqual(self.wb.read_bytes(),
                         ('# 约定\n\n- 只走海运。\n\n').encode() + ps.WORKBUDDY_BLOCK)
        return shared

    def test_cli_full_return_restores_bytes_and_strips_entries(self):
        shared = self.do_share()
        agent_plan = self.return_plan(shared)
        return_file = Path(self.tmp.name) / 'return.json'
        return_file.write_text(json.dumps(agent_plan, ensure_ascii=False))
        done, preview = self.cli('return-project-memory', '--project', str(self.repo),
                                 '--home', str(self.home), '--return-plan-file',
                                 str(return_file))
        self.assertEqual(done.returncode, 5, done.stdout + done.stderr)
        approval_file = Path(self.tmp.name) / 'ra.json'
        approval_file.write_text(json.dumps(dict(
            preview['approval_plan'], confirmed_at='2026-11-03T15:12:00Z',
            reference='synthetic CLI project return'), ensure_ascii=False))
        done, returned = self.cli('return-project-memory', '--project', str(self.repo),
                                  '--home', str(self.home), '--return-plan-file',
                                  str(return_file), '--approval-file', str(approval_file))
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertEqual(returned['status'], 'completed', returned)
        # AGENTS 既有公共项原样保留，仅新增段归还；原文逐字节回到各文件。
        self.assertEqual(self.agents.read_bytes(), AGENTS_TEXT.encode() + b'\n')
        self.assertEqual(self.claude.read_bytes(), CLAUDE_TEXT.encode() + b'\n')
        self.assertEqual(self.wb.read_bytes(), WB_TEXT.encode() + b'\n')

    # ---- review corrections ------------------------------------------------

    def test_pure_dedup_executes_without_agents_change(self):
        proposal = self.proposal()
        proposal['groups'] = proposal['groups'][:1]
        result = ps.plan_share(dict(self.req, proposal=proposal,
                                    selection='按默认方案'))
        self.assertEqual(result['status'], 'approval_required', result)
        plan = result['approval_plan']
        self.assertNotIn(str(self.agents), {c['path'] for c in plan['changes']})
        outcome = ps.execute_share(
            plan, dict(plan, confirmed_at='2026-11-03T15:13:00Z',
                       reference='synthetic pure dedup'),
            request=self.req)
        self.assertEqual(outcome['status'], 'completed', outcome)
        self.assertEqual(self.agents.read_bytes(), self.originals[self.agents])
        self.assertIn(b'@AGENTS.md\n', self.claude.read_bytes())
        self.assertIn(ps.WORKBUDDY_BLOCK, self.wb.read_bytes())
        # 归还同样可在纯去重现场闭环。
        agent_plan = self.return_plan(outcome, remove_entries=True)
        preview = ps.run_return(dict(self.req, return_plan=agent_plan))
        self.assertEqual(preview['status'], 'approval_required', preview)
        result = ps.run_return(dict(self.req, return_plan=agent_plan,
                                    approval=dict(preview['approval_plan'],
                                                  confirmed_at='2026-11-03T15:13:30Z',
                                                  reference='synthetic pure dedup return')))
        self.assertEqual(result['status'], 'completed', result)
        self.assertEqual(self.claude.read_bytes(), CLAUDE_TEXT.encode() + b'\n')
        self.assertEqual(self.wb.read_bytes(), WB_TEXT.encode() + b'\n')

    def test_parent_scope_difference_is_not_automatched(self):
        # 复验复现件：父级作用域不同、仅末级标题同名，不得复用 AGENTS 公共。
        self.agents.write_bytes(('# 生产环境\n## 约定\n\n' + ZH).encode())
        self.claude.write_bytes(('# 测试环境\n## 约定\n\n' + ZH + TESTS
                                 + '- 表达简洁，先给结论。\n').encode())
        self.wb.write_bytes(('# 测试环境\n## 约定\n\n' + ZH + TESTS
                             + '- 只走海运。\n').encode())
        git(self.repo, 'add', '-A')
        git(self.repo, 'commit', '-m', 'parent scope')
        result = ps.plan_share(dict(self.req, proposal=self.proposal(),
                                    selection='按默认方案'))
        plan = result['approval_plan']
        self.assertEqual(plan['default_numbers'], [])
        self.assertEqual(plan['optional_numbers'], [1, 2])
        self.assertEqual(plan['in_agents_numbers'], [])

    def plan_for_files(self, agents_text, claude_text, wb_text):
        """按给定正文重建三文件并生成单组提案（claude+workbuddy 各一处 ZH）。"""
        self.agents.write_text(agents_text)
        self.claude.write_text(claude_text)
        self.wb.write_text(wb_text)
        git(self.repo, 'add', '-A')
        git(self.repo, 'commit', '-m', 'fixture')
        preview = self.preview()
        def seg(name, text):
            match = [x for x in preview['segments']
                     if x['source'] == name and x['text'] == text]
            self.assertTrue(match, (name, text))
            return match[0]
        proposal = {'schema_version': 1, 'basis': preview['basis'], 'groups': [
            {'summary': '同文中文提交要求', 'same_content': True,
             'items': [{'file': f, 'start': seg(f, ZH)['start'],
                        'end': seg(f, ZH)['end']}
                       for f in ('claude', 'workbuddy')]}]}
        return ps.plan_share(dict(self.req, proposal=proposal,
                                  selection='按默认方案'))

    def test_heading_level_order_swap_is_not_automatched(self):
        # 层级换位反例：'# A/## B' 栈为 [(1,A),(2,B)]；'## A/# B' 栈为 [(1,B)]。
        result = self.plan_for_files(
            '# A\n\n## B\n\n' + ZH,
            '## A\n\n# B\n\n' + ZH + '- 表达简洁，先给结论。\n',
            '## A\n\n# B\n\n' + ZH + '- 只走海运。\n')
        plan = result['approval_plan']
        self.assertEqual(plan['default_numbers'], [])
        self.assertEqual(plan['in_agents_numbers'], [])
        self.assertEqual(plan['optional_numbers'], [1])

    def test_sibling_heading_reset_matches_but_parent_difference_does_not(self):
        # 正例：历史同级兄弟标题不污染，'# 历史/# 约定' 与 '# 约定' 栈同为 [(1,约定)]。
        result = self.plan_for_files(
            '# 历史\n\n# 约定\n\n' + ZH,
            '# 约定\n\n' + ZH + '- 表达简洁，先给结论。\n',
            '# 约定\n\n' + ZH + '- 只走海运。\n')
        self.assertEqual(result['approval_plan']['default_numbers'], [1])
        self.assertEqual(result['approval_plan']['in_agents_numbers'], [1])
        # 父级不同仍不匹配：'# C/## 约定' 栈为 [(1,C),(2,约定)]。
        result = self.plan_for_files(
            '# C\n\n## 约定\n\n' + ZH,
            '# 约定\n\n' + ZH + '- 表达简洁，先给结论。\n',
            '# 约定\n\n' + ZH + '- 只走海运。\n')
        self.assertEqual(result['approval_plan']['default_numbers'], [])
        self.assertEqual(result['approval_plan']['in_agents_numbers'], [])

    def test_duplicate_stack_and_bytes_refuse_auto_reuse(self):
        # AGENTS 同文同栈两处出现：不可 next 盲猜位置，拒绝自动复用。
        result = self.plan_for_files(
            '# 约定\n\n' + ZH + '\n\n# 约定\n\n' + ZH,
            '# 约定\n\n' + ZH + '- 表达简洁，先给结论。\n',
            '# 约定\n\n' + ZH + '- 只走海运。\n')
        plan = result['approval_plan']
        self.assertEqual(plan['in_agents_numbers'], [])
        self.assertEqual(plan['default_numbers'], [])

    def test_fenced_headings_do_not_pollute_scope_stack(self):
        # 围栏内 '# 假' 不是真实标题，不进入有效栈，正反两侧一致仍可去重。
        fake = '```\n# 假标题\n```\n\n'
        result = self.plan_for_files(
            fake + '# 约定\n\n' + ZH,
            fake + '# 约定\n\n' + ZH + '- 表达简洁，先给结论。\n',
            '# 约定\n\n' + ZH + '- 只走海运。\n')
        self.assertEqual(result['approval_plan']['in_agents_numbers'], [1])

    def test_registry_null_record_and_dangling_symlink_fail_closed(self):
        registry = self.home / '.mem-sharing' / 'var' / 'registry.json'
        registry.parent.mkdir(parents=True)
        registry.write_text(json.dumps(
            {'schema_version': 3, 'projects': {str(self.repo): None}}))
        result = ps.plan_share(dict(self.req))
        self.assertEqual(result['status'], 'failed', result)
        self.assertEqual(result['errors'][0]['code'], 'disabled_unknown')
        registry.unlink()
        registry.symlink_to(str(Path(self.tmp.name) / 'no-such-registry'))
        self.assertFalse(registry.exists())  # 悬空 symlink 不能当缺失放行
        result = ps.plan_share(dict(self.req))
        self.assertEqual(result['errors'][0]['code'], 'disabled_unknown')
        registry.unlink()

    def test_heading_stack_fence_length_and_indentation(self):
        # 开栏 4 反引号：内部 3 反引号不关闭，仅同字符且长度>=开栏才关闭。
        four = ('````\n# 假标题\n```\n仍假\n````\n\n# 约定\n\nx\n').encode()
        self.assertEqual(ps._heading_stack(four, four.index(b'x\n'), []),
                         [(1, '约定')])
        # 4 空格缩进的 "# 标题" 是缩进代码，不是真实标题。
        indent = ('    # 缩进假\n\n# 约定\n\nx\n').encode()
        self.assertEqual(ps._heading_stack(indent, indent.index(b'x\n'), []),
                         [(1, '约定')])
        mixed = ('# A\n## B\n    # 假\nx\n').encode()
        self.assertEqual(ps._heading_stack(mixed, mixed.index(b'x\n'), []),
                         [(1, 'A'), (2, 'B')])

    def test_language_fences_and_trailing_whitespace_closing(self):
        # 常见带语言开栏（```python、~~~ts）必须识别；关闭允许尾部空白。
        py = ('# Real\n```python\n# Fake\n```\nrule\n').encode()
        self.assertEqual(ps._heading_stack(py, py.index(b'rule\n'), []),
                         [(1, 'Real')])
        ts = ('# Real\n~~~ts\n# Fake\n~~~   \nrule\n').encode()
        self.assertEqual(ps._heading_stack(ts, ts.index(b'rule\n'), []),
                         [(1, 'Real')])
        after = ('```python\n# Fake\n```  \n# After\nrule\n').encode()
        self.assertEqual(ps._heading_stack(after, after.index(b'rule\n'), []),
                         [(1, 'After')])

    def test_plan_scope_with_language_fence_keeps_dedup(self):
        lang = '```python\n# 假标题\n```\n\n'
        result = self.plan_for_files(
            lang + '# 约定\n\n' + ZH,
            lang + '# 约定\n\n' + ZH + '- 表达简洁，先给结论。\n',
            '# 约定\n\n' + ZH + '- 只走海运。\n')
        self.assertEqual(result['approval_plan']['in_agents_numbers'], [1])

    def test_plan_scope_with_long_fence_and_indented_fake_headings(self):
        # 计划级：4 反引号围栏内假标题与缩进代码假标题都不污染有效栈。
        # （围栏内再嵌 3 反引号的病态源由冻结分段器整体拒绝，函数级已覆盖栈语义。）
        fence4 = '````\n# 假标题\n仍假\n````\n\n'
        indent_fake = '    # 缩进假\n\n'
        result = self.plan_for_files(
            fence4 + '# 约定\n\n' + ZH,
            fence4 + '# 约定\n\n' + ZH + '- 表达简洁，先给结论。\n',
            indent_fake + '# 约定\n\n' + ZH + '- 只走海运。\n')
        self.assertEqual(result['approval_plan']['in_agents_numbers'], [1])

    def test_same_text_different_scope_is_not_automatched(self):
        self.agents.write_bytes(('# 项目规则\n\n' + ZH).encode())
        git(self.repo, 'add', '-A')
        git(self.repo, 'commit', '-m', 'scope change')
        result = ps.plan_share(dict(self.req, proposal=self.proposal(),
                                    selection='按默认方案'))
        plan = result['approval_plan']
        # AGENTS 出现在 # 项目规则 下，与 # 约定 语境不同：不得自动认定去重。
        self.assertEqual(plan['default_numbers'], [])
        self.assertEqual(plan['optional_numbers'], [1, 2])
        self.assertEqual(plan['in_agents_numbers'], [])

    def test_format_variants_each_keep_complete_public_copy(self):
        variant = '* 提交信息使用中文。\n'
        self.claude.write_text('# 约定\n\n' + variant + TESTS + '- 表达简洁，先给结论。\n')
        git(self.repo, 'add', '-A')
        git(self.repo, 'commit', '-m', 'variant')
        preview = self.preview()
        def seg(name, text):
            match = [s for s in preview['segments']
                     if s['source'] == name and s['text'] == text]
            self.assertTrue(match, (name, text))
            return match[0]
        proposal = {'schema_version': 1, 'basis': preview['basis'], 'groups': [
            {'summary': '同义但格式不同的中文提交要求', 'same_content': True,
             'items': [{'file': 'claude', 'start': seg('claude', variant)['start'],
                        'end': seg('claude', variant)['end']},
                       {'file': 'workbuddy', 'start': seg('workbuddy', ZH)['start'],
                        'end': seg('workbuddy', ZH)['end']}]},
            {'summary': '两份独立文件都要求修改后运行测试', 'same_content': True,
             'items': [{'file': f, 'start': seg(f, TESTS)['start'],
                        'end': seg(f, TESTS)['end']}
                       for f in ('claude', 'workbuddy')]}]}
        result = ps.plan_share(dict(self.req, proposal=proposal, selection='共享 1、2'))
        plan = result['approval_plan']
        self.assertEqual(plan['in_agents_numbers'], [])  # 变体组整体不再算既有公共
        outcome = ps.execute_share(
            plan, dict(plan, confirmed_at='2026-11-03T15:14:00Z',
                       reference='synthetic variant confirmation'), request=self.req)
        self.assertEqual(outcome['status'], 'completed', outcome)
        records = self.migrations(outcome['manifest'])
        public = self.agents.read_bytes()
        # 变体逐份完整进入公共：'-' 与 '*' 各有自己的完整字节与来源关系。
        self.assertEqual(public.count(ZH.encode()), 1)
        self.assertIn(variant.encode(), public)
        variant_records = [r for r in records if r['text_hex'] == variant.encode().hex()]
        self.assertEqual(len(variant_records), 1)
        self.assertNotIn(variant.encode(), self.claude.read_bytes())

    def test_exclusion_requires_explicit_bound_destination(self):
        preview = self.preview()
        proposal = self.proposal()
        span = next(s for s in preview['segments'] if s['text'] == '- 仅用标准库。\n')
        proposal['exclusions'] = [{'start': span['start'], 'end': span['end'],
                                   'text_hex': self.agents.read_bytes()[
                                       span['start']:span['end']].hex()}]
        result = ps.plan_share(dict(self.req, proposal=proposal))
        self.assertEqual(result['status'], 'failed', result)
        self.assertEqual(result['errors'][0]['code'], 'invalid_exclusion')
        proposal['exclusions'][0]['target'] = {'path': str(self.claude), 'insert_at': 0}
        result = ps.plan_share(dict(self.req, proposal=proposal))
        self.assertEqual(result['status'], 'approval_required', result)

    def test_registry_states_distinguished(self):
        registry = self.home / '.mem-sharing' / 'var' / 'registry.json'
        registry.parent.mkdir(parents=True)
        main = str(self.repo)
        # 合法台账但本项目未登记：放行。
        registry.write_text(json.dumps(
            {'schema_version': 3, 'projects': {'/other/repo': {'memory_policy': 'follow_ck'}}}))
        result = ps.plan_share(dict(self.req))
        self.assertEqual(result['status'], 'completed', result)
        # disabled：拒绝。
        registry.write_text(json.dumps(
            {'schema_version': 3, 'projects': {main: {'memory_policy': 'disabled'}}}))
        result = ps.plan_share(dict(self.req))
        self.assertEqual(result['errors'][0]['code'], 'project_disabled')
        # 损坏 JSON / 结构破坏 / 登记值未知：fail closed，不当成未登记。
        for body in ('{corrupt json',
                     json.dumps({'schema_version': 3, 'projects': []}),
                     json.dumps({'schema_version': 3, 'projects': {main: 'broken'}}),
                     json.dumps({'schema_version': 3, 'projects': {main: {'memory_policy': 'weird'}}})):
            registry.write_text(body)
            result = ps.plan_share(dict(self.req))
            self.assertEqual(result['errors'][0]['code'], 'disabled_unknown', body)
        registry.write_text(json.dumps(
            {'schema_version': 3, 'projects': {main: {'memory_policy': 'follow_ck'}}}))
        result = ps.plan_share(dict(self.req))
        self.assertEqual(result['status'], 'completed', result)

    def test_linked_worktree_rejected(self):
        git(self.repo, 'worktree', 'add', str(Path(self.tmp.name) / 'wt'), '-b', 'wt')
        result = ps.plan_share({'home': str(self.home),
                                'project': str(Path(self.tmp.name) / 'wt')})
        self.assertEqual(result['status'], 'failed', result)

    # ---- phase ordering and rollback ---------------------------------------

    def test_phase_order_and_first_deletion_invariants(self):
        events = []
        natives = (str(self.claude), str(self.wb))
        first_delete = {'done': False}

        def fault(event, path):
            events.append((event, str(path)))
            p = str(path)
            if event != 'before_write' or p not in natives or first_delete['done']:
                return
            bridge = 'claude' if p.endswith('CLAUDE.md') else 'workbuddy'
            data = Path(p).read_bytes()
            if ps._entry_state(bridge, data) != 1 or ZH.encode() not in data:
                return  # 尚在入口安装阶段（无入口）或非删源对象
            # 第一处删源写入：全部入口就绪、各家原文逐字节仍在。
            first_delete['done'] = True
            for other in natives:
                other_data = Path(other).read_bytes()
                other_bridge = 'claude' if other.endswith('CLAUDE.md') else 'workbuddy'
                self.assertEqual(ps._entry_state(other_bridge, other_data), 1,
                                 '删源前入口未就绪：' + other)
                for original_path, original in self.originals.items():
                    if str(original_path) == other:
                        self.assertIn(original.rstrip(b'\n'), other_data,
                                      '删源前原文不完整：' + other)
            raise ps.TransactionError('synthetic failure at first deletion')
        outcome = self.do_share(hook=fault)
        self.assertIn(outcome['status'], ('failed', 'recovery_required'), outcome)
        self.assertIn(outcome['errors'][0]['code'],
                      ('transaction_failed', 'recovery_required'))
        writes = [p for event, p in events if event == 'after_write']
        # 顺序合同：公共 AGENTS 先落盘；两桥入口都已安装后才出现删源写入。
        self.assertLess(writes.index(str(self.agents)),
                        min(writes.index(p) for p in natives))
        for path in natives:
            self.assertEqual(writes.count(path), 1, '失败点前仅应有入口写入：%s' % path)
        for path, original in self.originals.items():
            self.assertEqual(path.read_bytes(), original, str(path))
        self.assertTrue(list((self.repo / '.mem-sharing' / 'backups')
                             .glob('*/manifest.json')))

    def test_phased_whitelist_allows_project_operation(self):
        import tempfile as tf
        from agm_core.transaction import Transaction
        with tf.TemporaryDirectory() as d:
            root = Path(d).resolve()  # 锁链路要求真实路径（/var 为符号链接）
            target = root / 'f.md'
            target.write_text('a\n')
            lock = root / 'var' / '.agm.lock'
            lock.parent.mkdir(parents=True)
            tx = Transaction(lock_path=lock, backup_root=root / 'b',
                             allowed_roots=[root], operation=ps.COMMAND)
            result = tx.run([ps.Change.file(target, b'a\nb\n',
                                            expected=ps.read_snapshot(target))],
                            phased_writes=True)
            self.assertEqual(target.read_bytes(), b'a\nb\n')
            self.assertTrue(result['manifest'])


if __name__ == '__main__':
    unittest.main()
