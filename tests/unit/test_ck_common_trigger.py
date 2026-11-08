"""Synthetic public-template tests; no native user memory or upstream import."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'scripts'))
from agm_core import ck_common_trigger as ck, entries

BODY = b'\xe4\xbb\xa5\xe4\xb8\x8b\xe4\xbb\xbb\xe4\xb8\x80\xe6\x9d\xa1\xe4\xbb\xb6\xe8\xa7\xa6\xe5\x8f\x91\xe6\x97\xb6\xef\xbc\x8c\xe5\x85\x88\xe8\xaf\xbb\xe5\xb9\xb6\xe9\x81\xb5\xe5\xae\x88\xe5\xb7\xb2\xe5\xae\x89\xe8\xa3\x85\xe7\x9a\x84 context-keeper/SKILL.md\xef\xbc\x9b\xe8\xaf\xbb\xe4\xb8\x8d\xe5\x88\xb0\xe5\x88\x99\xe5\x81\x9c\xe6\xad\xa2\xe8\xae\xb0\xe5\xbf\x86\xe6\x93\x8d\xe4\xbd\x9c\xef\xbc\x9a\n- \xe7\x94\xa8\xe6\x88\xb7\xe8\xa6\x81\xe6\xb1\x82\xe4\xbf\x9d\xe5\xad\x98\xe3\x80\x81\xe7\xbb\xa7\xe7\xbb\xad\xe6\x88\x96\xe6\x9f\xa5\xe6\x89\xbe\xe3\x80\x82\n- \xe6\x8f\x90\xe5\x8f\x8a\xe4\xbb\xa5\xe5\x89\x8d\xe3\x80\x81\xe4\xb8\x8a\xe6\xac\xa1\xe3\x80\x81\xe9\x87\x8d\xe5\xa4\x8d\xe9\x97\xae\xe9\xa2\x98\xef\xbc\x9b\xe7\x94\xa8\xe6\x88\xb7\xe8\xae\xb0\xe5\xbf\x86\xe4\xb8\x8e\xe8\xae\xb0\xe5\xbd\x95\xe4\xb8\x8d\xe4\xb8\x80\xe8\x87\xb4\xef\xbc\x9b\xe9\x87\x8d\xe8\xaf\x95\xe6\x88\x96\xe6\x8d\xa2\xe8\xb7\xaf\xe7\xba\xbf\xe4\xb8\x94\xe4\xbe\x9d\xe6\x8d\xae\xe4\xb8\x8d\xe8\xb6\xb3\xef\xbc\x9b\xe6\x8e\xa8\xe7\xbf\xbb\xe6\x97\xa7\xe5\x86\xb3\xe7\xad\x96\xe4\xbd\x86\xe5\x8e\x9f\xe4\xbe\x9d\xe6\x8d\xae\xe7\xbc\xba\xe5\xa4\xb1\xe3\x80\x82\n- \xe9\xa1\xb9\xe7\x9b\xae\xe5\xb7\xb2\xe6\x9c\x89\xe6\x8e\x88\xe6\x9d\x83\xe8\xae\xb0\xe5\xbd\x95\xe5\xba\x93\xe3\x80\x81\xe6\x9c\xaa\xe7\xa6\x81\xe6\xad\xa2\xe4\xbf\x9d\xe5\xad\x98\xe6\x88\x96\xe6\x94\xb9\xe6\x96\x87\xe4\xbb\xb6\xe4\xb8\x94\xe6\x9c\x89\xe6\x9c\xaa\xe8\xae\xb0\xe5\xbd\x95\xe4\xba\x8b\xe5\xae\x9e\xef\xbc\x9a\xe9\x98\xb6\xe6\xae\xb5\xe6\x88\x90\xe6\x9e\x9c\xe3\x80\x81\xe6\x8a\x80\xe6\x9c\xaf\xe9\x80\x89\xe6\x8b\xa9\xe6\x98\x8e\xe7\xa1\xae\xe3\x80\x81\xe5\xbd\xb1\xe5\x93\x8d\xe5\x90\x8e\xe7\xbb\xad\xe7\x9a\x84\xe5\xa4\xb1\xe8\xb4\xa5\xe6\x88\x96\xe6\x94\xbe\xe5\xbc\x83\xe8\xb7\xaf\xe7\xba\xbf\xe3\x80\x81\xe7\x94\xa8\xe6\x88\xb7\xe7\xba\xa0\xe6\xad\xa3\xe3\x80\x81\xe6\x96\xb0\xe8\xaf\x81\xe6\x8d\xae\xe6\x94\xb9\xe5\x8f\x98\xe5\x88\xa4\xe6\x96\xad\xe3\x80\x81\xe6\x9a\x82\xe5\x81\x9c\xe3\x80\x81\xe4\xba\xa4\xe6\x8e\xa5\xe3\x80\x81\xe9\x98\xbb\xe5\xa1\x9e\xe6\x88\x96\xe5\xa4\x96\xe9\x83\xa8\xe7\xad\x89\xe5\xbe\x85\xef\xbc\x9b\xe4\xba\xa4\xe4\xbb\x98\xe6\x88\x96\xe6\x9a\x82\xe5\x81\x9c\xe5\x9b\x9e\xe5\xa4\x8d\xe5\x89\x8d\xe8\xa7\xa6\xe5\x8f\x91\xe3\x80\x82\n\xe6\x97\xa0\xe9\xa1\xb9\xe7\x9b\xae\xe8\x81\x8a\xe5\xa4\xa9\xe4\xb8\x8d\xe8\x87\xaa\xe5\x8a\xa8\xe8\xae\xb0\xe5\xbd\x95\xe3\x80\x81\xe6\x9f\xa5\xe7\x8a\xb6\xe6\x80\x81\xe6\x88\x96\xe8\xaf\xa2\xe9\x97\xae\xe5\xbb\xba\xe5\xba\x93\xef\xbc\x8c\xe4\xbb\x85\xe6\x98\x8e\xe7\xa1\xae\xe8\xa6\x81\xe6\xb1\x82\xe4\xbf\x9d\xe5\xad\x98\xe6\x97\xb6\xe8\xbf\x9b\xe5\x85\xa5\xe4\xbf\x9d\xe5\xad\x98\xe8\xb7\xaf\xe7\x94\xb1\xef\xbc\x9bcwd \xe6\x88\x96\xe8\xae\xa8\xe8\xae\xba\xe4\xbb\x93\xe5\xba\x93\xe4\xb8\x8d\xe7\xad\x89\xe4\xba\x8e\xe9\xa1\xb9\xe7\x9b\xae\xe4\xbc\x9a\xe8\xaf\x9d\xe3\x80\x82\n'


def block(agent, body=BODY):
    first, last, title = ck.MARKERS[agent == 'workbuddy']
    return first + b'\n' + title.encode() + b'\n\n' + body + last + b'\n'


class CommonTriggerTests(unittest.TestCase):
    def test_six_hosts_same_body_different_shells_exact_roundtrip(self):
        for agent in ('codex', 'claude', 'workbuddy', 'zcode', 'dsh', 'opencode'):
            with self.subTest(agent=agent):
                original = b'private prefix\n' + block(agent) + b'private suffix\n'
                result = ck.recognize(original, agent)
                self.assertEqual(original[result['start']:result['end']], BODY)
                shell = original[:result['start']] + original[result['end']:]
                self.assertIn(ck.MARKERS[agent == 'workbuddy'][2].encode(), shell)
                self.assertEqual(shell[:result['start']] + BODY + shell[result['start']:], original)

    def test_unknown_edited_partial_and_wrong_host_remain_protected(self):
        for body in (b'private text\n', BODY[:-1], BODY + b'extra\n', BODY.replace(b'SKILL', b'OTHER')):
            self.assertIsNone(ck.recognize(block('codex', body), 'codex'))
        self.assertIsNone(ck.recognize(block('workbuddy'), 'codex'))
        self.assertIsNone(ck.recognize(b'ordinary text', 'codex'))

    def test_duplicate_damaged_reversed_mixed_midline_rejected(self):
        first, last, _ = ck.MARKERS[0]
        for raw in (block('codex') * 2, first, last, last + first,
                    block('codex') + block('workbuddy'),
                    b'prefix' + block('codex'), block('codex').rstrip() + b'suffix'):
            with self.subTest(raw=raw[:50]):
                with self.assertRaises(entries.EntryConflict):
                    ck.recognize(raw, 'codex')

    def test_recognition_does_not_relax_existing_share_protection(self):
        from agm_core import memory_share as ms
        raw = block('codex')
        result = ck.recognize(raw, 'codex')
        self.assertTrue(any(a <= result['start'] < result['end'] <= b
                            for a,b in ms._protected_spans(raw)))

    def test_literal_fenced_and_outer_private_protocol_not_candidates(self):
        for raw in (b'```md\n'+block('codex')+b'```\n',
                    b'<!-- mem-sharing:private:start -->\n'+block('codex')+b'<!-- mem-sharing:private:end -->\n'):
            self.assertIsNone(ck.candidate(raw,'codex'))

    def test_adjacent_native_protocols_keep_the_audited_ck_boundary(self):
        from agm_core import memory_share as ms
        pointer = (b'<!-- mem-sharing:rules:start -->\nread public rules\n'
                   b'<!-- mem-sharing:rules:end -->\n')
        for agent in ('codex', 'claude', 'workbuddy', 'zcode', 'dsh', 'opencode'):
            for raw in (pointer + block(agent), block(agent) + pointer,
                        pointer + block(agent) + b'@public-memory.md\n'):
                with self.subTest(agent=agent, prefix=raw[:30]):
                    candidate = ck.candidate(raw, agent)
                    self.assertIsNotNone(candidate)
                    self.assertEqual(raw[candidate['start']:candidate['end']], BODY)
                    self.assertTrue(any(a == candidate['block_start'] and
                                        candidate['block_end'] <= b <= candidate['block_end'] + 1
                                        for a, b in ms._protected_spans(raw)))

    def test_nested_private_protocol_is_still_not_a_ck_candidate(self):
        pointer = (b'<!-- mem-sharing:rules:start -->\nread public rules\n'
                   b'<!-- mem-sharing:rules:end -->\n')
        for agent in ('codex', 'workbuddy'):
            raw = (pointer + b'<!-- mem-sharing:private:start -->\n' + block(agent)
                   + b'<!-- mem-sharing:private:end -->\n')
            self.assertIsNone(ck.candidate(raw, agent))

    def test_mandatory_reader_rejects_literal_and_negated_lines(self):
        from agm_core.user_entries import public_memory_contract_text
        valid=public_memory_contract_text().encode()
        ck.require_reader(valid)
        full=next(line for line in valid.splitlines() if line.startswith(ck.READ_RULE))
        for raw in (b'```md\n'+valid+b'```\n', b'prefix '+full, ('不要').encode()+full, b'<!-- literal\n'+full+b'\n-->\n', b'<!-- mem-sharing:private:start -->\n'+full+b'\n<!-- mem-sharing:private:end -->\n',
                    b'```md\n'+ck.READ_RULE+b'\n```\n',('不要').encode()+ck.READ_RULE):
            with self.assertRaises(entries.EntryConflict):ck.require_reader(raw)
