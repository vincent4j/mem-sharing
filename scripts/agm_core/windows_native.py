"""Read-only Windows handle inspection. Never a production write authorization.

Read-attributes handles do not guarantee rename exclusion on all Windows paths. The
absolute-path walk is not an atomic relative-handle traversal: external writers
can still change metadata. All ancestors and final-handle names are rechecked.
Sources: Microsoft CreateFileW, GetFileInformationByHandleEx, FILE_ID_INFO,
FILE_ATTRIBUTE_TAG_INFO, GetFinalPathNameByHandleW, GetVolumeInformationByHandleW,
GetSecurityInfo and LocalFree documentation (see Windows validation record).
"""
import base64
from contextlib import contextmanager, ExitStack
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


class CaseSensitiveInfo(C.Structure):
    _fields_ = [('flags', DWORD)]


class StandardInfo(C.Structure):
    _fields_ = [('allocation_size', C.c_int64), ('end_of_file', C.c_int64),
                ('number_of_links', DWORD), ('delete_pending', C.c_ubyte),
                ('directory', C.c_ubyte)]


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
    """Observed volume/file ID equality only; hard links may have other names.

    This does not enumerate aliases or protect operations through other names.
    """
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

    def candidate_metadata(self, handle, directory):
        # FILE_STANDARD_INFO / FileStandardInfo=1; BOOLEAN fields are one byte.
        standard = self.info(handle, 1, StandardInfo())
        if bool(standard.directory) != directory:
            raise NativeInspectionError('node_type_drift', 'Node type changed')
        flags = 0
        if directory:
            # FILE_CASE_SENSITIVE_INFO / FileCaseSensitiveInfo=23 (SDK).
            flags = self.info(handle, 23, CaseSensitiveInfo()).flags
            if flags & ~1:
                raise NativeInspectionError('case_sensitivity_flags_unknown', 'Unknown case flags')
        return {'case_sensitivity_checked': True,
                'case_sensitive_directory': bool(flags & 1),
                'number_of_links': standard.number_of_links,
                'delete_pending': bool(standard.delete_pending)}

    def registered_cloud_root(self, handle):
        try:
            library = C.WinDLL('CldApi.dll', winmode=0x800)
            query = library.CfGetSyncRootInfoByHandle
        except (OSError, AttributeError) as exc:
            raise NativeInspectionError('cloud_query_unavailable', 'Cloud Files query unavailable',
                                        getattr(exc, 'winerror', None)) from exc
        query.argtypes = [HANDLE, C.c_int32, C.c_void_p, DWORD, C.POINTER(DWORD)]
        query.restype = C.c_int32
        # CF_SYNC_ROOT_INFO_BASIC=0; one LARGE_INTEGER, no provider strings copied.
        buffer, returned = C.c_int64(), DWORD()
        status = query(handle, 0, C.byref(buffer), C.sizeof(buffer), C.byref(returned))
        return classify_registered_cloud_result(status, returned.value)

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
                if self.k.LocalFree(descriptor):
                    self.fail('security_descriptor_free_failed')


