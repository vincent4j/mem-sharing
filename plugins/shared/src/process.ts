// memSharing plugin common layer — subprocess thin runner.
// True source: plugins/shared/src — generated copy lives in each plugin's
// server bundle (plugins/paseo/server/shared/common). Do not edit the copy.
//
// Rules enforced here (design §6/§7): argv-only invocation (never a shell),
// explicit cwd/env overrides, hard output caps, timeout and AbortSignal
// cancellation, and structured results that distinguish exit code from
// business status. Business semantics stay in the Python core.

export interface RunProcessOptions {
  readonly argv: readonly string[];
  readonly stdin?: string;
  readonly cwd?: string;
  readonly env?: Readonly<Record<string, string | undefined>>;
  readonly timeoutMs: number;
  readonly signal?: AbortSignal;
  readonly maxStdoutBytes?: number;
  readonly maxStderrBytes?: number;
}

export type ProcessResult =
  | {
      kind: "completed";
      exitCode: number;
      stdout: string;
      stderr: string;
      stdoutTruncated: boolean;
      stderrTruncated: boolean;
    }
  | { kind: "timeout"; partialStdout: string; partialStderr: string }
  | { kind: "canceled"; partialStdout: string; partialStderr: string }
  | { kind: "spawn_error"; message: string };

export const DEFAULT_MAX_STDOUT_BYTES = 8 * 1024 * 1024;
export const DEFAULT_MAX_STDERR_BYTES = 512 * 1024;
const KILL_GRACE_MS = 2000;
// Absolute ceiling after a group SIGKILL before giving up on 'close';
// bounded so a stuck grandchild can never hang the caller forever.
const FINAL_DEADLINE_MS = 10000;

function killGroup(pid: number | undefined, signal: NodeJS.Signals): void {
  if (pid === undefined) return;
  try {
    // The child was spawned detached, so it leads its own process group;
    // signaling the group reaps grandchildren holding our pipes too.
    process.kill(-pid, signal);
  } catch {
    try {
      process.kill(pid, signal);
    } catch {
      // already gone
    }
  }
}

export class ProcessInputError extends Error {
  readonly code = "process_input_invalid";
}

function validateArgv(argv: readonly string[]): void {
  if (!Array.isArray(argv) || argv.length === 0) {
    throw new ProcessInputError("argv must be a non-empty array");
  }
  for (const token of argv) {
    if (typeof token !== "string" || token.length === 0) {
      throw new ProcessInputError("argv tokens must be non-empty strings");
    }
    if (token.includes("\0")) {
      throw new ProcessInputError("argv tokens must not contain NUL bytes");
    }
  }
}

interface CollectedOutput {
  data: string;
  truncated: boolean;
}

function collector(cap: number): {
  push(chunk: Buffer): void;
  finish(): CollectedOutput;
} {
  const chunks: Buffer[] = [];
  let total = 0;
  let truncated = false;
  return {
    push(chunk: Buffer): void {
      if (truncated) return;
      if (total + chunk.length > cap) {
        chunks.push(chunk.subarray(0, cap - total));
        total = cap;
        truncated = true;
        return;
      }
      chunks.push(chunk);
      total += chunk.length;
    },
    finish(): CollectedOutput {
      return { data: Buffer.concat(chunks).toString("utf8"), truncated };
    },
  };
}

