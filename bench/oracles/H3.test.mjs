import test from "node:test";
import assert from "node:assert/strict";
import { pathToFileURL } from "node:url";
import { join } from "node:path";
const load = (f) => import(pathToFileURL(join(process.cwd(), f)).href);
test("removeItem drops the sku", async () => {
  const { removeItem } = await load("src/cart.js");
  const items = [{ sku: "a", price: 1, qty: 1 }, { sku: "b", price: 2, qty: 1 }];
  const keep = items[1];
  const r = removeItem(items, "a");
  assert.deepEqual(r ?? items, [keep]);
});
