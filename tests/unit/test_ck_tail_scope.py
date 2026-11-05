"""Complete optional-CK conversation against actual local synthetic detection."""
import io
import sys
import unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).parent))
import test_ck_install as fixtures
from agm_core import ck_install as ck

class TailScopeTests(unittest.TestCase):
    def setUp(self):
        self.f=fixtures.CKInstallTests();self.f.setUp();self.addCleanup(self.f.doCleanups)
        self.f.installed_evidence(('claude','workbuddy','dsh','zcode','opencode'))

    def test_skip_then_explicit_install_uses_all_installed_not_only_connected(self):
        f=self.f; before=f.snapshot()
        with patch.object(ck,'discover_source',return_value=str(f.cksource)):
            for answer in ('跳过\n','\n',''):
                out=io.StringIO()
                skipped=ck.tail({'status':'completed','fusion_status':'declined'},f.request,stdin=fixtures.TTY(answer),stderr=out)
                self.assertEqual(skipped['context_keeper']['status'],'skipped',skipped)
                self.assertEqual(f.snapshot(),before)
                for label in ck.PRODUCT_LABELS.values():self.assertIn(label,out.getvalue())
            out=io.StringIO()
            done=ck.tail({'status':'completed','fusion_status':'completed'},f.request,stdin=fixtures.TTY('安装\n'),stderr=out)
        self.assertEqual(done['context_keeper']['status'],'configured',done)
        self.assertEqual(done['context_keeper']['agents'],['codex','claude','workbuddy'])
        self.assertEqual([x['agent'] for x in done['context_keeper']['skipped_upstream_agents']],['dsh','zcode','opencode'])
        self.assertIn('/context-keeper',out.getvalue())
        self.assertNotIn('同一作者',out.getvalue())
        for agent in ('dsh','zcode','opencode'):
            root=f.home/('.config/opencode' if agent=='opencode' else '.'+agent)
            self.assertFalse((root/'skills/context-keeper').exists())

    def test_pending_and_non_tty_never_plan_or_invoke_CK(self):
        with patch.object(ck,'plan_context_keeper',side_effect=AssertionError('premature')):
            result=ck.tail({'status':'completed','fusion':{'status':'pending_selection'}},self.f.request,stdin=fixtures.TTY('安装\n'))
            self.assertEqual(result['context_keeper']['reason'],'user_memory_pending')
            result=ck.tail({'status':'completed'},self.f.request,stdin=io.StringIO('安装\n'))
            pending=result['context_keeper']
            self.assertEqual(pending['status'],'pending_selection')
            self.assertEqual(pending['reason'],'user_choice_required')
            self.assertEqual(pending['choices'],['安装','跳过'])
            self.assertEqual(set(pending['agents']),set(ck.PRODUCT_LABELS))
            for label in ck.PRODUCT_LABELS.values():
                self.assertIn(label,pending['prompt'])
            self.assertIn('新会话中接着上次',pending['prompt'])

    def test_non_tty_detection_failure_is_reported_without_installing(self):
        with patch.object(ck,'installed_agents',side_effect=OSError('detection failed')), patch.object(ck,'plan_context_keeper',side_effect=AssertionError('must not plan')):
            result=ck.tail({'status':'completed'},self.f.request,stdin=io.StringIO())
        self.assertEqual(result['context_keeper']['status'],'unavailable')
