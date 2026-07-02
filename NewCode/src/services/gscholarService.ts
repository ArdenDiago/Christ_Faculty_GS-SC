// Google Scholar data fetching - same scrape tactics as OldCode/the Python
// prototype (python-grpc-prototype/services/gscholar_service.py), exposed as
// async generators so results can be gRPC-streamed to the client as soon as
// each author's fetch completes.
import * as cheerio from 'cheerio';
import type { Agent } from 'undici';
import { asCompleted } from '../lib/asCompleted';
import { createAgent, httpGet, sleep } from '../lib/httpClient';
import { Semaphore } from '../lib/semaphore';
import type { AuthorPapers, GScholarStats, Paper } from '../types';
import type { GScholarAuthor } from './authors';

const USER_AGENT =
  'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36';
const HEADERS = { 'User-Agent': USER_AGENT };
const CAPTCHA_MARKER = 'Our systems have detected unusual traffic';

function isAbortError(err: unknown): boolean {
  return err instanceof DOMException && err.name === 'AbortError';
}

// Dedup key for a scraped paper row: prefer the paper's own link (stable
// across pages), falling back to a title+year composite when Google Scholar
// doesn't expose a link for that row.
export function buildPaperId(link: string, title: string, year: string): string {
  return link !== 'N/A' ? link : `${title}_${year}`;
}

// Shared retry+backoff loop: same policy as OldCode (429 -> exponential
// backoff, other errors -> flat 1s backoff, gives up after max_retries).
async function getWithRetry(
  url: string,
  agent: Agent,
  signal: AbortSignal,
  maxRetries = 3,
): Promise<string | null> {
  for (let attempt = 0; attempt < maxRetries; attempt++) {
    try {
      const res = await httpGet(url, HEADERS, agent, signal, 30_000);
      if (res.status === 200) {
        return await res.text();
      } else if (res.status === 429) {
        await sleep(2 * (attempt + 1) * 1000, signal);
      } else {
        await sleep(1000, signal);
      }
    } catch (err) {
      if (isAbortError(err)) throw err;
      await sleep(1000, signal);
    }
  }
  return null;
}

// Fetch all papers for one author. Same pagination/dedup/CAPTCHA logic as
// OldCode.
export async function fetchGoogleScholarPapersAsync(
  author: GScholarAuthor,
  semaphore: Semaphore,
  agent: Agent,
  signal: AbortSignal,
): Promise<AuthorPapers> {
  const authorName = author.name;
  const authorUrl = author.gscholar_url;
  if (!authorUrl) {
    return { name: authorName, papers: [] };
  }

  return semaphore.run(async () => {
    const papers: Paper[] = [];
    let start = 0;
    const pageSize = 100;
    const seenPaperIds = new Set<string>();

    while (true) {
      const pageUrl = `${authorUrl}&cstart=${start}&pagesize=${pageSize}`;
      const text = await getWithRetry(pageUrl, agent, signal);
      if (text === null) break;
      if (text.includes(CAPTCHA_MARKER)) {
        console.log(`CAPTCHA detected for ${authorName}`);
        break;
      }

      const $ = cheerio.load(text);
      const entries = $('tr.gsc_a_tr');
      if (entries.length === 0) break;

      let newPapers = 0;
      entries.each((_, el) => {
        const row = $(el);
        const titleEl = row.find('a.gsc_a_at');
        if (titleEl.length === 0) return;
        const citationsEl = row.find('a.gsc_a_ac.gs_ibl');
        const yearEl = row.find('span.gsc_a_h.gsc_a_hc.gs_ibl');

        const title = titleEl.text().trim();
        const href = titleEl.attr('href');
        const link = href ? `https://scholar.google.com${href}` : 'N/A';
        const citations = citationsEl.length ? citationsEl.text().trim() : '0';
        let year = yearEl.length ? yearEl.text().trim() : 'N/A';
        if (year === '') year = 'N/A';

        const paperId = buildPaperId(link, title, year);
        if (!seenPaperIds.has(paperId)) {
          papers.push({ title, link, citations, year });
          seenPaperIds.add(paperId);
          newPapers += 1;
        }
      });

      if (newPapers === 0 || entries.length < pageSize) break;
      start += pageSize;
      await sleep(500, signal);
    }

    console.log(`Fetched ${papers.length} papers for ${authorName}`);
    return { name: authorName, papers };
  });
}

