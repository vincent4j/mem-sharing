"""M4-05: executor installation facts as three states (installed/absent/unknown).

Contract: docs/plan/decisions-m4.md §7.1. Detection observes only local static
facts: the current PATH, the standard application directories (/Applications and
<home>/Applications) and explicitly user-provided executable/app/receipt paths.
It never launches an application, never makes network or model requests and
never reads credentials, sessions or cookies. The only subprocess it may run is
the system static signature verifier (codesign); when that read-only backend is
unavailable the affected candidate fails, which yields unknown, not absent.

Aggregation rules (§7.1, frozen):
- exactly one fully verified candidate and no failed candidate ⇒ installed;
- a candidate that exists but fails verification (unknown wrapper script, bare
  binary without a package identity, broken link, name/product mismatch,
  signature or permission failure), or several verified candidates with an
  undeterminable active source ⇒ unknown;
- a hint (residual directory) without a strong signal ⇒ unknown;
- every supported candidate checkable, none present, and no hint ⇒ absent.

Every verified fact records absolute path, type, package/bundle identity,
version and executable hash; the detection result carries the observation time
and rules version. Detection itself performs zero writes.
"""

from __future__ import annotations

import hashlib
import json
import os
import plistlib
import re
import stat as stat_module
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from . import paths as agm_paths
from .paths import PathsError

DETECT_RULES_VERSION = "m4-05/1"
STANDARD_APP_DIRECTORIES = ("/Applications",)

_CODESIGN_VERIFY = ("codesign", "--verify")
_CODESIGN_DISPLAY = ("codesign", "-d", "--verbose=2")
_IDENTIFIER_RE = re.compile(r"^Identifier=(.+)$", re.MULTILINE)
_RECEIPT_SCHEMA_VERSION = 1
# Walking up from a resolved CLI entry to the nearest package.json is bounded by
# the filesystem root; this cap keeps pathological deep trees from long loops.
_MAX_PACKAGE_WALK = 64


class DetectionError(ValueError):
    """Invalid detection input (not an observation failure)."""

    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


def _utc_now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _sha256_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _default_runner(command):
    """Run the system static verifier; None means no read-only backend."""
    try:
        return subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    except OSError:
        return None


def _record(kind, candidate, result, detail, **facts):
    record = {"kind": kind, "candidate": candidate, "result": result, "detail": detail}
    record.update({key: value for key, value in facts.items() if value is not None})
    return record


def _resolve_active_entry(path):
    """Resolve one candidate command path to a real readable executable file.

    Returns (real_path, None) on success or (None, reason) describing why the
    candidate cannot serve as a verifiable package entry. reason "not_found"
    means the path does not exist at all (not an anomaly).
    """
    if not os.path.lexists(path):
        return None, "not_found"
    real = os.path.realpath(path)
    try:
        info = os.stat(real)
    except OSError as exc:
        return None, "断链接或无法 stat: %s" % exc
    if not stat_module.S_ISREG(info.st_mode):
        return None, "落点不是普通文件"
    if not os.access(real, os.R_OK | os.X_OK):
        return None, "不可读或不可执行(权限错误)"
    return real, None


def _nearest_package_json(start_dir):
    current = Path(start_dir)
    for _ in range(_MAX_PACKAGE_WALK):
        candidate = current / "package.json"
        if candidate.is_file():
            return candidate
        if current.parent == current:
            break
        current = current.parent
    return None


def _check_path_executable(signal, path):
    real, problem = _resolve_active_entry(path)
    if real is None:
        if problem == "not_found":
            return _record("path_executable", path, "not_found", "该路径不存在命令")
        return _record("path_executable", path, "failed", problem)
    package_json = _nearest_package_json(os.path.dirname(real))
    if package_json is None:
        return _record(
            "path_executable", path, "failed",
            "无可识别的最近 package.json(自编译/裸二进制,来源不明)",
            path=real, type="file",
        )
    try:
        with open(package_json, "r", encoding="utf-8") as handle:
            package = json.load(handle)
    except (OSError, ValueError) as exc:
        return _record("path_executable", path, "failed", "package.json 不可读/非法: %s" % exc, path=real, type="file")
    declared = package.get("name") if isinstance(package, dict) else None
    if declared != signal["package_name"]:
        return _record(
            "path_executable", path, "failed",
            "包名不符: 期望 %r, 实际 %r(未知包装脚本)" % (signal["package_name"], declared),
            path=real, type="file",
        )
    version = package.get("version")
    if not isinstance(version, str) or not version:
        return _record("path_executable", path, "failed", "包版本为空", path=real, type="file")
    package_dir = package_json.parent
    bin_field = package.get("bin")
    entry_ok = True
    if isinstance(bin_field, str):
        entry_ok = (package_dir / bin_field).exists()
    elif isinstance(bin_field, dict) and bin_field:
        entry_ok = any((package_dir / target).exists()
                       for target in bin_field.values() if isinstance(target, str))
    if not entry_ok:
        return _record(
            "path_executable", path, "failed", "声明的 bin 入口/平台二进制不存在",
            path=real, type="file", name=package["name"], version=version,
        )
    return _record(
        "path_executable", path, "verified",
        "解析到 %s %s 的真实包入口,bin 入口存在" % (package["name"], version),
        path=real, type="file", name=package["name"], version=version,
        executable_path=real, sha256=_sha256_file(real),
    )


