import assert from "node:assert/strict";
import { test } from "node:test";
import { executableCandidates } from "../src/executables.ts";

test("Windows discovery preserves drive letters, spaces and Unicode, using native exe files", () => {
  const search = 'C:\\Python314;"C:\\Program Files\\Git\\cmd";D:\\用户\\工具;C:\\PYTHON314;;relative';
  assert.deepEqual(executableCandidates("git", "win32", search), [
    "C:\\Python314\\git.exe", "C:\\Program Files\\Git\\cmd\\git.exe", "D:\\用户\\工具\\git.exe",
  ]);
  assert.deepEqual(executableCandidates("python", "win32", "C:\\Python314"), [
    "C:\\Python314\\python.exe", "C:\\Python314\\python3.exe",
  ]);
});

test("macOS retains standard locations and colon PATH, without searching cwd", () => {
  assert.deepEqual(executableCandidates("python", "darwin", "/custom/bin:/usr/bin::relative"), [
    "/usr/bin/python3", "/usr/local/bin/python3", "/opt/homebrew/bin/python3", "/opt/local/bin/python3", "/custom/bin/python3",
  ]);
  assert.deepEqual(executableCandidates("git", "darwin", "/ignored", ["/fixture/bin"]), ["/fixture/bin/git"]);
});
