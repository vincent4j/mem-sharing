#!/usr/bin/env python3
"""Explicit, non-release Windows preview entry. No ordinary installer bypass."""
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
from agm_core.windows_preview import main

if __name__ == '__main__':
    raise SystemExit(main())
