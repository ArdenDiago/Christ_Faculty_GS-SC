"""Scopus data fetching service - same official-API tactics as OldCode,
exposed as async generators for gRPC streaming.
"""
import asyncio
import aiohttp
from .config import API_KEY

HEADERS = {'X-ELS-APIKey': API_KEY, 'Accept': 'application/json'}


async def _get_json_with_retry(session, url, author_name, max_retries=3):
    """Same retry policy as OldCode: flat 1s backoff between attempts,
    gives up after max_retries with no data."""
    for attempt in range(max_retries):
        try:
            async with session.get(url, headers=HEADERS) as response:
                if response.status == 200:
                    return await response.json()
                print(f"Error fetching Scopus for {author_name} (attempt {attempt + 1}): Status {response.status}")
        except Exception as e:
            print(f"Exception during fetch for {author_name} (attempt {attempt + 1}): {e}")
        await asyncio.sleep(1)
    return None


async def fetch_scopus_papers_async(session, author_id, author_name, semaphore):
    """Fetch all Scopus papers for one author. Same count=25/start pagination as OldCode."""
    base_url = f'https://api.elsevier.com/content/search/scopus?query=AU-ID({author_id})'
    count = 25
    start = 0
    papers = []
    profile_link = f"https://www.scopus.com/authid/detail.uri?authorId={author_id}" if author_id else ''
    if not author_id:
        return {'name': author_name, 'papers': [], 'profile_link': ''}

    async with semaphore:
        while True:
            url = f"{base_url}&count={count}&start={start}"
            data = await _get_json_with_retry(session, url, author_name)
            if data is None:
                print(f"Failed to fetch Scopus for {author_name} at start={start}")
                break
            if 'search-results' not in data:
                print(f"No 'search-results' for {author_name} at start={start}")
                break
            entries = data['search-results'].get('entry', [])
            for entry in entries:
                papers.append({
                    'title': entry.get('dc:title'),
                    'year': entry.get('prism:coverDate', '')[:4],
                    'citations': entry.get('citedby-count'),
                    'link': entry.get('prism:doi'),
                })
            total_results = int(data['search-results'].get('opensearch:totalResults', '0'))
            start += count
            if len(entries) < count or start >= total_results:
                break
        print(f"Fetched {len(papers)} Scopus papers for {author_name}")
        return {'name': author_name, 'papers': papers, 'profile_link': profile_link}


async def fetch_scopus_stats_async(session, author_id, author_name, semaphore):
    """Fetch Scopus stats for one author. H-index computed client-side same
    as OldCode (Scopus API has no h-index field)."""
    empty = {'name': author_name, 'total_papers': 0, 'total_citations': 0, 'h_index': 0}
    if not author_id:
        return empty

    base_url = f'https://api.elsevier.com/content/search/scopus?query=AU-ID({author_id})'
    count = 25
    start = 0
    total_papers = 0
    citations = []

    async with semaphore:
        while True:
            url = f"{base_url}&count={count}&start={start}"
            data = await _get_json_with_retry(session, url, author_name)
            if data is None or 'search-results' not in data:
                break
            entries = data['search-results'].get('entry', [])
            total_papers += len(entries)
            citations.extend(int(entry.get('citedby-count', '0')) for entry in entries)
            total_results = int(data['search-results'].get('opensearch:totalResults', '0'))
            start += count
            if len(entries) < count or start >= total_results:
                break

        total_citations = sum(citations)
        citations.sort(reverse=True)
        h_index = sum(c >= i + 1 for i, c in enumerate(citations))
        print(f"Fetched Scopus stats for {author_name}: {total_citations} citations, {total_papers} papers, h-index {h_index}")
        return {'name': author_name, 'total_papers': total_papers, 'total_citations': total_citations, 'h_index': h_index}


async def stream_all_scopus_papers(scopus_authors):
    """Async generator: same semaphore(10)/connector-bounded concurrency as
    OldCode's fetch_all_scopus_papers, yielding each author as it completes."""
    semaphore = asyncio.Semaphore(10)
    connector = aiohttp.TCPConnector(limit=20, limit_per_host=10)
    timeout = aiohttp.ClientTimeout(total=60)

    async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
        tasks = [
            asyncio.ensure_future(
                fetch_scopus_papers_async(session, author.get('scopus_id'), author.get('name'), semaphore)
            )
            for author in scopus_authors
        ]
        try:
            for coro in asyncio.as_completed(tasks):
                try:
                    yield await coro
                except Exception as e:
                    print(f"Exception during streamed Scopus fetch: {e}")
        finally:
            # If the consumer stops iterating early (e.g. client cancels the
            # gRPC stream), cancel remaining fetches instead of leaving them
            # to run against a session that's about to close underneath them.
            for task in tasks:
                if not task.done():
                    task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
