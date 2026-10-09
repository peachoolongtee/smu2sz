// node --import ./scripts/ts-resolve.mjs --test scripts/<file>.test.mjs  (see package.json test:unit)
import { register } from "node:module";

register("./ts-resolve-hooks.mjs", import.meta.url);
