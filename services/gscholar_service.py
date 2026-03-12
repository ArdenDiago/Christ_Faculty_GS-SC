"""Google Scholar data fetching service - sync and async functions."""
import asyncio
import time
import aiohttp
import requests
from bs4 import BeautifulSoup


def fetch_google_scholar_data(gscholar_link):
    """Fetch Google Scholar stats (papers, citations, h-index, i10-index)."""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }

    try:
        # First, fetch the initial page
        response = requests.get(gscholar_link, headers=headers)
        if response.status_code == 200:
            soup = BeautifulSoup(response.content, 'html.parser')

            # Get user ID from the URL
            user_id = gscholar_link.split('user=')[1].split('&')[0]
            
            # Initialize variables
            total_papers = 0
            start = 0
            page_size = 100  # Google Scholar typically shows 100 papers per page
            
            while True:
                # Construct URL for each page
                page_url = f"{gscholar_link}&cstart={start}&pagesize={page_size}"
                page_response = requests.get(page_url, headers=headers)
                
                if page_response.status_code == 200:
                    page_soup = BeautifulSoup(page_response.content, 'html.parser')
                    publication_entries = page_soup.find_all('tr', class_='gsc_a_tr')
                    
                    if not publication_entries:
                        break
                        
                    total_papers += len(publication_entries)
                    
                    # If we got fewer papers than the page size, we've reached the end
                    if len(publication_entries) < page_size:
                        break
                        
                    # Move to next page
                    start += page_size
                    
                    # Add a small delay to avoid overwhelming the server
                    time.sleep(1)
                else:
                    break

            try:
                # Get other statistics as before
                citation_count = soup.find('td', class_='gsc_rsb_std')
                total_citations = int(citation_count.text.strip()) if citation_count else 0
                
                stats = soup.find_all('td', class_='gsc_rsb_std')
                h_index = 0
                i10_index = 0

                if len(stats) >= 5:
                    h_index = int(stats[2].text.strip()) if stats[2] else 0
                    i10_index = int(stats[4].text.strip()) if stats[4] else 0

                return total_papers, total_citations, h_index, i10_index
            
            except (IndexError, ValueError) as e:
                print(f"Error parsing Google Scholar data for {gscholar_link}: {e}")
                return None, None, None, None
        else:
            print(f"Error fetching Google Scholar data from {gscholar_link}: Status code {response.status_code}")
            return None, None, None, None
            
    except Exception as e:
        print(f"Error in fetch_google_scholar_data: {e}")
        return None, None, None, None


def fetch_yearly_citations(gscholar_link):
    """Fetch yearly citation data from Google Scholar."""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }

    response = requests.get(gscholar_link, headers=headers)
    if response.status_code == 200:
        soup = BeautifulSoup(response.content, 'html.parser')

        try:
            yearly_data = {}
            
            # Find all the year elements
            year_elements = soup.find_all('span', class_='gsc_g_t')
            # Find all the citation count elements
            citation_elements = soup.find_all('span', class_='gsc_g_al')

            # Iterate over the years and corresponding citations
            for year_elem, citation_elem in zip(year_elements, citation_elements):
                year = year_elem.text.strip()
                citation_count = citation_elem.text.strip()

                # Clean the citation count and convert to int
                citation_count = int(citation_count) if citation_count.isdigit() else 0
                yearly_data[year] = citation_count

            return yearly_data
        
        except Exception as e:
            print(f"Error fetching yearly citations: {e}")
            return {}

    else:
        print(f"Error fetching Google Scholar data from {gscholar_link}: Status code {response.status_code}")
        return {}


def fetch_google_scholar_papers(author_url):
    """Fetch all papers from Google Scholar for an author."""
    papers = []
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    try:
        start = 0
        page_size = 100
        seen_paper_ids = set()
        while True:
            page_url = f"{author_url}&cstart={start}&pagesize={page_size}"
            response = requests.get(page_url, headers=headers)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')
            if 'Our systems have detected unusual traffic' in soup.text:
                print(f"CAPTCHA detected for {author_url}. Unable to fetch papers.")
                break
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
                # Use link as unique identifier
                paper_id = link
                paper_entry = {
                    'title': title,
                    'link': link,
                    'citations': citations,
                    'year': year
                }
                if paper_id not in seen_paper_ids:
                    papers.append(paper_entry)
                    seen_paper_ids.add(paper_id)
                    new_papers += 1
            # Terminate if no new papers were found
            if new_papers == 0:
                break
            start += page_size
            time.sleep(1)
        if not papers:
            print(f"No papers could be extracted from {author_url}. The page structure might have changed.")
    except requests.exceptions.RequestException as e:
        print(f"Error fetching papers for {author_url}: {str(e)}")
    except Exception as e:
        print(f"Unexpected error while processing {author_url}: {str(e)}")
    return papers


