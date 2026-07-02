"""Google Scholar data fetching service - same scrape tactics as OldCode,
exposed as async generators so results can be gRPC-streamed to the client
as soon as each author's fetch completes, instead of waiting for every
author before returning anything.
"""
import asyncio
import aiohttp
from bs4 import BeautifulSoup

USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
HEADERS = {'User-Agent': USER_AGENT}


async def _get_with_retry(session, url, max_retries=3):
    """Shared retry+backoff loop: same policy as OldCode (429 -> exponential
    backoff, other errors -> flat 1s backoff, gives up after max_retries)."""
    for attempt in range(max_retries):
        try:
            async with session.get(url, headers=HEADERS) as response:
                if response.status == 200:
                    return await response.text()
                elif response.status == 429:
                    await asyncio.sleep(2 * (attempt + 1))
                else:
                    await asyncio.sleep(1)
        except Exception:
            await asyncio.sleep(1)
    return None


async def fetch_google_scholar_papers_async(session, author_url, author_name, semaphore):
    """Fetch all papers for one author. Same pagination/dedup/CAPTCHA logic as OldCode."""
    papers = []
    if not author_url:
        return {'name': author_name, 'papers': []}
    async with semaphore:
        start = 0
        page_size = 100
        seen_paper_ids = set()
        while True:
            page_url = f"{author_url}&cstart={start}&pagesize={page_size}"
            text = await _get_with_retry(session, page_url)
            if text is None:
                break
            if 'Our systems have detected unusual traffic' in text:
                print(f"CAPTCHA detected for {author_name}")
                break
            soup = BeautifulSoup(text, 'html.parser')
            entries = soup.find_all('tr', class_='gsc_a_tr')
            if not entries:
                break
            new_papers = 0
            for entry in entries:
                title_element = entry.find('a', class_='gsc_a_at')
                citations_element = entry.find('a', class_='gsc_a_ac gs_ibl')
                year_element = entry.find('span', class_='gsc_a_h gsc_a_hc gs_ibl')
                if not title_element:
                    continue
                title = title_element.text.strip()
                link = f"https://scholar.google.com{title_element['href']}" if 'href' in title_element.attrs else 'N/A'
                citations = citations_element.text.strip() if citations_element else '0'
                year = year_element.text.strip() if year_element else 'N/A'
                if year == '':
                    year = 'N/A'
                paper_id = link if link != 'N/A' else f"{title}_{year}"
                if paper_id not in seen_paper_ids:
                    papers.append({'title': title, 'link': link, 'citations': citations, 'year': year})
                    seen_paper_ids.add(paper_id)
                    new_papers += 1
            if new_papers == 0 or len(entries) < page_size:
                break
            start += page_size
            await asyncio.sleep(0.5)
        print(f"Fetched {len(papers)} papers for {author_name}")
    return {'name': author_name, 'papers': papers}


async def fetch_google_scholar_data_async(session, gscholar_link, author_name, semaphore):
    """Fetch stats (papers/citations/h-index/i10/yearly) for one author. Same
    positional gsc_rsb_std indexing as OldCode."""
    empty = {
        'name': author_name, 'total_papers': 0, 'total_citations': 0,
        'h_index': 0, 'i10_index': 0, 'yearly_citations': {}
    }
    if not gscholar_link:
        return empty

    async with semaphore:
        text = await _get_with_retry(session, gscholar_link)
        if not text:
            return empty
        if 'Our systems have detected unusual traffic' in text:
            print(f"CAPTCHA detected for {author_name}")
            return empty

        soup = BeautifulSoup(text, 'html.parser')

        total_papers = 0
        start = 0
        page_size = 100
        while True:
            page_text = await _get_with_retry(session, f"{gscholar_link}&cstart={start}&pagesize={page_size}")
            if not page_text:
                break
            entries = BeautifulSoup(page_text, 'html.parser').find_all('tr', class_='gsc_a_tr')
            if not entries:
                break
            total_papers += len(entries)
            if len(entries) < page_size:
                break
            start += page_size
            await asyncio.sleep(0.5)

        total_citations = 0
        h_index = 0
        i10_index = 0
        try:
            citation_count = soup.find('td', class_='gsc_rsb_std')
            total_citations = int(citation_count.text.strip()) if citation_count else 0
            stats = soup.find_all('td', class_='gsc_rsb_std')
            if len(stats) >= 5:
                h_index = int(stats[2].text.strip()) if stats[2] else 0
                i10_index = int(stats[4].text.strip()) if stats[4] else 0
        except (IndexError, ValueError) as e:
            print(f"Error parsing stats for {author_name}: {e}")

        yearly_data = {}
        try:
            year_elements = soup.find_all('span', class_='gsc_g_t')
            citation_elements = soup.find_all('span', class_='gsc_g_al')
            for year_elem, citation_elem in zip(year_elements, citation_elements):
                year = year_elem.text.strip()
                count = citation_elem.text.strip()
                yearly_data[year] = int(count) if count.isdigit() else 0
        except Exception as e:
            print(f"Error parsing yearly citations for {author_name}: {e}")

        print(f"Fetched GS stats for {author_name}: {total_papers} papers, {total_citations} citations")
        await asyncio.sleep(0.3)

        return {
            'name': author_name,
            'total_papers': total_papers,
            'total_citations': total_citations,
            'h_index': h_index,
            'i10_index': i10_index,
            'yearly_citations': yearly_data,
        }


async def stream_all_authors_papers(gscholar_authors):
    """Async generator: same semaphore(5)/connector-bounded concurrency as
    OldCode's fetch_all_authors_papers, but yields each author's result as
    soon as it completes instead of gathering everything first."""
    semaphore = asyncio.Semaphore(5)
    connector = aiohttp.TCPConnector(limit=10, limit_per_host=5)
    timeout = aiohttp.ClientTimeout(total=30)

    async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
        tasks = [
            asyncio.ensure_future(
                fetch_google_scholar_papers_async(session, author['gscholar_url'], author['name'], semaphore)
            )
            for author in gscholar_authors
        ]
        try:
            for coro in asyncio.as_completed(tasks):
                try:
                    yield await coro
                except Exception as e:
                    print(f"Exception during streamed GScholar fetch: {e}")
        finally:
            # If the consumer stops iterating early (e.g. client cancels the
            # gRPC stream), cancel remaining fetches instead of leaving them
            # to run against a session that's about to close underneath them.
            for task in tasks:
                if not task.done():
                    task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
