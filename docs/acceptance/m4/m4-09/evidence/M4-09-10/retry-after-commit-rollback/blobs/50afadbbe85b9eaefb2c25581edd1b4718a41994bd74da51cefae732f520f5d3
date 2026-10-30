"""Synthetic installed machine for project-command tests; never an installer."""
from agm_core.layout import resolve_layout
from agm_core.registry import empty_registry, serialize_registry


def installed_registry():
    data = empty_registry()
    data["product"] = {
        "product_id": "mem-sharing", "installation_id": "fixture-machine",
        "product_structure_version": 1, "product_code_version": "0.4.0",
        "source": {"url": "fixture://agm", "commit": "a" * 40, "tree_sha256": "b" * 64},
        "installation_status": "complete", "last_operation_id": "fixture-install",
    }
    return data


def seed_runtime(home):
    runtime = resolve_layout(home)
    runtime.var.mkdir(parents=True)
    runtime.registry.write_bytes(serialize_registry(installed_registry()))
    return runtime


def seed_project_executors(home):
    """M4 §7: synthetic positive installations, never host application state."""
    import json
    import plistlib
    import shutil
    from pathlib import Path
    from types import SimpleNamespace
    home=Path(home);base=home/'fixture-executors';bin_dir=base/'bin';bin_dir.mkdir(parents=True,exist_ok=True)
    for agent,name in (('codex','@openai/codex'),('claude','@anthropic-ai/claude-code')):
        package=base/'packages'/agent;(package/'bin').mkdir(parents=True,exist_ok=True)
        exe=package/'bin'/agent;exe.write_text('#!/bin/sh\n');exe.chmod(0o755)
        (package/'package.json').write_text(json.dumps({'name':name,'version':'1.0.0','bin':{agent:'bin/'+agent}}))
        path=bin_dir/agent
        if not path.exists():path.symlink_to(exe)
    bundle=home/'Applications/WorkBuddy.app';(bundle/'Contents/MacOS').mkdir(parents=True,exist_ok=True)
    (bundle/'Contents/Info.plist').write_bytes(plistlib.dumps({'CFBundleName':'WorkBuddy','CFBundleIdentifier':'fixture.workbuddy',
        'CFBundleExecutable':'WorkBuddy','CFBundleShortVersionString':'1.0'}))
    exe=bundle/'Contents/MacOS/WorkBuddy';exe.write_text('#!/bin/sh\n');exe.chmod(0o755)
    def signature(command):return SimpleNamespace(returncode=0,stdout='',stderr='Identifier=fixture.workbuddy\n' if command[1]=='-d' else '')
    git=bin_dir/'git'
    if not git.exists():git.symlink_to(shutil.which('git'))
    codesign=bin_dir/'codesign';codesign.write_text('#!/bin/sh\nif [ "$1" = "-d" ]; then printf "Identifier=fixture.workbuddy\\n" >&2; fi\nexit 0\n');codesign.chmod(0o755)
    return {'search_paths':[str(bin_dir)],'app_directories':[],'detect_runner':signature}


# CLI subprocesses keep the real copied product files, while the test launcher
# bounds standard app scanning to synthetic HOME (no /Applications dependency).
CLI_DETECTION_BOOTSTRAP = "import runpy,sys;from pathlib import Path;sys.path.insert(0,str(Path(sys.argv[1]).parent));from agm_core import detect;detect.STANDARD_APP_DIRECTORIES=();sys.argv=sys.argv[1:];runpy.run_path(sys.argv[0],run_name='__main__')"