@contextmanager
def inspect_path(path, *, security=False, candidate_metadata=False, registered_cloud_check=False):
    """Yield observed-chain identity; reopen names and recheck before release. No writes/ACL changes.

    Refuses every observed reparse node, non-fixed drive, non-NTFS volume,
    normalized-name alias. Directory case flags are queried only when
    candidate_metadata=True; otherwise they remain unverified;
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
            if candidate_metadata:
                info.update(api.candidate_metadata(h, info['directory']))
            if registered_cloud_check and name == chain[-1]:
                info.update(api.registered_cloud_root(h))
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
                if candidate_metadata:
                    after.update(api.candidate_metadata(h, after['directory']))
                if registered_cloud_check and name == chain[-1]:
                    after.update(api.registered_cloud_root(h))
                fresh = api.k.CreateFileW(name, 0x80, 3, None, 3, 0x02200000, None)
                if fresh is None or fresh == C.c_void_p(-1).value:
                    api.fail('node_drift')
                try:
                    named = api.inspect(fresh, name)
                    if candidate_metadata:
                        named.update(api.candidate_metadata(fresh, named['directory']))
                    if registered_cloud_check and name == chain[-1]:
                        named.update(api.registered_cloud_root(fresh))
                finally:
                    api.k.CloseHandle(fresh)
                if not same_node(before, after) or before != after or not same_node(before, named) or before != named:
                    raise NativeInspectionError('node_drift', 'Observed node changed')
            except NativeInspectionError as exc:
                raise NativeInspectionError('node_drift', 'Named node cannot be revalidated', exc.winerror) from exc
    finally:
        for h, _, _ in reversed(held):
            api.k.CloseHandle(h)


def validate_candidate_scope(root, target):
    """Check necessary snapshot conditions only; never authorize a write.

    Both snapshots must come from candidate_metadata inspections held together.
    ID prefixes bind observed ancestry; string common-prefix is insufficient.
    Other storage-provider checks, transactions and atomic traversal remain open.
    """
    def refuse(code):
        raise NativeInspectionError(code, 'Candidate path conditions not met')
    if not root['directory']:
        refuse('scope_root_not_directory')
    for snapshot in (root, target):
        if snapshot.get('filesystem') != 'NTFS':
            refuse('storage_refused')
        for node in snapshot['chain']:
            if not node.get('case_sensitivity_checked'):
                refuse('case_sensitivity_unknown')
            if node.get('case_sensitive_directory'):
                refuse('case_sensitive_directory_refused')
            if node.get('attributes', 0) & (0x400 | 0x1000 | 0x40000 | 0x400000):
                refuse('storage_attributes_refused')
            if node.get('delete_pending') is not False:
                refuse('node_delete_state_unknown')
            if not node['directory'] and node.get('number_of_links') != 1:
                refuse('hardlink_or_unknown_links_refused')
            if node['volume_id'] != root['volume_id']:
                refuse('cross_volume_refused')
    prefix, chain = root['chain'], target['chain']
    if len(chain) < len(prefix) or any(not same_node(a, b) for a, b in zip(prefix, chain)):
        refuse('outside_allowed_root')
    return {'path_checks_passed': True, 'production_write_authorized': False,
            'race_free': False, 'storage_provider_verified': False}


@contextmanager
def inspect_candidate_path(path, *, allowed_root, security=False, registered_cloud_check=False):
    """Read-only candidate observations under one explicit existing directory.

    No missing-leaf creation, alias enumeration, sync-provider identification or
    write authorization. Ancestors and names are rechecked on release.
    """
    with inspect_path(allowed_root, candidate_metadata=True, registered_cloud_check=registered_cloud_check) as root:
        with inspect_path(path, security=security, candidate_metadata=True, registered_cloud_check=registered_cloud_check) as target:
            conditions = validate_candidate_scope(root, target)
            yield dict(target, **conditions)



def validate_candidate_set(candidates):
    """Reject duplicate or ancestor/descendant candidates by observed identity.

    All observations must be held together. No entries are silently removed and
    no ordering of candidates makes an overlapping set acceptable.
    """
    if not candidates or len(candidates) > 256:
        raise NativeInspectionError('candidate_set_size', 'Expected 1 to 256 candidates')
    for candidate in candidates:
        if candidate.get('path_checks_passed') is not True:
            raise NativeInspectionError('candidate_unchecked', 'Candidate conditions unknown')
        if not candidate.get('chain') or not same_node(candidate, candidate['chain'][-1]):
            raise NativeInspectionError('candidate_identity_unknown', 'Candidate identity inconsistent')
    for index, left in enumerate(candidates):
        for right in candidates[index + 1:]:
            if (any(same_node(left, node) for node in right['chain']) or
                    any(same_node(right, node) for node in left['chain'])):
                raise NativeInspectionError('candidate_overlap', 'Duplicate or nested candidates refused')
    return {'candidate_count': len(candidates), 'overlap_checks_passed': True,
            'production_write_authorized': False, 'race_free': False,
            'registered_cloud_roots_checked': all(c.get('registered_cloud_root_checked') is True for c in candidates)}


@contextmanager
def inspect_candidate_set(paths, *, allowed_root, registered_cloud_check=True):
    """Hold and revalidate a disjoint set of existing nodes under one root.

    Necessary read-only preflight, not a transaction lock or approved plan.
    """
    paths = list(paths)
    if not paths or len(paths) > 256:
        raise NativeInspectionError('candidate_set_size', 'Expected 1 to 256 paths')
    with ExitStack() as stack:
        candidates = [stack.enter_context(inspect_candidate_path(path, allowed_root=allowed_root, registered_cloud_check=registered_cloud_check))
                      for path in paths]
        conditions = validate_candidate_set(candidates)
        yield dict(conditions, candidates=candidates)



def classify_registered_cloud_result(hresult, returned_length):
    """Narrow Cloud Files result only; not proof against third-party syncing.

    0x80070186 is HRESULT_FROM_WIN32(ERROR_CLOUD_FILE_NOT_UNDER_SYNC_ROOT).
    CfGet's exact mapping is inferred from documented Cloud Files error semantics,
    not promised by its function page. This must never grant write authorization.
    """
    status = hresult & 0xffffffff
    if status == 0x80070186:
        return {'registered_cloud_root_checked': True,
                'registered_cloud_root_present': False,
                'registered_cloud_hresult': status,
                'cloud_hresult_mapping_inferred': True}
    if status == 0 and returned_length >= 8:
        raise NativeInspectionError('registered_cloud_root_refused', 'Registered cloud root refused')
    raise NativeInspectionError('cloud_query_unverified', 'Cloud Files state unknown', status)


def validate_r2_admission(candidates):
    """Require all R2 evidence, never promote a partial/overlap-only result.

    Internal trusted observations only, not a serialized approval or user input.
    Inferred Cloud Files error mappings and unknown provider coverage cannot
    become admission. Production writes remain separately prohibited.
    """
    conditions = validate_candidate_set(candidates)
    for candidate in candidates:
        if candidate.get('registered_cloud_root_checked') is not True:
            raise NativeInspectionError('cloud_check_required', 'Cloud root evidence required')
        if candidate.get('registered_cloud_root_present') is not False:
            raise NativeInspectionError('cloud_root_or_unknown', 'Cloud root absent state not established')
        if candidate.get('cloud_hresult_mapping_inferred') is not False:
            raise NativeInspectionError('cloud_evidence_inferred', 'Inferred mapping is not admission evidence')
        if candidate.get('storage_provider_verified') is not True:
            raise NativeInspectionError('storage_provider_unverified', 'Storage provider coverage unknown')
    return dict(conditions, r2_conditions_satisfied=True, production_write_authorized=False)


@contextmanager
def inspect_r2_admission(paths, *, allowed_root):
    """Single strict read-only admission entry; no cloud-disable parameter.

    Current provider evidence is incomplete, so current real snapshots remain
    blocked. This entry never authorizes install, ACL changes or transactions.
    """
    with inspect_candidate_set(paths, allowed_root=allowed_root, registered_cloud_check=True) as observed:
        conditions = validate_r2_admission(observed['candidates'])
        yield dict(conditions, candidates=observed['candidates'])
