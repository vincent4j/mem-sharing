// GENERATED FILE — do not edit by hand.
// True source: plugins/shared/src/<name> (run plugins/shared/sync-to-plugins.mjs).
// memSharing plugin common layer — safe tar.gz extraction.
// True source: plugins/shared/src. Generated copy: plugin server bundles.
//
// Content policy (design §6 and shared security review 2026-10-31):
//   - refuse an existing destination; on any failure remove only this
//     call's own staging directory, never the destination or anything else;
//   - every declared size must be a non-negative safe integer within the
//     caller's byte cap, counting member data, headers, and hardlink
//     copies; extended-header records and entry counts are bounded;
//   - absolute paths, "..", unlisted links, escaping link targets, and
//     special file types are rejected;
//   - permission bits are preserved from the archive masked to 0o777
//     (special bits dropped); entries with any execute bit are verified
//     X_OK after extraction;
//   - extraction goes to a sibling staging directory and is renamed into
//     place atomically.

import fs from "node:fs";
import path from "node:path";
import { createGunzip } from "node:zlib";

export type ExtractResult =
  | { kind: "ok"; root: string; files: number; bytes: number }
  | { kind: "failed"; code: string; message: string };

export interface ExtractOptions {
  readonly archivePath: string;
  readonly destDir: string;
  readonly maxBytes: number;
  readonly allowedSymlinks?: readonly string[];
  /** Exact, package-locked targets. Required for links using parent segments. */
  readonly expectedLinks?: Readonly<Record<string, string>>;
  readonly signal?: AbortSignal;
}

class ExtractFailure extends Error {
  readonly code: string;
  constructor(code: string, message: string) {
    super(message);
    this.code = code;
  }
}

const BLOCK = 512;
const MAX_PAX_RECORD_BYTES = 64 * 1024;
const MAX_ENTRIES = 100_000;

interface Header {
  readonly name: string;
  readonly size: number;
  readonly mode: number;
  readonly typeflag: string;
  readonly linkname: string;
}

function readString(block: Buffer, offset: number, length: number): string {
  const raw = block.subarray(offset, offset + length);
  const nul = raw.indexOf(0);
  return raw.subarray(0, nul === -1 ? raw.length : nul).toString("utf8").trim();
}

function readOctal(block: Buffer, offset: number, length: number, what: string): number {
  const text = readString(block, offset, length);
  if (text.length === 0) return 0;
  const value = Number.parseInt(text, 8);
  if (!Number.isSafeInteger(value) || value < 0) {
    throw new ExtractFailure("bad_size", `${what} is not a valid non-negative octal: ${text}`);
  }
  return value;
}

function readSize(block: Buffer): number {
  // GNU base-256 extension first byte 0x80, else octal ASCII.
  if (block[124] & 0x80) {
    let value = 0;
    for (let i = 124 + 1; i < 124 + 12; i += 1) {
      value = value * 256 + block[i];
    }
    if (!Number.isSafeInteger(value) || value < 0) {
      throw new ExtractFailure("bad_size", "base-256 size is not a safe non-negative integer");
    }
    return value;
  }
  return readOctal(block, 124, 12, "member size");
}

function parseHeader(block: Buffer, overrides: { path?: string }): Header {
  const name = overrides.path ?? readString(block, 0, 100);
  const linkname = readString(block, 157, 100);
  const typeflag = String.fromCharCode(block[156] || 0x30);
  const size = readSize(block);
  const mode = readOctal(block, 100, 8, "member mode") & 0o777;
  return { name, size, mode, typeflag, linkname };
}

function safeRelative(candidate: string, what: string): string {
  if (candidate.length === 0) throw new ExtractFailure("bad_path", `${what} is empty`);
  const posix = candidate.replace(/\\/g, "/");
  const parts = posix.split("/").filter((part) => part.length > 0 && part !== ".");
  if (posix.startsWith("/") || /^[A-Za-z]:/.test(posix)) {
    throw new ExtractFailure("absolute_path", `${what} must be relative: ${candidate}`);
  }
  if (posix.split("/").some((part) => part === "..")) {
    throw new ExtractFailure("path_escape", `${what} must not contain '..': ${candidate}`);
  }
  if (posix.includes("\0")) throw new ExtractFailure("bad_path", `${what} contains NUL`);
  return parts.join("/");
}

