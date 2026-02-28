"""Services package for Google Scholar and Scopus data fetching."""
from .config import API_KEY
from .scopus_service import (
    fetch_author_papers,
    parse_scopus_data,
    parse_scopus_papers,
    fetch_scopus_papers_async,
    fetch_scopus_stats_async,
    fetch_all_scopus_papers,
)
from .gscholar_service import (
    fetch_google_scholar_data,
    fetch_yearly_citations,
    fetch_google_scholar_papers,
    fetch_google_scholar_papers_async,
    fetch_google_scholar_data_async,
    fetch_all_authors_papers,
)
from .combined_service import fetch_all_combined_data
