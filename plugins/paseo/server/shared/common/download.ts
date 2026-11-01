// GENERATED FILE — do not edit by hand.
// True source: plugins/shared/src/<name> (run plugins/shared/sync-to-plugins.mjs).
// memSharing plugin common layer — verified download into a staging file.
// True source: plugins/shared/src. Generated copy: plugin server bundles.
//
// Downloads run only after host-approved dependency preparation. The URL
// always comes from a validated supply manifest (https enforced there);
// this module additionally caps bytes, streams SHA-256, follows only
// https redirects, honors write backpressure, attaches stream error
// handlers before any I/O can fail, and cleans up its own staging file on
// any failure.

import { createHash, type Hash } from "node:crypto";
import fs from "node:fs";
import path from "node:path";

export type DownloadResult =
  | { kind: "ok"; path: string; sha256: string; bytes: number }
  | { kind: "failed"; code: string; message: string };

export interface DownloadOptions {
  readonly url: string;
  readonly expectedSha256: string;
  readonly maxBytes: number;
  readonly stagingPath: string;
  readonly signal?: AbortSignal;
  readonly timeoutMs?: number;
  readonly maxRedirects?: number;
  /**
   * Test seam only: allows plain-http transport so local fixtures can run.
   * Never set by plugin code; production URLs come from a supply manifest
   * that validateSupplyManifest already restricts to https.
   */
  readonly allowInsecureTransportForTests?: boolean;
}

class DownloadFailure extends Error {
  readonly code: string;
  constructor(code: string, message: string) {
    super(message);
    this.code = code;
  }
}

type Sink = (chunk: Buffer) => void | Promise<void>;

async function fetchToStream(
  url: string,
  redirectsLeft: number,
  sink: Sink,
  hash: Hash,
  options: DownloadOptions,
): Promise<number> {
  if (!options.allowInsecureTransportForTests && !url.startsWith("https://")) {
    throw new DownloadFailure("url_rejected", "only https downloads are allowed");
  }
  const transport: typeof import("node:https") = url.startsWith("https://")
    ? ((await import("node:https")) as typeof import("node:https"))
    : ((await import("node:http")) as unknown as typeof import("node:https"));
  const { get } = transport;
  return new Promise<number>((resolve, reject) => {
    let settled = false;
    let request: import("node:http").ClientRequest | undefined;
    const fail = (code: string, message: string): void => {
      if (settled) return;
      settled = true;
      request?.destroy();
      reject(new DownloadFailure(code, message));
    };
    const complete = (bytes: number): void => {
      if (settled) return;
      settled = true;
      resolve(bytes);
    };
    try {
      request = get(url, async (response) => {
        const status = response.statusCode ?? 0;
        if (status >= 301 && status <= 308 && response.headers.location) {
          response.resume();
          if (redirectsLeft <= 0) {
            fail("too_many_redirects", "download exceeded redirect limit");
            return;
          }
          let next: string;
          try {
            next = new URL(response.headers.location, url).toString();
          } catch {
            fail("bad_redirect", `redirect Location is not a valid URL: ${response.headers.location}`);
            return;
          }
          fetchToStream(next, redirectsLeft - 1, sink, hash, options).then(complete, (error) => {
            fail(
              error instanceof DownloadFailure ? error.code : "request_failed",
              error instanceof Error ? error.message : String(error),
            );
          });
          return;
        }
        if (status !== 200) {
          response.resume();
          fail("http_status", `download returned HTTP ${status}`);
          return;
        }
        let total = 0;
        // Async iteration gives real backpressure: the response pauses
        // until each chunk is written and awaited, so slow disks cannot
        // queue the whole transfer in memory.
        try {
          for await (const chunk of response as NodeJS.ReadableStream) {
            const data = Buffer.isBuffer(chunk) ? chunk : Buffer.from(chunk as string);
            total += data.length;
            if (total > options.maxBytes) {
              fail("size_cap", "download exceeded the declared byte cap");
              return;
            }
            hash.update(data);
            await sink(data);
          }
        } catch (error) {
          fail(
            "transfer_failed",
            error instanceof Error ? error.message : String(error),
          );
          return;
        }
        complete(total);
        response.on("error", (error) => fail("transfer_failed", error.message));
      });
      request.on("error", (error) => {
        if (error instanceof DownloadFailure) {
          fail(error.code, error.message);
          return;
        }
        fail("request_failed", error.message);
      });
    } catch (error) {
      fail("request_failed", error instanceof Error ? error.message : String(error));
      return;
    }
    if (options.signal) {
      const onAbort = (): void => fail("canceled", "download canceled");
      if (options.signal.aborted) onAbort();
      else options.signal.addEventListener("abort", onAbort, { once: true });
    }
    if (options.timeoutMs) {
      request?.setTimeout(options.timeoutMs, () => fail("timeout", "download timed out"));
    }
  });
}

