def fetch_all_combined_data():
    """Fetch combined data for all authors from both sources."""
    return fetch_combined_data()

import asyncio
import aiohttp
from .gscholar_service import fetch_google_scholar_data_async
from .scopus_service import fetch_scopus_stats_async


async def fetch_combined_data():
    """Fetch Google Scholar and Scopus data concurrently"""
    from services.authors import scopus_authors, gscholar_authors
    gs_semaphore = asyncio.Semaphore(5)
    scopus_semaphore = asyncio.Semaphore(10)
    connector = aiohttp.TCPConnector(limit=20, limit_per_host=10)
    timeout = aiohttp.ClientTimeout(total=60)

    # Build unified author list by name
    all_authors = {}
    for author in scopus_authors:
        all_authors[author['name']] = {'scopus': author, 'gscholar': None}
    for author in gscholar_authors:
        if author['name'] in all_authors:
            all_authors[author['name']]['gscholar'] = author
        else:
            all_authors[author['name']] = {'scopus': None, 'gscholar': author}

    author_names = list(all_authors.keys())

    async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
        # Fetch Google Scholar data for all authors
        gs_tasks = [
            fetch_google_scholar_data_async(
                session,
                all_authors[name]['gscholar']['gscholar_url'] if all_authors[name]['gscholar'] else None,
                name,
                gs_semaphore
            ) for name in author_names
        ]
        # Fetch Scopus data for all authors
        scopus_tasks = [
            fetch_scopus_stats_async(
                session,
                all_authors[name]['scopus']['scopus_id'] if all_authors[name]['scopus'] else None,
                name,
                scopus_semaphore
            ) for name in author_names
        ]

        gs_results, scopus_results = await asyncio.gather(
            asyncio.gather(*gs_tasks, return_exceptions=True),
            asyncio.gather(*scopus_tasks, return_exceptions=True)
        )

        combined_data = []
        for i, name in enumerate(author_names):
            gs_data = gs_results[i] if not isinstance(gs_results[i], Exception) else {
                'total_papers': 0, 'total_citations': 0, 'h_index': 0, 'i10_index': 0, 'yearly_citations': {}
            }
            scopus_data = scopus_results[i] if not isinstance(scopus_results[i], Exception) else {
                'total_papers': 0, 'total_citations': 0, 'h_index': 0
            }
            citations_by_year_str = ', '.join(f"{year}: {count}" for year, count in gs_data.get('yearly_citations', {}).items())
            combined_data.append({
                'name': name,
                'papers_google_scholar': gs_data.get('total_papers', 0),
                'citations_google_scholar': gs_data.get('total_citations', 0),
                'h_index_google_scholar': gs_data.get('h_index', 0),
                'i10_index_google_scholar': gs_data.get('i10_index', 0),
                'papers_scopus': scopus_data.get('total_papers', 0),
                'citations_scopus': scopus_data.get('total_citations', 0),
                'h_index_scopus': scopus_data.get('h_index', 0),
                'citations_by_year': citations_by_year_str
            })
        return combined_data
