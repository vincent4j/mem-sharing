"""WorkBuddy pointer follows actual native use; CK's old block needs explicit review."""
from test_m204_enable import EnableFixture
from agm_core import enable


class WorkBuddyProtocolTests(EnableFixture):
    def test_existing_legacy_block_requires_explicit_review_then_replaces(self):
        self.request['agents']=['workbuddy']
        path=self.root/'.workbuddy/memory/MEMORY.md';path.parent.mkdir(parents=True)
        old=enable._block(enable.LEGACY_WORKBUDDY_MARKER,'legacy WB rules')
        path.write_bytes(old+b'\n\n# existing notes\r\n\xff')
        before=path.read_bytes();plan=self.preview('follow_ck')
        self.assertEqual(path.read_bytes(),before)
        self.assertEqual(plan['legacy_bridge_transition'][0]['ownership'],'reused')
        self.request['approval']=plan;self.assertEqual(enable.run(self.request)['status'],'completed')
        self.assertTrue(path.read_bytes().startswith(enable.WORKBUDDY_MARKER['start'].encode()))
        self.assertTrue(path.read_bytes().endswith(b'\n\n# existing notes\r\n\xff'))
        self.assertEqual(self.calls,[])

    def test_workbuddy_pointer_drift_stops_whole_order(self):
        self.apply('follow_ck',True)
        path=self.root/'.workbuddy/memory/MEMORY.md';path.write_bytes(path.read_bytes().replace(b'AGENTS.md',b'OTHER.md'))
        before=path.read_bytes(),self.runtime.registry.read_bytes();self.request['approval']=None
        self.assertEqual(enable.run(self.request)['errors'][0]['code'],'drift')
        self.assertEqual((path.read_bytes(),self.runtime.registry.read_bytes()),before)

    def test_no_template_or_install_dependency(self):
        (self.source/'scripts/install.py').write_bytes(b'invalid python !!')
        self.apply('follow_ck',True)
        self.assertEqual(self.calls,[])

    def test_native_symlink_directory_fails_closed(self):
        target=self.area/'native';target.mkdir();path=self.root/'.workbuddy/memory';path.parent.mkdir();path.symlink_to(target)
        self.assertEqual(enable.run(self.request)['errors'][0]['code'],'path_conflict')
        self.assertFalse((self.root/'AGENTS.md').exists())
        self.assertEqual(list(target.iterdir()),[])
