// Test-only resolve hook: the plugin's server sources import the generated
// common copy with extensionless specifiers (idiomatic for the host
// bundler); Node's type-stripping runner needs explicit extensions, so this
// hook appends .ts for relative extensionless specifiers.
export async function resolve(specifier, context, next) {
  if ((specifier.startsWith("./") || specifier.startsWith("../")) && !/\.[cm]?[jt]sx?$/.test(specifier)) {
    try {
      return await next(`${specifier}.ts`, context);
    } catch {
      // fall through to the default resolution
    }
  }
  return next(specifier, context);
}
