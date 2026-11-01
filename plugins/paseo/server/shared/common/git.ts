// GENERATED FILE — do not edit by hand.
// True source: plugins/shared/src/<name> (run plugins/shared/sync-to-plugins.mjs).
// memSharing plugin common layer — Git availability probe.
// True source: plugins/shared/src. Generated copy: plugin server bundles.
//
// The kernel needs a real Git for checkout-based source resolution and
// treats a missing Git as a hard runtime dependency (runtime_missing). The
// Paseo plugin documents make no promise that a daemon host exposes git on
// the plugin subprocess PATH, so this probe only reports; it never
// installs or fabricates a Git. No verified private Git supply package
// exists today. On macOS /usr/bin/git can be a CommandLineTools stub that
// pops a developer-tools dialog when executed; it is guarded with a
// read-only xcode-select check first, exactly like the Python probe.

import fs from "node:fs";
import path from "node:path";
import { runProcess } from "./process";

export type GitStatus = "ready" | "missing" | "blocked" | "unknown";

export interface GitCandidate {
  readonly path: string;
  readonly status: GitStatus;
  readonly detail?: string;
}

export interface GitEnvironment {
  readonly status: GitStatus;
  readonly version?: string;
  readonly path?: string;
  readonly detail: string;
  readonly candidates?: readonly GitCandidate[];
}

const GIT_CANDIDATE_DIRS = ["/usr/bin", "/usr/local/bin", "/opt/homebrew/bin", "/opt/local/bin"];
const GIT_VERSION_PATTERN = /^git version \d+\.\d+/;

function candidatePaths(options: ProbeGitOptions): string[] {
  if (options.candidateDirs) {
    return [...options.candidateDirs].map((dir) => path.join(dir, "git"));
  }
  const candidates = GIT_CANDIDATE_DIRS.map((dir) => path.join(dir, "git"));
  if (process.env.PATH && process.env.PATH.length > 0) {
    for (const dir of process.env.PATH.split(":")) {
      if (dir.length > 0) candidates.push(path.join(dir, "git"));
    }
  }
  return [...new Set(candidates)];
}

async function isMacosCltReady(): Promise<boolean> {
  const result = await runProcess({
    argv: ["/usr/bin/xcode-select", "-p"],
    timeoutMs: 5000,
    maxStdoutBytes: 4096,
  });
  return result.kind === "completed" && result.exitCode === 0;
}

function isMacosStub(candidatePath: string): boolean {
  return process.platform === "darwin" && path.resolve(candidatePath) === "/usr/bin/git";
}

export interface ProbeGitOptions {
  /** Test seam: override candidate paths (default: standard dirs + PATH). */
  readonly candidateDirs?: readonly string[];
  /** Test seam: override the CommandLineTools read-only check. */
  readonly cltCheck?: () => Promise<boolean>;
}

export async function probeGitEnvironment(options: ProbeGitOptions = {}): Promise<GitEnvironment> {
  const candidates: GitCandidate[] = [];
  for (const candidate of candidatePaths(options)) {
    let stat: fs.Stats;
    try {
      stat = fs.statSync(candidate);
    } catch {
      continue;
    }
    if (!stat.isFile()) continue;

    if (isMacosStub(candidate)) {
      const ready = options.cltCheck ? await options.cltCheck() : await isMacosCltReady();
      if (!ready) {
        candidates.push({
          path: candidate,
          status: "blocked",
          detail: "CommandLineTools not installed; executing the stub would trigger a developer-tools dialog",
        });
        continue;
      }
    }

    const probed = await runProcess({
      argv: [candidate, "--version"],
      timeoutMs: 5000,
      maxStdoutBytes: 4096,
    });
    if (probed.kind !== "completed" || probed.exitCode !== 0) {
      candidates.push({
        path: candidate,
        status: "unknown",
        detail: `git --version failed (${probed.kind === "completed" ? probed.exitCode : probed.kind})`,
      });
      continue;
    }
    const version = probed.stdout.trim();
    if (!GIT_VERSION_PATTERN.test(version)) {
      candidates.push({
        path: candidate,
        status: "unknown",
        detail: `unexpected --version output: ${version.slice(0, 80)}`,
      });
      continue;
    }
    return {
      status: "ready",
      path: candidate,
      version,
      detail: "located, executed, and version-verified on this daemon host",
      candidates,
    };
  }

  if (candidates.some((entry) => entry.status === "blocked")) {
    return {
      status: "blocked",
      detail: candidates.map((entry) => `${entry.path}:${entry.status}`).join("; "),
      candidates,
    };
  }
  if (candidates.length > 0) {
    return {
      status: "unknown",
      detail: candidates.map((entry) => `${entry.path}:${entry.status}`).join("; "),
      candidates,
    };
  }
  return {
    status: "missing",
    detail: "no git executable on daemon PATH or standard locations; host Git availability is unverified, no private Git supply exists",
    candidates,
  };
}
