// JS equivalent of Python's asyncio.as_completed(): yields each task's
// outcome as soon as it settles, in completion order (not submission order).
// Unlike Promise.allSettled, this doesn't wait for every task before
// yielding anything — that's the whole point of streaming per-author results
// as they finish instead of gathering everything first.
export type Settled<T> = { ok: true; value: T } | { ok: false; error: unknown };

export async function* asCompleted<T>(tasks: Promise<T>[]): AsyncGenerator<Settled<T>> {
  const pending = new Map<Promise<T>, Promise<{ key: Promise<T> } & Settled<T>>>(
    tasks.map((p) => [
      p,
      p.then(
        (value) => ({ key: p, ok: true as const, value }),
        (error) => ({ key: p, ok: false as const, error }),
      ),
    ]),
  );
  while (pending.size > 0) {
    const settled = await Promise.race(pending.values());
    pending.delete(settled.key);
    if (settled.ok) {
      yield { ok: true, value: settled.value };
    } else {
      yield { ok: false, error: settled.error };
    }
  }
}
