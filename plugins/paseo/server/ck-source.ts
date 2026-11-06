// Host-owned optional acquisition from current official main.
// The Python kernel revalidates the acquired commit and tracked bytes.
import fs from "node:fs";
import path from "node:path";
import { hostname } from "node:os";
import { ensureRealDirectory } from "./owned-paths";
import type { Runner } from "./orchestrator";

export const CK_BRANCH = "main";
export const CK_URL = "https://github.com/vincent4j/context-keeper.git";
export function ckDestination(home: string): string {
  return path.join(home, ".local", "share", "context-keeper-sources", CK_BRANCH);
}
export function ckAcquisitionPlan(home: string): Record<string, unknown> {
  return { command: "prepare-context-keeper-source", home, host: hostname(), url: CK_URL,
    branch: CK_BRANCH, destination: ckDestination(home), network: "Git fetch from current upstream main",
    installs_context_keeper: false, agent_support: "determined by the acquired upstream installer plan" };
}

export async function acquireCkSource(home: string, git: string, runner: Runner, signal?: AbortSignal): Promise<string> {
  const destination = ckDestination(home);
  // Resolve each parent independently: no symlink traversal or OS temporary
  // source roots; a fixture may supply a durable scratch HOME instead.
  const absolute = path.resolve(destination);
  if (absolute !== destination || /^(\/private\/var\/folders|\/private\/tmp|\/tmp)(\/|$)/.test(absolute)) throw new Error("Context Keeper acquisition requires a durable real HOME");
  const parent = path.dirname(destination);
  ensureRealDirectory(parent);
  const lock = destination + ".lock";
  fs.mkdirSync(lock, { mode: 0o700 }); // exclusive; never remove a foreign lock
  const identity = fs.lstatSync(lock);
  let stage: string | undefined;
  const run = async (args: string[]): Promise<string> => {
    const out = await runner.run([git, "-c", "core.hooksPath=/dev/null", "-c", "core.fsmonitor=false", ...args], { timeoutMs: 120_000, signal });
    if (out.kind !== "completed" || out.exitCode !== 0) throw new Error(`Context Keeper Git acquisition ${out.kind}; outcome unknown, inspect operation before retry`);
    return (out.stdout ?? "").trim();
  };
  const verify = async (root: string, requireMain = true) => {
    if (fs.realpathSync(root) !== root || !fs.lstatSync(path.join(root, ".git")).isDirectory()) throw new Error("unsafe Context Keeper checkout");
    if ((requireMain && await run(["-C", root, "rev-parse", "HEAD"]) !== await run(["-C", root, "rev-parse", "refs/remotes/origin/main"])) || await run(["-C", root, "status", "--porcelain", "--untracked-files=all"]) !== "") throw new Error("Context Keeper source drift");
    if (await run(["-C", root, "remote", "get-url", "origin"]) !== CK_URL) throw new Error("Context Keeper origin drift");
    for (const name of (await run(["-C", root, "ls-files", "-z"])).split("\0").filter(Boolean)) {
      const file = path.join(root, name);
      if (!fs.lstatSync(file).isFile() || fs.realpathSync(file) !== file ||
          await run(["-C", root, "hash-object", "--no-filters", file]) !== await run(["-C", root, "rev-parse", "HEAD:" + name])) throw new Error("Context Keeper tracked source drift");
    }
  };
  try {
    if (fs.existsSync(destination)) {
      await verify(destination, false);
      await run(["-C", destination, "fetch", "--no-tags", "origin", "+refs/heads/main:refs/remotes/origin/main"]);
      await run(["-C", destination, "merge", "--ff-only", "refs/remotes/origin/main"]);
      await verify(destination);
      return destination;
    }
    stage = fs.mkdtempSync(path.join(parent, ".acquire-"));
    await run(["init", "--quiet", stage]);
    await run(["-C", stage, "remote", "add", "origin", CK_URL]);
    await run(["-C", stage, "fetch", "--no-tags", "origin", "+refs/heads/main:refs/remotes/origin/main"]);
    await run(["-C", stage, "checkout", "--quiet", "--detach", "refs/remotes/origin/main"]);
    await verify(stage);
    if (signal?.aborted) throw new Error("Context Keeper acquisition canceled");
    if (fs.existsSync(destination)) throw new Error("Context Keeper destination appeared during acquisition");
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
