// memSharing plugin common layer — plan digests and confirmation evidence.
// True source: plugins/shared/src. Generated copy: plugin server bundles.
//
// The Python installer compares approval files to plans by dict equality
// (order-insensitive), but the host-side confirmation must still bind the
// user action to the exact plan the user saw. We do that with a canonical
// JSON digest: recursive key sorting, no whitespace, UTF-8 bytes. Evidence
// fields (confirmed_at UTC "Z", reference) mirror registry._evidence.

import { createHash } from "node:crypto";

export function sha256Hex(input: string | Uint8Array): string {
  return createHash("sha256").update(input).digest("hex");
}

export function canonicalJson(value: unknown): string {
  return JSON.stringify(sortValue(value));
}

function sortValue(value: unknown): unknown {
  if (Array.isArray(value)) return value.map(sortValue);
  if (value !== null && typeof value === "object") {
    const sorted: Record<string, unknown> = {};
    for (const key of Object.keys(value as Record<string, unknown>).sort()) {
      sorted[key] = sortValue((value as Record<string, unknown>)[key]);
    }
    return sorted;
  }
  return value;
}

export function planDigest(plan: unknown): string {
  return sha256Hex(canonicalJson(plan));
}

// registry._time accepts YYYY-MM-DDTHH:MM:SS(.fff)?Z — we always emit
// whole seconds to match the examples in the Python sources.
export function utcConfirmedAt(now: Date = new Date()): string {
  return now.toISOString().replace(/\.\d{3}Z$/, "Z");
}

export interface Evidence {
  readonly confirmed_at: string;
  readonly reference: string;
}

export function buildEvidence(reference: string, now: Date = new Date()): Evidence {
  if (typeof reference !== "string" || reference.trim().length === 0) {
    throw new Error("confirmation reference must be non-empty text");
  }
  if (reference.length > 512) {
    throw new Error("confirmation reference too long");
  }
  return { confirmed_at: utcConfirmedAt(now), reference };
}

// Approval file = exact plan object plus evidence keys. Python compares by
// dict equality, so key order does not matter; content does.
export function buildApproval(plan: Record<string, unknown>, evidence: Evidence): Record<string, unknown> {
  return { ...plan, confirmed_at: evidence.confirmed_at, reference: evidence.reference };
}

export function isSha256Hex(value: unknown): value is string {
  return typeof value === "string" && /^[0-9a-f]{64}$/.test(value);
}
