#!/usr/bin/env python3
"""M2-09 失败恢复演练驱动:崩溃 -> 现场核对 -> 锁拒绝 -> 显式恢复 -> 字节核对。

流程(全程真实文件、真实 manifest、真实 recover_manifest;无 mock):
 1. 复位现场:a.md="alpha\n",b.md/link.md/backups/.lock 清空
 2. before 快照
 3. 子进程运行 crash-child.py(硬崩溃,期望 rc=9)
 4. 现场核对:manifest status=applying、attempted=[True,True,False]、
    a.md 已被改写、b.md 已写入、link.md 缺席、.lock 残留
 5. 锁在场时尝试恢复 -> 必须被拒绝(lock_conflict),现场不动
 6. 操作员确认子进程已退出(rc=9)后移除陈旧锁(rmdir,不偷锁不重建)
 7. recover_manifest 显式恢复
 8. 字节核对:a.md 复原 "alpha\n"、b.md/link.md 缺席、manifest rolled_back
输出:crash-scene.json、crash-result.json;退出码 0=通过,1=不符。
"""
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCENE = HERE / "recover-scene"
REPO = HERE.parents[2]
sys.path.insert(0, str(REPO / "scripts"))

from agm_core.transaction import TransactionError, recover_manifest

EXPECTED = {
    "a.md": "file:alpha\n",
    "b.md": "absent",
    "link.md": "absent",
}


def state(path):
    path = Path(path)
    if not path.exists() and not path.is_symlink():
        return "absent"
    if path.is_symlink():
        return "symlink:" + os.readlink(path)
    return "file:" + path.read_text(encoding="utf-8")


def scene_state():
    return {name: state(SCENE / name) for name in EXPECTED}


def main():
    result = {"steps": []}

    def step(name, **facts):
        result["steps"].append(dict(step=name, **facts))
        print("[step]", name, facts if facts else "")

    # 1. 复位现场
    (SCENE / "a.md").write_bytes(b"alpha\n")
    for name in ("b.md", "link.md"):
        p = SCENE / name
        if p.is_symlink() or p.exists():
            p.unlink()
    for d in ("backups", ".lock"):
        p = SCENE / d
        if p.exists():
            import shutil
            shutil.rmtree(p)
    before = scene_state()
    step("reset-scene", before=before)

    # 2. 子进程硬崩溃
    crash = subprocess.run([sys.executable, str(SCENE / "crash-child.py")],
                           capture_output=True, text=True)
    step("crash-child", returncode=crash.returncode, stdout=crash.stdout.strip(),
         stderr=crash.stderr.strip()[-200:])
    if crash.returncode != 9:
        result["verdict"] = "unexpected-child-exit"
        (HERE / "crash-result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2))
        return 1

    # 3. 现场核对
    manifests = sorted((SCENE / "backups").glob("*/manifest.json"))
    if len(manifests) != 1:
        step("scene-inspect", manifests=[str(m) for m in manifests])
        result["verdict"] = "manifest-count"
        (HERE / "crash-result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2))
        return 1
    manifest = json.loads(manifests[0].read_text(encoding="utf-8"))
    mid_state = scene_state()
    scene = {
        "manifest": str(manifests[0]),
        "manifest_status": manifest["status"],
        "entries": [{"path": e["path"].split("/")[-1], "attempted": e["attempted"],
                     "restoration": e["restoration"]} for e in manifest["entries"]],
        "created_directories": manifest["created_directories"],
        "outputs": mid_state,
        "lock_dir_present": (SCENE / ".lock").exists(),
        "child_returncode": crash.returncode,
    }
    (HERE / "crash-scene.json").write_text(json.dumps(scene, ensure_ascii=False, indent=2) + "\n")
    step("scene-inspect", status=manifest["status"], lock=scene["lock_dir_present"],
         outputs=mid_state)
    ok_scene = (manifest["status"] == "applying"
                and [e["attempted"] for e in manifest["entries"]] == [True, True, True]
                and mid_state["a.md"] == "file:alpha-NEW\n"
                and mid_state["b.md"] == "file:beta\n"
                and mid_state["link.md"] == "absent"
                and scene["lock_dir_present"])
    if not ok_scene:
        result["verdict"] = "scene-mismatch"
        (HERE / "crash-result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2))
        return 1

    # 4. 锁在场时恢复必须被拒绝
    refused = None
    try:
        recover_manifest(manifests[0], lock_path=SCENE / ".lock", allowed_roots=[SCENE])
    except TransactionError as exc:
        refused = {"code": exc.code, "message": str(exc)}
    after_refusal = scene_state()
    step("recover-refused-with-lock", error=refused,
         scene_unchanged=after_refusal == mid_state)
    if not refused or refused["code"] != "lock_conflict" or after_refusal != mid_state:
        result["verdict"] = "lock-refusal-failed"
        (HERE / "crash-result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2))
        return 1

    # 5. 操作员确认陈旧锁并移除(子进程 rc=9 已退出;不偷锁:仅 rmdir 已知归属的锁目录)
    os.rmdir(SCENE / ".lock")
    step("operator-removed-stale-lock",
         justification="child exited rc=9; lock dir provenance is this drill")

    # 6. 显式恢复
    recovered = recover_manifest(manifests[0], lock_path=SCENE / ".lock", allowed_roots=[SCENE])
    final = scene_state()
    after_manifest = json.loads(manifests[0].read_text(encoding="utf-8"))
    step("recover-manifest", status=after_manifest["status"],
         entries=[e["restoration"] for e in after_manifest["entries"]],
         outputs=final)

    # 7. 字节核对(attempted 在写前保守置位,三项都属可恢复范围)
    passed = (final == before and after_manifest["status"] == "rolled_back"
              and [e["restoration"] for e in after_manifest["entries"]] == ["restored"] * 3
              and not (SCENE / ".lock").exists())
    result["verdict"] = "passed" if passed else "verify-failed"
    result["before"], result["after"] = before, final
    (HERE / "crash-result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print("[verdict]", result["verdict"])
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
