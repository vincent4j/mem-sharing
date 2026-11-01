"""Explicit project previews: temporary HOME/Git only, no implicit repairs."""
import io
import json
import os
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

from test_m204_enable import EnableFixture
import agm
from agm_core import detect, enable


class PreviewCLITests(EnableFixture):
    def invoke(self, command, *extra, interactive=False, readonly=False):
        argv = [command, '--project', str(self.root)]
        if command == 'enable-memory':
            argv += ['--agent','codex','claude','workbuddy','--no-memory']
        argv += list(extra)
        output, errors = io.StringIO(), io.StringIO()
        original = detect.detect_agents
        def isolated(config, agents=None, **kwargs):
            kwargs.update({k:self.request[k] for k in ('search_paths','app_directories')})
            kwargs['runner'] = self.request['detect_runner']
            return original(config, agents, **kwargs)
        with ExitStack() as stack:
            stack.enter_context(patch.object(detect,'detect_agents',side_effect=isolated))
            stack.enter_context(patch('builtins.input',side_effect=AssertionError('preview must never read stdin')))
            if readonly:
                for target in ('agm_core.enable.write_lock','agm_core.remove.write_lock','agm_core.transaction.write_lock'):
                    stack.enter_context(patch(target,side_effect=AssertionError('preview must never take a write lock')))
            code = agm.main(argv, stdout=output, stderr=errors, home=str(self.home), platform='darwin', interactive=interactive)
        return code, json.loads(output.getvalue())

    def snapshot(self):
        result = {}
        for root in (self.home, self.root):
            for p in [root,*root.rglob('*')]:
                meta = p.lstat()
                result[str(p)] = (meta.st_mode,meta.st_mtime_ns,
                    os.readlink(p) if p.is_symlink() else p.read_bytes() if p.is_file() else None)
        return result

    def approval_file(self, report):
        plan = json.loads(report['next_action'])
        plan.update(confirmed_at='2026-10-31T09:00:00Z',reference='synthetic CLI preview confirmation')
        path = self.area/'preview-approval.json'; path.write_text(json.dumps(plan)); return str(path)

    def test_enable_preview_fresh_tty_and_non_tty_home_and_project_zero_write(self):
        for interactive in (False, True):
            before = self.snapshot()
            code, report = self.invoke('enable-memory','--preview',interactive=interactive,readonly=True)
            self.assertEqual(code,5,report); self.assertEqual(report['status'],'approval_required')
            plan = json.loads(report['next_action'])
            self.assertEqual(plan['command'],'enable-memory'); self.assertIn('installation',plan)
            self.assertEqual(plan['confirmed_at'],'<UTC timestamp>')
            self.assertEqual(before,self.snapshot())

    def test_enable_consistent_repair_preview_returns_plan_and_old_implicit_repair_survives(self):
        self.apply('disabled',True)
        target = self.root/'.workbuddy/memory/MEMORY.md'; raw = target.read_bytes(); target.unlink()
        before = self.snapshot()
        code, report = self.invoke('enable-memory','--preview',readonly=True)
        self.assertEqual(code,5,report); self.assertEqual(before,self.snapshot())
        self.assertIn(str(target),[x['path'] for x in json.loads(report['next_action'])['changes']])
        code, repaired = self.invoke('enable-memory')
        self.assertEqual(code,0,repaired); self.assertEqual(target.read_bytes(),raw)
        before = self.snapshot()
        code, noop = self.invoke('enable-memory','--preview',interactive=True,readonly=True)
        self.assertEqual(code,0,noop); self.assertEqual(noop['status'],'completed')
        self.assertIsNone(noop['next_action']); self.assertEqual(before,self.snapshot())

    def test_enable_preview_approval_executes_and_later_drift_is_rejected(self):
        code, report = self.invoke('enable-memory','--preview',readonly=True)
        self.assertEqual(code,5,report)
        approval = self.approval_file(report)
        path = self.root/'AGENTS.md'; path.write_bytes(b'user bytes after preview\n')
        before = self.snapshot()
        code, rejected = self.invoke('enable-memory','--approval-file',approval)
        self.assertEqual(code,5,rejected); self.assertEqual(rejected['errors'][0]['code'],'approval_mismatch')
        self.assertEqual(before,self.snapshot())
        code, current = self.invoke('enable-memory','--preview',readonly=True)
        self.assertEqual(code,5,current)
        code, applied = self.invoke('enable-memory','--approval-file',self.approval_file(current))
        self.assertEqual(code,0,applied); self.assertIn(b'user bytes after preview',path.read_bytes())

    def test_remove_preview_json_without_locks_and_old_non_tty_gate_unchanged(self):
        self.apply('disabled',True)
        for interactive in (False,True):
            before = self.snapshot()
            code, report = self.invoke('remove-memory','--preview',interactive=interactive,readonly=True)
            self.assertEqual(code,5,report)
            plan = json.loads(report['next_action'])
            self.assertEqual(set(plan),{'schema_version','command','main_checkout','checkout','git_common_dir',
                'agents','memory_policy','registry_sha256','changes','confirmed_at','reference'})
            self.assertEqual(plan['memory_policy'],'disabled'); self.assertEqual(before,self.snapshot())
        code, old = self.invoke('remove-memory',readonly=True)
        self.assertEqual(code,5,old)
        with self.assertRaises(json.JSONDecodeError): json.loads(old['next_action'])

    def test_remove_preview_approved_execution_and_drift_refusal(self):
        self.apply('disabled',True)
        code, report = self.invoke('remove-memory','--preview',readonly=True)
        self.assertEqual(code,5,report); approval = self.approval_file(report)
        target = self.root/'CLAUDE.md'; target.write_bytes(target.read_bytes()+b'foreign free text\n')
        before = self.snapshot()
        code, rejected = self.invoke('remove-memory','--approval-file',approval)
        self.assertEqual(code,2,rejected); self.assertEqual(rejected['errors'][0]['code'],'approval_mismatch')
        # Approved execution takes/releases the existing writer lock before its
        # locked drift check; directory mtimes may change, user bytes may not.
        self.assertEqual({p:(v[0],v[2]) for p,v in before.items()},
                         {p:(v[0],v[2]) for p,v in self.snapshot().items()})
        code, current = self.invoke('remove-memory','--preview',readonly=True)
        self.assertEqual(code,5,current)
        code, applied = self.invoke('remove-memory','--approval-file',self.approval_file(current))
        self.assertEqual(code,0,applied); self.assertEqual(target.read_bytes(),b'foreign free text\n')

    def test_preview_rejects_approval_mix_repetition_batch_and_check(self):
        for command in ('enable-memory','remove-memory'):
            for extra in (('--preview','--approval-file','/does/not/exist.json'),('--preview','--preview')):
                before = self.snapshot()
                code, report = self.invoke(command,*extra,readonly=True)
                self.assertEqual(code,2,report); self.assertEqual(report['errors'][0]['code'],'invalid_arguments')
                self.assertEqual(before,self.snapshot())
        for argv in (['check-memory','--preview'],['enable-memory-batch','--directory',str(self.root),'--preview']):
            output = io.StringIO(); before = self.snapshot()
            code = agm.main(argv, stdout=output, stderr=io.StringIO(), home=str(self.home), platform='darwin',interactive=False)
            self.assertEqual(code,2,json.loads(output.getvalue())); self.assertEqual(before,self.snapshot())

    def test_preview_core_never_calls_confirmation_callback(self):
        before = self.snapshot()
        request = dict(self.request,preview=True,interactive=True,confirm=lambda _:self.fail('preview called confirmation'))
        report = enable.run(request)
        self.assertEqual(report['status'],'approval_required',report); self.assertEqual(before,self.snapshot())

    def test_preview_keeps_separate_rebuild_confirmation_unconfirmed(self):
        self.apply('disabled',True)
        data = json.loads(self.runtime.registry.read_bytes())
        data['projects'][str(self.root)]['memory_policy'] = 'INVALID'
        self.runtime.registry.write_text(json.dumps(data))
        before = self.snapshot()
        code, report = self.invoke('enable-memory','--preview',interactive=True,readonly=True)
        self.assertEqual(code,5,report)
        plan = json.loads(report['next_action'])
        self.assertEqual(plan['rebuild_confirmation']['confirmed_at'],'<UTC timestamp>')
        self.assertEqual(plan['rebuild_confirmation']['reference'],'<separate global rebuild confirmation>')
        self.assertEqual(plan['rebuild_confirmation']['registry_sha256'],plan['rebuild']['registry_sha256'])
        self.assertEqual(before,self.snapshot())
