import test from "node:test";
import assert from "node:assert/strict";
import { pathToFileURL } from "node:url";
import { join } from "node:path";
const load = (f) => import(pathToFileURL(join(process.cwd(), f)).href);
test("lineTotal is exported and total uses it", async () => {
  const { lineTotal, total } = await load("src/cart.js");
  assert.equal(typeof lineTotal, "function");
  assert.equal(lineTotal({ sku: "a", price: 2, qty: 3 }), 6);
  assert.match(total.toString(), /lineTotal/);
});
test("total multiplies by qty", async () => {
  const { total } = await load("src/cart.js");
  assert.equal(total([{ sku: "a", price: 2, qty: 3 }, { sku: "b", price: 1.5, qty: 2 }]), 9);
});
test("applyDiscount rounds to 2 decimals", async () => {
  const { applyDiscount } = await load("src/cart.js");
  assert.equal(applyDiscount(9.99, 10), 8.99);
  assert.equal(applyDiscount(100, 10), 90);
});
test("total of empty cart is 0", async () => {
  const { total } = await load("src/cart.js");
  assert.equal(total([]), 0);
});
