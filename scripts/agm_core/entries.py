"""Pure byte-preserving entry edits and read-only symlink checks."""
import hashlib
from pathlib import Path


class EntryConflict(ValueError):
    code = "entry_conflict"


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _marker(value):
    value = value.encode("utf-8") if isinstance(value, str) else value
    if not isinstance(value, bytes) or not value:
        raise EntryConflict("markers must be nonempty UTF-8 bytes or text")
    value.decode("utf-8")
    return value


def managed_span(data: bytes, start, end):
    """Return the unique marker-inclusive span, or None if both are absent."""
    start, end = _marker(start), _marker(end)
    if start == end or start in end or end in start:
        raise EntryConflict("ambiguous markers")
    a, b = data.count(start), data.count(end)
    if not a and not b:
        return None
    if a != 1 or b != 1:
        raise EntryConflict("duplicate or incomplete markers")
    left, right = data.index(start), data.index(end)
    if right < left + len(start):
        raise EntryConflict("reversed or nested markers")
    return left, right + len(end)


def block_fingerprint(data: bytes, start, end):
    span = managed_span(data, start, end)
    return None if span is None else sha256(data[span[0]:span[1]])


def _verified_span(data, start, end, expected):
    span = managed_span(data, start, end)
    actual = None if span is None else sha256(data[span[0]:span[1]])
    if actual != expected:
        raise EntryConflict("managed block missing or drifted")
    return span


def render_block(data: bytes, block: bytes, start, end, *, expected_fingerprint=None,
                 position="append") -> bytes:
    """Replace a verified block or add an absent one. Never trim outside bytes.

    expected_fingerprint=None means expected absence. For an existing object,
    callers must supply its trusted fingerprint (or explicitly verify reuse).
    block contains exactly the two markers; outside newlines are caller policy.
    """
    if position not in ("append", "top"):
        raise EntryConflict("unknown block position")
    new_span = managed_span(block, start, end)
    if new_span != (0, len(block)):
        raise EntryConflict("replacement must contain exactly the marker-inclusive block")
    span = _verified_span(data, start, end, expected_fingerprint)
    if span is not None:
        if position == "top" and span[0] != 0:
            raise EntryConflict("top block is not at byte zero")
        return data[:span[0]] + block + data[span[1]:]
    if position == "top":
        return block + (b"\n" if data else b"") + data
    return data + (b"\n" if data and not data.endswith(b"\n") else b"") + block


def remove_block(data: bytes, start, end, *, expected_fingerprint) -> bytes:
    span = _verified_span(data, start, end, expected_fingerprint)
    if span is None:
        return data
    return data[:span[0]] + data[span[1]:]


def link_fingerprint(target) -> str:
    return sha256(str(Path(target).resolve()).encode("utf-8"))


def verify_link(path, target):
    """An occupied directory/copy or different source is always a conflict."""
    path, target = Path(path), Path(target).resolve()
    if not path.is_symlink() or path.resolve() != target:
        raise EntryConflict("not the expected symlink: " + str(path))
    return link_fingerprint(target)
