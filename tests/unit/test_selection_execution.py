"""Explicit selection, displayed-scene binding and deferred CK; synthetic only."""
import io
import json
import sys
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).parent))
import test_m408_organize as fixtures
from agm_core import user_rules_organize as org, memory_share as ms, ck_install as ck, user_entries as ue

class SelectionExecutionTests(unittest.TestCase):
    def setUp(self):
        self.f = fixtures.OrganizeTests(); self.f.setUp(); self.addCleanup(self.f.doCleanups)

    def call(self, selection, *, mutate=False):
        shown = org.plan_organize(self.f.request)['approval_plan']
        saved = self.f.area/'shown.json'; saved.write_text(json.dumps(shown))
        if mutate: self.f.files['codex'].write_bytes(self.f.files['codex'].read_bytes()+b'changed\n')
        out = io.StringIO()
        with redirect_stdout(out), patch.object(ck, 'tail', side_effect=lambda r,q:r):
            rc = org.cli(['organize-user-memory','--selection',selection,
                '--selection-plan-file',str(saved),'--selection-reference','用户回复：'+selection], home=self.f.home)
        return rc, json.loads(out.getvalue())

    def test_selection_executes_once_and_manifest_records_actual_reply(self):
        rc, result = self.call('按默认方案')
        self.assertEqual(rc,0,result); self.assertEqual(result['fusion_status'],'completed')
        text = Path(result['manifest']).read_text()
        self.assertIn('用户回复：按默认方案',text)
        self.assertNotIn('提交信息'.encode(),self.f.files['codex'].read_bytes())

    def test_decline_remains_declined_without_writes(self):
        before={p:p.read_bytes() for p in self.f.files.values()}
        rc,result=self.call('暂不整理')
        self.assertEqual(rc,0,result);self.assertEqual(result['fusion_status'],'declined')
        self.assertEqual(before,{p:p.read_bytes() for p in self.f.files.values()})

    def test_changed_displayed_scene_rejects(self):
        rc,result = self.call('按默认方案',mutate=True)
        self.assertEqual(rc,2,result); self.assertEqual(result['errors'][0]['code'],'drift')
        self.assertFalse((self.f.memories/'user-rules.md').exists())

    def test_view_is_zero_write_even_with_selection_reference(self):
        before={p:p.read_bytes() for p in self.f.files.values()}
        rc,result = self.call('查看 1')
        self.assertEqual(rc,0,result);self.assertEqual(result['status'],'viewed')
        self.assertEqual(before,{p:p.read_bytes() for p in self.f.files.values()})

    def test_exact_duplicate_and_empty_heading_keep_canonical_and_private(self):
        runtime=self.f.runtime
        canonical=ue.native_public_source_block('codex',runtime.root/'memories/MEMORY.md')
        old=ms._entry_bytes('codex',runtime)
        raw=canonical+b'\n'+ '# 用户规则\n\n'.encode()+old
        cleaned=ms.clean_native_navigation('codex',raw,runtime,original=raw,migrated=[{'scope':['用户规则']}])
        self.assertIn(canonical,cleaned);self.assertNotIn(old,cleaned);self.assertNotIn('# 用户规则'.encode(),cleaned)
        private=raw+b'\n'+ '- 仅本地保留。\n'.encode()
        self.assertIn('# 用户规则'.encode(),ms.clean_native_navigation('codex',private,runtime,original=private,migrated=[{'scope':['用户规则']}]))
        fenced=b'```md\n'+raw+b'```\n'
        self.assertEqual(fenced,ms.clean_native_navigation('codex',fenced,runtime,original=fenced,migrated=[{'scope':['用户规则']}]))
        self.assertFalse(ms._canonical_entry('codex',fenced,runtime))
        self.assertEqual(ms._entry_state('codex',fenced,runtime),0)
        info_fence=b'```text\nexample\n```python\n'+canonical+b'\n'+old+b'```\n'
        self.assertEqual(ms.clean_native_navigation('codex',info_fence,runtime),info_fence)
        self.assertEqual(ms._entry_state('codex',info_fence,runtime),0)

    def test_ck_waits_for_user_memory_and_detects_full_machine_scope(self):
        with patch.object(ck,'installed_agents',side_effect=AssertionError('too early')):
            result=ck.tail({'status':'completed','fusion':{'status':'pending_selection'}},self.f.request)
        self.assertEqual(result['context_keeper']['reason'],'user_memory_pending')
        facts={'agents':{a:{'status':'installed'} for a in self.f.config}}
        with patch.object(ck.detect,'detect_agents',return_value=facts) as detect:
            self.assertEqual(set(ck.installed_agents(dict(self.f.request,agents=['codex']))),set(self.f.config))
            self.assertNotIn('agents',detect.call_args.kwargs)
