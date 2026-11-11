"""Explicit, approved relocation of registered user-entry layout units.

Uses the normal assembly transaction; no new ownership/adoption or CK parser.
"""
import argparse
import json
from pathlib import Path
import sys
from . import layout, paths, registry, user_entries, user_entry_layout

COMMAND = "migrate-user-entry-layout"


def cli(argv, *, home=None):
    parser = argparse.ArgumentParser(prog=COMMAND, allow_abbrev=False)
    parser.add_argument("command", choices=[COMMAND])
    parser.add_argument("--agent", action="append", choices=paths.AGENT_ORDER)
    parser.add_argument("--request-file")
    parser.add_argument("--approval-file")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    try:
        runtime = layout.from_request({"home": str(Path.home() if home is None else home)})
        user_entry_layout.require_kernel(runtime)
        inputs = {} if args.request_file is None else json.loads(Path(args.request_file).read_bytes(), object_pairs_hook=registry._no_duplicates)
        if not isinstance(inputs, dict) or set(inputs) - {"search_paths", "app_directories", "user_candidates"}:
            raise ValueError("Unknown detection request fields")
        request = dict(inputs, home=str(runtime.home), agents=args.agent, interactive=False,
                       platform_config=paths.select_platform(paths.load_agents_table(), sys.platform))
        if args.approval_file:
            approval = json.loads(Path(args.approval_file).read_bytes(), object_pairs_hook=registry._no_duplicates)
            evidence = {key: approval[key] for key in ("confirmed_at", "reference")}
            registry._evidence(evidence)
            if any(not isinstance(v, str) or not v.strip() or v.startswith("<") for v in evidence.values()):
                raise ValueError("Actual confirmation reference and UTC timestamp required")
            request["approval"] = approval
        result = user_entries.run_user_entries(request)
        print(json.dumps(result, ensure_ascii=False))
        return 5 if result.get("approval_required") else 0 if result["status"] == "completed" else 2
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(json.dumps({"status": "failed", "errors": [{"code": "entry_layout_conflict", "message": str(exc)}]}))
        return 2
