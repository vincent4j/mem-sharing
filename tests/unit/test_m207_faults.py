"""Project lifecycle fault matrix with synthetic HOME and exact approved snapshots."""
import json
from pathlib import Path
from test_m204_enable import EnableFixture
from agm_core import check, enable, remove


class M207Fixture(EnableFixture):
    def check(self, **fields):
        return check.run(dict(self.request,**fields))
    def remove(self, **fields):
        return remove.run(dict(self.request,approval=None,**fields))
    def remove_approval(self,preview,root=None):
        approval=json.loads(preview['next_action'])
        approval.update(confirmed_at='2026-10-30T00:00:00Z',reference='exact removal approval')
        return approval


class FaultMatrixTests(M207Fixture):
    def test_store_absent_check_is_healthy_and_enable_does_not_create(self):
        self.apply('follow_ck',True);store=self.root/'docs/context-keeper'
        self.assertFalse(store.exists());self.assertEqual(self.check()['status'],'completed')
        self.request.update(approval=None,memory_choice=None)
        self.assertEqual(enable.run(self.request)['status'],'completed');self.assertFalse(store.exists())

    def test_registry_missing_all_commands_conservative(self):
        self.apply('follow_ck',True)
        outputs={p:p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
        self.runtime.registry.unlink();self.request.update(approval=None,memory_choice=None)
        self.assertEqual(enable.run(self.request)['errors'][0]['code'],'machine_not_installed')
        self.assertEqual(self.check()['status'],'gaps')
        self.assertEqual(self.remove()['errors'][0]['code'],'machine_not_installed')
        self.assertEqual({p:p.read_bytes() for p in outputs},outputs)

    def test_corrupt_registry_never_repairs_or_deletes(self):
        self.apply('follow_ck',True);self.runtime.registry.write_bytes(b'{broken')
        before={p:p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
        self.assertEqual(self.check()['status'],'gaps');self.assertEqual(self.remove()['errors'][0]['code'],'registry_invalid')
        self.assertEqual(self.runtime.registry.read_bytes(),b'{broken');self.assertEqual({p:p.read_bytes() for p in before},before)

    def test_directory_conflict_zero_write(self):
        (self.root/'AGENTS.md').mkdir();(self.root/'AGENTS.md/keep').write_bytes(b'occupied')
        self.request['memory_choice']=None
        self.assertEqual(enable.run(self.request)['errors'][0]['code'],'path_conflict')
        self.assertEqual((self.root/'AGENTS.md/keep').read_bytes(),b'occupied')
        self.assertFalse(self.runtime.backups.exists())

    def test_workbuddy_native_bytes_survive_remove(self):
        self.apply('follow_ck',True);entry=self.root/'.workbuddy/memory/MEMORY.md'
        with entry.open('ab') as handle:handle.write(b'native daily log\r\n\xff\xfe')
        preview=self.remove();result=remove.run(dict(self.request,approval=self.remove_approval(preview)))
        self.assertEqual(result['status'],'completed',result)
        self.assertEqual(entry.read_bytes(),b'native daily log\r\n\xff\xfe')

    def test_remove_sets_disabled_and_persists_priority_guard(self):
        self.apply('follow_ck',True);preview=self.remove()
        result=remove.run(dict(self.request,approval=self.remove_approval(preview)))
        self.assertEqual(result['status'],'completed',result)
        self.assertEqual(self.load()['projects'][str(self.root)]['memory_policy'],'disabled')
        raw=(self.root/'AGENTS.md').read_bytes()
        self.assertIn(enable.DENIED_TEXT.encode(),raw);self.assertNotIn(enable.KEEPER_MARKER['start'].encode(),raw)
        self.assertFalse((self.root/'CLAUDE.md').exists())
        self.assertEqual(self.remove()['changes'],[])

    def test_disabled_to_follow_requires_new_explicit_plan(self):
        self.apply('disabled');self.request.update(approval=None,memory_choice=None)
        self.assertEqual(enable.run(self.request)['status'],'completed')
        self.assertEqual(self.load()['projects'][str(self.root)]['memory_policy'],'disabled')
        self.request['memory_choice']='follow_ck'
        preview=enable.run(self.request);self.assertEqual(preview['status'],'approval_required')
        plan=json.loads(preview['next_action']);plan.update(confirmed_at='2026-10-30T00:00:00Z',reference='lift')
        self.request['approval']=plan;self.assertEqual(enable.run(self.request)['status'],'completed')
        self.assertFalse((self.root/'docs/context-keeper').exists())

    def test_legacy_drift_prevents_any_partial_conversion(self):
        self.apply('follow_ck',True);path=self.root/'AGENTS.md'
        data=self.load();a=data['projects'][str(self.root)]['checkouts'][str(self.root)]
        obj=next(o for o in a['objects'].values() if o.get('marker')==enable.KEEPER_MARKER)
        path.write_bytes(path.read_bytes().replace('入口'.encode(),b'edited'))
        before=self.runtime.registry.read_bytes();self.request['approval']=None
        self.assertEqual(enable.run(self.request)['errors'][0]['code'],'drift')
        self.assertEqual(self.remove()['errors'][0]['code'],'drift')
        self.assertEqual(self.runtime.registry.read_bytes(),before)
