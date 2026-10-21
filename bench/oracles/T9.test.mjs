import test from "node:test";
import assert from "node:assert/strict";
import { pathToFileURL } from "node:url";
import { join } from "node:path";
const load = (f) => import(pathToFileURL(join(process.cwd(), f)).href);
test("total multiplies by qty", async () => {
  const { total } = await load("src/cart.js");
  assert.equal(total([{ sku: "a", price: 2, qty: 3 }, { sku: "b", price: 1.5, qty: 2 }]), 9);
});
