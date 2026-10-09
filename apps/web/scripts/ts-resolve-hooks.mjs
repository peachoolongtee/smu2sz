// A resolver for the unit tests that import the app's own modules: the app writes extensionless relative imports and "@/" paths
// (Next and tsc resolve them); node's native type stripping does not. Registered by scripts/ts-resolve.mjs.
import { existsSync } from "node:fs";
import { fileURLToPath, pathToFileURL } from "node:url";
import { dirname, resolve as resolvePath } from "node:path";

const root = fileURLToPath(new URL("..", import.meta.url));

function withExtension(path) {
  for (const candidate of [path, `${path}.ts`, `${path}.tsx`, `${path}/index.ts`]) {
    if (existsSync(candidate) && /\.tsx?$/.test(candidate)) return candidate;
  }
  return null;
}

export async function resolve(specifier, context, next) {
  let base = null;
  if (specifier.startsWith("@/")) base = resolvePath(root, specifier.slice(2));
  else if ((specifier.startsWith("./") || specifier.startsWith("../")) && context.parentURL?.startsWith("file:")) base = resolvePath(dirname(fileURLToPath(context.parentURL)), specifier);
  const found = base ? withExtension(base) : null;
  return next(found ? pathToFileURL(found).href : specifier, context);
}

// The mock API imports the recorded answers as JSON without the attribute (the bundler does not need it).
export async function load(url, context, next) {
  if (url.endsWith(".json")) return next(url, { ...context, importAttributes: { ...context.importAttributes, type: "json" } });
  return next(url, context);
}
