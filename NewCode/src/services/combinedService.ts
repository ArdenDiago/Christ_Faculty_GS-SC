// Combined Google Scholar + Scopus stats - same name-keyed join as OldCode,
// streamed per author as each author's pair of fetches completes.
import type { Agent } from 'undici';
import { asCompleted } from '../lib/asCompleted';
import { createAgent } from '../lib/httpClient';
import { Semaphore } from '../lib/semaphore';
import type { CombinedAuthorStats, GScholarStats, ScopusStats } from '../types';
import { gscholarAuthors, scopusAuthors } from './authors';
import type { GScholarAuthor, ScopusAuthor } from './authors';
import { fetchGoogleScholarDataAsync } from './gscholarService';
import { fetchScopusStatsAsync } from './scopusService';

const GS_EMPTY: GScholarStats = { totalPapers: 0, totalCitations: 0, hIndex: 0, i10Index: 0, yearlyCitations: {} };
const SCOPUS_EMPTY: ScopusStats = { totalPapers: 0, totalCitations: 0, hIndex: 0 };

interface AuthorIndexEntry {
  scopus: ScopusAuthor | null;
  gscholar: GScholarAuthor | null;
}

// Name-keyed join of the two author lists. Same join key (exact-match on
// `name`) and same silent-default behavior as OldCode: every Scopus author
// gets an entry first (insertion order), then any Google-Scholar-only names
// are appended at the end.
export function buildAuthorIndex(): Map<string, AuthorIndexEntry> {
  const allAuthors = new Map<string, AuthorIndexEntry>();
  for (const author of scopusAuthors) {
    allAuthors.set(author.name, { scopus: author, gscholar: null });
  }
  for (const author of gscholarAuthors) {
    const existing = allAuthors.get(author.name);
    if (existing) {
      existing.gscholar = author;
    } else {
      allAuthors.set(author.name, { scopus: null, gscholar: author });
    }
  }
  return allAuthors;
}

async function fetchCombinedForAuthor(
  name: string,
  entry: AuthorIndexEntry,
  gsSemaphore: Semaphore,
  scopusSemaphore: Semaphore,
  agent: Agent,
  signal: AbortSignal,
): Promise<CombinedAuthorStats> {
  const gscholarUrl = entry.gscholar?.gscholar_url ?? null;
  const scopusId = entry.scopus?.scopus_id ?? null;

  const [gsResult, scopusResult] = await Promise.allSettled([
    fetchGoogleScholarDataAsync(gscholarUrl, name, gsSemaphore, agent, signal),
    fetchScopusStatsAsync(scopusId, name, scopusSemaphore, agent, signal),
  ]);

  const gsData = gsResult.status === 'fulfilled' ? gsResult.value : GS_EMPTY;
  const scopusData = scopusResult.status === 'fulfilled' ? scopusResult.value : SCOPUS_EMPTY;

  return {
    name,
    papersGoogleScholar: gsData.totalPapers,
    citationsGoogleScholar: gsData.totalCitations,
    hIndexGoogleScholar: gsData.hIndex,
    i10IndexGoogleScholar: gsData.i10Index,
    yearlyCitationsGoogleScholar: gsData.yearlyCitations,
    papersScopus: scopusData.totalPapers,
    citationsScopus: scopusData.totalCitations,
    hIndexScopus: scopusData.hIndex,
  };
}

// Async generator: same gs_semaphore(5)/scopus_semaphore(10) bounds as
// OldCode's fetch_combined_data, shared across all per-author tasks, but
// yields each author's combined record as soon as both of its fetches
// finish instead of waiting for every author.
export async function* streamCombinedStats(): AsyncGenerator<CombinedAuthorStats> {
  const allAuthors = buildAuthorIndex();
  const gsSemaphore = new Semaphore(5);
  const scopusSemaphore = new Semaphore(10);
  const controller = new AbortController();
  const agent = createAgent(10);

  const tasks = Array.from(allAuthors.entries()).map(([name, entry]) =>
    fetchCombinedForAuthor(name, entry, gsSemaphore, scopusSemaphore, agent, controller.signal),
  );

  try {
    for await (const settled of asCompleted(tasks)) {
      if (!settled.ok) {
        console.log(`Exception during streamed combined fetch: ${settled.error}`);
        continue;
      }
      yield settled.value;
    }
  } finally {
    // If the consumer stops iterating early (e.g. client cancels the gRPC
    // stream), abort remaining fetches instead of leaving them running
    // against an agent that's about to close underneath them.
    controller.abort();
    await Promise.allSettled(tasks);
    await agent.close();
  }
}
