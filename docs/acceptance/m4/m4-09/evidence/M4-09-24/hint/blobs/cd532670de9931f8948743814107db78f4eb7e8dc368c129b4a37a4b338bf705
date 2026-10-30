"""Read-only Git identity discovery. M2 supports main checkouts only."""
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


class ProjectError(ValueError):
    code = "project_invalid"


class WorktreeUnsupported(ProjectError):
    code = "worktree_unsupported"


@dataclass(frozen=True)
class ProjectIdentity:
    main_checkout: Path
    checkout: Path
    git_common_dir: Path
    status: bytes

    @property
    def is_main(self):
        return self.checkout == self.main_checkout


def _git(root, *args):
    env = dict(os.environ, GIT_OPTIONAL_LOCKS="0")
    for name in ("GIT_DIR", "GIT_WORK_TREE", "GIT_COMMON_DIR", "GIT_INDEX_FILE"):
        env.pop(name, None)
    result = subprocess.run(["git", "-c", "core.fsmonitor=false", "-c", "core.untrackedCache=false", "-C", str(root), *args], stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, env=env)
    if result.returncode:
        raise ProjectError(result.stderr.decode("utf-8", "replace").strip())
    return result.stdout


def resolve_project(project: Optional[Path] = None, *, cwd=None,
                    allow_worktree=False) -> ProjectIdentity:
    """Explicit project must be a root; implicit cwd may be a subdirectory.

    allow_worktree is for read-only check diagnostics, never write authorization.
    Paths alone cannot detect replacing .git at the same location.
    """
    requested = Path(project if project is not None else (cwd or Path.cwd())).resolve()
    root = Path(os.fsdecode(_git(requested, "rev-parse", "--show-toplevel").rstrip(b"\n"))).resolve()
    if project is not None and root != requested:
        raise ProjectError("--project must name the Git root")
    common_raw = Path(os.fsdecode(_git(root, "rev-parse", "--git-common-dir").rstrip(b"\n")))
    common = (root / common_raw).resolve() if not common_raw.is_absolute() else common_raw.resolve()
    # -z avoids quoting and supports spaces, newlines and non-ASCII path names.
    records = _git(root, "worktree", "list", "--porcelain", "-z").split(b"\0")
    first = next((r[len(b"worktree "):] for r in records if r.startswith(b"worktree ")), None)
    if first is None:
        raise ProjectError("Git did not identify a main checkout")
    main = Path(os.fsdecode(first)).resolve()
    # With --separate-git-dir Git may report the metadata directory as the
    # first worktree. A main checkout is still distinguishable from a linked
    # worktree because its absolute git-dir equals its common-dir.
    git_dir = Path(os.fsdecode(_git(root, "rev-parse", "--absolute-git-dir").rstrip(b"\n"))).resolve()
    if main == common and git_dir == common and (root / ".git").is_file():
        main = root
    main_raw = Path(os.fsdecode(_git(main, "rev-parse", "--git-common-dir").rstrip(b"\n")))
    main_common = (main / main_raw).resolve() if not main_raw.is_absolute() else main_raw.resolve()
    if main_common != common:
        raise ProjectError("Git common-dir does not identify a supported main checkout")
    if root != main and not allow_worktree:
        raise WorktreeUnsupported("M2 supports only the main checkout: " + str(main))
    return ProjectIdentity(main, root, common,
                           _git(root, "status", "--porcelain=v1", "-z", "--untracked-files=all"))