def _check_app_bundle(signal, path, *, runner):
    if not os.path.lexists(path):
        return _record("macos_app_bundle", path, "not_found", "该位置无此应用")
    if os.path.islink(path):
        return _record("macos_app_bundle", path, "failed", "应用落点是符号链接")
    if not os.path.isdir(path):
        return _record("macos_app_bundle", path, "failed", "应用落点不是目录")
    info_path = os.path.join(path, "Contents", "Info.plist")
    try:
        with open(info_path, "rb") as handle:
            info = plistlib.load(handle)
    except (OSError, ValueError) as exc:
        return _record("macos_app_bundle", path, "failed", "Info.plist 不可读/非法: %s" % exc)
    declared = info.get("CFBundleName") if isinstance(info, dict) else None
    if declared != signal["product_name"]:
        return _record(
            "macos_app_bundle", path, "failed",
            "Info.plist 产品名不符: 期望 %r, 实际 %r" % (signal["product_name"], declared),
        )
    bundle_id = info.get("CFBundleIdentifier")
    if not isinstance(bundle_id, str) or not bundle_id:
        return _record("macos_app_bundle", path, "failed", "bundle 标识为空")
    executable_name = info.get("CFBundleExecutable")
    if not isinstance(executable_name, str) or not executable_name:
        return _record("macos_app_bundle", path, "failed", "CFBundleExecutable 为空")
    executable = os.path.join(path, "Contents", "MacOS", executable_name)
    real, problem = _resolve_active_entry(executable)
    if real is None:
        return _record("macos_app_bundle", path, "failed", "可执行文件不可用: %s" % problem, name=bundle_id)
    version = info.get("CFBundleShortVersionString") or info.get("CFBundleVersion")
    if signal.get("require_bundle_version") and (not isinstance(version, str) or not version):
        return _record("macos_app_bundle", path, "failed", "bundle 版本为空(要求非空)", name=bundle_id)
    verified = runner(list(_CODESIGN_VERIFY) + [path])
    if verified is None:
        return _record(
            "macos_app_bundle", path, "failed",
            "无只读签名校验后端(codesign 不可用)", name=bundle_id,
        )
    if verified.returncode != 0:
        lines = (verified.stderr or "").strip().splitlines()
        return _record(
            "macos_app_bundle", path, "failed",
            "静态签名校验未通过: %s" % (lines[-1] if lines else "rc=%s" % verified.returncode),
            name=bundle_id,
        )
    if signal.get("require_signature_identifier_match"):
        displayed = runner(list(_CODESIGN_DISPLAY) + [path])
        if displayed is None:
            return _record("macos_app_bundle", path, "failed", "无只读签名后端可读 identifier", name=bundle_id)
        match = _IDENTIFIER_RE.search(displayed.stderr or "") or _IDENTIFIER_RE.search(displayed.stdout or "")
        identifier = match.group(1).strip() if match else None
        if identifier != bundle_id:
            return _record(
                "macos_app_bundle", path, "failed",
                "签名 identifier(%r)与 plist bundle 标识(%r)不一致" % (identifier, bundle_id),
                name=bundle_id,
            )
    return _record(
        "macos_app_bundle", path, "verified",
        "Info.plist 产品名/可执行/静态签名核验通过",
        path=str(Path(path).absolute()), type="app_bundle", name=bundle_id,
        version=version if isinstance(version, str) and version else None,
        executable_path=real, sha256=_sha256_file(real),
    )


