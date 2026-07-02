"""gRPC server for faculty citation data - server-streaming equivalent of
OldCode's Flask /generate_report endpoint. See NewCode/protos/citations.proto
for the service contract.
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'generated'))

import grpc
import citations_pb2
import citations_pb2_grpc

from services.authors import scopus_authors, gscholar_authors
from services.gscholar_service import stream_all_authors_papers
from services.scopus_service import stream_all_scopus_papers
from services.combined_service import stream_combined_stats


class CitationServiceServicer(citations_pb2_grpc.CitationServiceServicer):
    async def StreamGoogleScholarPapers(self, request, context):
        async for author in stream_all_authors_papers(gscholar_authors):
            yield citations_pb2.AuthorPapers(
                name=author['name'],
                papers=[
                    citations_pb2.Paper(
                        title=p['title'], link=p['link'],
                        citations=str(p['citations']), year=str(p['year']),
                    )
                    for p in author['papers']
                ],
            )

    async def StreamScopusPapers(self, request, context):
        async for author in stream_all_scopus_papers(scopus_authors):
            yield citations_pb2.AuthorScopusPapers(
                name=author['name'],
                profile_link=author['profile_link'],
                papers=[
                    citations_pb2.ScopusPaper(
                        title=p['title'] or '', year=p['year'] or '',
                        citations=str(p['citations'] or '0'), link=p['link'] or '',
                    )
                    for p in author['papers']
                ],
            )

    async def StreamCombinedStats(self, request, context):
        async for stats in stream_combined_stats():
            yield citations_pb2.CombinedAuthorStats(
                name=stats['name'],
                papers_google_scholar=stats['papers_google_scholar'],
                citations_google_scholar=stats['citations_google_scholar'],
                h_index_google_scholar=stats['h_index_google_scholar'],
                i10_index_google_scholar=stats['i10_index_google_scholar'],
                yearly_citations_google_scholar=stats['yearly_citations_google_scholar'],
                papers_scopus=stats['papers_scopus'],
                citations_scopus=stats['citations_scopus'],
                h_index_scopus=stats['h_index_scopus'],
            )


async def serve(port=50051):
    server = grpc.aio.server()
    citations_pb2_grpc.add_CitationServiceServicer_to_server(CitationServiceServicer(), server)
    server.add_insecure_port(f'[::]:{port}')
    print(f"gRPC server starting on port {port}")
    await server.start()
    await server.wait_for_termination()


if __name__ == '__main__':
    asyncio.run(serve())
