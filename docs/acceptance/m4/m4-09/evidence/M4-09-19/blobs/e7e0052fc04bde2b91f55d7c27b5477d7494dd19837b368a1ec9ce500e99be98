#!/usr/bin/env python3
"""M2-09 失败恢复演练:真实 Transaction 子进程,在第 3 个写前硬崩溃。

场景(父目录 = 本目录):
  a.md   "alpha\n"     -> "alpha-NEW\n"   (更新,产生真实 before 备份)
  b.md   不存在        -> "beta\n"        (新建)
  link.md 不存在       -> 符号链接指向 a.md
崩溃点:link.md 的 before_write 钩子内 os._exit(9) —— 绕过一切异常处理,
模拟断电/kill -9:不留回滚,manifest 停在 applying,写锁目录残留。
"""
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "scripts"))

from agm_core.transaction import Change, Transaction, read_snapshot

# tx.run() 自带 write_lock(lock_path);此处不再外层加锁。
tx = Transaction(lock_path=HERE / ".lock", backup_root=HERE / "backups",
                 allowed_roots=[HERE], operation="m2-09-crash-drill")
a = HERE / "a.md"
changes = [
    Change.file(a, b"alpha-NEW\n", expected=read_snapshot(a)),
    Change.file(HERE / "b.md", b"beta\n", expected=read_snapshot(HERE / "b.md")),
    Change.symlink(HERE / "link.md", a, expected=read_snapshot(HERE / "link.md")),
]


def crash_hook(event, path):
    if event == "before_write" and str(path) == str(HERE / "link.md"):
        sys.stdout.write("crash: %s %s\n" % (event, path))
        sys.stdout.flush()
        os._exit(9)  # 硬崩溃:不触发 rollback、不释放锁


tx.hook = crash_hook
receipt = tx.run(changes)
sys.stdout.write("unexpected completion: %r\n" % receipt)