// Downloads to stagingPath + ".part-<pid>-<ts>", verifies the hash, then
// renames into place. On any failure the partial file this call created is
// removed; nothing outside that file is touched.
export async function downloadVerified(options: DownloadOptions): Promise<DownloadResult> {
  if (!/^[0-9a-f]{64}$/.test(options.expectedSha256)) {
    return { kind: "failed", code: "bad_expected_hash", message: "expected sha256 must be 64 lowercase hex characters" };
  }
  if (!Number.isSafeInteger(options.maxBytes) || options.maxBytes <= 0) {
    return { kind: "failed", code: "bad_size_cap", message: "maxBytes must be a positive integer" };
  }
  let partPath = "";
  let output: fs.WriteStream | undefined;
  let partCreated = false;
  // Identity of the part object this call created, bound from the open
  // descriptor itself (no path race). Shared by the success and failure
  // branches: EVERY unlink/rm of the part path must re-verify it.
  let partDev = -1;
  let partIno = -1;
  const stillOwnsPart = async (): Promise<boolean> => {
    if (!partCreated) return false;
    try {
      const current = await fs.promises.lstat(partPath);
      return current.dev === partDev && current.ino === partIno && current.isFile();
    } catch {
      return false;
    }
  };
  try {
    await fs.promises.mkdir(path.dirname(options.stagingPath), { recursive: true });
    // The final target must never be clobbered: publishing uses an atomic
    // no-replace link below. The part file is created exclusively ('ax') and
    // the descriptor is kept; there is no probe, unlink, or reopen here.
    partPath = `${options.stagingPath}.part-${process.pid}-${Date.now()}-${Math.random().toString(16).slice(2, 10)}`;
    output = fs.createWriteStream(partPath, { flags: "ax" });
    output.on("open", (fd) => {
      partCreated = true;
      // Bind to the descriptor's own object identity; no path race.
      try {
        const stat = fs.fstatSync(fd);
        partDev = stat.dev;
        partIno = stat.ino;
      } catch {
        // stat failure leaves the sentinel; the final check then drifts
        // closed rather than unlinking something unverified.
      }
    });
    // Attach before any await so stream errors can never escape as
    // uncaught exceptions.
    const outputFailure = new Promise<never>((_, reject) => {
      output!.on("error", (error) => reject(new DownloadFailure("write_failed", error.message)));
    });
    const hash = createHash("sha256");
    const sink: Sink = (chunk) => {
      if (!output!.write(chunk)) {
        return new Promise<void>((resolve) => {
          output!.once("drain", () => resolve());
        });
      }
    };
    const transfer = fetchToStream(options.url, options.maxRedirects ?? 4, sink, hash, options);
    const bytes = await Promise.race([transfer, outputFailure]).finally(() => {
      // The losing promise must still have a handler attached.
      transfer.catch(() => {});
      outputFailure.catch(() => {});
    });
    await new Promise<void>((resolve, reject) => {
      output!.on("error", (error) => reject(new DownloadFailure("write_failed", error.message)));
      output!.end(() => resolve());
    });
    const actual = hash.digest("hex");
    if (actual !== options.expectedSha256) {
      throw new DownloadFailure("hash_mismatch", `downloaded sha256 ${actual} does not match approved manifest`);
    }
    // The hash was computed over THIS descriptor's bytes; publishing must
    // link the same object. If the part path now holds anything else (a
    // mid-transfer rename-and-replace), no final is created and the
    // replacement is preserved untouched. Accepted boundary: a
    // same-privilege non-cooperating process can still race between this
    // check and the link syscall itself (same narrow window as tar).
    if (!(await stillOwnsPart())) {
      throw new DownloadFailure("part_drift", "part file was replaced externally; refusing to publish");
    }
    // Atomic no-replace publish: link fails with EEXIST if anything
    // (including a concurrent writer) created the target meanwhile.
    try {
      await fs.promises.link(partPath, options.stagingPath);
    } catch (error) {
      const code = (error as NodeJS.ErrnoException).code;
      if (code === "EEXIST" || code === "ENOTEMPTY" || code === "EISDIR" || code === "EPERM") {
        throw new DownloadFailure("target_conflict", `staging target appeared during transfer: ${options.stagingPath} (${code})`);
      }
      throw error;
    }
    // Final unlink re-verifies ownership once more: only the exact object
    // this call created is removed; a replaced path is preserved untouched.
    if (!(await stillOwnsPart())) {
      throw new DownloadFailure("part_drift", "part file was replaced before cleanup; leaving it untouched");
    }
    await fs.promises.unlink(partPath);
    partCreated = false;
    return { kind: "ok", path: options.stagingPath, sha256: actual, bytes };
  } catch (error) {
    output?.destroy();
    // Failure cleanup is identity-bound too: a drifted part path (foreign
    // replacement) is never deleted; only our own object is.
    if (partPath.length > 0 && partCreated && (await stillOwnsPart())) {
      try {
        await fs.promises.rm(partPath, { force: true });
      } catch {
        // best-effort cleanup of the part file this call created
      }
    }
    if (error instanceof DownloadFailure) {
      return { kind: "failed", code: error.code, message: error.message };
    }
    return { kind: "failed", code: "download_failed", message: String(error) };
  }
}
