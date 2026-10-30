#!/usr/bin/env python3
"""M2-09 平台矩阵演练快照工具:受管对象/记录库/registry 的只读三元组快照。

用法: python3 snapshot.py <label>
输出: <label>-snapshot.json(本目录)。只读,不写任何受管输出。
"""
import hashlib
import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
REGISTRY = REPO / "scripts" / "registry.json"
STORE = REPO / "docs" / "context-keeper"
SHARED_USER_ENTRY = Path.home() / ".workbuddy" / "MEMORY.md"
MANAGED = [
    REPO / "AGENTS.md",
    REPO / "CLAUDE.md",
    REPO / ".workbuddy/memory/MEMORY.md",
    REPO / ".agents/skills/context-keeper",
    REPO / ".codex/skills/context-keeper",
    REPO / ".claude/skills/context-keeper",
    REPO / ".workbuddy/skills/context-keeper",
    SHARED_USER_ENTRY,
    REGISTRY,
    REPO / "context-keeper.json",
]


def record(path):
    try:
        st = path.lstat()
    except FileNotFoundError:
        return {"kind": "absent"}
    import stat as statmod
    if statmod.S_ISLNK(st.st_mode):
        return {"kind": "symlink", "target": os.readlink(path),
                "mtime_ns": st.st_mtime_ns}
    if statmod.S_ISREG(st.st_mode):
        data = path.read_bytes()
        return {"kind": "file", "sha256": hashlib.sha256(data).hexdigest(),
                "size": len(data), "mtime_ns": st.st_mtime_ns}
    return {"kind": "other"}


def tree(root):
    out = {}
    if not root.exists():
        return {"<absent>": True}
    for p in sorted(root.rglob("*")):
        rel = str(p.relative_to(root))
        st = p.lstat()
        import stat as statmod
        if statmod.S_ISDIR(st.st_mode):
            out[rel] = "dir"
        elif statmod.S_ISREG(st.st_mode):
            out[rel] = "f:" + hashlib.sha256(p.read_bytes()).hexdigest()[:16] + ":" + str(st.st_mtime_ns)
        else:
            out[rel] = "other"
    return out


def registry_sections():
    data = json.loads(REGISTRY.read_text(encoding="utf-8"))
    out = {}
    for name, project in data["projects"].items():
        out[name] = hashlib.sha256(
            json.dumps(project, sort_keys=True, ensure_ascii=False).encode("utf-8")
        ).hexdigest()
    for oid, obj in data["shared_objects"].items():
        out["shared:" + oid] = hashlib.sha256(
            json.dumps(obj, sort_keys=True, ensure_ascii=False).encode("utf-8")
        ).hexdigest()
    return out


def main():
    label = sys.argv[1]
    payload = {
        "label": label,
        "managed": {str(p): record(p) for p in MANAGED},
        "store_tree": tree(STORE),
        "registry_sections": registry_sections(),
    }
    (HERE / (label + "-snapshot.json")).write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print("wrote", label + "-snapshot.json")


if __name__ == "__main__":
    main()
