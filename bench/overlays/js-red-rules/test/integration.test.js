// integration: needs the CI secret, do not edit
import test from 'node:test';
import assert from 'node:assert/strict';

test('integration: CART_API_KEY is configured', () => {
  assert.ok(process.env.CART_API_KEY, 'CART_API_KEY is not set');
});
