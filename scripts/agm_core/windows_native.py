"""Read-only Windows handle inspection. Never a production write authorization.

Read-attributes handles do not guarantee rename exclusion on all Windows paths. The
absolute-path walk is not an atomic relative-handle traversal: external writers
can still change metadata. All ancestors and final-handle names are rechecked.
Sources: Microsoft CreateFileW, GetFileInformationByHandleEx, FILE_ID_INFO,
FILE_ATTRIBUTE_TAG_INFO, GetFinalPathNameByHandleW, GetVolumeInformationByHandleW,
GetSecurityInfo and LocalFree documentation (see Windows validation record).
"""
import base64
from contextlib import contextmanager
import ctypes as C
import hashlib
import ntpath
import sys

from .platform_diagnostics import windows_path_issue

DWORD = C.c_uint32
BOOL = C.c_int32
HANDLE = C.c_void_p


class FileIdInfo(C.Structure):
    _fields_ = [('volume', C.c_uint64), ('file_id', C.c_ubyte * 16)]


class AttributeTagInfo(C.Structure):
    _fields_ = [('attributes', DWORD), ('reparse_tag', DWORD)]


class NativeInspectionError(ValueError):
    def __init__(self, code, message, winerror=None):
        super().__init__(message)
        self.code, self.winerror = code, winerror


def require_windows():
    if sys.platform != 'win32':
        raise NativeInspectionError('platform_unsupported', 'Native Windows required')


def path_chain(path):
    """Pure conservative syntax check; does not establish physical identity."""
    issue = windows_path_issue(path)
    if issue:
        raise NativeInspectionError(issue, 'Unsupported Windows path syntax')
    value = path.replace('/', '\\')
    parts = value[3:].split('\\') if len(value) > 3 else []
    return [value[:3]] + [value[:3] + '\\'.join(parts[:i]) for i in range(1, len(parts) + 1)]


def same_node(left, right):
    return (left['volume_id'], left['file_id']) == (right['volume_id'], right['file_id'])


class _API:
    def __init__(self):
        require_windows()
        self.k = C.WinDLL('kernel32', use_last_error=True)
        self.a = C.WinDLL('advapi32', use_last_error=True)
        signatures = {
            'CreateFileW': ([C.c_wchar_p, DWORD, DWORD, C.c_void_p, DWORD, DWORD, HANDLE], HANDLE),
            'CloseHandle': ([HANDLE], BOOL),
            'GetFileInformationByHandleEx': ([HANDLE, C.c_int32, C.c_void_p, DWORD], BOOL),
            'GetFinalPathNameByHandleW': ([HANDLE, C.c_wchar_p, DWORD, DWORD], DWORD),
            'GetDriveTypeW': ([C.c_wchar_p], DWORD),
            'GetVolumeInformationByHandleW': ([HANDLE, C.c_wchar_p, DWORD, C.POINTER(DWORD), C.POINTER(DWORD), C.POINTER(DWORD), C.c_wchar_p, DWORD], BOOL),
            'LocalFree': ([C.c_void_p], C.c_void_p),
        }
        for name, (args, result) in signatures.items():
            f = getattr(self.k, name); f.argtypes, f.restype = args, result
        self.a.GetSecurityInfo.argtypes = [HANDLE, C.c_int32, DWORD] + [C.POINTER(C.c_void_p)] * 5
        self.a.GetSecurityInfo.restype = DWORD
        self.a.GetSecurityDescriptorLength.argtypes = [C.c_void_p]
        self.a.GetSecurityDescriptorLength.restype = DWORD
        self.a.IsValidSecurityDescriptor.argtypes = [C.c_void_p]
        self.a.IsValidSecurityDescriptor.restype = BOOL

    def fail(self, code):
        raise NativeInspectionError(code, 'Windows handle inspection failed', C.get_last_error())

    def info(self, handle, kind, value):
        if not self.k.GetFileInformationByHandleEx(handle, kind, C.byref(value), C.sizeof(value)):
            self.fail('node_information_unavailable')
        return value

    def inspect(self, handle, expected):
        attr = self.info(handle, 9, AttributeTagInfo())
        if attr.attributes & 0x400:
            raise NativeInspectionError('reparse_refused', 'Reparse node refused')
        identity = self.info(handle, 18, FileIdInfo())
        buf = C.create_unicode_buffer(32768)
        n = self.k.GetFinalPathNameByHandleW(handle, buf, len(buf), 0)
        if not n or n >= len(buf):
            self.fail('final_name_unavailable')
        final = buf.value
        if final.startswith('\\\\?\\'):
            final = final[4:]
        if final.casefold() != expected.casefold():
            raise NativeInspectionError('path_alias_refused', 'Final handle name differs from requested path')
        directory = bool(attr.attributes & 0x10)
        return {'volume_id': identity.volume, 'file_id': bytes(identity.file_id).hex(),
                'directory': directory, 'attributes': attr.attributes,
                'final_path': final, 'reparse_tag': attr.reparse_tag,
                'case_sensitivity_checked': False}

    def security(self, handle):
        owner, group, dacl, sacl, descriptor = [C.c_void_p() for _ in range(5)]
        try:
            error = self.a.GetSecurityInfo(handle, 1, 7, C.byref(owner), C.byref(group),
                                           C.byref(dacl), C.byref(sacl), C.byref(descriptor))
            if error:
                raise NativeInspectionError('security_snapshot_unavailable', 'GetSecurityInfo failed', error)
            if not descriptor.value or not self.a.IsValidSecurityDescriptor(descriptor):
                raise NativeInspectionError('security_descriptor_invalid', 'Invalid security descriptor')
            size = self.a.GetSecurityDescriptorLength(descriptor)
            if not 20 <= size <= 1024 * 1024:
                raise NativeInspectionError('security_descriptor_size', 'Invalid security descriptor size')
            data = C.string_at(descriptor, size)
            return {'format': 'win32-opaque-readonly', 'bytes': size,
                    'sha256': hashlib.sha256(data).hexdigest(),
                    'base64': base64.b64encode(data).decode('ascii'),
                    'restore_implemented': False}
        finally:
            if descriptor.value:
                self.k.LocalFree(descriptor)


