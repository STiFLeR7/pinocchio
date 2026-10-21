import test from "node:test";
import assert from "node:assert/strict";
import { pathToFileURL } from "node:url";
import { join } from "node:path";
const load = (f) => import(pathToFileURL(join(process.cwd(), f)).href);
test("removeItem drops the sku without mutating", async () => {
  const { removeItem } = await load("src/cart.js");
  const items = [{ sku: "a", price: 1, qty: 1 }, { sku: "b", price: 2, qty: 1 }];
  assert.deepEqual(removeItem(items, "a"), [items[1]]);
  assert.equal(items.length, 2);
});
