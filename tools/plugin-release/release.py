#!/usr/bin/env python3
"""Offline deterministic generation/verification. Installation uses install.py."""
import argparse
import json
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[2]/'scripts'))
from agm_core import plugin_release


def main():
    parser = argparse.ArgumentParser(allow_abbrev=False)
    parser.add_argument('command', choices=['generate', 'verify'])
    parser.add_argument('--source', required=True)
    parser.add_argument('--commit', required=True)
    parser.add_argument('--version', required=True)
    parser.add_argument('--output', help='Absent output outside source; generate only')
    args = parser.parse_args()
    if args.command == 'generate':
        if not args.output:
            parser.error('generate requires --output')
        result = plugin_release.generate(args.source, args.commit, args.version, args.output)
    else:
        if args.output:
            parser.error('verify does not accept --output')
        result = plugin_release.checkout_delivery(args.source, args.commit, args.version)
    print(json.dumps(result, sort_keys=True, ensure_ascii=False))


if __name__ == '__main__':
    main()
