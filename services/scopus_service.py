"""Scopus data fetching service - sync and async functions."""
import asyncio
import aiohttp
import requests
from .config import API_KEY


def fetch_author_papers(author_id):
    """Fetch author papers from Scopus using author ID."""
    url = f'https://api.elsevier.com/content/search/scopus?query=AU-ID({author_id})'
    
    headers = {
        'X-ELS-APIKey': API_KEY,
        'Accept': 'application/json'
    }
    
    response = requests.get(url, headers=headers)
    
    if response.status_code == 200:
        return response.json()
    else:
        print(f"Error: Unable to fetch data for author ID {author_id}. Status code: {response.status_code}")
        return None


def parse_scopus_data(response_json):
    """Parse Scopus response and calculate stats."""
    total_papers = 0
    total_citations = 0
    h_index = 0
    
    if response_json and 'search-results' in response_json:
        entries = response_json['search-results'].get('entry', [])
        total_papers = len(entries)
        
        citations = [int(entry.get('citedby-count', '0')) for entry in entries]
        total_citations = sum(citations)
        
        # Calculate H-index
        citations.sort(reverse=True)
        h_index = sum(c >= i + 1 for i, c in enumerate(citations))
    
    return total_papers, total_citations, h_index


def parse_scopus_papers(response_json):
    """Parse Scopus response into list of papers."""
    papers = []
    if response_json and 'search-results' in response_json:
        entries = response_json['search-results'].get('entry', [])
        for entry in entries:
            paper = {
                'title': entry.get('dc:title'),
                'year': entry.get('prism:coverDate', '')[:4], 
                'citations': entry.get('citedby-count'),
                'link': entry.get('prism:doi')
            }
            papers.append(paper)
    return papers


async def fetch_scopus_papers_async(session, author_id, author_name, semaphore):
    """Async version of Scopus paper fetching."""
    base_url = f'https://api.elsevier.com/content/search/scopus?query=AU-ID({author_id})'
    headers = {
        'X-ELS-APIKey': API_KEY,
        'Accept': 'application/json'
    }
    count = 25  # max per page for Scopus API
    start = 0
    papers = []
    max_retries = 3
    if not author_id:
        return {'Name': author_name, 'ScopusPapers': [], 'ProfileLink': ''}
    async with semaphore:
        try:
            while True:
                url = f"{base_url}&count={count}&start={start}"
                for attempt in range(max_retries):
                    try:
                        async with session.get(url, headers=headers) as response:
                            if response.status == 200:
                                data = await response.json()
                                break
                            else:
                                print(f"Error fetching Scopus for {author_name} (attempt {attempt+1}): Status {response.status}")
                                data = None
                    except Exception as e:
                        print(f"Exception during fetch for {author_name} (attempt {attempt+1}): {e}")
                        data = None
                    await asyncio.sleep(1)
                else:
                    print(f"Failed to fetch after {max_retries} attempts for {author_name} at start={start}")
                    return {'Name': author_name, 'ScopusPapers': papers, 'ProfileLink': f"https://www.scopus.com/authid/detail.uri?authorId={author_id}"}

                if data and 'search-results' in data:
                    entries = data['search-results'].get('entry', [])
                    for entry in entries:
                        paper = {
                            'title': entry.get('dc:title'),
                            'year': entry.get('prism:coverDate', '')[:4],
                            'citations': entry.get('citedby-count'),
                            'link': entry.get('prism:doi')
                        }
                        papers.append(paper)
                    total_results = int(data['search-results'].get('opensearch:totalResults', '0'))
                    print(f"Scopus fetch: {author_name} start={start} got {len(entries)} entries (total_results={total_results})")
                    start += count
                    # If fewer entries than requested, or no entries, we've reached the end
                    if len(entries) < count or start >= total_results:
                        break
                else:
                    print(f"No data or missing 'search-results' for {author_name} at start={start}")
                    break
            print(f"Fetched {len(papers)} Scopus papers for {author_name}")
            return {
                'Name': author_name,
                'ScopusPapers': papers,
                'ProfileLink': f"https://www.scopus.com/authid/detail.uri?authorId={author_id}"
            }
        except Exception as e:
            print(f"Error fetching Scopus for {author_name}: {e}")
            return {'Name': author_name, 'ScopusPapers': [], 'ProfileLink': ''}


async def fetch_scopus_stats_async(session, author_id, author_name, semaphore):
    """Async version of Scopus stats fetching."""
    base_url = f'https://api.elsevier.com/content/search/scopus?query=AU-ID({author_id})'
    headers = {
        'X-ELS-APIKey': API_KEY,
        'Accept': 'application/json'
    }
    count = 25
    start = 0
    max_retries = 3
    total_papers = 0
    total_citations = 0
    citations = []
    if not author_id:
        return {
            'name': author_name,
            'total_papers': 0,
            'total_citations': 0,
            'h_index': 0
        }
    async with semaphore:
        try:
            while True:
                url = f"{base_url}&count={count}&start={start}"
                for attempt in range(max_retries):
                    try:
                        async with session.get(url, headers=headers) as response:
                            if response.status == 200:
                                data = await response.json()
                                break
                            else:
                                print(f"Error fetching Scopus stats for {author_name} (attempt {attempt+1}): Status {response.status}")
                                data = None
                    except Exception as e:
                        print(f"Exception during stats fetch for {author_name} (attempt {attempt+1}): {e}")
                        data = None
                    await asyncio.sleep(1)
                else:
                    print(f"Failed to fetch stats after {max_retries} attempts for {author_name} at start={start}")
                    break

                if data and 'search-results' in data:
                    entries = data['search-results'].get('entry', [])
                    total_papers += len(entries)
                    citations.extend([int(entry.get('citedby-count', '0')) for entry in entries])
                    total_results = int(data['search-results'].get('opensearch:totalResults', '0'))
                    start += count
                    if len(entries) < count or start >= total_results:
                        break
                else:
                    print(f"No data or missing 'search-results' for stats {author_name} at start={start}")
                    break
            total_citations = sum(citations)
            citations.sort(reverse=True)
            h_index = sum(c >= i + 1 for i, c in enumerate(citations))
            print(f"Fetched Scopus stats for {author_name}: {total_citations} citations, {total_papers} papers, h-index {h_index}")
            return {
                'name': author_name,
                'total_papers': total_papers,
                'total_citations': total_citations,
                'h_index': h_index
            }
        except Exception as e:
            print(f"Error fetching Scopus stats for {author_name}: {e}")
            return {'name': author_name, 'total_papers': 0, 'total_citations': 0, 'h_index': 0}


async def fetch_all_scopus_papers(scopus_authors):
    """Fetch Scopus papers for all authors concurrently."""
    semaphore = asyncio.Semaphore(10)  # Scopus API can handle more concurrent requests
    connector = aiohttp.TCPConnector(limit=20, limit_per_host=10)
    timeout = aiohttp.ClientTimeout(total=60)
    
    async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
        tasks = [
            fetch_scopus_papers_async(session, author.get('scopus_id'), author.get('name'), semaphore)
            for author in scopus_authors
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        all_data = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                print(f"Exception for Scopus {scopus_authors[i]['name']}: {result}")
                all_data.append({'Name': scopus_authors[i]['name'], 'ScopusPapers': [], 'ProfileLink': ''})
            else:
                all_data.append(result)
        
        return all_data
