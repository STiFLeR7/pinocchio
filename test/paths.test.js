import { test } from 'node:test';
import assert from 'node:assert/strict';
import path from 'node:path';
import { norm, confine, rel } from '../src/paths.js';

const root = path.resolve('/tmp/proj');

test('confine keeps inside paths', () => {
  assert.equal(confine(root, 'src/a.js'), path.join(root, 'src', 'a.js'));
  assert.equal(confine(root, path.join(root, 'b.js')), path.join(root, 'b.js'));
});

test('confine rejects traversal and outside absolute paths', () => {
  assert.equal(confine(root, '../../etc/passwd'), null);
  assert.equal(confine(root, path.resolve('/etc/passwd')), null);
});

test('norm makes the same file compare equal (Review Focus 2)', () => {
  assert.equal(norm(path.join(root, 'src', 'a.js')), norm(path.join(root, 'src', '.', 'a.js')));
});

test('norm ignores drive-letter case and slashes on Windows', { skip: process.platform !== 'win32' }, () => {
  assert.equal(norm('D:\\Repo\\src\\a.js'), norm('d:/repo/src/a.js'));
});

test('rel returns forward slashes', () => {
  assert.equal(rel(root, path.join(root, 'src', 'a.js')), 'src/a.js');
});
