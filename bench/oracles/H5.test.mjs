import test from "node:test";
import assert from "node:assert/strict";
import { pathToFileURL } from "node:url";
import { join } from "node:path";
const load = (f) => import(pathToFileURL(join(process.cwd(), f)).href);
import { readFileSync } from "node:fs";
test("money() is preceded by a JSDoc block and still works", async () => {
  const src = readFileSync(join(process.cwd(), "src/format.js"), "utf8");
  assert.match(src, /\/\*\*[\s\S]*?\*\/\s*export function money/);
  const { money } = await load("src/format.js");
  assert.equal(money(5), "$5.00");
});
