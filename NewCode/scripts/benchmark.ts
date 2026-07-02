// Speed/load-time comparison between OldCode's REST endpoint and NewCode's
// gRPC service, run against the SAME live data sources (Google Scholar +
// Scopus) so the underlying fetch tactics (semaphore bounds, retry,
// pagination) are identical on both sides - only the transport differs.
//
// REST is a single atomic response (Flask's jsonify() after
// asyncio.run(...)), so it has no meaningful "time to first result" - the
// whole payload arrives at once. gRPC streams one message per author as
// soon as that author's fetch completes. Both "time to first result" and
// "time to full completion" are recorded for gRPC; only "time to full
// completion" is meaningful for REST.
//
// Usage: tsx scripts/benchmark.ts > /path/to/benchmark-results.json
import * as grpc from '@grpc/grpc-js';
import {
  CitationServiceClient,
  AuthorPapers,
  AuthorScopusPapers,
  CombinedAuthorStats,
} from '../src/generated/citations';
import { GRPC_PORT } from '../src/lib/config';

const REST_BASE = process.env.REST_BASE_URL ?? 'http://127.0.0.1:5000';

interface RestResult {
  system: 'REST';
  source: string;
  totalMs: number;
  statusCode: number;
  authorCount: number;
  bytes: number;
}

interface GrpcResult {
  system: 'gRPC';
  rpc: string;
  firstMessageMs: number | null;
  totalMs: number;
  authorCount: number;
  bytes: number;
}

async function benchmarkRest(source: string): Promise<RestResult> {
  const start = performance.now();
  const res = await fetch(`${REST_BASE}/generate_report`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ source }),
  });
  const text = await res.text();
  const totalMs = performance.now() - start;
  let authorCount = 0;
  try {
    const data = JSON.parse(text);
    authorCount = Array.isArray(data) ? data.length : 0;
  } catch {
    // leave authorCount at 0 if the response wasn't the expected array shape
  }
  return { system: 'REST', source, totalMs, statusCode: res.status, authorCount, bytes: Buffer.byteLength(text) };
}

function benchmarkGrpcStream<T>(
  rpc: string,
  startCall: () => grpc.ClientReadableStream<T>,
  encodedSize: (item: T) => number,
): Promise<GrpcResult> {
  return new Promise((resolve, reject) => {
    const start = performance.now();
    let firstMessageMs: number | null = null;
    let count = 0;
    let bytes = 0;
    const call = startCall();
    call.on('data', (item: T) => {
      if (firstMessageMs === null) firstMessageMs = performance.now() - start;
      count += 1;
      bytes += encodedSize(item);
    });
    call.on('end', () => {
      resolve({ system: 'gRPC', rpc, firstMessageMs, totalMs: performance.now() - start, authorCount: count, bytes });
    });
    call.on('error', (err) => reject(err));
  });
}

interface ComparisonPair {
  label: string;
  restSource: string;
  grpcRpc: string;
  rest: RestResult;
  grpc: GrpcResult;
}

async function main(): Promise<void> {
  const client = new CitationServiceClient(`localhost:${GRPC_PORT}`, grpc.credentials.createInsecure());
  const results: ComparisonPair[] = [];

  async function run(
    label: string,
    restSource: string,
    grpcRpc: string,
    grpcCall: () => Promise<GrpcResult>,
  ): Promise<void> {
    console.error(`\n--- ${label} ---`);
    console.error(`REST: POST /generate_report {source: "${restSource}"} ...`);
    const rest = await benchmarkRest(restSource);
    console.error(`REST done: ${rest.totalMs.toFixed(0)}ms, ${rest.authorCount} authors, ${rest.bytes} bytes`);

    console.error(`gRPC: ${grpcRpc} ...`);
    const grpc = await grpcCall();
    console.error(
      `gRPC done: first=${grpc.firstMessageMs?.toFixed(0)}ms total=${grpc.totalMs.toFixed(0)}ms, ${grpc.authorCount} authors, ${grpc.bytes} bytes`,
    );

    results.push({ label, restSource, grpcRpc, rest, grpc });
  }

  await run('Google Scholar paper details', 'paperDetails', 'StreamGoogleScholarPapers', () =>
    benchmarkGrpcStream<AuthorPapers>(
      'StreamGoogleScholarPapers',
      () => client.streamGoogleScholarPapers({}),
      (item) => AuthorPapers.encode(item).finish().length,
    ),
  );

  await run('Scopus paper details', 'paperDetailsScopus', 'StreamScopusPapers', () =>
    benchmarkGrpcStream<AuthorScopusPapers>(
      'StreamScopusPapers',
      () => client.streamScopusPapers({}),
      (item) => AuthorScopusPapers.encode(item).finish().length,
    ),
  );

  await run('Combined Google Scholar + Scopus stats', 'both', 'StreamCombinedStats', () =>
    benchmarkGrpcStream<CombinedAuthorStats>(
      'StreamCombinedStats',
      () => client.streamCombinedStats({}),
      (item) => CombinedAuthorStats.encode(item).finish().length,
    ),
  );

  client.close();
  console.log(JSON.stringify(results, null, 2));
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
