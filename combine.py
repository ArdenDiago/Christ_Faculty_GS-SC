import requests
import json
import pandas as pd
from bs4 import BeautifulSoup

# Load API key from config.json
with open('config.json') as config_file:
    config = json.load(config_file)

API_KEY = config['API_KEY']  # Access the API key directly

# Function to fetch author papers from Scopus using author ID
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

# Parse the results and extract desired details from Scopus
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

# Function to fetch Google Scholar data for an author using the provided link
def fetch_google_scholar_data(gscholar_link):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }

    response = requests.get(gscholar_link, headers=headers)
    if response.status_code == 200:
        soup = BeautifulSoup(response.content, 'html.parser')

        # Extract relevant data from the profile page
        try:
            # Count total papers based on the publication entries
            publication_entries = soup.find_all('tr', class_='gsc_a_tr')  # Find all publication rows
            total_papers = len(publication_entries)
            
            # Extract the Total Citations value directly from the HTML
            citation_count = soup.find('td', class_='gsc_rsb_std')  # This should find the first value (Total Citations)
            total_citations = int(citation_count.text.strip()) if citation_count else 0
            
            # Extract H-Index
            h_index = int(soup.find_all('td', class_='gsc_rsb_std')[2].text.strip()) if len(soup.find_all('td', class_='gsc_rsb_std')) > 2 else 0
            
            # Extract I10 Index
            i10_index = int(soup.find_all('td', class_='gsc_rsb_std')[3].text.strip()) if len(soup.find_all('td', class_='gsc_rsb_std')) > 3 else 0

            return total_papers, total_citations, h_index, i10_index
        except (IndexError, ValueError) as e:
            print(f"Error parsing Google Scholar data for {gscholar_link}: {e}")
            return None, None, None, None
    else:
        print(f"Error fetching Google Scholar data from {gscholar_link}: Status code {response.status_code}")
        return None, None, None, None


# Save the combined data to an Excel file
def save_combined_to_excel(data, output_file):
    df = pd.DataFrame(data)
    df.to_excel(output_file, index=False)
    print(f"Combined data saved to {output_file}")

# Main function to run the script
def main(author_ids):
    combined_data = []  # Store combined data from Scopus and Google Scholar

    for author_id, author_name, gscholar_link in author_ids:
        # Fetch papers for the given author ID from Scopus
        scopus_response_json = fetch_author_papers(author_id)
        total_papers_scopus, total_citations_scopus, h_index_scopus = parse_scopus_data(scopus_response_json)

        # Fetch data from Google Scholar using the provided link
        total_papers_gscholar, total_citations_gscholar, h_index_gscholar, i10_index = fetch_google_scholar_data(gscholar_link)

        # Append to combined data
        combined_data.append({
            'Name': author_name,
            'Total Papers (Google Scholar)': total_papers_gscholar,
            'Total Citations (Google Scholar)': total_citations_gscholar,
            'H-Index (Google Scholar)': h_index_gscholar,
            'I10 Index (Google Scholar)': i10_index,
            'Total Papers (Scopus)': total_papers_scopus,
            'Total Citations (Scopus)': total_citations_scopus,
            'H-Index (Scopus)': h_index_scopus,
        })

    # Save combined data to Excel
    save_combined_to_excel(combined_data, 'combined_papers_data.xlsx')

if __name__ == "__main__":
    from services.authors import scopus_authors, gscholar_authors

    def main():
        combined_data = []  # Store combined data from Scopus and Google Scholar

        for s_author, g_author in zip(scopus_authors, gscholar_authors):
            # Fetch papers for the given author ID from Scopus
            scopus_response_json = fetch_author_papers(s_author['scopus_id'])
            total_papers_scopus, total_citations_scopus, h_index_scopus = parse_scopus_data(scopus_response_json)

            # Fetch data from Google Scholar using the provided link
            total_papers_gscholar, total_citations_gscholar, h_index_gscholar, i10_index = fetch_google_scholar_data(g_author['gscholar_url'])

            # Append to combined data
            combined_data.append({
                'Name': g_author['name'],
                'Total Papers (Google Scholar)': total_papers_gscholar,
                'Total Citations (Google Scholar)': total_citations_gscholar,
                'H-Index (Google Scholar)': h_index_gscholar,
                'I10 Index (Google Scholar)': i10_index,
                'Total Papers (Scopus)': total_papers_scopus,
                'Total Citations (Scopus)': total_citations_scopus,
                'H-Index (Scopus)': h_index_scopus,
            })

        # Save combined data to Excel
        save_combined_to_excel(combined_data, 'combined_papers_data.xlsx')

    if __name__ == "__main__":
        main()
