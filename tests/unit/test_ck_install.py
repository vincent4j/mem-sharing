"""CK optional install uses synthetic Git source and an isolated fixture HOME."""
import copy
import io
import json
import os
import plistlib
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_m404_install import InstallFixture, approved
from agm_core import ck_install as ck, detect, paths, registry, user_entries
from agm_core.layout import RuntimeLayout

DURABLE_CHECK = ck._durable_source

# A deliberately small synthetic upstream, implementing the verified pin's JSON
# shape and its exact byte-preserving block replacement algorithm. Never imports
# or runs the real CK checkout, and never uses a real HOME.
UPSTREAM = r'''import json, os, sys
from pathlib import Path
home=Path(os.environ['HOME']); source=Path(__file__).resolve().parents[1]
import argparse
parser=argparse.ArgumentParser()
parser.add_argument('--codex')
parser.add_argument('--claude')
parser.add_argument('--workbuddy')
parser.add_argument('--zcode')
parser.add_argument('--dsh')
parser.add_argument('--opencode')
agents=[a for a in ('codex','claude','workbuddy','zcode','dsh','opencode') if '--'+a in sys.argv]
roots={'codex':['.agents/skills','.codex/skills'],'claude':['.claude/skills'],'workbuddy':['.workbuddy/skills'],'zcode':['.zcode/skills','.agents/skills'],'dsh':['.dsh/skills','.agents/skills'],'opencode':['.config/opencode/skills']}
rules={'codex':'.codex/AGENTS.md','claude':'.claude/CLAUDE.md','workbuddy':'.workbuddy/MEMORY.md','zcode':'.zcode/AGENTS.md','dsh':'.dsh/AGENTS.md','opencode':'.config/opencode/AGENTS.md'}
labels={'codex':'Codex','claude':'Claude Code','workbuddy':'WorkBuddy','zcode':'ZCode','dsh':'DeepSeek Harness','opencode':'OpenCode'}
skills=list(dict.fromkeys(str(home/r/'context-keeper') for a in agents for r in roots[a]))
files=[str(home/rules[a]) for a in agents]
if '--approved' not in sys.argv:
 print(json.dumps({'approval_required':True,'operation':'安装','skill_entries':skills,'rule_files':files,'effect':'新增或复用 Skill 入口，并更新自身区块'})); sys.exit(0)
for s in skills:
 p=Path(s); p.parent.mkdir(parents=True,exist_ok=True)
 if not p.is_symlink(): p.symlink_to(source)
for a,name in zip(agents,files):
 p=Path(name); p.parent.mkdir(parents=True,exist_ok=True)
 mid=':workbuddy' if a=='workbuddy' else ''
 first='<!-- context-keeper'+mid+':start -->'; last='<!-- context-keeper'+mid+':end -->'
 bridge=first+'\nsynthetic pinned CK block\n'+last+'\n'
 if not p.exists(): p.write_bytes((bridge+'\n').encode()); continue
 text=p.read_bytes().decode(); start=text.find(first); end=text.find(last)
 if start>=0:
  end+=len(last); replacement=bridge.rstrip('\n')
  updated=(replacement+'\n\n'+text[:start]+text[end:] if a=='workbuddy' and start else text[:start]+replacement+text[end:])
 elif a=='workbuddy': updated=bridge+'\n'+text
 else: updated=text+('\n' if text.endswith('\n') else '\n\n')+bridge
 p.write_bytes(updated.encode())
print(json.dumps({'scope':'user','project':None,'installed':skills,'removed':[], 'bridges':[{'file':f,'action':'created'} for f in files], 'configured_agents':[labels[a] for a in agents]}))
'''


class TTY(io.StringIO):
    def isatty(self): return True


