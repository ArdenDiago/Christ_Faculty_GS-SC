// Test client for the CitationService gRPC server. Exercises each RPC,
// printing results as they stream in plus a wall-clock time to first message
// and time to completion - the numbers that matter for the REST-vs-gRPC
// comparison against OldCode's /generate_report. Port of
// python-grpc-prototype/client.py.
//
// Usage: tsx scripts/testClient.ts [gscholar|scopus|combined|all]
import * as grpc from '@grpc/grpc-js';
import {
  CitationServiceClient,
  type AuthorPapers,
  type AuthorScopusPapers,
  type CombinedAuthorStats,
} from '../src/generated/citations';
import { GRPC_PORT } from '../src/lib/config';

function drainStream<T>(
  label: string,
  startCall: () => grpc.ClientReadableStream<T>,
  describe: (item: T) => string,
): Promise<void> {
  console.log(`\n=== ${label} ===`);
  const start = performance.now();
  let firstMs: number | null = null;
  let count = 0;
  return new Promise((resolve, reject) => {
    const call = startCall();
    call.on('data', (item: T) => {
      if (firstMs === null) firstMs = performance.now() - start;
      count += 1;
      console.log(`  [${count}] ${describe(item)}`);
    });
    call.on('end', () => {
      const totalMs = performance.now() - start;
      const firstStr = firstMs === null ? 'n/a' : `${(firstMs / 1000).toFixed(2)}s`;
      console.log(`  -> ${count} authors, first message in ${firstStr}, total ${(totalMs / 1000).toFixed(2)}s`);
      resolve();
    });
    call.on('error', (err) => reject(err));
  });
}

async function main(): Promise<void> {
  const which = process.argv[2] ?? 'all';
  const client = new CitationServiceClient(`localhost:${GRPC_PORT}`, grpc.credentials.createInsecure());

  try {
    if (which === 'gscholar' || which === 'all') {
      await drainStream<AuthorPapers>(
        'StreamGoogleScholarPapers',
        () => client.streamGoogleScholarPapers({}),
        (author) => `${author.name}: ${author.papers.length} papers`,
      );
    }
    if (which === 'scopus' || which === 'all') {
      await drainStream<AuthorScopusPapers>(
        'StreamScopusPapers',
        () => client.streamScopusPapers({}),
        (author) => `${author.name}: ${author.papers.length} papers`,
      );
    }
    if (which === 'combined' || which === 'all') {
      await drainStream<CombinedAuthorStats>(
        'StreamCombinedStats',
        () => client.streamCombinedStats({}),
        (stats) =>
          `${stats.name}: GS papers=${stats.papersGoogleScholar} citations=${stats.citationsGoogleScholar} ` +
          `h=${stats.hIndexGoogleScholar} | Scopus papers=${stats.papersScopus} citations=${stats.citationsScopus} ` +
          `h=${stats.hIndexScopus}`,
      );
    }
  } finally {
    client.close();
  }
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