// Runs one subprocess without a shell. All callers pass the interpreter as
// argv[0] plus literal arguments; nothing here ever joins a command string.
export async function runProcess(options: RunProcessOptions): Promise<ProcessResult> {
  validateArgv(options.argv);
  const { spawn } = await import("node:child_process");
  const maxStdout = options.maxStdoutBytes ?? DEFAULT_MAX_STDOUT_BYTES;
  const maxStderr = options.maxStderrBytes ?? DEFAULT_MAX_STDERR_BYTES;

  return new Promise<ProcessResult>((resolve) => {
    let child: import("node:child_process").ChildProcess;
    try {
      child = spawn(options.argv[0], options.argv.slice(1), {
        shell: false,
        windowsHide: true,
        cwd: options.cwd,
        env: options.env ? { ...options.env } : process.env,
        // Own process group on POSIX so timeout/cancel can terminate the
        // whole tree, not just the direct child (grandchildren otherwise
        // hold the stdio pipes and block 'close').
        detached: process.platform !== "win32",
      });
    } catch (error) {
      resolve({ kind: "spawn_error", message: String(error) });
      return;
    }

    // Private plans travel over stdin, never command-line arguments or a shell.
    child.stdin?.on("error", () => {});
    child.stdin?.end(options.stdin);

    const stdout = collector(maxStdout);
    const stderr = collector(maxStderr);
    let settled = false;
    // Terminating freezes the reason on FIRST trigger (timeout or abort),
    // clears the main timer so a late deadline cannot flip the reason or
    // signal a reused pid, and is idempotent: once set, neither callback
    // re-enters and no additional escalation paths are armed.
    let terminating = false;
    let termReason: "timeout" | "canceled" | null = null;
    let timer: NodeJS.Timeout | undefined;
    let killTimer: NodeJS.Timeout | undefined;
    let finalTimer: NodeJS.Timeout | undefined;

    const clearAllTimers = (): void => {
      if (timer) clearTimeout(timer);
      if (killTimer) clearTimeout(killTimer);
      if (finalTimer) clearTimeout(finalTimer);
    };

    const settle = (result: ProcessResult): void => {
      if (settled) return;
      settled = true;
      clearAllTimers();
      options.signal?.removeEventListener("abort", onAbort);
      resolve(result);
    };

    // settleAfterGroupKill escalates SIGTERM -> SIGKILL across the whole
    // group and only then resolves. The parent's 'close' event does NOT
    // end a timeout/cancel: grandchildren that ignore SIGTERM and hold no
    // stdio would otherwise keep writing after we return.
    const settleAfterGroupKill = (): void => {
      killGroup(child.pid, "SIGKILL");
      const out = stdout.finish();
      const err = stderr.finish();
      settle(
        termReason === "timeout"
          ? { kind: "timeout", partialStdout: out.data, partialStderr: err.data }
          : { kind: "canceled", partialStdout: out.data, partialStderr: err.data },
      );
    };

    const beginTermination = (reason: "timeout" | "canceled"): void => {
      if (settled || terminating) return;
      terminating = true;
      termReason = reason;
      if (timer) clearTimeout(timer);
      killGroup(child.pid, "SIGTERM");
      killTimer = setTimeout(settleAfterGroupKill, KILL_GRACE_MS);
      finalTimer = setTimeout(settleAfterGroupKill, FINAL_DEADLINE_MS);
    };

    function onAbort(): void {
      beginTermination("canceled");
    }

    child.stdout?.on("data", (chunk: Buffer) => stdout.push(chunk));
    child.stderr?.on("data", (chunk: Buffer) => stderr.push(chunk));
    child.stdout?.on("error", () => {});
    child.stderr?.on("error", () => {});
    child.on("error", (error: NodeJS.ErrnoException) => {
      if (terminating) return;
      settle({ kind: "spawn_error", message: error.message });
    });

    timer = setTimeout(() => beginTermination("timeout"), options.timeoutMs);
    if (options.signal) {
      if (options.signal.aborted) {
        onAbort();
      } else {
        options.signal.addEventListener("abort", onAbort, { once: true });
      }
    }

    child.on("close", (exitCode) => {
      if (terminating) {
        // The direct child died during group termination; the settle waits
        // for the SIGKILL escalation so stragglers cannot outlive us.
        return;
      }
      if (child.pid !== undefined && process.platform !== "win32") {
        // The parent exiting does not mean the group is gone: a detached
        // grandchild may still be running with stdio ignored. Only a dead
        // group proves completion; otherwise the timeout timer bounds us.
        let groupGone = false;
        try {
          process.kill(-child.pid, 0);
        } catch (error) {
          groupGone = (error as NodeJS.ErrnoException).code === "ESRCH";
        }
        if (!groupGone) return;
      }
      const out = stdout.finish();
      const err = stderr.finish();
      settle({
        kind: "completed",
        exitCode: exitCode ?? -1,
        stdout: out.data,
        stderr: err.data,
        stdoutTruncated: out.truncated,
        stderrTruncated: err.truncated,
      });
    });
  });
}
