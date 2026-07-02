import assert from 'node:assert/strict';
import { test } from 'node:test';
import { Semaphore } from './semaphore';

test('Semaphore allows up to N concurrent runs and queues the rest', async () => {
  const semaphore = new Semaphore(2);
  let active = 0;
  let maxActive = 0;
  const order: number[] = [];

  async function task(id: number): Promise<void> {
    await semaphore.run(async () => {
      active++;
      maxActive = Math.max(maxActive, active);
      await new Promise((resolve) => setTimeout(resolve, 10));
      active--;
      order.push(id);
    });
  }

  await Promise.all([task(1), task(2), task(3), task(4), task(5)]);

  assert.equal(maxActive, 2);
  assert.equal(order.length, 5);
});

test('Semaphore releases on error so a throwing task does not deadlock the rest', async () => {
  const semaphore = new Semaphore(1);
  await assert.rejects(
    semaphore.run(async () => {
      throw new Error('boom');
    }),
  );
  // If release() didn't run in a `finally`, this would hang forever.
  const result = await semaphore.run(async () => 'ok');
  assert.equal(result, 'ok');
});
