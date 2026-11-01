// GENERATED FILE — do not edit by hand.
// True source: plugins/shared/src/<name> (run plugins/shared/sync-to-plugins.mjs).
// memSharing plugin common layer — dependency supply manifest contract.
// True source: plugins/shared/src. Generated copy: plugin server bundles.
//
// FAIL-CLOSED: no upstream URL, hash, or version is built into this file.
// A supply manifest is a runtime input the user approves in the host UI;
// it must satisfy every constraint below before any download happens.
// Status of real suppliers (2026-10-31): astral python-build-standalone is
// the candidate but its release SHA manifest was unreachable
// (UPSTREAM_BROKEN), so no production manifest is shipped. When a verified
// manifest exists it is loaded from disk at runtime, never from RPC input.

export interface SupplyArchive {
  readonly arch: "arm64" | "x86_64";
  readonly url: string;
  readonly sha256: string;
  readonly bytes: number;
}

export interface SupplyManifest {
  readonly schema_version: 1;
  readonly kind: "python-runtime";
  readonly runtime_id: string;
  readonly version: string;
  readonly license: string;
  readonly entry: string;
  readonly archives: readonly SupplyArchive[];
  readonly max_unpack_bytes: number;
  readonly allowed_symlinks?: readonly string[];
  readonly minimum_macos?: { readonly arm64?: string; readonly x86_64?: string };
  readonly source_note: string;
}

export interface SupplyValidation {
  readonly ok: boolean;
  readonly errors: readonly string[];
}

const RUNTIME_ID_PATTERN = /^[A-Za-z0-9][A-Za-z0-9._+-]{0,127}$/;
const RELATIVE_ENTRY_PATTERN = /^[A-Za-z0-9][A-Za-z0-9._+\/-]*$/;
const HTTPS_URL_PATTERN = /^https:\/\/[^\s]+$/;
const SHA256_PATTERN = /^[0-9a-f]{64}$/;
const MAX_ARCHIVE_BYTES = 2 * 1024 * 1024 * 1024;
const MAX_UNPACK_BYTES = 8 * 1024 * 1024 * 1024;

function isPlainObject(value: unknown): value is Record<string, unknown> {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

export function validateSupplyManifest(input: unknown): SupplyValidation {
  const errors: string[] = [];
  if (!isPlainObject(input)) {
    return { ok: false, errors: ["supply manifest must be a JSON object"] };
  }
  if (input.schema_version !== 1) errors.push("schema_version must be 1");
  if (input.kind !== "python-runtime") errors.push("kind must be 'python-runtime'");

  for (const key of ["runtime_id", "version", "license", "entry", "source_note"] as const) {
    if (typeof input[key] !== "string" || (input[key] as string).trim().length === 0) {
      errors.push(`${key} must be non-empty text`);
    }
  }
  if (typeof input.runtime_id === "string" && !RUNTIME_ID_PATTERN.test(input.runtime_id)) {
    errors.push("runtime_id charset invalid");
  }
  if (typeof input.entry === "string") {
    if (!RELATIVE_ENTRY_PATTERN.test(input.entry) || input.entry.includes("..") || input.entry.startsWith("/")) {
      errors.push("entry must be a safe relative path inside the unpacked runtime");
    }
  }
  if (input.minimum_macos !== undefined && !isPlainObject(input.minimum_macos)) {
    errors.push("minimum_macos must be an object when present");
  }

  const archives = input.archives;
  if (!Array.isArray(archives) || archives.length === 0 || archives.length > 2) {
    errors.push("archives must contain one or two entries");
  } else {
    const seenArch = new Set<string>();
    for (const archive of archives) {
      if (!isPlainObject(archive)) {
        errors.push("each archive must be an object");
        continue;
      }
      if (archive.arch !== "arm64" && archive.arch !== "x86_64") {
        errors.push("archive arch must be arm64 or x86_64");
      } else if (seenArch.has(archive.arch)) {
        errors.push(`duplicate archive arch ${archive.arch}`);
      } else {
        seenArch.add(archive.arch);
      }
      if (typeof archive.url !== "string" || !HTTPS_URL_PATTERN.test(archive.url)) {
        errors.push("archive url must be an absolute https URL");
      }
      if (typeof archive.sha256 !== "string" || !SHA256_PATTERN.test(archive.sha256)) {
        errors.push("archive sha256 must be 64 lowercase hex characters");
      }
      if (typeof archive.bytes !== "number" || !Number.isSafeInteger(archive.bytes) || archive.bytes <= 0 || archive.bytes > MAX_ARCHIVE_BYTES) {
        errors.push("archive bytes must be a positive integer within the cap");
      }
    }
  }

  if (
    typeof input.max_unpack_bytes !== "number" ||
    !Number.isSafeInteger(input.max_unpack_bytes) ||
    input.max_unpack_bytes <= 0 ||
    input.max_unpack_bytes > MAX_UNPACK_BYTES
  ) {
    errors.push("max_unpack_bytes must be a positive integer within the cap");
  }

  if (input.allowed_symlinks !== undefined) {
    if (!Array.isArray(input.allowed_symlinks)) {
      errors.push("allowed_symlinks must be an array when present");
    } else {
      for (const link of input.allowed_symlinks) {
        if (typeof link !== "string" || link.length === 0 || link.includes("..") || link.startsWith("/")) {
          errors.push("allowed_symlinks entries must be safe relative paths");
          break;
        }
      }
    }
  }

  return { ok: errors.length === 0, errors };
}

export interface LoadedSupply {
  readonly status: "ready" | "not_ready";
  readonly reason: string;
  readonly manifest?: SupplyManifest;
}

// Reads and validates a manifest file. Any missing, unreadable, or invalid
// file is 'not_ready' — never a guess or a built-in fallback.
export async function loadSupplyManifest(path: string): Promise<LoadedSupply> {
  const fs = await import("node:fs/promises");
  let text: string;
  try {
    text = await fs.readFile(path, "utf8");
  } catch {
    return { status: "not_ready", reason: `supply manifest missing or unreadable at ${path}` };
  }
  let parsed: unknown;
  try {
    parsed = JSON.parse(text);
  } catch {
    return { status: "not_ready", reason: `supply manifest at ${path} is not valid JSON` };
  }
  const validation = validateSupplyManifest(parsed);
  if (!validation.ok) {
    return { status: "not_ready", reason: `supply manifest invalid: ${validation.errors.join("; ")}` };
  }
  return { status: "ready", reason: `validated supply manifest at ${path}`, manifest: parsed as SupplyManifest };
}