def _check_user_receipt(signal, path):
    if path is None:
        return _record("user_receipt", None, "not_applicable", "用户未提供收据(该通道无候选可查)")
    try:
        with open(path, "rb") as handle:
            receipt = json.loads(handle.read().decode("utf-8"))
    except (OSError, ValueError) as exc:
        return _record("user_receipt", path, "failed", "收据不可读/非法 JSON: %s" % exc)
    if not isinstance(receipt, dict) or receipt.get("schema_version") != _RECEIPT_SCHEMA_VERSION:
        return _record("user_receipt", path, "failed", "收据 schema_version 必须是 1")
    if receipt.get("product") != signal["product_name"]:
        return _record(
            "user_receipt", path, "failed",
            "收据产品不符: 期望 %r, 实际 %r" % (signal["product_name"], receipt.get("product")),
        )
    executable = receipt.get("executable")
    files = receipt.get("files")
    if not isinstance(executable, str) or not os.path.isabs(executable):
        return _record("user_receipt", path, "failed", "收据 executable 必须是绝对路径")
    if not isinstance(files, list) or not files:
        return _record("user_receipt", path, "failed", "收据 files 必须是非空清单")
    listed = {}
    for item in files:
        if not isinstance(item, dict) or set(item) != {"path", "sha256"}:
            return _record("user_receipt", path, "failed", "收据 files 项字段必须恰好是 path、sha256")
        if not isinstance(item["path"], str) or not os.path.isabs(item["path"]):
            return _record("user_receipt", path, "failed", "收据 files 项 path 必须是绝对路径")
        if not isinstance(item["sha256"], str) or not re.fullmatch(r"[0-9a-f]{64}", item["sha256"]):
            return _record("user_receipt", path, "failed", "收据 files 项 sha256 必须是 64 位小写十六进制")
        listed[item["path"]] = item["sha256"]
    if executable not in listed:
        return _record("user_receipt", path, "failed", "收据清单未覆盖 executable")
    for listed_path, digest in sorted(listed.items()):
        try:
            if _sha256_file(listed_path) != digest:
                return _record("user_receipt", path, "failed", "清单哈希不符: %s" % listed_path)
        except OSError as exc:
            return _record("user_receipt", path, "failed", "清单文件不可读: %s (%s)" % (listed_path, exc))
    real, problem = _resolve_active_entry(executable)
    if real is None:
        return _record("user_receipt", path, "failed", "收据 executable 不可用: %s" % problem)
    version = receipt.get("version")
    return _record(
        "user_receipt", path, "verified",
        "收据清单哈希与可执行文件一致",
        path=real, type="receipt_manifest", name=signal["product_name"],
        version=version if isinstance(version, str) and version else None,
        executable_path=real, sha256=_sha256_file(real),
    )


def _default_search_paths():
    raw = os.environ.get("PATH", "")
    ordered, seen = [], set()
    for item in raw.split(os.pathsep):
        if item and item not in seen:
            seen.add(item)
            ordered.append(item)
    return ordered


def _explicit_candidates(user_candidates, agent, kind):
    """User-provided candidate paths of one signal kind for one agent."""
    if not user_candidates:
        return []
    values = user_candidates.get(agent) or []
    return [item["path"] for item in values if item["kind"] == kind]


def _validate_user_candidates(user_candidates):
    if not user_candidates:
        return
    if not isinstance(user_candidates, dict):
        raise DetectionError("detection_input_invalid", "user_candidates 必须是 {agent: [{kind, path}]}")
    for agent, values in user_candidates.items():
        if agent not in agm_paths.AGENTS:
            raise DetectionError("detection_input_invalid", "user_candidates 未知执行器: %r" % (agent,))
        if not isinstance(values, list):
            raise DetectionError("detection_input_invalid", "user_candidates[%s] 必须是数组" % agent)
        for item in values:
            if (not isinstance(item, dict) or item.get("kind") not in agm_paths.STRONG_SIGNAL_KINDS
                    or not isinstance(item.get("path"), str) or not item["path"]):
                raise DetectionError(
                    "detection_input_invalid",
                    "user_candidates[%s] 项必须是 {kind: path_executable/macos_app_bundle/user_receipt, path: 非空路径}" % agent)


def _path_hits(name, search_paths):
    """All PATH entries whose <dir>/<name> exists, in PATH order (manual scan).

    Manual scanning (instead of shutil.which) so broken links and non-executable
    files named like the command are observed: per §7.1 they are anomalies of
    this executor's name and must surface as failed candidates, not silence.
    """
    hits = []
    for directory in search_paths:
        candidate = os.path.join(directory, name)
        if os.path.lexists(candidate):
            hits.append(candidate)
    return hits


