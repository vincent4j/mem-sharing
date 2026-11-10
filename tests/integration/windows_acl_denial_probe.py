"""Temporary denial on one new empty fixture; restore on a preheld handle."""
import ctypes as C
import hashlib
import json
import os
from pathlib import Path
import sys
import time
import uuid

PLAN = None


def need(value, message):
    if not value:
        raise RuntimeError(message)


def exercise(runtime, save):
    result = dict(status='failed', started=time.time(), set_attempted=False,
                  production_write_authorized=False, race_free=False, checks=[])
    original = None
    try:
        original = runtime.snapshot()
        result['before'] = original
        runtime.prepare()
        save('backup', original)
        save('intent', dict(result, set_may_change=True,
                            recovery='original descriptor backup; preheld WRITE_DAC handle; never use denied read-open'))
        result['set_attempted'] = True
        runtime.deny()
        result['denied_state'] = runtime.snapshot()
        result['checks'] = runtime.verify_denied()
        result['status'] = 'passed'
    except BaseException as exc:
        result['error'] = dict(type=type(exc).__name__, message=str(exc),
                               winerror=getattr(exc, 'winerror', None))
    finally:
        if result['set_attempted']:
            try:
                # Never reopen the path to obtain restoration authority.
                runtime.restore(original)
                result['after'] = runtime.snapshot()
                need(result['after'] == original, 'Descriptor/control/identity readback differs; preserve')
                runtime.verify_readable()
                result['restore_complete'] = True
            except BaseException as exc:
                result.update(status='needs_inspection', restore_complete=False,
                              restore_error=dict(type=type(exc).__name__, message=str(exc)))
        result['finished'] = time.time()
        save('result', result)
    return result