class CKInstallTests(InstallFixture):
    def setUp(self):
        super().setUp()
        self.codex(); self.execute()
        self.cksource=self.area/'durable CK fixture'; (self.cksource/'scripts').mkdir(parents=True)
        (self.cksource/'SKILL.md').write_text('name: context-keeper\n')
        (self.cksource/'scripts/install.py').write_text(UPSTREAM)
        def git(*args):
            return subprocess.run(['git','-C',str(self.cksource),*args],capture_output=True,check=True,text=True).stdout.strip()
        git('init');git('add','SKILL.md','scripts/install.py')
        git('-c','user.name=fixture','-c','user.email=fixture@example.invalid','commit','-m','synthetic CK')
        self.pin=git('rev-parse','HEAD')
        self.addCleanup(patch.stopall)
        git('remote','add','origin',ck.OFFICIAL)
        git('update-ref','refs/remotes/origin/main',self.pin)
        patch.object(ck,'prepare_source',return_value=str(self.cksource)).start()
        # Production rejects OS-temp sources. Fixtures deliberately live in temp;
        # this single check is mocked while all source identity/bytes stay real.
        patch.object(ck,'_durable_source').start()
        self.op=self.request['operation_id']

    def plan_ck(self, **kwargs):
        return ck.plan_context_keeper(self.request,self.op,str(self.cksource),**kwargs)

    def snapshot(self):
        return {str(p.relative_to(self.home)):(p.lstat().st_mode,p.lstat().st_mtime_ns,
            os.readlink(p) if p.is_symlink() else p.read_bytes() if p.is_file() else None)
            for p in [self.home,*self.home.rglob('*')]}

    def apply(self, plan=None, **kwargs):
        plan=plan or self.plan_ck()
        return ck.execute_context_keeper(plan,approved(plan),request=self.request,**kwargs)

    def installed_evidence(self, agents):
        for agent in agents:
            signal = next((s for s in self.config[agent]['installation_signals'] if s['kind']=='macos_app_bundle'), None)
            if signal is None:
                signal = next(s for s in self.config[agent]['installation_signals'] if s['kind']=='path_executable')
                package = self.area/('installed-'+agent); (package/'bin').mkdir(parents=True,exist_ok=True)
                executable = package/'bin'/signal['executable']; executable.write_text('#!/bin/sh\n'); executable.chmod(0o755)
                (package/'package.json').write_text(json.dumps({'name':signal['package_name'],'version':'1.0.0','bin':{agent:'bin/'+agent}}))
                self.request['search_paths'].append(str(package/'bin'))
                continue
            bundle = self.home/'Applications'/signal['bundle_name']
            exe = signal['bundle_name'][:-4]
            (bundle/'Contents/MacOS').mkdir(parents=True, exist_ok=True)
            (bundle/'Contents/Info.plist').write_bytes(plistlib.dumps({
                'CFBundleName':signal['product_name'], 'CFBundleDisplayName':signal['product_name'], 'CFBundleExecutable':exe,
                'CFBundleIdentifier':'ai.opencode.desktop' if agent=='opencode' else 'fixture.'+agent,
                'CFBundleShortVersionString':'1.0.0', 'CFBundleVersion':'1.0.0'}))
            path=bundle/'Contents/MacOS'/exe; path.write_text('#!/bin/sh\n'); path.chmod(0o755)

    def connect_desktops(self):
        self.installed_evidence(('dsh','zcode','opencode'))
        facts = detect.detect_agents(self.config, None, home=str(self.home),
            search_paths=self.request['search_paths'], app_directories=[])
        for agent in ('dsh', 'zcode', 'opencode'):
            facts['agents'][agent] = copy.deepcopy(facts['agents']['codex'])
        req = dict(self.request, agents=['dsh', 'zcode', 'opencode'])
        with patch.dict(os.environ, DSH_HOME='', XDG_CONFIG_HOME='', OPENCODE_CONFIG_DIR='', OPENCODE_CONFIG=''), patch.object(detect, 'detect_agents', return_value=facts):
            preview = user_entries.run_user_entries(req)
            self.assertEqual(preview['status'], 'approval_required', preview)
            plan = json.loads(preview['next_action'])
            req['approval'] = approved({k:v for k,v in plan.items() if k not in ('confirmed_at','reference')})
            done = user_entries.run_user_entries(req)
            self.assertEqual(done['status'], 'completed', done)

    def test_mixed_six_host_support_deduplicates_shared_paths_and_preserves_private_bytes(self):
        self.connect_desktops()
        private = {a: (Path(paths.expand_path(self.config[a]['user_entry'], home=str(self.home)))).read_bytes() for a in ('dsh', 'zcode', 'opencode')}
        before = self.snapshot()
        plan = self.plan_ck()
        self.assertEqual(plan['agents'], ['codex', 'zcode', 'dsh', 'opencode'])
        self.assertEqual(plan['skipped_upstream_agents'], [])
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(len(plan['skill_entries']), 5)
        self.assertEqual(len(plan['skill_entries']), len(set(plan['skill_entries'])))
        for agent in ('dsh', 'zcode', 'opencode'):
            self.assertIn('--'+agent, plan['argv'])
        result = self.apply(plan)
        self.assertEqual(result['status'], 'configured', result)
        self.assertEqual(result['agents'], plan['agents'])
        self.assertEqual(result['skipped_upstream_agents'], [])
        for agent, raw in private.items():
            entry = Path(paths.expand_path(self.config[agent]['user_entry'], home=str(self.home)))
            ck._verify_rule(raw, entry.read_bytes(), agent)
            for root in ck.ROOTS[agent]:
                self.assertEqual((self.home/root/'context-keeper').resolve(), self.cksource)

    def test_desktop_only_installs_without_legacy_three_hosts(self):
        self.connect_desktops()
        (Path(self.request['search_paths'][0])/'codex').unlink()
        import shutil
        (Path(self.request['search_paths'][0])/'git').symlink_to(shutil.which('git'))
        data = json.loads(self.runtime.registry.read_bytes())
        data['machine']['agents'].pop('codex')
        data['machine']['objects'] = {k:v for k,v in data['machine']['objects'].items() if 'codex' not in v['agents']}
        self.runtime.registry.write_bytes(registry.serialize_registry(data,
            allowed_user_paths=paths.allowed_user_paths(self.config, None, home=str(self.home))))
        before = self.snapshot()
        plan = self.plan_ck()
        self.assertEqual(plan['agents'], ['zcode', 'dsh', 'opencode'])
        self.assertEqual(plan['skipped_upstream_agents'], [])
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(len(plan['skill_entries']), 4)
        result = self.apply(plan)
        self.assertEqual(result['status'], 'configured', result)
        self.assertEqual(result['agents'], plan['agents'])

    def test_no_installed_agent_keeps_missing_agent_error(self):
        (Path(self.request['search_paths'][0])/'codex').unlink()
        data = json.loads(self.runtime.registry.read_bytes())
        data['machine'] = {'agents': {}, 'objects': {}}
        self.runtime.registry.write_bytes(registry.serialize_registry(data,
            allowed_user_paths=paths.allowed_user_paths(self.config, None, home=str(self.home))))
        before = self.snapshot()
        with patch.object(ck, '_invoke', side_effect=AssertionError('no upstream call')):
            with self.assertRaises(ck.CKError) as stopped: self.plan_ck()
        self.assertEqual(stopped.exception.code, 'ck_no_agents')
        self.assertEqual(self.snapshot(), before)

    def test_preview_is_read_only_exact_scope_and_commit_content(self):
        before=self.snapshot(); plan=self.plan_ck()
        self.assertEqual(before,self.snapshot())
        self.assertEqual(plan['command'],'install-context-keeper')
        self.assertEqual(plan['main_operation_id'],self.op)
        self.assertEqual(plan['source']['commit'],self.pin)
        self.assertEqual(set(plan['source']['files']),{'SKILL.md','scripts/install.py'})
        self.assertEqual(plan['agents'],['codex'])
        self.assertEqual(plan['argv'][-2:],['--codex','--approved'])
        for flag in ('--all','--project','--ensure-bridge','--init'):
            self.assertNotIn(flag,plan['argv'])
        self.assertEqual(len(plan['changes']),3)
        self.assertTrue(plan['upstream_preview']['approval_required'])
        self.assertFalse(Path(plan['journal']).exists())

    def test_production_durability_check_rejects_product_and_temporary_sources(self):
        runtime=RuntimeLayout(Path('/Users/synthetic-ck-install-home'))
        for root in (runtime.root/'ck', runtime.code/'ck',
                runtime.home/'.local/share/mem-sharing-versions/ck', Path('/tmp').resolve()/'ck',
                Path('/private/var/folders/synthetic/ck'), runtime.home/'.mem-sharing-install-op/checkout',
                Path(ck.__file__).resolve().parents[2]/'vendor/context-keeper'):
            with self.subTest(root=root),self.assertRaises(ck.CKError):
                DURABLE_CHECK(root,runtime)
        DURABLE_CHECK(runtime.home/'independent-ck-source',runtime)

    def test_execute_readback_preserves_main_registry_and_rule_bytes(self):
        raw=self.runtime.registry.read_bytes(); entry=self.home/'.codex/AGENTS.md'
        before=entry.read_bytes(); result=self.apply()
        self.assertEqual(result['status'],'configured',result)
        self.assertEqual(result['runtime_acceptance'],'pending')
        self.assertEqual(raw,self.runtime.registry.read_bytes())
        self.assertTrue(entry.read_bytes().startswith(before))
        for p in ('.agents/skills/context-keeper','.codex/skills/context-keeper'):
            self.assertEqual((self.home/p).resolve(),self.cksource)
        self.assertFalse((self.home/'.claude').exists())
        journal=Path(result['journal']); self.assertEqual(journal.stat().st_mode & 0o777,0o600)
        with self.assertRaises(ck.CKError) as stopped:self.plan_ck()
        self.assertEqual(stopped.exception.code,'ck_operation_exists')

    def test_all_ledger_consumers_selected_even_when_request_names_only_new_agents(self):
        # Installation detection is synthetic; the resulting registered entry
        # transactions and CK subprocesses are real isolated file operations.
        entry = self.home/".workbuddy/MEMORY.md"
        entry.parent.mkdir()
        private = b"my private rules\r\n"
        entry.write_bytes(private)
        remember_mode(self, entry)
        self.installed_evidence(('claude','workbuddy'))
        facts=detect.detect_agents(self.config,None,home=str(self.home),
            search_paths=self.request['search_paths'],app_directories=[])
        for agent in ('claude','workbuddy'):
            facts['agents'][agent]=copy.deepcopy(facts['agents']['codex'])
        request=dict(self.request,agents=['claude','workbuddy'])
        with patch.object(detect,'detect_agents',return_value=facts):
            preview=user_entries.run_user_entries(request)
            self.assertEqual(preview['status'],'approval_required',preview)
            plan=json.loads(preview['next_action'])
            result=user_entries.run_user_entries(dict(request,approval=approved({k:v for k,v in plan.items() if k not in ('confirmed_at','reference')})))
            self.assertEqual(result['status'],'completed',result)
        installed = entry.read_bytes()
        assert_opaque(self, installed, private, index=self.runtime.root/"memories/MEMORY.md", path=entry)
        self.assertIn(str(self.runtime.root/'memories/MEMORY.md').encode(), installed)
        for damaged in (b'', installed.replace(b'AGENTS.md', b'CHANGED.md')):
            entry.write_bytes(damaged)
            with self.assertRaises(ValueError):
                ck.plan_context_keeper(request,self.op,str(self.cksource))
        entry.write_bytes(installed)
        saved_ledger = self.runtime.registry.read_bytes()
        old = installed.replace((user_entries.public_read_text(self.runtime.root/'memories/MEMORY.md') + "\n").encode(), b'')
        entry.write_bytes(old)
        ledger = json.loads(saved_ledger)
        obj = ledger['machine']['objects'][str(entry)+'#convention']
        obj['fingerprint']['value'] = user_entries.block_fingerprint(old, **obj['marker'])
        self.runtime.registry.write_text(json.dumps(ledger))
        with self.assertRaises(ck.CKError) as missing_semantics:
            ck.plan_context_keeper(request,self.op,str(self.cksource))
        self.assertEqual(missing_semantics.exception.code, 'ck_main_incomplete')
        self.runtime.registry.write_bytes(saved_ledger)
        entry.write_bytes(installed)
        plan=ck.plan_context_keeper(request,self.op,str(self.cksource))
        self.assertEqual(plan['agents'],['codex','claude','workbuddy'])
        self.assertEqual(plan['argv'][-4:],['--codex','--claude','--workbuddy','--approved'])
        result=ck.execute_context_keeper(plan,approved(plan),request=request)
        self.assertEqual(result['status'],'configured',result)
        self.assertEqual(len(plan['skill_entries']),4)
        self.assertIn(installed, entry.read_bytes())
        self.assertTrue((self.home/'.workbuddy/MEMORY.md').read_bytes().startswith(b'<!-- context-keeper:workbuddy:start -->'))

    def test_approval_evidence_and_unrelated_main_approval_rejected(self):
        plan=self.plan_ck(); before=self.snapshot()
        for evidence in ({},dict(plan),dict(approved(plan),reference=''),dict(approved(plan),scope='project'),dict(approved(plan),confirmed_at='<UTC>'),
                         dict(approved(plan),confirmed_at='2026-10-30T00:00:00+00:00'),
                         dict(approved(plan),confirmed_at='2026-10-30T00:00:00+08:00'),
                         dict(approved(plan),confirmed_at='2026-10-30T00:00:00')):
            with self.subTest(evidence=evidence):
                with self.assertRaises(ck.CKError):ck.execute_context_keeper(plan,evidence,request=self.request)
        self.assertEqual(before,self.snapshot())

    def test_target_parent_source_registry_and_connected_entry_drift_stop(self):
        for kind in ('target','source','registry','missing_entry','parent'):
            with self.subTest(kind=kind):
                plan=self.plan_ck()
                target=self.home/'.codex/AGENTS.md'; original=target.read_bytes()
                registry_raw=self.runtime.registry.read_bytes()
                source=self.cksource/'SKILL.md'; source_raw=source.read_bytes()
                if kind=='target':target.write_bytes(original+b'user change\n')
                elif kind=='source':source.write_bytes(source_raw+b'local change\n')
                elif kind=='registry':self.runtime.registry.write_bytes(registry_raw+b'\n')
                elif kind=='missing_entry':target.unlink()
                else:(self.home/'.agents').mkdir()
                before=self.snapshot()
                with self.assertRaises(ValueError):self.apply(plan)
                self.assertEqual(before,self.snapshot())
                target.write_bytes(original);source.write_bytes(source_raw);self.runtime.registry.write_bytes(registry_raw)
                if kind=='parent':(self.home/'.agents').rmdir()

    def test_wrong_pin_and_hidden_tracked_change_rejected(self):
        subprocess.run(['git','-C',str(self.cksource),'remote','set-url','origin','https://example.invalid/other.git'],check=True)
        with self.assertRaises(ck.CKError):self.plan_ck()
        subprocess.run(['git','-C',str(self.cksource),'remote','set-url','origin',ck.OFFICIAL],check=True)
        subprocess.run(['git','-C',str(self.cksource),'update-index','--assume-unchanged','SKILL.md'],check=True)
        (self.cksource/'SKILL.md').write_text('hidden dirty bytes')
        with self.assertRaises(ck.CKError):self.plan_ck()

    def test_wrong_main_operation_and_missing_source_are_read_only(self):
        before=self.snapshot()
        with self.assertRaises(ck.CKError):ck.plan_context_keeper(self.request,'other-op',str(self.cksource))
        with self.assertRaises(ck.CKError) as stopped:ck.plan_context_keeper(self.request,self.op)
        self.assertEqual(stopped.exception.code,'ck_source_unavailable')
        self.assertIn('--ck-source',str(stopped.exception))
        self.assertEqual(before,self.snapshot())

    def test_pending_upgrade_marker_before_preview_or_after_approval_is_zero_write(self):
        marker=self.home/'.mem-sharing-upgrade.json'
        for phase in ('before_preview','after_approval'):
            with self.subTest(phase=phase):
                plan=self.plan_ck() if phase=='after_approval' else None
                marker.write_text('{}')
                before=self.snapshot()
                with patch.object(ck,'_invoke',side_effect=AssertionError('pending machine must not invoke CK')):
                    with self.assertRaises(ValueError) as stopped:
                        self.apply(plan) if plan else self.plan_ck()
                self.assertEqual(stopped.exception.code,'machine_upgrade_pending')
                self.assertEqual(before,self.snapshot())
                self.assertFalse((self.runtime.var/('ck-install-'+self.op+'.json')).exists())
                self.assertFalse((self.home/'.codex/skills/context-keeper').exists())
                marker.unlink()

    def test_unfinished_main_journal_blocks_even_when_v_is_complete(self):
        journal=self.home/('.mem-sharing-install-'+self.op)/'journal.json'
        original=journal.read_bytes()
        for phase in ('before_preview','after_approval'):
            for status in ('running','outputs_verified','recovery_required'):
                with self.subTest(phase=phase,status=status):
                    plan=self.plan_ck() if phase=='after_approval' else None
                    data=json.loads(original);data['status']=status
                    journal.write_text(json.dumps(data))
                    before=self.snapshot()
                    self.assertEqual(json.loads(self.runtime.registry.read_bytes())['product']['installation_status'],'complete')
                    with patch.object(ck,'_invoke',side_effect=AssertionError('unfinished main must not invoke CK')):
                        with self.assertRaises(ck.CKError) as stopped:
                            self.apply(plan) if plan else self.plan_ck()
                    self.assertEqual(stopped.exception.code,'ck_main_incomplete')
                    self.assertEqual(before,self.snapshot())
                    self.assertFalse((self.runtime.var/('ck-install-'+self.op+'.json')).exists())
                    journal.write_bytes(original)

    def test_main_journal_identity_and_pending_marker_symlink_are_not_bypassed(self):
        plan=self.plan_ck()
        journal=self.home/('.mem-sharing-install-'+self.op)/'journal.json'
        self.assertEqual(plan['main_journal']['path'],str(journal))
        original=journal.read_bytes();data=json.loads(original)
        data['operation_id']='other-main-operation';journal.write_text(json.dumps(data))
        before=self.snapshot()
        with self.assertRaises(ValueError):self.apply(plan)
        self.assertEqual(before,self.snapshot())
        self.assertFalse(Path(plan['journal']).exists())
        for invalid in ([],{'status':'committed','plan':None}):
            journal.write_text(json.dumps(invalid));before=self.snapshot()
            with self.assertRaises(ck.CKError):self.plan_ck()
            self.assertEqual(before,self.snapshot())
            self.assertFalse(Path(plan['journal']).exists())
        journal.write_bytes(original)
        marker=self.home/'.mem-sharing-upgrade.json';marker.symlink_to(self.area/'missing-marker-target')
        before=self.snapshot()
        with self.assertRaises(ValueError) as stopped:self.plan_ck()
        self.assertEqual(stopped.exception.code,'machine_upgrade_pending')
        self.assertEqual(before,self.snapshot())

    def test_missing_completed_main_journal_cannot_create_a_ck_operation(self):
        plan=self.plan_ck()
        journal=self.home/('.mem-sharing-install-'+self.op)/'journal.json'
        journal.unlink();before=self.snapshot()
        with patch.object(ck,'_invoke',side_effect=AssertionError('missing main proof must not invoke CK')):
            for action in (self.plan_ck,lambda:self.apply(plan)):
                with self.assertRaises((ValueError,OSError)):action()
        self.assertEqual(before,self.snapshot())
        self.assertFalse(Path(plan['journal']).exists())

    def test_scope_preview_and_execution_unknown_never_report_configured(self):
        for response in ({'approval_required':True,'skill_entries':[],'rule_files':[]}, {'scope':'project'}):
            with self.subTest(response=response):
                runner=lambda *a,**k:SimpleNamespace(returncode=0,stdout=json.dumps(response))
                with self.assertRaises(ck.CKError):self.plan_ck(runner=runner)
        plan=self.plan_ck()
        def runner(argv,**kwargs):
            if '--approved' not in argv:return subprocess.run(argv,**kwargs)
            return SimpleNamespace(returncode=0,stdout='{"scope":"project"}')
        result=self.apply(plan,runner=runner)
        self.assertEqual(result['status'],'unknown')
        self.assertFalse((self.home/'.codex/skills/context-keeper').exists())
        self.assertTrue(self.runtime.registry.exists())
        with self.assertRaises(ck.CKError):self.plan_ck()

    def test_approved_runner_still_pending_is_not_configured(self):
        plan=self.plan_ck()
        runner=lambda argv,**kwargs:(subprocess.run(argv,**kwargs) if '--approved' not in argv else SimpleNamespace(returncode=0,stdout='{"approval_required":true}'))
        result=self.apply(plan,runner=runner)
        self.assertEqual(result['status'],'approval_required')
        self.assertTrue(result['approval_required'])
        self.assertFalse((self.home/'.codex/skills/context-keeper').exists())

    def test_non_json_timeout_and_nonzero_are_unknown_with_preserved_journal(self):
        plan=self.plan_ck()
        def runner(argv,**kwargs):
            if '--approved' not in argv:return subprocess.run(argv,**kwargs)
            raise subprocess.TimeoutExpired(argv,1)
        result=self.apply(plan,runner=runner)
        self.assertEqual(result['status'],'unknown')
        self.assertTrue(Path(result['journal']).exists())
        self.assertTrue(self.runtime.registry.exists())

    def _bad_result(self, value, code=0):
        plan=self.plan_ck()
        def runner(argv,**kwargs):
            if '--approved' not in argv:return subprocess.run(argv,**kwargs)
            return SimpleNamespace(returncode=code,stdout=value)
        result=self.apply(plan,runner=runner)
        self.assertEqual(result['status'],'unknown',result)
        self.assertTrue(Path(result['journal']).exists())
        self.assertTrue(self.runtime.registry.exists())

    def test_non_json_success_is_unknown(self):
        self._bad_result('not JSON')

    def test_nonzero_installer_is_unknown(self):
        self._bad_result('failure',2)

    def test_nonboolean_approval_required_is_unknown(self):
        self._bad_result('{"approval_required":"false"}')

    def test_missing_project_is_not_success(self):
        plan=self.plan_ck()
        result={'scope':'user','installed':plan['skill_entries'],'removed':[],
            'bridges':[{'file':p,'action':'created'} for p in plan['rule_files']],
            'configured_agents':['Codex']}
        self._bad_result(json.dumps(result))

    def test_upstream_preview_cannot_mutate_source_or_targets(self):
        def runner(argv,**kwargs):
            result=subprocess.run(argv,**kwargs)
            (self.cksource/'SKILL.md').write_text('changed during preview')
            return result
        with self.assertRaises(ck.CKError):self.plan_ck(runner=runner)

    def test_download_failure_still_has_positive_question_and_safe_next_action(self):
        out=io.StringIO();before=self.snapshot()
        with patch.object(ck, 'prepare_source', side_effect=OSError('download failed')):
            result=ck.tail({'status':'completed'},self.request,stdin=TTY('安装\n'),stderr=out)
        self.assertEqual(result['status'],'completed')
        self.assertEqual(result['context_keeper']['status'],'unavailable')
        self.assertNotIn('同一作者',out.getvalue())
        self.assertIn('--context-keeper',result['context_keeper']['next_action'])
        self.assertEqual(before,self.snapshot())

    def test_tail_ck_failure_keeps_main_completed_and_main_bytes(self):
        original=ck.execute_context_keeper
        def runner(argv,**kwargs):
            if '--approved' not in argv:return subprocess.run(argv,**kwargs)
            return SimpleNamespace(returncode=2,stdout='synthetic failure')
        raw=self.runtime.registry.read_bytes()
        entry=(self.home/'.codex/AGENTS.md').read_bytes()
        with patch.object(ck,'discover_source',return_value=str(self.cksource)),patch.object(
                ck,'execute_context_keeper',side_effect=lambda p,a,**kw:original(p,a,runner=runner,**kw)):
            result=ck.tail({'status':'completed'},self.request,stdin=TTY('安装\n'),stderr=io.StringIO())
        self.assertEqual(result['status'],'completed')
        self.assertEqual(result['context_keeper']['status'],'unknown')
        self.assertEqual(raw,self.runtime.registry.read_bytes())
        self.assertEqual(entry,(self.home/'.codex/AGENTS.md').read_bytes())

    def test_writer_lock_conflict_preserves_existing_lock(self):
        plan=self.plan_ck();self.runtime.lock.mkdir()
        before=self.snapshot()
        with self.assertRaises(ValueError):self.apply(plan)
        self.assertEqual(before,self.snapshot())
        self.assertFalse(Path(plan['journal']).exists())

    def test_interpreter_fingerprint_is_bound_by_exact_replan(self):
        plan=self.plan_ck();plan['interpreter']['fingerprint']['sha256']='0'*64
        before=self.snapshot()
        with self.assertRaises(ck.CKError):self.apply(plan)
        self.assertEqual(before,self.snapshot())

    def test_existing_same_source_alias_reused_without_replacement(self):
        link=self.home/'.agents/skills/context-keeper';link.parent.mkdir(parents=True)
        link.symlink_to(self.cksource)
        before=link.lstat().st_mtime_ns
        result=self.apply()
        self.assertEqual(result['status'],'configured',result)
        self.assertEqual(before,link.lstat().st_mtime_ns)

    def test_other_source_alias_is_not_replaced(self):
        link=self.home/'.agents/skills/context-keeper';link.parent.mkdir(parents=True)
        link.symlink_to(self.source)
        before=self.snapshot()
        with self.assertRaises(ck.CKError):self.plan_ck()
        self.assertEqual(before,self.snapshot())

    def test_block_external_change_is_detected_after_upstream_success(self):
        plan=self.plan_ck()
        def runner(argv,**kwargs):
            result=subprocess.run(argv,**kwargs)
            if '--approved' in argv:
                entry=self.home/'.codex/AGENTS.md';entry.write_bytes(b'external corruption'+entry.read_bytes())
            return result
        result=self.apply(plan,runner=runner)
        self.assertEqual(result['status'],'unknown',result)
        self.assertTrue(self.runtime.registry.exists())

    def test_tty_eof_spaces_skip_and_only_install_consents(self):
        plan=self.plan_ck()
        for value in ('','n\n',' \n','yes\n','\n','跳过\n'):
            with self.subTest(value=value),patch.object(ck,'plan_context_keeper',return_value=plan),patch.object(ck,'execute_context_keeper',side_effect=AssertionError('must not write')):
                result=ck.tail({'status':'completed'},self.request,stdin=TTY(value),stderr=io.StringIO())
                self.assertEqual(result['context_keeper']['status'],'skipped')
        for value in ('安装\n','安装\r\n'):
            with self.subTest(value=value),patch.object(ck,'plan_context_keeper',return_value=plan),patch.object(ck,'execute_context_keeper',return_value={'status':'configured'}) as execute:
                err=io.StringIO();result=ck.tail({'status':'completed'},self.request,stdin=TTY(value),stderr=err)
                self.assertEqual(result['context_keeper']['status'],'configured')
                self.assertNotIn('同一作者',err.getvalue());execute.assert_called_once()
                self.assertLess(err.getvalue().index('公共用户记忆流程已结束'),err.getvalue().index('为了让 Agent'))
                self.assertIn('Codex',err.getvalue())
        with patch.object(ck,'plan_context_keeper',side_effect=AssertionError('non TTY is zero work')):
            result=ck.tail({'status':'completed'},self.request,stdin=io.StringIO('\n'),stderr=io.StringIO())
            self.assertEqual(result['context_keeper']['status'],'pending_selection')
            self.assertEqual(result['context_keeper']['reason'],'user_choice_required')
        with patch.object(ck,'plan_context_keeper',side_effect=AssertionError('main is incomplete')):
            self.assertNotIn('context_keeper',ck.tail({'status':'partial'},self.request,stdin=TTY('安装\n')))

    def test_rule_verifier_handles_existing_blocks_and_workbuddy_relocation(self):
        for agent in ('codex','claude','workbuddy'):
            mid=':workbuddy' if agent=='workbuddy' else ''
            block=('<!-- context-keeper'+mid+':start -->\nnew\n<!-- context-keeper'+mid+':end -->').encode()
            old=block.replace(b'new',b'old');before=b'user\r\n'+old+b'\r\ntail'
            after=(block+b'\n\n'+b'user\r\n\r\ntail' if agent=='workbuddy' else before.replace(old,block))
            ck._verify_rule(before,after,agent)
            with self.assertRaises(ck.CKError):ck._verify_rule(before,after+b'corruption',agent)

from entry_opaque_fixture import assert_opaque, remember_mode
