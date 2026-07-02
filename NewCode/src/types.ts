// Internal domain shapes, independent of the generated proto types — mirrors
// the plain dicts the Python prototype's services pass around before
// server.py maps them onto citations_pb2 messages.

export interface Paper {
  title: string;
  link: string;
  citations: string;
  year: string;
}

export interface AuthorPapers {
  name: string;
  papers: Paper[];
}

export interface ScopusPaper {
  title: string;
  year: string;
  citations: string;
  link: string;
}

export interface AuthorScopusPapers {
  name: string;
  papers: ScopusPaper[];
  profileLink: string;
}

export interface GScholarStats {
  totalPapers: number;
  totalCitations: number;
  hIndex: number;
  i10Index: number;
  yearlyCitations: Record<string, number>;
}

export interface ScopusStats {
  totalPapers: number;
  totalCitations: number;
  hIndex: number;
}

export interface CombinedAuthorStats {
  name: string;
  papersGoogleScholar: number;
  citationsGoogleScholar: number;
  hIndexGoogleScholar: number;
  i10IndexGoogleScholar: number;
  yearlyCitationsGoogleScholar: Record<string, number>;
  papersScopus: number;
  citationsScopus: number;
  hIndexScopus: number;
}
