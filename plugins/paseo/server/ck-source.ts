// Host-owned optional acquisition. The Python kernel remains the only CK
// installer and revalidates every tracked byte and the fixed integration pin.
import fs from "node:fs";
import path from "node:path";
import { hostname } from "node:os";
import { ensureRealDirectory } from "./owned-paths";
import type { Runner } from "./orchestrator";

export const CK_PIN = "86af15073c1da7fedddc34342eb10bba64062b73";
export const CK_URL = "https://github.com/vincent4j/context-keeper.git";
export function ckDestination(home: string): string {
  return path.join(home, ".local", "share", "context-keeper-sources", CK_PIN);
}
export function ckAcquisitionPlan(home: string): Record<string, unknown> {
  return { command: "prepare-context-keeper-source", home, host: hostname(), url: CK_URL,
    commit: CK_PIN, destination: ckDestination(home), network: "Git fetch from fixed upstream",
    installs_context_keeper: false, agents: ["codex", "claude", "workbuddy", "zcode", "dsh", "opencode"] };
}

export async function acquireCkSource(home: string, git: string, runner: Runner, signal?: AbortSignal): Promise<string> {
  const destination = ckDestination(home);
  // Resolve each parent independently: no symlink traversal or OS temporary
  // source roots; a fixture may supply a durable scratch HOME instead.
  const absolute = path.resolve(destination);
  if (absolute !== destination || /^(\/private\/var\/folders|\/private\/tmp|\/tmp)(\/|$)/.test(absolute)) throw new Error("CK acquisition requires a durable real HOME");
  const parent = path.dirname(destination);
  ensureRealDirectory(parent);
  const lock = destination + ".lock";
  fs.mkdirSync(lock, { mode: 0o700 }); // exclusive; never remove a foreign lock
  const identity = fs.lstatSync(lock);
  let stage: string | undefined;
  const run = async (args: string[]): Promise<string> => {
    const out = await runner.run([git, "-c", "core.hooksPath=/dev/null", "-c", "core.fsmonitor=false", ...args], { timeoutMs: 120_000, signal });
    if (out.kind !== "completed" || out.exitCode !== 0) throw new Error(`CK Git acquisition ${out.kind}; outcome unknown, inspect operation before retry`);
    return (out.stdout ?? "").trim();
  };
  const verify = async (root: string) => {
    if (fs.realpathSync(root) !== root || !fs.lstatSync(path.join(root, ".git")).isDirectory()) throw new Error("unsafe CK checkout");
    if (await run(["-C", root, "rev-parse", "HEAD"]) !== CK_PIN || await run(["-C", root, "status", "--porcelain", "--untracked-files=all"]) !== "") throw new Error("CK source drift");
    if (await run(["-C", root, "remote", "get-url", "origin"]) !== CK_URL) throw new Error("CK origin drift");
  };
  try {
    if (fs.existsSync(destination)) { await verify(destination); return destination; }
    stage = fs.mkdtempSync(path.join(parent, ".acquire-"));
    await run(["init", "--quiet", stage]);
    await run(["-C", stage, "remote", "add", "origin", CK_URL]);
    await run(["-C", stage, "fetch", "--no-tags", "--depth=1", "origin", CK_PIN]);
    await run(["-C", stage, "checkout", "--quiet", "--detach", CK_PIN]);
    await verify(stage);
    if (signal?.aborted) throw new Error("CK acquisition canceled");
    if (fs.existsSync(destination)) throw new Error("CK destination appeared during acquisition");
    fs.renameSync(stage, destination);
    stage = undefined;
    return destination;
  } finally {
    // Preserve failed acquisition directories for inspection; never delete a
    // checkout that could already back another client's installed Skill.
    const now = fs.lstatSync(lock);
    if (now.dev === identity.dev && now.ino === identity.ino) fs.rmdirSync(lock);
  }
}