def _detect_one(agent, entry, *, home, search_paths, user_candidates, runner, app_directories):
    hints = []
    for signal in entry["installation_signals"]:
        if signal["strength"] != "hint":
            continue
        hint_path = agm_paths.expand_path(signal["path"], home=home)
        hints.append({"path": hint_path, "exists": os.path.isdir(hint_path)})
    records = []
    for signal in entry["installation_signals"]:
        if signal["strength"] != "strong":
            continue
        kind = signal["kind"]
        if kind == "path_executable":
            candidates = list(_explicit_candidates(user_candidates, agent, kind))
            for hit in _path_hits(signal["executable"], search_paths):
                if hit not in candidates:
                    candidates.append(hit)
            if not candidates:
                records.append(_record(kind, signal["executable"], "not_found", "PATH 中无该命令且未提供显式路径"))
            else:
                for candidate in candidates:
                    records.append(_check_path_executable(signal, candidate))
        elif kind == "macos_app_bundle":
            locations = [os.path.join(directory, signal["bundle_name"])
                         for directory in app_directories]
            locations.append(os.path.join(home, "Applications", signal["bundle_name"]))
            for provided in _explicit_candidates(user_candidates, agent, kind):
                if provided not in locations:
                    locations.append(provided)
            for location in locations:
                records.append(_check_app_bundle(signal, location, runner=runner))
        else:  # user_receipt
            provided = _explicit_candidates(user_candidates, agent, kind)
            if len(provided) > 1:
                records.append(_record(kind, provided, "failed", "收据路径只能提供一个"))
            else:
                records.append(_check_user_receipt(signal, provided[0] if provided else None))
    verified, failed, seen_verified = [], [], set()
    for record in records:
        if record["result"] == "verified":
            key = (record["kind"], record.get("path") or record.get("candidate"))
            if key not in seen_verified:
                seen_verified.add(key)
                verified.append(record)
        elif record["result"] == "failed":
            failed.append(record)
    if len(verified) > 1:
        status = "unknown"
        summary = "多个可核验候选,无法确定活动来源: " + "; ".join(
            str(record.get("path") or record.get("candidate")) for record in verified)
    elif len(verified) == 1 and not failed:
        status = "installed"
        summary = verified[0]["detail"]
    elif failed:
        status = "unknown"
        summary = "候选核验失败/权限错误: " + "; ".join(record["detail"] for record in failed)
    elif any(hint["exists"] for hint in hints):
        status = "unknown"
        summary = "仅有残留目录 hint,无强安装信号: " + "; ".join(
            hint["path"] for hint in hints if hint["exists"])
    else:
        status = "absent"
        summary = "全部支持候选均可检查且不存在,无 hint"
    return {
        "agent": agent,
        "status": status,
        "observed_at": _utc_now(),
        "rules_version": DETECT_RULES_VERSION,
        "summary": summary,
        "hints": hints,
        "evidence": records,
    }


def detect_agents(platform_config, agents=None, *, home, search_paths=None,
                  user_candidates=None, runner=None, app_directories=None):
    """Read-only three-state installation facts for the requested agents.

    search_paths defaults to the real PATH and app_directories to /Applications;
    tests inject synthetic values. user_candidates maps agent -> [{kind, path}]
    for explicitly provided executable/app/receipt paths. runner(command)
    substitutes the signature verification backend. Raises DetectionError only
    for malformed input, never for what the machine actually looks like.
    """
    if not isinstance(home, str) or not os.path.isabs(home):
        raise DetectionError("detection_input_invalid", "home 必须是绝对路径")
    _validate_user_candidates(user_candidates)
    resolved_search = _default_search_paths() if search_paths is None else list(search_paths)
    for item in resolved_search:
        if not isinstance(item, str):
            raise DetectionError("detection_input_invalid", "search_paths 项必须是字符串")
    resolved_apps = list(STANDARD_APP_DIRECTORIES) if app_directories is None else list(app_directories)
    for item in resolved_apps:
        if not isinstance(item, str) or not os.path.isabs(item):
            raise DetectionError("detection_input_invalid", "app_directories 项必须是绝对路径")
    effective_runner = _default_runner if runner is None else runner
    result = {
        "observed_at": _utc_now(),
        "rules_version": DETECT_RULES_VERSION,
        "agents": {},
    }
    for agent in agm_paths.resolve_agents(agents):
        result["agents"][agent] = _detect_one(
            agent, platform_config[agent], home=home,
            search_paths=resolved_search, user_candidates=user_candidates,
            runner=effective_runner, app_directories=resolved_apps,
        )
    return result


def detection_fingerprint(detection):
    """Stable fingerprint of one agent's detection (no timestamps) for approval binding."""
    view = {
        "status": detection["status"],
        "summary": detection["summary"],
        "hints": detection["hints"],
        "evidence": detection["evidence"],
    }
    return hashlib.sha256(
        json.dumps(view, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()
