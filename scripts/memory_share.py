#!/usr/bin/env python3
"""薄 CLI：python3 scripts/memory_share.py <share-user-memory|return-user-memory|recover-memory-share> …"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from agm_core import memory_share  # noqa: E402

if __name__ == '__main__':
    sys.exit(memory_share.cli(sys.argv[1:]))
