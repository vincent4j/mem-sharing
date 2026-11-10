// GENERATED FILE — do not edit by hand.
// True source: plugins/shared/src/<name> (run plugins/shared/sync-to-plugins.mjs).
// memSharing plugin common layer — Python interpreter discovery.
// True source: plugins/shared/src. Generated copy: plugin server bundles.
//
// Order (design §6): product private runtime first, then a compatible
// system interpreter. On macOS /usr/bin/python3 may be a CommandLineTools
// stub that triggers a developer-tools install dialog when executed; we
// probe `xcode-select -p` (read-only, no dialog) first and mark the
// candidate blocked instead of executing it. Version floor is 3.9 because
// the kernel parses sources with feature_version=(3,9).

import fs from "node:fs";
import path from "node:path";
import { runProcess } from "./process";
import { privatePythonCandidates } from "./paths";
import { executableCandidates } from "./executables";

export const MIN_PYTHON_VERSION = "3.9";

export type InterpreterStatus = "ready" | "missing" | "blocked" | "unknown";

export interface InterpreterCandidate {
  readonly origin: "private-runtime" | "system";
  readonly path: string;
  readonly status: InterpreterStatus;
  readonly detail?: string;
  readonly probe?: PythonProbe;
}

export interface PythonProbe {
  readonly pythonVersion: string;
  readonly executable: string;
  readonly machine: string;
  readonly platform: string;
  readonly stdlibOk: boolean;
}

export interface PythonEnvironment {
  readonly status: InterpreterStatus;
  readonly selected?: InterpreterCandidate;
  readonly candidates: readonly InterpreterCandidate[];
  readonly evidence: string;
}

// Fixed server-owned probe program; never composed from client input.
const PROBE_PROGRAM = [
  "import json, platform, sys",
  "print(json.dumps({",
  " 'pythonVersion': platform.python_version(),",
  " 'executable': sys.executable,",
  " 'machine': platform.machine(),",
  " 'platform': platform.system(),",
  " 'stdlibOk': all(__import__(m) is not None for m in ('json','hashlib','zlib')),",
  "}))",
].join("\n");

function versionTuple(version: string): number[] {
  return version
    .split(".")
    .map((part) => Number.parseInt(part, 10))
    .filter((part) => Number.isFinite(part));
}

function meetsFloor(version: string): boolean {
  const actual = versionTuple(version);
  const floor = versionTuple(MIN_PYTHON_VERSION);
  for (let i = 0; i < floor.length; i += 1) {
    if ((actual[i] ?? 0) !== floor[i]) return (actual[i] ?? 0) > floor[i];
  }
  return true;
}

async function isMacosCltReady(): Promise<boolean> {
  const result = await runProcess({
    argv: ["/usr/bin/xcode-select", "-p"],
    timeoutMs: 5000,
    maxStdoutBytes: 4096,
  });
  return result.kind === "completed" && result.exitCode === 0;
}

async function probeInterpreter(candidatePath: string): Promise<{ status: InterpreterStatus; probe?: PythonProbe; detail?: string }> {
  const result = await runProcess({
    argv: [candidatePath, "-B", "-c", PROBE_PROGRAM],
    timeoutMs: 15000,
    maxStdoutBytes: 64 * 1024,
  });
  if (result.kind !== "completed") {
    return { status: "unknown", detail: `probe ${result.kind}` };
  }
  if (result.exitCode !== 0) {
    return { status: "unknown", detail: `probe exited ${result.exitCode}: ${result.stderr.trim().slice(0, 200)}` };
  }
  let parsed: unknown;
  try {
    parsed = JSON.parse(result.stdout.trim());
  } catch {
    return { status: "unknown", detail: "probe stdout is not JSON" };
  }
  const probe = parsed as PythonProbe;
  if (typeof probe.pythonVersion !== "string" || typeof probe.machine !== "string" || typeof probe.stdlibOk !== "boolean") {
    return { status: "unknown", detail: "probe JSON missing required fields" };
  }
  if (!probe.stdlibOk) {
    return { status: "blocked", probe, detail: "required standard library modules unavailable" };
  }
  if (!meetsFloor(probe.pythonVersion)) {
    return { status: "blocked", probe, detail: `python ${probe.pythonVersion} below floor ${MIN_PYTHON_VERSION}` };
  }
  return { status: "ready", probe };
}

export interface ProbePythonOptions {
  readonly runtimeRoot: string;
  /** Test seam: override system candidate paths (default: standard dirs + PATH). */
  readonly systemCandidates?: readonly string[];
  readonly now?: () => Date;
}

export async function probePythonEnvironment(options: ProbePythonOptions): Promise<PythonEnvironment> {
  const candidates: InterpreterCandidate[] = [];
  const evidenceParts: string[] = [];

  for (const candidatePath of privatePythonCandidates(options.runtimeRoot)) {
    const candidate = await examine(candidatePath, "private-runtime");
    candidates.push(candidate);
    evidenceParts.push(`${candidate.path}:${candidate.status}`);
    if (candidate.status === "ready") {
      return { status: "ready", selected: candidate, candidates, evidence: evidenceParts.join(";") };
    }
  }

  const systemPaths = options.systemCandidates ?? executableCandidates("python");
  for (const candidatePath of systemPaths) {
    const candidate = await examine(candidatePath, "system");
    candidates.push(candidate);
    evidenceParts.push(`${candidate.path}:${candidate.status}`);
    if (candidate.status === "ready") {
      return { status: "ready", selected: candidate, candidates, evidence: evidenceParts.join(";") };
    }
  }

  const anyBlocked = candidates.some((candidate) => candidate.status === "blocked");
  const status: InterpreterStatus = candidates.length === 0 ? "missing" : anyBlocked ? "blocked" : "missing";
  return { status, candidates, evidence: evidenceParts.join(";") || "no candidate paths" };
}

async function examine(candidatePath: string, origin: "private-runtime" | "system"): Promise<InterpreterCandidate> {
  const stat = statFile(candidatePath);
  if (!stat.isFile()) {
    return { origin, path: candidatePath, status: "missing", detail: "not a regular file" };
  }
  if (origin === "system" && process.platform === "darwin" && isMacosStub(candidatePath)) {
    const cltReady = await isMacosCltReady();
    if (!cltReady) {
      return {
        origin,
        path: candidatePath,
        status: "blocked",
        detail: "CommandLineTools not installed; executing the stub would trigger a developer-tools dialog",
      };
    }
  }
  const probed = await probeInterpreter(candidatePath);
  return { origin, path: candidatePath, ...probed };
}

function isMacosStub(candidatePath: string): boolean {
  return path.resolve(candidatePath) === "/usr/bin/python3";
}

function statFile(candidatePath: string): fs.Stats {
  try {
    return fs.statSync(candidatePath);
  } catch {
    return { isFile: () => false } as unknown as fs.Stats;
  }
}
