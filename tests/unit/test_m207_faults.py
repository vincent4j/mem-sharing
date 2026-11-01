"""Project lifecycle fault matrix with synthetic HOME and exact approved snapshots."""
import json
from pathlib import Path
from test_m204_enable import EnableFixture
from agm_core import check, enable


class M207Fixture(EnableFixture):
    def check(self, **fields):
        return check.run(dict(self.request,**fields))


class FaultMatrixTests(M207Fixture):
    def test_store_absent_check_is_healthy_and_enable_does_not_create(self):
        self.apply(None,True);store=self.root/'docs/context-keeper'
        self.assertFalse(store.exists());self.assertEqual(self.check()['status'],'completed')
        self.request.update(approval=None)
        self.assertEqual(enable.run(self.request)['status'],'completed');self.assertFalse(store.exists())

    def test_registry_missing_all_commands_conservative(self):
        self.apply(None,True)
        outputs={p:p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
        self.runtime.registry.unlink();self.request.update(approval=None)
        self.assertEqual(enable.run(self.request)['errors'][0]['code'],'machine_not_installed')
        self.assertEqual(self.check()['status'],'gaps')
        self.assertEqual({p:p.read_bytes() for p in outputs},outputs)

    def test_corrupt_registry_never_repairs_or_deletes(self):
        self.apply(None,True);self.runtime.registry.write_bytes(b'{broken')
        before={p:p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
        self.assertEqual(self.check()['status'],'gaps')
        self.assertEqual(enable.run(self.request)['errors'][0]['code'],'registry_invalid')
        self.assertEqual(self.runtime.registry.read_bytes(),b'{broken');self.assertEqual({p:p.read_bytes() for p in before},before)

    def test_directory_conflict_zero_write(self):
        (self.root/'AGENTS.md').mkdir();(self.root/'AGENTS.md/keep').write_bytes(b'occupied')
        self.assertEqual(enable.run(self.request)['errors'][0]['code'],'path_conflict')
        self.assertEqual((self.root/'AGENTS.md/keep').read_bytes(),b'occupied')
        self.assertFalse(self.runtime.backups.exists())

    def test_workbuddy_native_bytes_survive_tombstone_skip(self):
        # 保全断言承接:原生 WorkBuddy 私有字节在默认跳过下原样保留。
        self.apply(None,True);entry=self.root/'.workbuddy/memory/MEMORY.md'
        with entry.open('ab') as handle:handle.write(b'native daily log\r\n\xff\xfe')
        self.apply_tombstone();self.request.update(approval=None)
        result=enable.run(self.request)
        self.assertEqual(result['status'],'gaps',result)
        self.assertTrue(entry.read_bytes().endswith(b'native daily log\r\n\xff\xfe'))  # 受管块原样+私有日志保全

    def test_tombstone_registry_keeps_disabled_and_default_no_rebuild(self):
        # 历史停用登记(承接旧 remove 的终态):默认流程不重建、政策保持 disabled、零写入。
        self.apply(None,True);self.apply_tombstone();self.request.update(approval=None)
        result=enable.run(self.request)
        self.assertEqual(result['status'],'gaps',result)
        self.assertEqual(self.load()['projects'][str(self.root)]['memory_policy'],'disabled')
        raw=(self.root/'AGENTS.md').read_bytes()
        self.assertIn(enable.KEEPER_MARKER['start'].encode(),raw)  # 入口按登记保留,不宣称已撤
        self.assertNotIn(enable.DENIED_MARKER['start'].encode(),raw)  # 也不再渲染任何 denied
        self.assertTrue((self.root/'CLAUDE.md').exists())

    def test_retired_switch_is_rejected_not_a_lift_request(self):
        # 退役开关显式传值=零写拒绝,不存在「解除 disabled」路径(重新接入本轮未定义)。
        self.apply(None,True);self.apply_tombstone();self.request.update(approval=None)
        result=enable.run(dict(self.request,memory_choice='follow_ck'))
        self.assertEqual(result['status'],'failed',result)
        self.assertEqual(result['errors'][0]['code'],'retired_option',result)
        self.assertEqual(self.load()['projects'][str(self.root)]['memory_policy'],'disabled')
        self.assertFalse((self.root/'docs/context-keeper').exists())

    def test_legacy_drift_prevents_any_partial_conversion(self):
        self.apply(None,True);path=self.root/'AGENTS.md'
        data=self.load();a=data['projects'][str(self.root)]['checkouts'][str(self.root)]
        obj=next(o for o in a['objects'].values() if o.get('marker')==enable.KEEPER_MARKER)
        path.write_bytes(path.read_bytes().replace('入口'.encode(),b'edited'))
        before=self.runtime.registry.read_bytes();self.request['approval']=None
        self.assertEqual(enable.run(self.request)['errors'][0]['code'],'drift')
        self.assertEqual(self.runtime.registry.read_bytes(),before)
