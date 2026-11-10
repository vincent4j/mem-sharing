// Native executable paths only: no shell, launcher aliases, or cwd search.
import path from "node:path";

export function executableCandidates(
  tool: "python" | "git",
  platform: NodeJS.Platform = process.platform,
  searchPath: string = process.env.PATH ?? "",
  candidateDirs?: readonly string[],
): string[] {
  const windows = platform === "win32";
  const paths = windows ? path.win32 : path.posix;
  const defaults = windows ? [] : ["/usr/bin", "/usr/local/bin", "/opt/homebrew/bin", "/opt/local/bin"];
  const dirs = candidateDirs ?? [...defaults, ...searchPath.split(paths.delimiter)];
  const names = windows ? (tool === "python" ? ["python.exe", "python3.exe"] : ["git.exe"]) : [tool === "python" ? "python3" : "git"];
  const seen = new Set<string>();
  return dirs.flatMap(directory => {
    // Windows PATH can contain quoted directories with spaces.
    const dir = windows ? directory.replace(/^"(.*)"$/, "$1") : directory;
    if (!paths.isAbsolute(dir)) return [];
    return names.map(name => paths.join(dir, name));
  }).filter(candidate => {
    const key = windows ? candidate.toLowerCase() : candidate;
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
}