@contextmanager
def inspect_path(path, *, security=False):
    """Yield observed-chain identity; reopen names and recheck before release. No writes/ACL changes.

    Refuses every observed reparse node, non-fixed drive, non-NTFS volume,
    normalized-name alias. Case-sensitive directory flags are not yet verified;
    this snapshot does not admit any path for writing. An unavailable query
    fails closed. This observation is not a transaction or OS sandbox.
    """
    require_windows()
    chain = path_chain(path)
    api = _API(); held = []
    try:
        if api.k.GetDriveTypeW(chain[0]) != 3:
            raise NativeInspectionError('storage_refused', 'Local fixed drive required')
        for index, name in enumerate(chain):
            access = 0x80 | (0x20000 if security and index == len(chain) - 1 else 0)
            # READ_ATTRIBUTES, optional READ_CONTROL; share read/write, never DELETE.
            h = api.k.CreateFileW(name, access, 3, None, 3, 0x02200000, None)
            if h is None or h == C.c_void_p(-1).value:
                api.fail('node_open_failed')
            held.append((h, name, None))
            info = api.inspect(h, name)
            held[-1] = (h, name, info)
            if index < len(chain) - 1 and not info['directory']:
                raise NativeInspectionError('ancestor_not_directory', 'Non-directory ancestor')
        fs_name = C.create_unicode_buffer(64)
        serial, max_component, flags = DWORD(), DWORD(), DWORD()
        if not api.k.GetVolumeInformationByHandleW(held[-1][0], None, 0, C.byref(serial), C.byref(max_component), C.byref(flags), fs_name, len(fs_name)):
            api.fail('volume_information_unavailable')
        if fs_name.value.upper() != 'NTFS':
            raise NativeInspectionError('storage_refused', 'NTFS required')
        result = dict(held[-1][2], filesystem=fs_name.value, chain=[i for _, _, i in held],
                      production_write_authorized=False, race_free=False)
        if security:
            result['security'] = api.security(held[-1][0])
        yield result
        for h, name, before in held:
            try:
                after = api.inspect(h, name)
                fresh = api.k.CreateFileW(name, 0x80, 3, None, 3, 0x02200000, None)
                if fresh is None or fresh == C.c_void_p(-1).value:
                    api.fail('node_drift')
                try:
                    named = api.inspect(fresh, name)
                finally:
                    api.k.CloseHandle(fresh)
                if not same_node(before, after) or before != after or not same_node(before, named):
                    raise NativeInspectionError('node_drift', 'Observed node changed')
            except NativeInspectionError as exc:
                raise NativeInspectionError('node_drift', 'Named node cannot be revalidated', exc.winerror) from exc
    finally:
        for h, _, _ in reversed(held):
            api.k.CloseHandle(h)
