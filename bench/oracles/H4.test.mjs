import test from "node:test";
import assert from "node:assert/strict";
import { pathToFileURL } from "node:url";
import { join } from "node:path";
const load = (f) => import(pathToFileURL(join(process.cwd(), f)).href);
test("total of empty cart is 0", async () => {
  const { total } = await load("src/cart.js");
  assert.equal(total([]), 0);
});
