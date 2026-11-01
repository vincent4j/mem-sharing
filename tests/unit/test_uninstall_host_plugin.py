"""Temporary HOME + fake independent CLI, never real Paseo management."""
import json
import subprocess
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

import test_uninstall as fixtures
from agm_core import uninstall, uninstall_recovery as recovery


class HostPluginTests(unittest.TestCase):
    def setUp(self):
        self.fixture=fixtures.UninstallTests();self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.area=self.fixture.area
        self.source=self.area/'candidate-source';self.source.mkdir()
        (self.source/'plugin.json').write_text('{"id":"mem-sharing"}')
        self.row={'id':'custom-install-alias','path':str(self.source),'enabled':True,'status':'running',
                  'installation':{'identity':{'kind':'directory','path':str(self.source)}}}
        self.obligation={'kind':'paseo-plugin','plugin_id':self.row['id'],'source_dir':str(self.source),
                         'source_tree_sha256':recovery.digest(recovery.encoded(recovery.tree(self.source))),
                         'manifest_sha256':None,'host':'synthetic-host','required_state':'removed',
                         'aliases':[{'id':self.row['id'],'source':'directory','path':str(self.source),'enabled':True}]}
        self.target={'kind':'home','value':str(self.area/'explicit-daemon')}
        self.state=self.area/'fake-cli-state.json'
        self.write_state()
        self.cli=self.area/'paseo-fake'
        self.cli.write_text('#!'+sys.executable+'\n'+'''import json,sys
from pathlib import Path
state=json.loads(Path('''+repr(str(self.state))+''').read_text())
if sys.argv[-2:]!=['--home','''+repr(self.target['value'])+''']:raise SystemExit(9)
if state.get('fail'):raise SystemExit(7)
if sys.argv[1:2]==['status']:
    print(json.dumps({'connectedDaemon':state.get('connected','reachable'),'serverId':state['server']}))
elif sys.argv[1:3]==['plugin','ls']:
    print(json.dumps(state['rows']))
else:raise SystemExit(8) # No remove/enable command is ever authorized here.
''');self.cli.chmod(0o700)
        plan=uninstall.preview(home=self.fixture.home,backup_dir=self.fixture.backup,host_obligation=self.obligation)
        self.result=uninstall.execute(fixtures.approval(recovery.summary(plan)),home=self.fixture.home,
                                      backup_dir=self.fixture.backup,host_obligation=self.obligation)
        self.manifest=self.fixture.backup/'manifest.json'

    def write_state(self,rows=None,server='server-original',**kwargs):
        self.state.write_text(json.dumps({'rows':[self.row] if rows is None else rows,'server':server,**kwargs}))

    def bind(self):
        result=recovery.bind_host_plugin(self.manifest,cli=self.cli,target=self.target)
        self.assertEqual(result['status'],'approval_required')
        return recovery.bind_host_plugin(self.manifest,cli=self.cli,target=self.target,
                                         approval=fixtures.approval(result['plan']))

    def test_independent_binding_live_absence_and_metadata(self):
        self.assertEqual(self.result['machine_assets'],'completed')
        self.assertEqual(self.result['scope'],'machine_and_paseo')
        self.assertEqual(self.result['overall'],'partial')
        before=self.manifest.read_bytes()
        preview=recovery.bind_host_plugin(self.manifest,cli=self.cli,target=self.target)
        self.assertFalse((self.manifest.parent/'host-binding.json').exists())
        with self.assertRaises(ValueError):
            recovery.bind_host_plugin(self.manifest,cli=self.cli,target=self.target,
                                       approval=json.loads(before)['approval'])
        self.bind()
        self.assertEqual(recovery.check_host_plugin(self.manifest)['host_plugin'],'pending')
        self.write_state(rows=[])
        result=recovery.check_host_plugin(self.manifest)
        self.assertEqual(result['host_plugin'],'removed');self.assertEqual(result['overall'],'completed')
        self.assertEqual(self.manifest.read_bytes(),before)
        self.assertEqual(preview['plan']['host_obligation']['plugin_id'],'custom-install-alias')

    def test_retain_reports_live_host_state_without_changing_manifest(self):
        original=self.manifest.read_bytes()
        unbound=recovery.ck_followup(self.manifest)
        self.assertEqual(unbound['status'],'retained')
        self.assertEqual(unbound['host_plugin'],'pending')
        self.assertEqual(unbound['overall'],'partial')
        self.bind()
        for state,kwargs,overall in (
                ('pending',{},'partial'),
                ('disabled',{'rows':[dict(self.row,enabled=False,status='disabled')]},'partial'),
                ('removed',{'rows':[]},'completed'),
                ('pending',{'rows':[],'fail':True},'partial')):
            with self.subTest(state=state,kwargs=kwargs):
                self.write_state(**kwargs)
                before=recovery.tree(self.fixture.home)
                result=recovery.ck_followup(self.manifest)
                self.assertEqual(result['status'],'retained')
                self.assertEqual(result['scope'],'machine_and_paseo')
                self.assertEqual(result['host_plugin'],state)
                self.assertEqual(result['overall'],overall)
                self.assertEqual(self.manifest.read_bytes(),original)
                self.assertEqual(recovery.tree(self.fixture.home),before)

    def test_declared_standalone_scope_and_omission_cannot_remove_bound_obligation(self):
        fresh=fixtures.UninstallTests();fresh.setUp();self.addCleanup(fresh.doCleanups)
        standalone=uninstall.preview(home=fresh.home,backup_dir=fresh.backup)
        self.assertEqual(recovery.summary(standalone)['scope'],'standalone_declared')
        self.assertEqual(recovery.completion_metadata(standalone),{
            'scope':'standalone_declared','machine_assets':'completed',
            'host_plugin':'not_applicable','overall':'completed'})
        bound=uninstall.preview(home=fresh.home,backup_dir=fresh.backup,host_obligation=self.obligation)
        self.assertEqual(recovery.summary(bound)['scope'],'machine_and_paseo')
        before=recovery.tree(fresh.home)
        # A formerly approved obligation cannot be dropped by omitting CLI/API options.
        with self.assertRaisesRegex(ValueError,'Approval does not match'):
            uninstall.execute(fixtures.approval(recovery.summary(bound)),home=fresh.home,backup_dir=fresh.backup)
        self.assertEqual(recovery.tree(fresh.home),before)
        self.assertFalse(fresh.backup.exists())
        original=self.manifest.read_bytes()
        result=recovery.ck_followup(self.manifest)
        self.assertEqual(result['scope'],'machine_and_paseo')
        self.assertEqual(result['host_plugin'],'pending')
        self.assertEqual(result['overall'],'partial')
        self.assertEqual(self.manifest.read_bytes(),original)

    def test_initial_absence_or_wrong_source_never_binds(self):
        for rows in ([],[{**self.row,'path':str(self.area)}],
                     [{**self.row,'installation':{'identity':{'kind':'directory','path':str(self.area)}}}],
                     [self.row,self.row],[self.row,dict(self.row,id='another-alias',enabled=False,status='disabled')]):
            with self.subTest(rows=rows):
                self.write_state(rows=rows)
                with self.assertRaises(ValueError):recovery.bind_host_plugin(self.manifest,cli=self.cli,target=self.target)
                self.assertFalse((self.manifest.parent/'host-binding.json').exists())

    def test_query_failure_changed_daemon_disabled_and_shape_stay_pending(self):
        self.bind()
        for kwargs in ({'rows':[],'fail':True},{'rows':[],'server':'another-daemon'},
                       {'rows':[],'connected':'unreachable'},
                       {'rows':[dict(self.row,enabled=False,status='disabled')]},
                       {'rows':{'enabled':False,'status':'disabled'}},
                       {'rows':[dict(self.row,id='new-alias',enabled=False,status='disabled')]}):
            with self.subTest(kwargs=kwargs):
                self.write_state(**kwargs)
                result=recovery.check_host_plugin(self.manifest)
                self.assertNotEqual(result['host_plugin'],'removed');self.assertEqual(result['overall'],'partial')
                self.assertEqual(recovery.exit_code(result),2)
                with patch.object(recovery,'_ck_source',side_effect=AssertionError('CK must remain locked')):
                    self.assertEqual(recovery.ck_followup(self.manifest,choice='uninstall',source='/unused',agents=['codex'])['status'],'pending')

    def test_cli_identity_and_binding_approval_drift(self):
        self.bind();self.write_state(rows=[])
        self.cli.write_text(self.cli.read_text()+'\n# changed CLI\n')
        self.assertEqual(recovery.check_host_plugin(self.manifest)['status'],'pending')
        self.assertEqual(recovery.ck_followup(self.manifest)['status'],'retained')

    def test_directory_loading_with_managed_git_provenance_and_unknown_kind(self):
        # Official listPlugins exposes identity.kind/remote; managed Git installs
        # still publish config source=directory and the final plugin path.
        git={'kind':'git','remote':'https://example.invalid/synthetic-source.git'}
        self.row['installation']={'identity':git}
        self.write_state()
        preview=recovery.bind_host_plugin(self.manifest,cli=self.cli,target=self.target)
        self.assertEqual(preview['plan']['plugin']['installation']['identity'],git)
        self.assertEqual(preview['plan']['host_obligation']['aliases'][0]['source'],'directory')
        self.row['installation']={'identity':{'kind':'unrecognized'}};self.write_state()
        with self.assertRaisesRegex(ValueError,'Unknown plugin source identity'):
            recovery.bind_host_plugin(self.manifest,cli=self.cli,target=self.target)
        self.row['installation']={'identity':dict(git,remote='https://example.invalid/changed.git')};self.write_state()
        with self.assertRaisesRegex(ValueError,'Approval does not match'):
            recovery.bind_host_plugin(self.manifest,cli=self.cli,target=self.target,approval=fixtures.approval(preview['plan']))
        self.row['installation']={'identity':git};self.write_state();self.bind()
        binding=json.loads((self.manifest.parent/'host-binding.json').read_text())
        self.assertEqual(binding['plan']['plugin']['installation'],{'identity':git})
        self.write_state(rows=[])
        self.assertEqual(recovery.check_host_plugin(self.manifest)['host_plugin'],'removed')

    def test_copied_standalone_cli_codes_and_ck_gate(self):
        base=[sys.executable,'-I','-S','-B',str(self.manifest.parent/'recover.py'),'--manifest',str(self.manifest)]
        pending=subprocess.run(base+['--check-host-plugin'],capture_output=True,text=True)
        self.assertEqual(pending.returncode,2)
        self.assertEqual(json.loads(pending.stdout)['status'],'pending')
        bind=base+['--bind-host-plugin','--paseo-cli',str(self.cli),'--paseo-home',self.target['value']]
        preview=subprocess.run(bind,capture_output=True,text=True)
        self.assertEqual(preview.returncode,5,preview.stdout)
        approved=self.area/'binding-approval.json'
        approved.write_bytes(recovery.encoded(fixtures.approval(json.loads(preview.stdout)['plan'])))
        execute=subprocess.run(bind+['--host-binding-approval-file',str(approved)],capture_output=True,text=True)
        self.assertEqual(execute.returncode,0,execute.stdout)
        self.write_state(rows=[dict(self.row,enabled=False,status='disabled')])
        ck=subprocess.run(base+['--ck-choice','uninstall','--ck-source','/unused','--ck-agent','codex'],capture_output=True,text=True)
        self.assertEqual(ck.returncode,2);self.assertEqual(json.loads(ck.stdout)['host_plugin'],'disabled')
        self.write_state(rows=[])
        check=subprocess.run(base+['--check-host-plugin'],capture_output=True,text=True)
        self.assertEqual(check.returncode,0,check.stdout)
        self.assertEqual(json.loads(check.stdout)['host_plugin'],'removed')
        # No target replacement accepted on either check or CK.
        wrong=subprocess.run(base+['--check-host-plugin','--paseo-home',self.target['value']],capture_output=True,text=True)
        self.assertEqual(wrong.returncode,2)

    def test_approval_binds_target_server_and_source(self):
        preview=recovery.bind_host_plugin(self.manifest,cli=self.cli,target=self.target)
        self.write_state(server='replacement')
        with self.assertRaises(ValueError):
            recovery.bind_host_plugin(self.manifest,cli=self.cli,target=self.target,approval=fixtures.approval(preview['plan']))
        self.assertFalse((self.manifest.parent/'host-binding.json').exists())
        self.write_state();(self.source/'new').write_text('source changed')
        with self.assertRaises(ValueError):recovery.bind_host_plugin(self.manifest,cli=self.cli,target=self.target)


if __name__=='__main__':unittest.main()
