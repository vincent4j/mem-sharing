"""Read-only platform preflight. No platform admission or write authorization.

Windows paths are checked lexically even on macOS. Node classification uses
lstat metadata only; neither result establishes ACLs, volume or node identity.
"""
import argparse
import json
import os
import platform
import re
import shutil
import stat
import sys

from .paths import AGENT_ORDER, current_platform


def windows_path_issue(value):
    """Return a conservative syntax rejection code, or None (syntax only).

    No filesystem lookup, normalization, environment expansion or path echo.
    Native identity and storage checks remain mandatory before any future write.
    """
    if not isinstance(value, str) or not value or any(ord(c) < 32 for c in value):
        return "invalid_path"
    name = value.replace("/", "\\")
    if name.startswith("\\\\"):
        return "network_or_device_path"
    if not re.match(r"^[A-Za-z]:\\", name):
        return "absolute_drive_path_required"
    parts = name[3:].split("\\")
    if parts == [""]:
        return None
    for part in parts:
        if not part or part in (".", ".."):
            return "ambiguous_component"
        if part.endswith((" ", ".")):
            return "trailing_dot_or_space"
        if any(c in part for c in '<>:"|?*'):
            return "reserved_character_or_stream"
        base = part.split(".", 1)[0].rstrip(" .").upper()
        if base in {"CON", "PRN", "AUX", "NUL", "CONIN$", "CONOUT$"} or re.fullmatch(r"(?:COM|LPT)[1-9¹²³]", base):
            return "reserved_device_name"
    return None


def classify_node(path):
    """lstat a node without reading its content or following a link leaf.

    This helper does not traverse/approve ancestors and is never a write guard.
    Unknown reparse nodes are refused regardless of their apparent file type.
    """
    try:
        node = os.lstat(path)
    except FileNotFoundError:
        return "absent"
    except OSError:
        return "unreadable"
    # FILE_ATTRIBUTE_REPARSE_POINT, supplied by Python's Windows stat result.
    # https://docs.python.org/3/library/stat.html#stat.FILE_ATTRIBUTE_REPARSE_POINT
    if getattr(node, "st_file_attributes", 0) & 0x400:
        return "reparse"
    if stat.S_ISLNK(node.st_mode):
        return "symlink"
    if stat.S_ISREG(node.st_mode):
        return "file"
    if stat.S_ISDIR(node.st_mode):
        return "directory"
    return "other"


def diagnose(*, windows_paths=()):
    """Inspect interpreter and PATH presence only; never execute dependencies.

    No user config/memory read, subprocess, mkdir, download, ACL probe or write.
    Git presence is explicitly weaker than an executable/version verification.
    """
    return {
        "schema_version": 1,
        "command": "diagnose-platform",
        "status": "diagnostic_only",
        "changes": [],
        "host": {"platform": current_platform(), "native_platform": sys.platform,
                 "python_version": platform.python_version(),
                 "python_compatible": sys.version_info >= (3, 9),
                 "architecture": platform.machine(),
                 "git_on_path": shutil.which("git") is not None,
                 "git_execution_verified": False},
        "windows": {
            "production_write_enabled": False,
            "agents": {agent: "not_admitted" for agent in AGENT_ORDER},
            "pending": ["official_client_paths", "native_node_identity", "storage_scope",
                        "acl_snapshot_restore", "external_recovery", "client_acceptance"],
            "path_checks": [{"index": i, "syntax_issue": windows_path_issue(p),
                             "write_authorized": False}
                            for i, p in enumerate(windows_paths, 1)],
        },
    }


def cli(argv, *, home=None):
    parser = argparse.ArgumentParser(prog="diagnose-platform", allow_abbrev=False)
    parser.add_argument("command", choices=["diagnose-platform"])
    parser.add_argument("--windows-path", action="append", default=[])
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    report = diagnose(windows_paths=args.windows_path)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 1 if any(p["syntax_issue"] for p in report["windows"]["path_checks"]) else 0