def main():
    need(PLAN is not None, 'Unbound plan')
    need(sys.flags.optimize == 0 and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode, 'Use -I -S -B')
    root = Path(PLAN['root'])
    os.environ.update(HOME=str(root/'synthetic-home'), USERPROFILE=str(root/'synthetic-home'),
                      TEMP=str(root/'tmp'), TMP=str(root/'tmp'))
    for name, digest in PLAN['sources'].items():
        need(hashlib.sha256((root/'code'/name).read_bytes()).hexdigest() == digest, 'Source drift')
    sys.path.insert(0, str(root/'code/scripts'))
    from agm_core import windows_native as w
    op = str(uuid.uuid4())
    evidence = root/'evidence'/('acl-denial-'+op)
    evidence.mkdir()
    fixture = root/'synthetic-home'/('acl-denial-'+op)

    def save(name, value):
        with (evidence/(name+'.json')).open('x', encoding='utf8') as f:
            json.dump(dict(value, run_id=PLAN['run_id'], operation_id=op, fixture=str(fixture)), f, indent=2)
            f.flush(); os.fsync(f.fileno())

    api = w._API()
    pointer = C.c_void_p
    api.a.SetSecurityInfo.argtypes = [w.HANDLE, C.c_int32, w.DWORD, pointer, pointer, pointer, pointer]
    api.a.SetSecurityInfo.restype = w.DWORD
    api.a.GetSecurityDescriptorControl.argtypes = [pointer, C.POINTER(C.c_uint16), C.POINTER(w.DWORD)]
    api.a.GetSecurityDescriptorControl.restype = w.BOOL
    api.a.GetSecurityDescriptorDacl.argtypes = [pointer, C.POINTER(w.BOOL), C.POINTER(pointer), C.POINTER(w.BOOL)]
    api.a.GetSecurityDescriptorDacl.restype = w.BOOL
    api.a.ConvertStringSecurityDescriptorToSecurityDescriptorW.argtypes = [C.c_wchar_p, w.DWORD, C.POINTER(pointer), C.POINTER(w.DWORD)]
    api.a.ConvertStringSecurityDescriptorToSecurityDescriptorW.restype = w.BOOL
    api.a.ConvertSidToStringSidW.argtypes = [pointer, C.POINTER(pointer)]
    api.a.ConvertSidToStringSidW.restype = w.BOOL
    api.k.GetCurrentProcess.argtypes = []; api.k.GetCurrentProcess.restype = w.HANDLE
    api.a.OpenProcessToken.argtypes = [w.HANDLE, w.DWORD, C.POINTER(w.HANDLE)]
    api.a.OpenProcessToken.restype = w.BOOL
    api.a.GetTokenInformation.argtypes = [w.HANDLE, C.c_int32, pointer, w.DWORD, C.POINTER(w.DWORD)]
    api.a.GetTokenInformation.restype = w.BOOL
    allocated = []

    def user_sid():
        token = w.HANDLE()
        need(api.a.OpenProcessToken(api.k.GetCurrentProcess(), 8, C.byref(token)), 'Token open failed')
        try:
            elevated, n = w.DWORD(), w.DWORD()
            need(api.a.GetTokenInformation(token, 20, C.byref(elevated), 4, C.byref(n)) and n.value == 4 and not elevated.value, 'Ordinary token required')
            api.a.GetTokenInformation(token, 1, None, 0, C.byref(n))
            need(16 <= n.value <= 65536, 'TOKEN_USER size invalid')
            buf = C.create_string_buffer(n.value)
            need(api.a.GetTokenInformation(token, 1, buf, len(buf), C.byref(n)), 'TOKEN_USER query failed')
            sid = C.cast(buf, C.POINTER(pointer))[0]
            text = pointer()
            need(api.a.ConvertSidToStringSidW(sid, C.byref(text)), 'SID conversion failed')
            allocated.append(text)
            value = C.wstring_at(text)
            need(value.startswith('S-1-') and all(c in 'S-0123456789' for c in value), 'SID string invalid')
            return value
        finally:
            api.k.CloseHandle(token)

    def acl_bytes(acl):
        size = C.c_uint16.from_address(acl.value+2).value
        need(8 <= size <= 65535, 'ACL size invalid')
        return C.string_at(acl, size)

    def dacl_from(descriptor):
        present, defaulted, acl = w.BOOL(), w.BOOL(), pointer()
        need(api.a.GetSecurityDescriptorDacl(descriptor, C.byref(present), C.byref(acl), C.byref(defaulted)), 'DACL extraction failed')
        need(present.value and acl.value, 'Absent/NULL DACL refused')
        return acl, bool(defaulted.value)

    # Bind the existing fixture identity before creating a new sibling directory.
    with w.inspect_path(PLAN['case_path'], security=True, candidate_metadata=True) as anchor:
        need(w.same_node(anchor, PLAN['identity']) and anchor['security']['sha256'] == PLAN['security_sha256'], 'Anchor drift')
        need(anchor['case_sensitive_directory'] is False, 'Restored anchor required')
        sid = user_sid()
        save('preflight', dict(token_elevated=False, sources=PLAN['sources'],
                               environment={x:os.environ.get(x) for x in ('HOME','USERPROFILE','TEMP','TMP','SystemRoot')},
                               anchor_identity=PLAN['identity']))
        fixture.mkdir()
        h = api.k.CreateFileW(str(fixture), 0x20000 | 0x40000 | 0x80, 3, None, 3, 0x02200000, None)
        need(h not in (None, C.c_void_p(-1).value), 'Preheld READ_CONTROL/WRITE_DAC/READ_ATTRIBUTES unavailable')
        try:
            identity = api.inspect(h, str(fixture))

            class Runtime:
                original_acl = None
                original_control = None
                replacement_acl = None
                denial_active = False
                last_acl = None

                def snapshot(self):
                    owner, group, acl, sacl, sd = [pointer() for _ in range(5)]
                    error = api.a.GetSecurityInfo(h, 1, 7, C.byref(owner), C.byref(group), C.byref(acl), C.byref(sacl), C.byref(sd))
                    if sd.value:
                        allocated.append(sd)
                    need(error == 0 and sd.value and api.a.IsValidSecurityDescriptor(sd), 'Security snapshot unavailable')
                    length = api.a.GetSecurityDescriptorLength(sd)
                    need(20 <= length <= 1048576, 'Security descriptor length invalid')
                    control, revision = C.c_uint16(), w.DWORD()
                    need(api.a.GetSecurityDescriptorControl(sd, C.byref(control), C.byref(revision)), 'Control query failed')
                    dacl, defaulted = dacl_from(sd)
                    current = api.inspect(h, str(fixture))
                    need(w.same_node(current, identity), 'Fixture identity drift')
                    if not self.denial_active:
                        need(not list(fixture.iterdir()), 'Fixture nonempty drift')
                    self.last_acl = dacl
                    if self.original_acl is None:
                        self.original_acl, self.original_control = dacl, control.value
                    raw = C.string_at(sd, length)
                    return dict(descriptor_hex=raw.hex(), descriptor_sha256=hashlib.sha256(raw).hexdigest(),
                                control=control.value, revision=revision.value, dacl_defaulted=defaulted,
                                identity=dict(volume_id=current['volume_id'], file_id=current['file_id']), empty=None if self.denial_active else True)

                def prepare(self):
                    sd, length = pointer(), w.DWORD()
                    need(api.a.ConvertStringSecurityDescriptorToSecurityDescriptorW('D:P(D;;0x80;;;'+sid+')(A;;FA;;;'+sid+')', 1, C.byref(sd), C.byref(length)), 'Deny descriptor conversion failed')
                    allocated.append(sd)
                    self.replacement_acl, _ = dacl_from(sd)

                def deny(self):
                    self.denial_active = True
                    error = api.a.SetSecurityInfo(h, 1, 4 | 0x80000000, None, None, self.replacement_acl, None)
                    need(error == 0, 'Set deny DACL failed: '+str(error))

                def verify_denied(self):
                    try:
                        with w.inspect_candidate_path(str(fixture), allowed_root=str(root/'synthetic-home')):
                            pass
                    except w.NativeInspectionError as exc:
                        need(exc.code == 'node_open_failed' and exc.winerror == 5, 'Unexpected refusal '+exc.code)
                        return [dict(name='real_access_denied_refused', status='passed', code=exc.code, winerror=exc.winerror)]
                    raise RuntimeError('Denied candidate was admitted')

                def restore(self, original):
                    need(self.original_acl is not None and original['control'] == self.original_control, 'Missing original restoration state')
                    # Refuse a foreign DACL rather than overwriting concurrent changes.
                    self.snapshot()
                    need(acl_bytes(self.last_acl) in (acl_bytes(self.original_acl), acl_bytes(self.replacement_acl)), 'Foreign DACL drift; preserve')
                    # No automatic retry; same original handle and live original buffer.
                    error = api.a.SetSecurityInfo(h, 1, 4 | (0x80000000 if self.original_control & 0x1000 else 0x20000000), None, None, self.original_acl, None)
                    need(error == 0, 'Restore DACL failed: '+str(error))
                    self.denial_active = False

                def verify_readable(self):
                    with w.inspect_path(str(fixture), security=True) as reopened:
                        need(w.same_node(reopened, identity), 'Restored new-open identity differs')

            result = exercise(Runtime(), save)
        finally:
            api.k.CloseHandle(h)
            free_errors = []
            for allocation in reversed(allocated):
                if api.k.LocalFree(allocation):
                    free_errors.append('LocalFree returned non-NULL')
            if free_errors:
                save('allocation-errors', dict(errors=free_errors))
                result['status'] = 'needs_inspection'
                result['allocation_errors'] = free_errors
    save('completion', dict(result, held_anchor_exit_revalidated=True, fixture_preserved=True))
    print(json.dumps(dict(status=result['status'], restore_complete=result.get('restore_complete'), evidence=str(evidence))))
    return 0 if result['status'] == 'passed' and result.get('restore_complete') else 2


if __name__ == '__main__':
    raise SystemExit(main())
