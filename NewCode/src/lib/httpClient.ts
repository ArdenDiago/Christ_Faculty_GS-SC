import { Agent, request } from 'undici';

// Interruptible sleep: rejects immediately if `signal` fires mid-wait, so the
// stream-cancellation path (see gscholarService/scopusService `finally`
// blocks) doesn't have to wait out an in-progress retry delay.
export function sleep(ms: number, signal?: AbortSignal): Promise<void> {
  return new Promise((resolve, reject) => {
    if (signal?.aborted) {
      reject(new DOMException('Aborted', 'AbortError'));
      return;
    }
    const timer = setTimeout(resolve, ms);
    signal?.addEventListener(
      'abort',
      () => {
        clearTimeout(timer);
        reject(new DOMException('Aborted', 'AbortError'));
      },
      { once: true },
    );
  });
}

export interface HttpResponse {
  status: number;
  text(): Promise<string>;
  json(): Promise<unknown>;
}

// Closest analog to aiohttp's ClientSession.get(): a plain per-call wrapper
// over undici's `request`, taking the same (headers, dispatcher, signal,
// timeout) knobs OldCode/the Python prototype configure per orchestrator.
export async function httpGet(
  url: string,
  headers: Record<string, string>,
  dispatcher: Agent,
  signal: AbortSignal,
  timeoutMs: number,
): Promise<HttpResponse> {
  const { statusCode, body } = await request(url, {
    method: 'GET',
    headers,
    dispatcher,
    signal,
    headersTimeout: timeoutMs,
    bodyTimeout: timeoutMs,
  });
  return {
    status: statusCode,
    text: () => body.text(),
    json: () => body.json(),
  };
}

// undici's Agent sizes a connection pool per-origin via `connections`, which
// is the practical analog to aiohttp's `TCPConnector(limit_per_host=...)`
// (the effective bound in OldCode/the Python prototype, since each
// orchestrator only ever talks to one or two hosts).
export function createAgent(connections: number): Agent {
  return new Agent({ connections });
}