async def fetch_google_scholar_papers_async(session, author_url, author_name, semaphore):
    """Async version of fetch_google_scholar_papers for concurrent fetching."""
    papers = []
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    if not author_url:
        return {'Name': author_name, 'Papers': []}
    async with semaphore:
        try:
            start = 0
            page_size = 100
            seen_paper_ids = set()
            max_retries = 3
            while True:
                page_url = f"{author_url}&cstart={start}&pagesize={page_size}"
                text = None
                
                for attempt in range(max_retries):
                    try:
                        async with session.get(page_url, headers=headers) as response:
                            if response.status == 200:
                                text = await response.text()
                                break
                            elif response.status == 429:
                                print(f"Rate limited for {author_name}, retrying... ({attempt+1}/{max_retries})")
                                await asyncio.sleep(2 * (attempt + 1))
                            else:
                                print(f"Error fetching {author_name}: Status {response.status}")
                                await asyncio.sleep(1)
                    except Exception as e:
                        print(f"Exception fetching {author_name} (attempt {attempt+1}): {e}")
                        await asyncio.sleep(1)
                
                if text is None:
                    print(f"Failed to fetch {author_name} after {max_retries} attempts.")
                    break
                    
                soup = BeautifulSoup(text, 'html.parser')
                if 'Our systems have detected unusual traffic' in text:
                    print(f"CAPTCHA detected for {author_name}")
                    break
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
                    
                    paper_entry = {
                        'title': title,
                        'link': link,
                        'citations': citations,
                        'year': year
                    }
                    if paper_id not in seen_paper_ids:
                        papers.append(paper_entry)
                        seen_paper_ids.add(paper_id)
                        new_papers += 1
                if new_papers == 0:
                    break
                
                # Check if we've reached the end
                if len(entries) < page_size:
                    break
                    
                start += page_size
                await asyncio.sleep(0.5)
            print(f"Fetched {len(papers)} papers for {author_name}")
        except Exception as e:
            print(f"Error fetching {author_name}: {str(e)}")
    return {'Name': author_name, 'Papers': papers}


async def fetch_google_scholar_data_async(session, gscholar_link, author_name, semaphore):
    """Async version of fetch_google_scholar_data for stats."""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    
    if not gscholar_link:
        return {
            'name': author_name,
            'total_papers': 0,
            'total_citations': 0,
            'h_index': 0,
            'i10_index': 0,
            'yearly_citations': {}
        }
    
    async with semaphore:
        try:
            max_retries = 3
            text = None
            
            # Fetch base profile page for stats and citations
            for attempt in range(max_retries):
                try:
                    async with session.get(gscholar_link, headers=headers) as response:
                        if response.status == 200:
                            text = await response.text()
                            break
                        elif response.status == 429:
                            await asyncio.sleep(2 * (attempt + 1))
                        else:
                            await asyncio.sleep(1)
                except Exception:
                    await asyncio.sleep(1)
                    
            if not text:
                return {
                    'name': author_name,
                    'total_papers': 0,
                    'total_citations': 0,
                    'h_index': 0,
                    'i10_index': 0,
                    'yearly_citations': {}
                }
                
            soup = BeautifulSoup(text, 'html.parser')
            
            if 'Our systems have detected unusual traffic' in text:
                print(f"CAPTCHA detected for {author_name}")
                return {
                    'name': author_name,
                    'total_papers': 0,
                    'total_citations': 0,
                    'h_index': 0,
                    'i10_index': 0,
                    'yearly_citations': {}
                }
            
            # Count papers using pagination like the sync function does
            total_papers = 0
            start = 0
            page_size = 100
            
            while True:
                page_url = f"{gscholar_link}&cstart={start}&pagesize={page_size}"
                page_text = None
                
                for attempt in range(max_retries):
                    try:
                        async with session.get(page_url, headers=headers) as response:
                            if response.status == 200:
                                page_text = await response.text()
                                break
                            elif response.status == 429:
                                await asyncio.sleep(2 * (attempt + 1))
                            else:
                                await asyncio.sleep(1)
                    except Exception:
                        await asyncio.sleep(1)
                        
                if not page_text:
                    break
                    
                page_soup = BeautifulSoup(page_text, 'html.parser')
                entries = page_soup.find_all('tr', class_='gsc_a_tr')
                
                if not entries:
                    break
                    
                total_papers += len(entries)
                
                if len(entries) < page_size:
                    break
                    
                start += page_size
                await asyncio.sleep(0.5)
            
            # Get stats
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
            
            # Get yearly citations
            yearly_data = {}
            try:
                year_elements = soup.find_all('span', class_='gsc_g_t')
                citation_elements = soup.find_all('span', class_='gsc_g_al')
                for year_elem, citation_elem in zip(year_elements, citation_elements):
                    year = year_elem.text.strip()
                    citation_count_year = citation_elem.text.strip()
                    citation_count_year = int(citation_count_year) if citation_count_year.isdigit() else 0
                    yearly_data[year] = citation_count_year
            except Exception as e:
                print(f"Error parsing yearly citations for {author_name}: {e}")
            
            print(f"Fetched GS stats for {author_name}: {total_papers} papers, {total_citations} citations")
            
            await asyncio.sleep(0.3)  # Respectful delay
            
            return {
                'name': author_name,
                'total_papers': total_papers,
                'total_citations': total_citations,
                'h_index': h_index,
                'i10_index': i10_index,
                'yearly_citations': yearly_data
            }
            
        except Exception as e:
            print(f"Error fetching GS stats for {author_name}: {e}")
            return {
                'name': author_name,
                'total_papers': 0,
                'total_citations': 0,
                'h_index': 0,
                'i10_index': 0,
                'yearly_citations': {}
            }


async def fetch_all_authors_papers(gscholar_authors):
    """Fetch papers for all authors concurrently."""
    # Limit concurrent requests to avoid rate limiting
    semaphore = asyncio.Semaphore(5)
    
    connector = aiohttp.TCPConnector(limit=10, limit_per_host=5)
    timeout = aiohttp.ClientTimeout(total=30)
    
    async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
        tasks = [
            fetch_google_scholar_papers_async(session, author['gscholar_url'], author['name'], semaphore)
            for author in gscholar_authors
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Handle any exceptions
        paper_details = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                print(f"Exception for author {gscholar_authors[i]['name']}: {result}")
                paper_details.append({'Name': gscholar_authors[i]['name'], 'Papers': []})
            else:
                paper_details.append(result)
        
        return paper_details
