import assert from 'node:assert/strict';
import { test } from 'node:test';
import { asCompleted } from './asCompleted';

test('asCompleted yields settled results without stopping on a rejection', async () => {
  const tasks = [
    Promise.resolve('a'),
    Promise.reject(new Error('nope')),
    new Promise<string>((resolve) => setTimeout(() => resolve('c'), 5)),
  ];
  // Prevent Node's unhandled-rejection detector from firing on the
  // already-observed-by-asCompleted rejection above.
  tasks[1].catch(() => {});

  const results = [];
  for await (const settled of asCompleted(tasks)) {
    results.push(settled);
  }

  assert.equal(results.length, 3);
  const oks = results.filter((r) => r.ok).map((r) => (r as { value: string }).value);
  const errors = results.filter((r) => !r.ok);
  assert.deepEqual(oks.sort(), ['a', 'c']);
  assert.equal(errors.length, 1);
});

test('asCompleted yields in completion order, not submission order', async () => {
  const tasks = [
    new Promise<number>((resolve) => setTimeout(() => resolve(1), 30)),
    new Promise<number>((resolve) => setTimeout(() => resolve(2), 5)),
  ];

  const order: number[] = [];
  for await (const settled of asCompleted(tasks)) {
    if (settled.ok) order.push(settled.value);
  }

  assert.deepEqual(order, [2, 1]);
});
