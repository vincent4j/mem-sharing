import fs from "node:fs";
import path from "node:path";

// Inspect the entire existing prefix before the first mutation. In particular,
// recursive mkdir must never follow an existing symlink into a foreign tree.
export function ensureRealDirectory(directory: string): void {
  if (!path.isAbsolute(directory) || path.resolve(directory) !== directory) throw new Error("absolute real directory required");
  const root = path.parse(directory).root;
  const chain = [root];
  for (const component of directory.slice(root.length).split(path.sep).filter(Boolean)) chain.push(path.join(chain[chain.length - 1], component));
  const validate = (file: string): boolean => {
    try {
      const st = fs.lstatSync(file);
      if (!st.isDirectory() || st.isSymbolicLink()) throw new Error("unsafe directory ancestor: " + file);
      return true;
    } catch (error) {
      if ((error as NodeJS.ErrnoException).code === "ENOENT") return false;
      throw error;
    }
  };
  for (const file of chain) if (!validate(file)) break;
  for (let i = 0; i < chain.length; i++) {
    if (i > 0 && !validate(chain[i - 1])) throw new Error("directory parent disappeared");
    if (!validate(chain[i])) {
      try { fs.mkdirSync(chain[i], { mode: 0o700 }); }
      catch (error) { if ((error as NodeJS.ErrnoException).code !== "EEXIST") throw error; }
      if (!validate(chain[i])) throw new Error("directory creation failed");
    }
  }
}
