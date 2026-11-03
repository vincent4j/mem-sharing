"""Owned user-entry units at the logical top; every other byte is opaque.

No Context Keeper detection, heading parsing, whitespace cleanup or import
inference. Only registry-owned exact spans may be taken out of the original.
"""
from pathlib import Path

from .entries import EntryConflict, managed_span, sha256

BOM = b"\xef\xbb\xbf"


def arrange(original, units):
    """units are (marker-or-None, desired-bytes, registered-object-or-None).

    An import desired unit is its exact @line token (without its newline).
    Existing outside separators remain in the opaque remainder, including CRLF.
    """
    bom_prefix = BOM if original.startswith(BOM) else b""
    canonical = bom_prefix + b"\n".join(new for _, new, _ in units)
    already_top = original.startswith(canonical) and (len(original) == len(canonical)
        or original[len(canonical):len(canonical)+1] in (b"\r", b"\n"))
    spans = []
    desired = []
    for marker, new, obj in units:
        if marker is not None:
            span = managed_span(original, **marker)
        else:
            matches, offset = [], 0
            for line in original.splitlines(keepends=True):
                token = line.rstrip(b"\r\n")
                left = offset
                if offset == 0 and token.startswith(BOM):
                    token = token[len(BOM):]
                    left += len(BOM)
                if token == new:
                    matches.append((left, left + len(token)))
                elif token.strip() == new:
                    raise EntryConflict("Ambiguous public import whitespace")
                offset += len(line)
            if len(matches) > 1:
                raise EntryConflict("Duplicate public import")
            span = matches[0] if matches else None
        if span is not None:
            if obj is None or obj.get("scope") not in ("machine", "user"):
                raise EntryConflict("Unregistered user unit cannot be relocated")
            if obj.get("scope") != "machine" and not already_top:
                raise EntryConflict("Shared user unit cannot be relocated")
            if marker is not None:
                if (obj.get("marker") != marker
                        or not obj.get("fingerprint")
                        or sha256(original[slice(*span)]) != obj["fingerprint"]["value"]):
                    raise EntryConflict("User block ownership/fingerprint is not proven")
                if obj.get("ownership") != "created" and not already_top:
                    raise EntryConflict("Reused user block cannot be relocated")
            elif (obj.get("kind") != "import" or not obj.get("fingerprint")
                    or obj["fingerprint"]["basis"] != "file_bytes"
                    or sha256(original) != obj["fingerprint"]["value"]):
                raise EntryConflict("Public import whole-file baseline drift")
            spans.append(span)
        elif obj is not None:
            raise EntryConflict("Registered user unit is missing")
        desired.append(new)
    spans.sort()
    if any(a[1] > b[0] for a, b in zip(spans, spans[1:])):
        raise EntryConflict("Overlapping user units")
    remainder, cursor = b"", 0
    for left, right in spans:
        remainder += original[cursor:left]
        cursor = right
    remainder += original[cursor:]
    bom = BOM if remainder.startswith(BOM) else b""
    remainder = remainder[len(bom):]
    top = b"\n".join(desired)
    # Existing top layouts are already canonical regardless of opaque suffix.
    prefix = bom + top
    if original.startswith(prefix) and (len(original) == len(prefix) or original[len(prefix):len(prefix)+1] in (b"\r", b"\n")):
        return original
    return prefix + (b"\n" if remainder and not remainder.startswith((b"\r", b"\n")) else b"") + remainder


def require_kernel(runtime):
    """A public layout command may only use the active installed full kernel."""
    from . import user_install, registry, paths, policy_migration
    allowed = paths.allowed_user_paths(policy_migration.config(), None, home=str(runtime.home))
    ledger = registry.require_installed(registry.load_registry(runtime.registry, allowed_user_paths=allowed))
    user_install._code_matches(runtime, ledger["product"])
    import json
    meta = json.loads((runtime.code / ".agm-code-manifest.json").read_bytes())
    files = {i["path"]: i for i in meta["files"]}
    required = {"scripts/agm_core/user_entry_layout.py", "scripts/agm_core/user_entries.py", "scripts/agm_core/entry_layout.py"}
    if not required <= files.keys():
        raise EntryConflict("Installed kernel has no unified user-entry layout capability")
    root = Path(__file__).resolve().parents[2]
    for name, item in files.items():
        if name.endswith(".py") or name == "scripts/agents.json":
            candidate = root / name
            if candidate.is_symlink() or sha256(candidate.read_bytes()) != item["sha256"]:
                raise EntryConflict("Running layout kernel differs from installed code")
    return ledger


def require_source(source):
    """Internal installer-only candidate binding, before C is replaced."""
    root = Path(__file__).resolve().parents[2]
    candidate = Path(source)
    for name in ("user_entries.py", "user_entry_layout.py", "entry_layout.py"):
        path = candidate / "scripts/agm_core" / name
        if path.is_symlink() or not path.is_file() or path.read_bytes() != (root / "scripts/agm_core" / name).read_bytes():
            raise EntryConflict("Approved candidate cannot carry unified user-entry layout")
