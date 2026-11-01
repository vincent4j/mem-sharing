// memSharing plugin common layer — CLI JSON envelope parsing.
// True source: plugins/shared/src. Generated copy: plugin server bundles.
//
// The Python CLIs print exactly one JSON document to stdout (install.py:
// single line sorted keys; agm.py: indented envelope). This module parses
// strictly one document and nothing else; business status is derived from
// the JSON plus the process exit code by the caller.

export interface CliJsonResult {
  readonly ok: boolean;
  readonly value?: unknown;
  readonly error?: string;
}

const MAX_JSON_BYTES = 8 * 1024 * 1024;

export class CliJsonError extends Error {
  readonly code: string;
  constructor(code: string, message: string) {
    super(message);
    this.code = code;
  }
}

export function parseCliJson(text: string): CliJsonResult {
  if (text.length > MAX_JSON_BYTES) {
    return { ok: false, error: "cli json output exceeded size cap" };
  }
  const trimmed = text.trim();
  if (trimmed.length === 0) {
    return { ok: false, error: "cli produced no stdout" };
  }
  try {
    return { ok: true, value: JSON.parse(trimmed) };
  } catch (error) {
    return {
      ok: false,
      error: `cli stdout is not a single JSON document: ${String(error)}`,
    };
  }
}

// Python-side contract: exit 5 = approval required (preview succeeded),
// 0 = completed family, anything else = failure. Derived here once so
// every bridge maps codes identically.
export function classifyExitCode(exitCode: number): "approval_required" | "completed" | "failed" {
  if (exitCode === 5) return "approval_required";
  if (exitCode === 0) return "completed";
  return "failed";
}
