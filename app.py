from flask import Flask, request, jsonify, render_template
import json
import requests
import asyncio
import aiohttp
from bs4 import BeautifulSoup
import time

app = Flask(__name__)

# Load your API key from config.json
with open('config.json') as config_file:
    config = json.load(config_file)

API_KEY = config['API_KEY']

# Fetch author papers from Scopus using author ID
def fetch_author_papers(author_id):
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

# Parse Scopus data
def parse_scopus_data(response_json):
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

def fetch_author_papers(author_id):
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

def parse_scopus_papers(response_json):
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

def fetch_google_scholar_data(gscholar_link):
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

def fetch_google_scholar_papers(gscholar_link):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }

    response = requests.get(gscholar_link, headers=headers)
    if response.status_code == 200:
        soup = BeautifulSoup(response.content, 'html.parser')
        papers = []

        publication_entries = soup.find_all('tr', class_='gsc_a_tr')
        for entry in publication_entries:
            title = entry.find('a', class_='gsc_a_at').text
            citation_count = entry.find('td', class_='gsc_a_c').text.strip()  # Citation count
            year = entry.find('span', class_='gsc_a_h gsc_a_hc').text.strip()  # Year of publication

            # Collect details
            papers.append({
                'title': title,
                'citations': citation_count,
                'year': year,
                'link': 'https://scholar.google.com' + entry.find('a', class_='gsc_a_at')['data-href']  # Link to paper
            })
        return papers
    else:
        print(f"Error fetching papers from {gscholar_link}: Status code {response.status_code}")
        return []
    
def fetch_google_scholar_papers(author_url):
    papers = []
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    
    try:
        # First, fetch the initial page to get the author's profile ID
        response = requests.get(author_url, headers=headers)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        if 'Our systems have detected unusual traffic' in soup.text:
            print(f"CAPTCHA detected for {author_url}. Unable to fetch papers.")
            return papers

        # Extract user ID from the URL
        user_id = author_url.split('user=')[1].split('&')[0]
        
        # Fetch all pages of papers
        start = 0
        page_size = 100  # Google Scholar typically shows 100 papers per page
        
        while True:
            # Construct URL for each page
            page_url = f"{author_url}&cstart={start}&pagesize={page_size}"
            
            response = requests.get(page_url, headers=headers)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            entries = soup.find_all('tr', class_='gsc_a_tr')
            
            if not entries:
                break
                
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
                
                # If year is empty, set it to 'N/A'
                if year == '':
                    year = 'N/A'
                
                # Only add if we haven't seen this paper before (avoid duplicates)
                paper_entry = {
                    'title': title,
                    'link': link,
                    'citations': citations,
                    'year': year
                }
                
                if paper_entry not in papers:  # Avoid duplicates
                    papers.append(paper_entry)
            
            # If we got fewer papers than the page size, we've reached the end
            if len(entries) < page_size:
                break
                
            # Move to next page
            start += page_size
            
            # Add a small delay to avoid overwhelming the server
            time.sleep(1)
        
        if not papers:
            print(f"No papers could be extracted from {author_url}. The page structure might have changed.")
        
    except requests.exceptions.RequestException as e:
        print(f"Error fetching papers for {author_url}: {str(e)}")
    except Exception as e:
        print(f"Unexpected error while processing {author_url}: {str(e)}")
    
    return papers

@app.route('/')
def index():
    return render_template('index.html')
