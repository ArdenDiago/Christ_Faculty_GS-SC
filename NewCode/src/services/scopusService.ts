// Scopus data fetching - same official-API tactics as OldCode/the Python
// prototype (python-grpc-prototype/services/scopus_service.py), exposed as
// async generators for gRPC streaming.
import type { Agent } from 'undici';
import { asCompleted } from '../lib/asCompleted';
import { createAgent, httpGet, sleep } from '../lib/httpClient';
import { Semaphore } from '../lib/semaphore';
import { SCOPUS_API_KEY } from '../lib/config';
import type { AuthorScopusPapers, ScopusPaper, ScopusStats } from '../types';
import type { ScopusAuthor } from './authors';

const HEADERS = { 'X-ELS-APIKey': SCOPUS_API_KEY, Accept: 'application/json' };

interface ScopusSearchResults {
  'search-results'?: {
    entry?: Array<Record<string, string | undefined>>;
    'opensearch:totalResults'?: string;
  };
}

function isAbortError(err: unknown): boolean {
  return err instanceof DOMException && err.name === 'AbortError';
}

// Classic H-index: largest N such that N papers each have >= N citations.
// Mutates a copy, not the input, since the input array is otherwise reused
// for the totalCitations sum computed by the caller.
export function computeHIndex(citationCounts: number[]): number {
  const sorted = [...citationCounts].sort((a, b) => b - a);
  let hIndex = 0;
  for (let i = 0; i < sorted.length; i++) {
    if (sorted[i] >= i + 1) hIndex++;
  }
  return hIndex;
}

// Same retry policy as OldCode: flat 1s backoff between attempts, gives up
// after max_retries with no data.
async function getJsonWithRetry(
  url: string,
  authorName: string,
  agent: Agent,
  signal: AbortSignal,
  maxRetries = 3,
): Promise<ScopusSearchResults | null> {
  for (let attempt = 0; attempt < maxRetries; attempt++) {
    try {
      const res = await httpGet(url, HEADERS, agent, signal, 60_000);
      if (res.status === 200) {
        return (await res.json()) as ScopusSearchResults;
      }
      console.log(`Error fetching Scopus for ${authorName} (attempt ${attempt + 1}): Status ${res.status}`);
    } catch (err) {
      if (isAbortError(err)) throw err;
      console.log(`Exception during fetch for ${authorName} (attempt ${attempt + 1}): ${err}`);
    }
    await sleep(1000, signal);
  }
  return null;
}

// Fetch all Scopus papers for one author. Same count=25/start pagination as
// OldCode.
export async function fetchScopusPapersAsync(
  author: ScopusAuthor,
  semaphore: Semaphore,
  agent: Agent,
  signal: AbortSignal,
): Promise<AuthorScopusPapers> {
  const authorName = author.name;
  const authorId = author.scopus_id;
  if (!authorId) {
    return { name: authorName, papers: [], profileLink: '' };
  }

  const baseUrl = `https://api.elsevier.com/content/search/scopus?query=AU-ID(${authorId})`;
  const profileLink = `https://www.scopus.com/authid/detail.uri?authorId=${authorId}`;
  const count = 25;

  return semaphore.run(async () => {
    const papers: ScopusPaper[] = [];
    let start = 0;

    while (true) {
      const url = `${baseUrl}&count=${count}&start=${start}`;
      const data = await getJsonWithRetry(url, authorName, agent, signal);
      if (data === null) {
        console.log(`Failed to fetch Scopus for ${authorName} at start=${start}`);
        break;
      }
      if (!data['search-results']) {
        console.log(`No 'search-results' for ${authorName} at start=${start}`);
        break;
      }
      const entries = data['search-results'].entry ?? [];
      for (const entry of entries) {
        papers.push({
          title: entry['dc:title'] ?? '',
          year: (entry['prism:coverDate'] ?? '').slice(0, 4),
          citations: entry['citedby-count'] ?? '0',
          link: entry['prism:doi'] ?? '',
        });
      }
      const totalResults = parseInt(data['search-results']['opensearch:totalResults'] ?? '0', 10);
      start += count;
      if (entries.length < count || start >= totalResults) break;
    }

    console.log(`Fetched ${papers.length} Scopus papers for ${authorName}`);
    return { name: authorName, papers, profileLink };
  });
}

// Fetch Scopus stats for one author. H-index computed client-side same as
// OldCode (Scopus API has no h-index field).
export async function fetchScopusStatsAsync(
  authorId: string | null,
  authorName: string,
  semaphore: Semaphore,
  agent: Agent,
  signal: AbortSignal,
): Promise<ScopusStats> {
  const empty: ScopusStats = { totalPapers: 0, totalCitations: 0, hIndex: 0 };
  if (!authorId) return empty;

  const baseUrl = `https://api.elsevier.com/content/search/scopus?query=AU-ID(${authorId})`;
  const count = 25;

  return semaphore.run(async () => {
    let start = 0;
    let totalPapers = 0;
    const citations: number[] = [];

    while (true) {
      const url = `${baseUrl}&count=${count}&start=${start}`;
      const data = await getJsonWithRetry(url, authorName, agent, signal);
      if (data === null || !data['search-results']) break;
      const entries = data['search-results'].entry ?? [];
      totalPapers += entries.length;
      for (const entry of entries) {
        citations.push(parseInt(entry['citedby-count'] ?? '0', 10));
      }
      const totalResults = parseInt(data['search-results']['opensearch:totalResults'] ?? '0', 10);
      start += count;
      if (entries.length < count || start >= totalResults) break;
    }

    const totalCitations = citations.reduce((sum, c) => sum + c, 0);
    const hIndex = computeHIndex(citations);

    console.log(
      `Fetched Scopus stats for ${authorName}: ${totalCitations} citations, ${totalPapers} papers, h-index ${hIndex}`,
    );
    return { totalPapers, totalCitations, hIndex };
  });
}

// Async generator: same semaphore(10)/connector-bounded concurrency as
// OldCode's fetch_all_scopus_papers, yielding each author as it completes.
export async function* streamAllScopusPapers(authors: ScopusAuthor[]): AsyncGenerator<AuthorScopusPapers> {
  const semaphore = new Semaphore(10);
  const controller = new AbortController();
  const agent = createAgent(10);
  const tasks = authors.map((author) => fetchScopusPapersAsync(author, semaphore, agent, controller.signal));

  try {
    for await (const settled of asCompleted(tasks)) {
      if (!settled.ok) {
        console.log(`Exception during streamed Scopus fetch: ${settled.error}`);
        continue;
      }
      yield settled.value;
    }
  } finally {
    controller.abort();
    await Promise.allSettled(tasks);
    await agent.close();
  }
}
