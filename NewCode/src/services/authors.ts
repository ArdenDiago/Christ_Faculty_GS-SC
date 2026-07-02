// Ported verbatim from python-grpc-prototype/services/authors.py (itself a
// verbatim copy of OldCode/services/authors.py). Two parallel lists matched
// by exact `name` string, not by any id — see combinedService.ts for the
// join. Raw data lives in authorsData.json so this file stays pure types.
import authorsData from './authorsData.json';

export interface ScopusAuthor {
  name: string;
  scopus_id: string | null;
  scopus_url: string | null;
  orcid: string | null;
}

export interface GScholarAuthor {
  name: string;
  gscholar_id: string | null;
  gscholar_url: string | null;
}

export const scopusAuthors: ScopusAuthor[] = authorsData.scopus_authors;
export const gscholarAuthors: GScholarAuthor[] = authorsData.gscholar_authors;
