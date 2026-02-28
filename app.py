"""Flask application for fetching faculty Google Scholar and Scopus data."""
from flask import Flask, request, jsonify, render_template
import asyncio

# Import from services package
from services.authors import scopus_authors, gscholar_authors
from services.gscholar_service import fetch_all_authors_papers
from services.scopus_service import fetch_all_scopus_papers
from services.combined_service import fetch_all_combined_data

app = Flask(__name__)


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/generate_report', methods=['POST'])
def generate_report():
    data = request.json
    source = data.get('source')

    # Handle fetching Google Scholar paper details

    if source == 'paperDetails':
        # Use async concurrent fetching for speed
        paper_details = asyncio.run(fetch_all_authors_papers(gscholar_authors))
        return jsonify(paper_details)

    # Handle fetching Scopus paper details

    elif source == 'paperDetailsScopus':
        # Use async concurrent fetching for speed
        all_authors_data = asyncio.run(fetch_all_scopus_papers(scopus_authors))
        return jsonify(all_authors_data)

    # Handle combined data sources with async fetching

    elif source in ['both', 'average', 'googleScholarOnly', 'scopus', 'googleScholar']:
        # Use async concurrent fetching for all combined data
        # For combined, use both lists zipped by name (assuming same order)
        combined_data = asyncio.run(fetch_all_combined_data())
        
        # Handle "googleScholarOnly" source
        if source == 'googleScholarOnly':
            google_scholar_data = []
            for entry in combined_data:
                print(entry)
                google_scholar_data.append({
                    'Name': entry['name'],
                    'Total Citations': entry['citations_google_scholar'],
                    'H-Index': entry['i10_index_google_scholar'],
                    'I10 Index': entry['h_index_google_scholar'],
                    'Yearly Citations': entry['citations_by_year']
                })
            return jsonify(google_scholar_data)

        # If source is "average", return all data per author
        if source == 'average':
            return jsonify(combined_data)

        # Filter data based on the source requested
        filtered_data = []
        for entry in combined_data:
            filtered_entry = {'Name': entry.get('name', '')}
            if source == 'googleScholar' or source == 'both':
                filtered_entry['Total Papers (Google Scholar)'] = entry.get('papers_google_scholar', 0)
                filtered_entry['Total Citations (Google Scholar)'] = entry.get('citations_google_scholar', 0)
                filtered_entry['H-Index (Google Scholar)'] = entry.get('h_index_google_scholar', 0)
                filtered_entry['I10 Index (Google Scholar)'] = entry.get('i10_index_google_scholar', 0)
                filtered_entry['Yearly Citations'] = entry.get('citations_by_year', '')
            if source == 'scopus' or source == 'both':
                filtered_entry['Total Papers (Scopus)'] = entry.get('papers_scopus', 0)
                filtered_entry['Total Citations (Scopus)'] = entry.get('citations_scopus', 0)
                filtered_entry['H-Index (Scopus)'] = entry.get('h_index_scopus', 0)

            filtered_data.append(filtered_entry)

        return jsonify(filtered_data)

    else:
        return jsonify({"error": "Invalid source specified"}), 400


if __name__ == '__main__':
    app.run(debug=True)
