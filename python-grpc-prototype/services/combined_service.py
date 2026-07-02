"""Combined Google Scholar + Scopus stats - same name-keyed join as OldCode,
streamed per author as each author's pair of fetches completes.
"""
import asyncio
import aiohttp
from .gscholar_service import fetch_google_scholar_data_async
from .scopus_service import fetch_scopus_stats_async
from .authors import scopus_authors, gscholar_authors

_GS_EMPTY = {'total_papers': 0, 'total_citations': 0, 'h_index': 0, 'i10_index': 0, 'yearly_citations': {}}
_SCOPUS_EMPTY = {'total_papers': 0, 'total_citations': 0, 'h_index': 0}


def _build_author_index():
    """Name-keyed join of the two author lists. Same join key (exact-match
    on `name`) and same silent-default behavior as OldCode."""
    all_authors = {}
    for author in scopus_authors:
        all_authors[author['name']] = {'scopus': author, 'gscholar': None}
    for author in gscholar_authors:
        if author['name'] in all_authors:
            all_authors[author['name']]['gscholar'] = author
        else:
            all_authors[author['name']] = {'scopus': None, 'gscholar': author}
    return all_authors


async def _fetch_combined_for_author(session, name, entry, gs_semaphore, scopus_semaphore):
    gscholar_url = entry['gscholar']['gscholar_url'] if entry['gscholar'] else None
    scopus_id = entry['scopus']['scopus_id'] if entry['scopus'] else None

    gs_result, scopus_result = await asyncio.gather(
        fetch_google_scholar_data_async(session, gscholar_url, name, gs_semaphore),
        fetch_scopus_stats_async(session, scopus_id, name, scopus_semaphore),
        return_exceptions=True,
    )
    gs_data = gs_result if not isinstance(gs_result, Exception) else _GS_EMPTY
    scopus_data = scopus_result if not isinstance(scopus_result, Exception) else _SCOPUS_EMPTY

    return {
        'name': name,
        'papers_google_scholar': gs_data.get('total_papers', 0),
        'citations_google_scholar': gs_data.get('total_citations', 0),
        'h_index_google_scholar': gs_data.get('h_index', 0),
        'i10_index_google_scholar': gs_data.get('i10_index', 0),
        'yearly_citations_google_scholar': gs_data.get('yearly_citations', {}),
        'papers_scopus': scopus_data.get('total_papers', 0),
        'citations_scopus': scopus_data.get('total_citations', 0),
        'h_index_scopus': scopus_data.get('h_index', 0),
    }


async def stream_combined_stats():
    """Async generator: same gs_semaphore(5)/scopus_semaphore(10) bounds as
    OldCode's fetch_combined_data, shared across all per-author tasks, but
    yields each author's combined record as soon as both of its fetches
    finish instead of waiting for every author."""
    all_authors = _build_author_index()
    gs_semaphore = asyncio.Semaphore(5)
    scopus_semaphore = asyncio.Semaphore(10)
    connector = aiohttp.TCPConnector(limit=20, limit_per_host=10)
    timeout = aiohttp.ClientTimeout(total=60)

    async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
        tasks = [
            asyncio.ensure_future(
                _fetch_combined_for_author(session, name, entry, gs_semaphore, scopus_semaphore)
            )
            for name, entry in all_authors.items()
        ]
        try:
            for coro in asyncio.as_completed(tasks):
                try:
                    yield await coro
                except Exception as e:
                    print(f"Exception during streamed combined fetch: {e}")
        finally:
            # If the consumer stops iterating early (e.g. client cancels the
            # gRPC stream), cancel remaining fetches instead of leaving them
            # to run against a session that's about to close underneath them.
            for task in tasks:
                if not task.done():
                    task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
