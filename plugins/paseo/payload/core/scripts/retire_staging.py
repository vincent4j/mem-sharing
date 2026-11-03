#!/usr/bin/env python3
"""Official independent legacy staging retirement entry (not a C upgrade)."""
import sys
sys.dont_write_bytecode = True
from agm_core.staging_retirement import cli
if __name__ == '__main__':
    raise SystemExit(cli())
