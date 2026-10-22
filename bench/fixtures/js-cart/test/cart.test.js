import test from 'node:test';
import assert from 'node:assert/strict';
import { total, applyDiscount } from '../src/cart.js';
import { money } from '../src/format.js';

test('total sums single-quantity items', () => {
  assert.equal(total([{ sku: 'a', price: 2, qty: 1 }, { sku: 'b', price: 3, qty: 1 }]), 5);
});

test('applyDiscount takes a percentage off', () => {
  assert.equal(applyDiscount(100, 10), 90);
});

test('money formats two decimals', () => {
  assert.equal(money(5), '$5.00');
});