// Fetch stats (papers/citations/h-index/i10/yearly) for one author. Same
// positional gsc_rsb_std indexing as OldCode.
export async function fetchGoogleScholarDataAsync(
  gscholarLink: string | null,
  authorName: string,
  semaphore: Semaphore,
  agent: Agent,
  signal: AbortSignal,
): Promise<GScholarStats> {
  const empty: GScholarStats = { totalPapers: 0, totalCitations: 0, hIndex: 0, i10Index: 0, yearlyCitations: {} };
  if (!gscholarLink) return empty;

  return semaphore.run(async () => {
    const text = await getWithRetry(gscholarLink, agent, signal);
    if (!text) return empty;
    if (text.includes(CAPTCHA_MARKER)) {
      console.log(`CAPTCHA detected for ${authorName}`);
      return empty;
    }
    const $ = cheerio.load(text);

    let totalPapers = 0;
    let start = 0;
    const pageSize = 100;
    while (true) {
      const pageText = await getWithRetry(`${gscholarLink}&cstart=${start}&pagesize=${pageSize}`, agent, signal);
      if (!pageText) break;
      const entries = cheerio.load(pageText)('tr.gsc_a_tr');
      if (entries.length === 0) break;
      totalPapers += entries.length;
      if (entries.length < pageSize) break;
      start += pageSize;
      await sleep(500, signal);
    }

    let totalCitations = 0;
    let hIndex = 0;
    let i10Index = 0;
    try {
      const statsEls = $('td.gsc_rsb_std');
      totalCitations = statsEls.length ? parseInt($(statsEls[0]).text().trim(), 10) || 0 : 0;
      if (statsEls.length >= 5) {
        hIndex = parseInt($(statsEls[2]).text().trim(), 10) || 0;
        i10Index = parseInt($(statsEls[4]).text().trim(), 10) || 0;
      }
    } catch (err) {
      console.log(`Error parsing stats for ${authorName}: ${err}`);
    }

    const yearlyCitations: Record<string, number> = {};
    try {
      const yearEls = $('span.gsc_g_t');
      const citationEls = $('span.gsc_g_al');
      const n = Math.min(yearEls.length, citationEls.length);
      for (let i = 0; i < n; i++) {
        const year = $(yearEls[i]).text().trim();
        const countStr = $(citationEls[i]).text().trim();
        yearlyCitations[year] = /^\d+$/.test(countStr) ? parseInt(countStr, 10) : 0;
      }
    } catch (err) {
      console.log(`Error parsing yearly citations for ${authorName}: ${err}`);
    }

    console.log(`Fetched GS stats for ${authorName}: ${totalPapers} papers, ${totalCitations} citations`);
    await sleep(300, signal);

    return { totalPapers, totalCitations, hIndex, i10Index, yearlyCitations };
  });
}

// Async generator: same semaphore(5)/connector-bounded concurrency as
// OldCode's fetch_all_authors_papers, but yields each author's result as
// soon as it completes instead of gathering everything first.
export async function* streamAllAuthorsPapers(authors: GScholarAuthor[]): AsyncGenerator<AuthorPapers> {
  const semaphore = new Semaphore(5);
  const controller = new AbortController();
  const agent = createAgent(5);
  const tasks = authors.map((author) => fetchGoogleScholarPapersAsync(author, semaphore, agent, controller.signal));

  try {
    for await (const settled of asCompleted(tasks)) {
      if (!settled.ok) {
        console.log(`Exception during streamed GScholar fetch: ${settled.error}`);
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
