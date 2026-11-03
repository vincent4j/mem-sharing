#!/usr/bin/env python3
"""Produce a private offline repair plan; never access original HOME or execute it."""
import argparse
import json
import os
import subprocess
from pathlib import Path
import sys
sys.dont_write_bytecode=True
from agm_core.uninstall_fusion_repair import plan_repair

def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('manifest','manifest-sha256','source-repo','source-commit','output'):
        parser.add_argument('--'+name,required=True)
    args=parser.parse_args(argv)
    try:
        result=plan_repair(args.manifest,manifest_sha256=args.manifest_sha256,source_repo=args.source_repo,source_commit=args.source_commit)
        output=Path(args.output)
        if not output.is_absolute() or output.parent.resolve()!=output.parent:raise ValueError('Canonical external output required')
        if output.is_relative_to(Path(result['home'])):raise ValueError('Repair plan must remain outside original HOME')
        raw=(json.dumps(result,ensure_ascii=False,sort_keys=True,indent=2)+'\n').encode()
        fd=os.open(output,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
        with os.fdopen(fd,'wb') as stream:stream.write(raw);stream.flush();os.fsync(stream.fileno())
        print(json.dumps({'status':'plan_only','execution_supported':False,'output':str(output),'changes':len(result['changes']),'plan_sha256':result['plan_sha256']}))
        return 0
    except (ValueError,OSError,KeyError,TypeError,subprocess.SubprocessError) as exc:
        # Diagnostics must not echo snapshot text, paths or arbitrary Git stderr.
        print(json.dumps({'status':'failed','error_type':type(exc).__name__,'code':'offline_evidence_rejected'}))
        return 2

if __name__=='__main__':raise SystemExit(main())