function resolveInside(root: string, relative: string): string {
  const target = path.resolve(root, relative);
  const rootResolved = path.resolve(root);
  if (target !== rootResolved && !target.startsWith(rootResolved + path.sep)) {
    throw new ExtractFailure("path_escape", `resolved path escapes the extraction root: ${relative}`);
  }
  return target;
}

interface PendingLink {
  readonly type: "symlink" | "hardlink";
  readonly linkname: string;
  readonly relative: string;
}

// Reassembles arbitrary stream chunks into fixed 512-byte tar blocks.
// Returns null once the stream ends cleanly between blocks; a trailing
// partial block is an error.
function streamBlockReader(stream: NodeJS.ReadableStream): { block(): Promise<Buffer | null> } {
  const iterator = stream[Symbol.asyncIterator]();
  let buffer: Buffer = Buffer.alloc(0);
  let done = false;
  return {
    async block(): Promise<Buffer | null> {
      while (buffer.length < BLOCK) {
        if (done) break;
        const chunk = await iterator.next();
        if (chunk.done) {
          done = true;
          break;
        }
        const data = Buffer.isBuffer(chunk.value) ? chunk.value : Buffer.from(chunk.value);
        buffer = buffer.length === 0 ? data : Buffer.concat([buffer, data]);
      }
      if (buffer.length === 0) return null;
      if (buffer.length < BLOCK) {
        throw new ExtractFailure("truncated", `archive ended mid-block (${buffer.length} of ${BLOCK} bytes)`);
      }
      const block = buffer.subarray(0, BLOCK);
      buffer = buffer.subarray(BLOCK);
      return block;
    },
  };
}

// Streams the archive member by member. Pax headers ('x'/'g') and GNU long
// names ('L') only override the next header's path field.
async function extract(options: ExtractOptions): Promise<{ files: number; bytes: number }> {
  if (!Number.isSafeInteger(options.maxBytes) || options.maxBytes <= 0) {
    throw new ExtractFailure("bad_size_cap", "maxBytes must be a positive safe integer");
  }
  if (options.destDir.length === 0 || path.resolve(options.destDir) === path.sep) {
    throw new ExtractFailure("bad_path", "destDir must be a non-root directory path");
  }
  // Atomic claim of the destination: mkdir is exclusive, so a pre-existing
  // destination (foreign or from a racing worker) is refused without
  // touching it, and the final rename can only replace OUR empty
  // placeholder.
  let claimed = false;
  let claimDev = -1;
  let claimIno = -1;
  try {
    await fs.promises.mkdir(options.destDir, { recursive: false });
    claimed = true;
    // Bind ownership to the created directory object itself. A path is not
    // proof: if anything moves our placeholder away and puts a foreign
    // directory at the same path, the dev/ino pair below will not match and
    // neither publish nor cleanup touches the replacement.
    const bound = await fs.promises.lstat(options.destDir);
    claimDev = bound.dev;
    claimIno = bound.ino;
  } catch (error) {
    throw new ExtractFailure("dest_exists", `destination already exists: ${options.destDir} (${(error as NodeJS.ErrnoException).code})`);
  }
  // True while the directory at destDir is still the exact object this call
  // created. Note the accepted boundary: a non-cooperating process can
  // still race between this final check and the rename itself; absolute
  // freedom from that race is not claimed.
  const stillOwnsDest = async (): Promise<boolean> => {
    try {
      const current = await fs.promises.lstat(options.destDir);
      return current.dev === claimDev && current.ino === claimIno && current.isDirectory();
    } catch {
      return false;
    }
  };
  let staging: string | null = null;
  let published = false;
  try {
    // mkdtemp gives an exclusive, unpredictable staging directory; only
    // this call owns it and only it is ever cleaned up here.
    staging = await fs.promises.mkdtemp(`${options.destDir}.extract-`);
    const extracted = await extractInto(staging, options);
    // Final write re-verifies ownership: only our own, unreplaced
    // placeholder may be replaced by the extraction result.
    if (!(await stillOwnsDest())) {
      throw new ExtractFailure("dest_drift", `destination was replaced externally: ${options.destDir}`);
    }
    await fs.promises.rename(staging, options.destDir);
    staging = null;
    published = true;
    return extracted;
  } finally {
    // Only this call's own staging directory is ever cleaned up.
    if (staging !== null) {
      try {
        await fs.promises.rm(staging, { recursive: true, force: true });
      } catch {
        // best-effort cleanup of the staging directory this call created
      }
    }
    if (!published && claimed) {
      // Reclaim only if the placeholder is still the exact object this
      // call created AND still empty; a concurrently populated or replaced
      // destination is foreign and left exactly as it is.
      try {
        if (await stillOwnsDest()) {
          if ((await fs.promises.readdir(options.destDir)).length === 0) {
            await fs.promises.rmdir(options.destDir);
          }
        }
      } catch {
        // nothing reclaimable
      }
    }
  }
}

