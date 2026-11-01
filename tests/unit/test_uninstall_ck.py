"""Separate CK choice; fake installers plus optional copied real upstream code."""
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

import test_uninstall as fixtures
from agm_core import uninstall_recovery as recovery

INSTALLER = '''import json,os,sys
from pathlib import Path
home=Path(os.environ['HOME']);source=Path(__file__).resolve().parents[1]
skills=[home/'.agents/skills/context-keeper',home/'.codex/skills/context-keeper']
rules=[home/'.codex/AGENTS.md']
if '--uninstall' not in sys.argv or '--codex' not in sys.argv:raise SystemExit(6)
if '--all' in sys.argv:raise SystemExit(7)
if (home/'.agents/skills/context-keeper').exists():
    print('shared root requires explicit full host scope',file=sys.stderr);raise SystemExit(5)
if '--approved' not in sys.argv:
    print(json.dumps({'approval_required':True,'operation':'卸载','skill_entries':[str(p) for p in skills],
                      'rule_files':[str(p) for p in rules],'effect':'only own controls'}))
elif (home/'fail-ck').exists():
    print('synthetic CK failure',file=sys.stderr);raise SystemExit(8)
else:
    (home/'ck-uninstalled').write_text('approved separate CK operation')
    removed=[]
    for target in skills:
        action='removed_symlink' if target.is_symlink() else 'absent'
        if target.is_symlink():target.unlink()
        removed.append({'path':str(target),'action':action})
    bridge=rules[0];text=bridge.read_bytes().decode();first='<!-- context-keeper:start -->';last='<!-- context-keeper:end -->'
    start,end=text.find(first),text.find(last);action='absent'
    if start>=0:
        text=(text[:start].rstrip()+'\\n\\n'+text[end+len(last):].lstrip('\\n')).strip()
        if text:bridge.write_text(text+'\\n');action='removed'
        else:bridge.unlink();action='removed_file'
    print(json.dumps({'scope':'user','project':None,'installed':[],'removed':removed,
                      'bridges':[{'file':str(bridge),'action':action}],'configured_agents':['Codex']}))
'''


