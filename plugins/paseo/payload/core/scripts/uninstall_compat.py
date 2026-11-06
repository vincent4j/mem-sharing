#!/usr/bin/env python3
"""Official independently pinned compatibility entry; no C replacement."""
import sys
sys.dont_write_bytecode=True
from agm_core.uninstall_compat import cli
if __name__=='__main__':raise SystemExit(cli())
