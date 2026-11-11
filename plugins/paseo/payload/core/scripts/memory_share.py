#!/usr/bin/env python3
"""薄 CLI：用户记忆走 memory_share，项目记忆走 project_share；同一退出码合同。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from agm_core import memory_share  # noqa: E402
from agm_core import project_share  # noqa: E402

PROJECT_COMMANDS = (project_share.COMMAND, project_share.RETURN_COMMAND,
                    project_share.RECOVER_COMMAND)

if __name__ == '__main__':
    argv = sys.argv[1:]
    entry = project_share if argv and argv[0] in PROJECT_COMMANDS else memory_share
    sys.exit(entry.cli(argv))