class CKFollowupTests(unittest.TestCase):
    def setUp(self):
        self.fixture=fixtures.UninstallTests();self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.home=self.fixture.home;self.area=self.fixture.area
        self.source=self.area/'ck-source';(self.source/'scripts').mkdir(parents=True)
        (self.source/'SKILL.md').write_text('name: context-keeper\n')
        (self.source/'scripts/install.py').write_text(INSTALLER)
        self.refresh_package()
        link=self.home/'.codex/skills/context-keeper';link.parent.mkdir(parents=True);link.symlink_to(self.source)
        self.fixture.entry.write_bytes(self.fixture.entry.read_bytes()+b'\n<!-- context-keeper:start -->\nCK rule\n<!-- context-keeper:end -->\n')
        self.fixture.apply_uninstall()
        self.manifest=self.fixture.backup/'manifest.json'

    def refresh_package(self):
        files=[{'path':name,'sha256':recovery.digest((self.source/name).read_bytes())}
               for name in ('SKILL.md','scripts/install.py')]
        (self.source/'manifest.json').write_text(json.dumps({'type':'skill','code':'context-keeper','files':files}))

    def preview(self):
        return recovery.ck_followup(self.manifest,choice='uninstall',source=self.source,agents=['codex'])

    def test_default_retain_no_write_and_incomplete_or_changed_main_rejected(self):
        before=recovery.tree(self.home);saved=self.manifest.read_bytes()
        retained=recovery.ck_followup(self.manifest)
        self.assertEqual(retained['status'],'retained')
        self.assertEqual(retained['scope'],'standalone_declared')
        self.assertEqual(retained['host_plugin'],'not_applicable')
        self.assertEqual(recovery.tree(self.home),before)
        data=json.loads(saved);data['status']='prepared';self.manifest.write_text(json.dumps(data))
        with self.assertRaises(ValueError):self.preview()
        self.manifest.write_bytes(saved)
        self.fixture.entry.write_bytes(self.fixture.entry.read_bytes()+b'later private edit')
        with self.assertRaises(ValueError):self.preview()
        self.assertFalse((self.home/'ck-uninstalled').exists())

    def test_distinct_approval_and_exact_source_targets_preview_binding(self):
        saved=self.manifest.read_bytes();view=self.preview()
        self.assertEqual(view['status'],'approval_required')
        self.assertFalse((self.home/'ck-uninstalled').exists())
        main=json.loads(saved)['approval']
        with self.assertRaises(ValueError):
            recovery.ck_followup(self.manifest,choice='uninstall',source=self.source,agents=['codex'],approval=main)
        with patch.object(recovery.subprocess,'run',wraps=subprocess.run) as run:
            result=recovery.ck_followup(self.manifest,choice='uninstall',source=self.source,agents=['codex'],
                                       approval=fixtures.approval(view['plan']))
        self.assertEqual(result['status'],'completed')
        args=[call.args[0] for call in run.call_args_list]
        self.assertEqual(len(args),2)
        self.assertNotIn('--approved',args[0]);self.assertEqual(args[1],args[0]+['--approved'])
        self.assertEqual(args[0][1:4],['-I','-S','-B'])
        self.assertNotIn('--all',args[0])
        self.assertTrue((self.home/'ck-uninstalled').exists())
        self.assertEqual(self.manifest.read_bytes(),saved)

    def test_ck_failure_does_not_rewrite_main_completed(self):
        (self.home/'fail-ck').write_text('synthetic failure')
        before=self.manifest.read_bytes();view=self.preview()
        result=recovery.ck_followup(self.manifest,choice='uninstall',source=self.source,agents=['codex'],
                                   approval=fixtures.approval(view['plan']))
        self.assertEqual(result['status'],'failed')
        self.assertEqual(result['main_status'],'completed')
        self.assertEqual(self.manifest.read_bytes(),before)

    def test_rc_zero_malformed_or_no_effect_is_ck_failure_only(self):
        saved=self.manifest.read_bytes();view=self.preview()
        original=recovery._ck_run
        claimed={'scope':'user','project':None,'installed':[],
                 'removed':[{'path':p,'action':'removed_symlink' if Path(p).is_symlink() else 'absent'}
                            for p in view['plan']['preview']['skill_entries']],
                 'bridges':[{'file':str(self.fixture.entry),'action':'removed'}],
                 'configured_agents':['Codex']}
        for stdout in ('not JSON','{}',json.dumps(claimed)):
            with self.subTest(stdout=stdout):
                def run(argv,**kwargs):
                    if '--approved' in argv:return subprocess.CompletedProcess(argv,0,stdout=stdout,stderr='')
                    return original(argv,**kwargs)
                with patch.object(recovery,'_ck_run',side_effect=run):
                    result=recovery.ck_followup(self.manifest,choice='uninstall',source=self.source,agents=['codex'],
                                               approval=fixtures.approval(view['plan']))
                self.assertEqual(result['status'],'failed')
                self.assertEqual(result['exit_code'],0)
                self.assertEqual(result['main_status'],'completed')
                self.assertEqual(self.manifest.read_bytes(),saved)
                self.assertTrue((self.home/'.codex/skills/context-keeper').is_symlink())
                self.assertIn(b'<!-- context-keeper:start -->',self.fixture.entry.read_bytes())
        def remove_skill_only(argv,**kwargs):
            if '--approved' not in argv:return original(argv,**kwargs)
            (self.home/'.codex/skills/context-keeper').unlink()
            return subprocess.CompletedProcess(argv,0,stdout=json.dumps(claimed),stderr='')
        with patch.object(recovery,'_ck_run',side_effect=remove_skill_only):
            result=recovery.ck_followup(self.manifest,choice='uninstall',source=self.source,agents=['codex'],
                                       approval=fixtures.approval(view['plan']))
        self.assertEqual(result['status'],'failed')
        self.assertIn('rule removal',result['errors'][0]['message'])
        self.assertEqual(self.manifest.read_bytes(),saved)

    def test_copied_real_upstream_installer_contract_in_temporary_home(self):
        candidate=os.environ.get('CK_UPSTREAM_INSTALLER_FIXTURE')
        if not candidate:self.skipTest('Set CK_UPSTREAM_INSTALLER_FIXTURE for copied real-upstream fixture acceptance')
        upstream=Path(candidate)
        installer=upstream.read_bytes();skill=(upstream.parent.parent/'SKILL.md').read_bytes()
        (self.source/'scripts/install.py').write_bytes(installer)
        (self.source/'SKILL.md').write_bytes(skill)
        self.refresh_package()
        saved=self.manifest.read_bytes();source_before=recovery.digest(installer)
        view=self.preview()
        self.assertEqual(view['status'],'approval_required')
        result=recovery.ck_followup(self.manifest,choice='uninstall',source=self.source,agents=['codex'],
                                   approval=fixtures.approval(view['plan']))
        self.assertEqual(result['status'],'completed',result)
        self.assertEqual(result['result']['configured_agents'],['Codex'])
        self.assertFalse(os.path.lexists(self.home/'.codex/skills/context-keeper'))
        self.assertNotIn(b'<!-- context-keeper:start -->',self.fixture.entry.read_bytes())
        self.assertEqual(self.manifest.read_bytes(),saved)
        self.assertEqual(recovery.digest(upstream.read_bytes()),source_before)

    def test_source_drift_unknown_host_and_shared_root_never_expand_scope(self):
        view=self.preview()
        (self.source/'scripts/install.py').write_text(INSTALLER+'\n# changed source\n')
        with self.assertRaises(ValueError):
            recovery.ck_followup(self.manifest,choice='uninstall',source=self.source,agents=['codex'],
                                 approval=fixtures.approval(view['plan']))
        self.refresh_package()
        with self.assertRaises(ValueError):
            recovery.ck_followup(self.manifest,choice='uninstall',source=self.source,agents=['dsh'])
        shared=self.home/'.agents/skills/context-keeper';shared.parent.mkdir(parents=True);shared.symlink_to(self.source)
        self.assertEqual(self.preview()['status'],'failed')
        self.assertTrue(shared.is_symlink())

    def test_external_cli_ck_branch_retains_and_default_still_previews_restore(self):
        runner=self.fixture.backup/'recover.py'
        base=[sys.executable,'-I','-S','-B',str(runner),'--manifest',str(self.manifest)]
        child=subprocess.run(base+['--ck-choice','retain'],capture_output=True,text=True,timeout=30)
        self.assertEqual(child.returncode,0,child.stdout+child.stderr)
        self.assertEqual(json.loads(child.stdout)['status'],'retained')
        child=subprocess.run(base,capture_output=True,text=True,timeout=30)
        self.assertEqual(child.returncode,5,child.stdout+child.stderr)
        self.assertEqual(json.loads(child.stdout)['plan']['command'],'recover-uninstall')
        ck=base+['--ck-choice','uninstall','--ck-source',str(self.source),'--ck-agent','codex']
        child=subprocess.run(ck,capture_output=True,text=True,timeout=30)
        self.assertEqual(child.returncode,5,child.stdout+child.stderr)
        self.assertEqual(json.loads(child.stdout)['plan']['command'],'uninstall-context-keeper')
        bad=base+['--ck-choice','uninstall','--ck-source',str(self.area/'unknown'),'--ck-agent','codex']
        child=subprocess.run(bad,capture_output=True,text=True,timeout=30)
        self.assertEqual(child.returncode,2,child.stdout+child.stderr)
        self.assertEqual(json.loads(child.stdout)['status'],'failed')
