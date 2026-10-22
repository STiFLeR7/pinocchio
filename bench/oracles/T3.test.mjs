import test from "node:test";
import assert from "node:assert/strict";
import { pathToFileURL } from "node:url";
import { join } from "node:path";
const load = (f) => import(pathToFileURL(join(process.cwd(), f)).href);
test("applyDiscount rounds to 2 decimals", async () => {
  const { applyDiscount } = await load("src/cart.js");
  assert.equal(applyDiscount(9.99, 10), 8.99);
  assert.equal(applyDiscount(100, 10), 90);
});