async function extractInto(staging: string, options: ExtractOptions): Promise<{ files: number; bytes: number }> {
  const charge = (n: number): void => {
    used += n;
    if (used > options.maxBytes) {
      throw new ExtractFailure("size_cap", "extraction exceeded the declared unpack byte cap");
    }
  };

  let used = 0;
  let entries = 0;
  let files = 0;
  const executableEntries: string[] = [];
  {
    const input = fs.createReadStream(options.archivePath);
    const gunzip = createGunzip();
    const reader = streamBlockReader(input.pipe(gunzip));

    let pending: { path?: string } = {};
    const deferredLinks: PendingLink[] = [];
    const allowSet = new Set(options.allowedSymlinks ?? []);

    const readBlock = async (): Promise<Buffer | null> => {
      charge(BLOCK);
      return reader.block();
    };

    // Reads exactly `size` payload bytes; data and its zero padding occupy
    // ceil(size / BLOCK) whole blocks, which are all charged to the cap
    // before any allocation.
    const readData = async (size: number, limit: number): Promise<Buffer> => {
      if (!Number.isSafeInteger(size) || size < 0) {
        throw new ExtractFailure("bad_size", "member size is not a safe non-negative integer");
      }
      if (size > limit) {
        throw new ExtractFailure("size_cap", `member data of ${size} bytes exceeds its bound of ${limit}`);
      }
      const payload = Buffer.alloc(size);
      const blocks = Math.ceil(size / BLOCK);
      let filled = 0;
      for (let i = 0; i < blocks; i += 1) {
        const block = await readBlock();
        if (block === null) throw new ExtractFailure("truncated", "archive ended inside member data");
        const take = Math.min(BLOCK, size - filled);
        block.subarray(0, take).copy(payload, filled);
        filled += take;
      }
      return payload;
    };

    for (;;) {
      if (options.signal?.aborted) throw new ExtractFailure("canceled", "extraction canceled");
      const block = await readBlock();
      if (block === null) throw new ExtractFailure("truncated", "archive ended without terminator");
      if (block.every((byte) => byte === 0)) break;
      entries += 1;
      if (entries > MAX_ENTRIES) {
        throw new ExtractFailure("entry_cap", `archive exceeds ${MAX_ENTRIES} entries`);
      }

      const header = parseHeader(block, pending);
      pending = {};

      if (header.typeflag === "x" || header.typeflag === "g") {
        const records = await readData(header.size, MAX_PAX_RECORD_BYTES);
        const text = records.toString("utf8");
        for (const record of text.split("\n")) {
          const match = /^(\d+) ([^=]+)=(.*)$/.exec(record);
          if (match && match[2] === "path") pending.path = match[3];
        }
        continue;
      }

      if (header.typeflag === "L") {
        const nameBytes = await readData(header.size, MAX_PAX_RECORD_BYTES);
        pending.path = nameBytes.toString("utf8").replace(/\0+$/, "");
        continue;
      }

      if (header.typeflag === "5") {
        const relative = safeRelative(header.name, "directory entry");
        const target = resolveInside(staging, relative);
        await fs.promises.mkdir(target, { recursive: true });
        // Owner rwx is always guaranteed on directories so extraction can
        // traverse and populate them; other bits follow the archive.
        await fs.promises.chmod(target, (header.mode | 0o700) & 0o777);
        await readData(header.size, 0);
        continue;
      }

      if (header.typeflag === "2" || header.typeflag === "1") {
        const relative = safeRelative(header.name, "link entry");
        if (!allowSet.has(relative)) {
          throw new ExtractFailure("link_not_allowed", `link entry not allowlisted: ${relative}`);
        }
        const linkTarget = header.linkname;
        if (options.expectedLinks && options.expectedLinks[relative] !== linkTarget) {
          throw new ExtractFailure("link_target_mismatch", `unexpected link target: ${relative}`);
        }
        if (linkTarget.startsWith("/") || (linkTarget.split("/").includes("..") && options.expectedLinks?.[relative] !== linkTarget)) {
          throw new ExtractFailure("link_escape", `link target escapes the tree: ${relative} -> ${linkTarget}`);
        }
        deferredLinks.push({ type: header.typeflag === "1" ? "hardlink" : "symlink", linkname: linkTarget, relative });
        await readData(header.size, 0);
        continue;
      }

      if (header.typeflag === "0" || header.typeflag === "\0" || header.typeflag === "7") {
        const relative = safeRelative(header.name, "file entry");
        if (relative === "" || relative === ".") throw new ExtractFailure("bad_path", "file entry has no usable name");
        const target = resolveInside(staging, relative);
        await fs.promises.mkdir(path.dirname(target), { recursive: true });
        const payload = await readData(header.size, options.maxBytes);
        const output = fs.createWriteStream(target, { mode: header.mode || 0o644 });
        const written = new Promise<void>((resolve, reject) => {
          output.on("error", reject);
          output.on("close", () => resolve());
        });
        output.end(payload);
        await written;
        if (header.mode) await fs.promises.chmod(target, header.mode);
        if ((header.mode & 0o111) !== 0) executableEntries.push(relative);
        files += 1;
        continue;
      }

      throw new ExtractFailure("entry_type_rejected", `unsupported tar entry type '${header.typeflag}'`);
    }

    for (const link of deferredLinks) {
      if (options.signal?.aborted) throw new ExtractFailure("canceled", "extraction canceled");
      const target = resolveInside(staging, link.relative);
      // Deferred links must not turn a later link's parent into a symlink.
      let parent = path.dirname(target);
      while (parent !== staging) {
        const st = await fs.promises.lstat(parent);
        if (!st.isDirectory() || st.isSymbolicLink()) throw new ExtractFailure("link_escape", `link parent is not a real directory: ${link.relative}`);
        parent = path.dirname(parent);
      }
      if (link.type === "hardlink") {
        const source = resolveInside(staging, link.linkname);
        const sourceReal = await fs.promises.realpath(source);
        if (!sourceReal.startsWith(await fs.promises.realpath(staging) + path.sep)) throw new ExtractFailure("link_escape", `hardlink source escapes root: ${link.relative}`);
        const stat = await fs.promises.stat(source).catch(() => {
          throw new ExtractFailure("truncated", `hardlink source missing: ${link.linkname}`);
        });
        if (!stat.isFile()) throw new ExtractFailure("link_escape", `hardlink source is not a regular file: ${link.linkname}`);
        charge(stat.size);
        await fs.promises.copyFile(source, target);
      } else {
        // Symlink targets must resolve inside the tree they will live in.
        resolveInside(staging, path.join(path.dirname(link.relative), link.linkname));
        await fs.promises.symlink(link.linkname, target);
      }
    }

    // All links are installed after files. Resolve the completed link graph,
    // including intermediate symlinks, before publishing any directory.
    for (const link of deferredLinks) {
      const resolved = await fs.promises.realpath(resolveInside(staging, link.relative));
      if (!resolved.startsWith(await fs.promises.realpath(staging) + path.sep)) throw new ExtractFailure("link_escape", `link graph escapes root: ${link.relative}`);
    }

    // Verify executability for every entry that declared an execute bit.
    for (const relative of executableEntries) {
      try {
        fs.accessSync(resolveInside(staging, relative), fs.constants.X_OK);
      } catch {
        throw new ExtractFailure("mode_verify_failed", `extracted entry is not executable as declared: ${relative}`);
      }
    }
  }
  return { files, bytes: used };
}

export async function extractTarGz(options: ExtractOptions): Promise<ExtractResult> {
  try {
    const result = await extract(options);
    return { kind: "ok", root: options.destDir, files: result.files, bytes: result.bytes };
  } catch (error) {
    if (error instanceof ExtractFailure) {
      return { kind: "failed", code: error.code, message: error.message };
    }
    return { kind: "failed", code: "extract_failed", message: String(error) };
  }
}