@app.route('/generate_report', methods=['POST'])
def generate_report():
    data = request.json
    source = data.get('source')

    # List of authors with Scopus IDs and Google Scholar links
    author_ids = [
    #   ("57223100630", "Dr AMRUTHA", "https://scholar.google.com/citations?user=fzs9d1IAAAAJ&hl=en"),
    #     ("55079543700", "Dr ANITA H B", "https://scholar.google.com/citations?user=-ZYIiGAAAAAJ&hl=en"),
    #     ("35737586100", "Dr AROKIA PAUL RAJAN R", "https://scholar.google.com/citations?hl=en&user=5Dl7tEYAAAAJ"),
    #     ("57189239708", "Dr ASHOK IMMANUEL V", "https://scholar.google.co.in/citations?user=px8Z3Q4AAAAJ&hl=en"),
    #     ("55881946700", "Dr BEAULAH SOUNDARABAI P", "https://scholar.google.co.in/citations?user=jTCHV4kAAAAJ&hl=en"),
    #     ("57044254900", "Dr CECIL DONALD A", "https://scholar.google.co.in/citations?user=_bbxYHsAAAAJ&hl=en&authuser=1"),
    #     ("57055221400", "Dr CHANDRA J", "https://scholar.google.com/citations?user=bn6WQUoAAAAJ"),
    #     ("59256484700", "Dr CYNTHIA T", "https://scholar.google.com/citations?hl=en&user=ThELNO0AAAAJ"),
    #     ("57162822500", "Dr DEEPA V JOSE", "https://scholar.google.co.in/citations?user=ryhyx4IAAAAJ&hl=en"),
    #     ("57205027677", "FABIOLA HAZEL POHRMEN", "https://scholar.google.com/citations?user=prcv4fAAAAAJ&hl=en&oi=ao"),
    #     ("57192668092", "Gobi Ramasamy", "https://scholar.google.com/citations?user=eu_o414AAAAJ&hl=en"),
    #     ("55811681700", "Helen k Joy", "https://scholar.google.com/citations?hl=en&user=uZXv4XIAAAAJ"),
    #     ("57205128308", "Hubert Shanthan", "https://scholar.google.com/citations?user=Cf2I4OoAAAAJ&hl=en"),
    #     ("57789387000", "R Kavitha", "https://scholar.google.com/citations?hl=en&user=Li0r8uMAAAAJ"),
    #     ("35069671200", "V.B.KIRUBANAND", "https://scholar.google.co.in/citations?user=FlLJ1SYAAAAJ&hl=en"),
    #     ("35332112400", "Dr. MANJUNATHA HIREMATH", "https://scholar.google.co.in/citations?user=AIdTGncAAAAJ&hl=en"),
    #     ("58529182900", "Dr Mohana Priya T", "https://scholar.google.com/citations?user=XPjU9AIAAAAJ&hl=en&authuser=1"),
    #     ("57193578932", "Nismon Rio Robert", "https://scholar.google.co.in/citations?hl=en&user=Z34wmvMAAAAJ"),
    #     ("57212476297", "Dr. NISHA VARGHESE", "https://scholar.google.com/citations?user=vGJxAzEAAAAJ&hl=en"),
    #     ("57201949000", "Dr. Neha Singhal", "https://scholar.google.com/citations?user=hlTGb-0AAAAJ&hl=en"),
    #     ("55263618900", "Dr. Nizar Banu P K", "https://scholar.google.co.in/citations?user=hC5psv4AAAAJ"),
    #     ("58244012600", "Peter Augustin D", "https://scholar.google.com/citations?user=cE0jxPcAAAAJ&hl=en"),
    #     ("57200798153", "Prabu P", "https://scholar.google.com/citations?user=GYjXshwAAAAJ"),
    #     ("59010451200", "Rajesh Kanna R", "https://scholar.google.com/citations?hl=en&user=HKK_hlsAAAAJ"),
    #     ("57201030358", "Dr.B.RAMAMURTHY", "https://scholar.google.co.in/citations?user=qIFXtnYAAAAJ&hl=en"),
    #     ("57211135848", "Resmi K R", "https://scholar.google.com/citations?hl=en&user=FmtW9kIAAAAJ"),
    #     ("56708741500", "Rohini V", "https://scholar.google.com/citations?user=_89sYcIAAAAJ&hl=en&oi=ao"),
    #     ("57209182380", "Sagaya Aurelia", "https://scholar.google.com/citations?user=qVkPhiAAAAAJ&hl=en"),
    #     ("56168895700", "J Sandeep", "https://scholar.google.co.in/citations?user=Hj3_OtwAAAAJ&hl=en"),
    #     ("57219413559", "Dr. Sangeetha G", "https://scholar.google.co.in/citations?user=kNdafyoAAAAJ&hl=en"),
    #     ("57209393752", "Saravanakumar K", "https://scholar.google.com/citations?hl=en&user=TIywHAYAAAAJ"),#clarification needed
    #     ("57203436758", "Shoney Sebastian", "https://scholar.google.co.in/citations?user=Mz8UAz8AAAAJ&hl=en"),
    #     ("57387061900", "SMERA C 1942049", "https://scholar.google.com/citations?user=5DpheNgAAAAJ&hl=en&authuser=1"),
    #     ("57213312387", "Smitha Vinod", "https://scholar.google.co.in/citations?user=RHYAEsoAAAAJ&hl=en"),
    #     ("56373322500", "Somnath Sinha", "https://scholar.google.com/citations?user=ORmwBEQAAAAJ&hl=en&authuser=1"),
    #     ("56703307000", "Sreeja CS", "https://scholar.google.com/citations?user=6_DGZukAAAAJ&hl=en&oi=ao"),
    #     ("57216788513", "Sridevi Rajasekaran", "https://scholar.google.com/citations?user=eiAIuOMAAAAJ&hl=en"),
    #     ("57189507074", "Dr Sudhakar T", "https://scholar.google.com/citations?hl=en&user=IkDN14UAAAAJ&view_op=list_works&sortby=pubdate"),
    #     ("57159691300", "Dr Suresh. K", "https://scholar.google.com/citations?user=i4ZqOsMAAAAJ&hl=en"),
    #     ("57159691300", "THIRUNAVUKKARASU V", "https://scholar.google.co.in/citations?user=TbJmY8IAAAAJ&hl=en"),
    #     ("57190966782", "Vaidhehi V", "https://scholar.google.com/citations?user=xfJLs0UAAAAJ&hl=en"),
    #     ("58873437100 ", "Dr Vijay Arputharaj J", "https://scholar.google.com/citations?hl=en&user=Ac5HrokAAAAJ"),
    #     ("57210956020", "Dr.Vineetha KR", "https://scholar.google.com/citations?user=-M-lmeUAAAAJ&hl=en"),
    #     ("57560038400", "S Chanti", "https://scholar.google.com/citations?hl=en&authuser=1&user=B8IlRMEAAAAJ"),
    #     ("57208210764", "Dr SURABHI SAXENA", "https://scholar.google.co.in/citations?user=0bjilf8AAAAJ&hl=en"),
    #     ("57195638295", "Dr. CYNTHIA C", "https://scholar.google.com/citations?user=By7k4REAAAAJ&hl=en"),#clarification needed
    #     ("57188976203", "Bhuvana Jayabalan", "https://scholar.google.com/citations?user=933fkHwAAAAJ"),
        ("57216241780", "Manasa Kulkarni", "https://scholar.google.com/citations?user=-W87fKwAAAAJ&hl=en"),
        ("57209855653", "New Begin M", "https://scholar.google.com/citations?hl=en&user=zp7srGsAAAAJ&view_op=list_works&authuser=1&gmla=AC6lMd9JmscOmxzs13XJXmG0F9ACK6jOOj7DEkYoUdCDTfhLaMqAW67nUbE6-gL-_39AZHtvXOOCmgIgXzMjrYMc"),
        ("57214340310", "Dr. LOGESHWARAN J", "https://scholar.google.com/citations?hl=en&user=CcVHJoQAAAAJ"),
        ("57220176692", "Dr. TEGIL  J  JOHN", "https://scholar.google.com/citations?user=xA99ggQAAAAJ&hl=en"),
        ("57224703422", "Dr. JOBIN FRANCIS", "https://scholar.google.com/citations?user=8T-ySqEAAAAJ&hl=en"),
        ("58310706200", "Dr. SANDHYA B", "https://scholar.google.co.in/citations?hl=en&user=8H2iIngAAAAJ"),
        ("57214244390", "Dr. Binayak Dutta", "https://scholar.google.com/citations?user=ZqyXA-MAAAAJ&hl=en")
    ]
    # Handle fetching Google Scholar paper details
    if source == 'paperDetails':
        paper_details = []
        for author_id, author_name, gscholar_link in author_ids:
            papers = fetch_google_scholar_papers(gscholar_link)
            print(f"Google Scholar Papers for {author_name}: {papers}")  # Debug logging
            paper_details.append({'Name': author_name, 'Papers': papers})
        return jsonify(paper_details)

    # Handle fetching Scopus paper details
    elif source == 'paperDetailsScopus':
        all_authors_data = []
        for author_id, author_name, _ in author_ids:
            scopus_response_json = fetch_author_papers(author_id)
            papers = parse_scopus_papers(scopus_response_json)
            author_data = {
                "Name": author_name,
                "ScopusPapers": papers,
                "ProfileLink": f"https://www.scopus.com/authid/detail.uri?authorId={author_id}"
            }
            all_authors_data.append(author_data)
        return jsonify(all_authors_data)

    # Handle 'both' option if needed (existing functionality)
    elif source == 'both':
        # Your existing code for 'both' option here
        pass

    # Handle 'average' option if needed (existing functionality)
    elif source == 'average':
        # Your existing code for 'average' option here
        pass

    # Handle 'googleScholarOnly' option if needed (existing functionality)
    elif source == 'googleScholarOnly':
        # Your existing code for 'googleScholarOnly' option here
        pass

    else:
        return jsonify({"error": "Invalid source specified"}), 400

    # Logic for handling 'both' and 'average' options (existing code) remains here...

    combined_data = []

    # Fetch data for each author
    for author_id, author_name, gscholar_link in author_ids:
        scopus_response_json = fetch_author_papers(author_id)
        total_papers_scopus, total_citations_scopus, h_index_scopus = parse_scopus_data(scopus_response_json)
        total_papers_gscholar, total_citations_gscholar, h_index_gscholar, i10_index = fetch_google_scholar_data(gscholar_link)

        # Get yearly citations
        yearly_citations = fetch_yearly_citations(gscholar_link)

        # Convert yearly_citations dictionary to a string format for easy display
        yearly_citations_str = ', '.join(f"{year}: {count}" for year, count in yearly_citations.items())

        # Append individual author data
        combined_data.append({
            'Name': author_name,
            'Total Papers (Google Scholar)': total_papers_gscholar or 0,
            'Total Citations (Google Scholar)': total_citations_gscholar or 0,
            'H-Index (Google Scholar)': h_index_gscholar or 0,
            'I10 Index (Google Scholar)': i10_index or 0,
            'Total Papers (Scopus)': total_papers_scopus or 0,
            'Total Citations (Scopus)': total_citations_scopus or 0,
            'H-Index (Scopus)': h_index_scopus or 0,
            'Yearly Citations': yearly_citations_str  # Store as a formatted string
        })

    # Handle "googleScholarOnly" source
    if source == 'googleScholarOnly':
        google_scholar_data = []
        for entry in combined_data:
            google_scholar_data.append({
                'Name': entry['Name'],
                'Total Citations': entry['Total Citations (Google Scholar)'],
                'H-Index': entry['H-Index (Google Scholar)'],
                'I10 Index': entry['I10 Index (Google Scholar)'],
                'Yearly Citations': entry['Yearly Citations']
            })
        return jsonify(google_scholar_data)

    # If source is "average", calculate individual averages per author
    if source == 'average':
        avg_data = []

        for entry in combined_data:
            avg_data.append({
                'Name': entry['Name'],
                'Total Papers (Google Scholar)': entry['Total Papers (Google Scholar)'],
                'Total Citations (Google Scholar)': entry['Total Citations (Google Scholar)'],
                'H-Index (Google Scholar)': entry['H-Index (Google Scholar)'],
                'I10 Index (Google Scholar)': entry['I10 Index (Google Scholar)'],
                'Total Papers (Scopus)': entry['Total Papers (Scopus)'],
                'Total Citations (Scopus)': entry['Total Citations (Scopus)'],
                'H-Index (Scopus)': entry['H-Index (Scopus)'],
                'Yearly Citations': entry['Yearly Citations'],
            })

        return jsonify(avg_data)

    # Filter data based on the source requested (if not 'average')
    filtered_data = []
    for entry in combined_data:
        filtered_entry = {'Name': entry['Name']}
        if source == 'googleScholar' or source == 'both':
            filtered_entry['Total Papers (Google Scholar)'] = entry['Total Papers (Google Scholar)']
            filtered_entry['Total Citations (Google Scholar)'] = entry['Total Citations (Google Scholar)']
            filtered_entry['H-Index (Google Scholar)'] = entry['H-Index (Google Scholar)']
            filtered_entry['I10 Index (Google Scholar)'] = entry['I10 Index (Google Scholar)']
            filtered_entry['Yearly Citations'] = entry['Yearly Citations']
        if source == 'scopus' or source == 'both':
            filtered_entry['Total Papers (Scopus)'] = entry['Total Papers (Scopus)']
            filtered_entry['Total Citations (Scopus)'] = entry['Total Citations (Scopus)']
            filtered_entry['H-Index (Scopus)'] = entry['H-Index (Scopus)']

        filtered_data.append(filtered_entry)


    return jsonify(filtered_data)

if __name__ == '__main__':
    app.run(debug=True)