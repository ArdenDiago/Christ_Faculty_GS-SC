"""Test client for the CitationService gRPC server. Exercises each RPC,
printing results as they stream in plus a wall-clock time to first message
and time to completion - the numbers that matter for the REST-vs-gRPC
comparison against OldCode's /generate_report.

Usage:
    python client.py [gscholar|scopus|combined|all]
"""
import asyncio
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'generated'))

import grpc
import citations_pb2
import citations_pb2_grpc


async def run_gscholar(stub):
    print("\n=== StreamGoogleScholarPapers ===")
    start = time.monotonic()
    first = None
    count = 0
    async for author in stub.StreamGoogleScholarPapers(citations_pb2.Empty()):
        if first is None:
            first = time.monotonic() - start
        count += 1
        print(f"  [{count}] {author.name}: {len(author.papers)} papers")
    print(f"  -> {count} authors, first message in {first:.2f}s, total {time.monotonic() - start:.2f}s")


async def run_scopus(stub):
    print("\n=== StreamScopusPapers ===")
    start = time.monotonic()
    first = None
    count = 0
    async for author in stub.StreamScopusPapers(citations_pb2.Empty()):
        if first is None:
            first = time.monotonic() - start
        count += 1
        print(f"  [{count}] {author.name}: {len(author.papers)} papers")
    print(f"  -> {count} authors, first message in {first:.2f}s, total {time.monotonic() - start:.2f}s")


async def run_combined(stub):
    print("\n=== StreamCombinedStats ===")
    start = time.monotonic()
    first = None
    count = 0
    async for stats in stub.StreamCombinedStats(citations_pb2.Empty()):
        if first is None:
            first = time.monotonic() - start
        count += 1
        print(
            f"  [{count}] {stats.name}: GS papers={stats.papers_google_scholar} "
            f"citations={stats.citations_google_scholar} h={stats.h_index_google_scholar} | "
            f"Scopus papers={stats.papers_scopus} citations={stats.citations_scopus} h={stats.h_index_scopus}"
        )
    print(f"  -> {count} authors, first message in {first:.2f}s, total {time.monotonic() - start:.2f}s")


async def main():
    which = sys.argv[1] if len(sys.argv) > 1 else 'all'
    async with grpc.aio.insecure_channel('localhost:50051') as channel:
        stub = citations_pb2_grpc.CitationServiceStub(channel)
        if which in ('gscholar', 'all'):
            await run_gscholar(stub)
        if which in ('scopus', 'all'):
            await run_scopus(stub)
        if which in ('combined', 'all'):
            await run_combined(stub)


if __name__ == '__main__':
    asyncio.run(main())
