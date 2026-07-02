import assert from 'node:assert/strict';
import { test } from 'node:test';
import { computeHIndex } from './scopusService';

test('computeHIndex: classic case (papers with citations [10,8,5,4,3] -> h=4)', () => {
  assert.equal(computeHIndex([10, 8, 5, 4, 3]), 4);
});

test('computeHIndex: no papers -> h=0', () => {
  assert.equal(computeHIndex([]), 0);
});

test('computeHIndex: all-zero citations -> h=0', () => {
  assert.equal(computeHIndex([0, 0, 0]), 0);
});

test('computeHIndex: every paper cited at least once per rank -> h=N', () => {
  assert.equal(computeHIndex([5, 5, 5, 5, 5]), 5);
});

test('computeHIndex: unsorted input is handled the same as sorted', () => {
  assert.equal(computeHIndex([3, 10, 4, 8, 5]), computeHIndex([10, 8, 5, 4, 3]));
});
