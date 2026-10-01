// Node module-resolution hook: lets Node load the app's TypeScript (lib/**/*.ts) under its built-in type stripping,
// where the app's imports are written without an extension ("../errors", "./live"). Used by scripts/record-mocks.mjs only.
export async function resolve(specifier, context, nextResolve) {
  if ((specifier.startsWith("./") || specifier.startsWith("../")) && !/\.[a-z]+$/i.test(specifier)) {
    try {
      return await nextResolve(`${specifier}.ts`, context);
    } catch {
      return nextResolve(`${specifier}/index.ts`, context);
    }
  }
  return nextResolve(specifier, context);
}
