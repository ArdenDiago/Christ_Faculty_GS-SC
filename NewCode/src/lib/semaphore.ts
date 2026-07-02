// Equivalent of Python's asyncio.Semaphore, used the same way OldCode/the
// Python prototype use `async with semaphore: <block>` — call `run(fn)` to
// wrap the critical section.
export class Semaphore {
  private available: number;
  private readonly queue: Array<() => void> = [];

  constructor(count: number) {
    this.available = count;
  }

  private acquire(): Promise<void> {
    if (this.available > 0) {
      this.available--;
      return Promise.resolve();
    }
    return new Promise((resolve) => this.queue.push(resolve));
  }

  private release(): void {
    const next = this.queue.shift();
    if (next) {
      next();
    } else {
      this.available++;
    }
  }

  async run<T>(fn: () => Promise<T>): Promise<T> {
    await this.acquire();
    try {
      return await fn();
    } finally {
      this.release();
    }
  }
}
