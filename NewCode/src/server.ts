// gRPC server for faculty citation data - server-streaming equivalent of
// OldCode's Flask /generate_report endpoint. See NewCode/proto/citations.proto
// for the service contract. Port of python-grpc-prototype/server.py.
import * as grpc from '@grpc/grpc-js';
import type { ServerWritableStream } from '@grpc/grpc-js';
import { GRPC_PORT } from './lib/config';
import {
  type CitationServiceServer,
  CitationServiceService,
  type Empty,
} from './generated/citations';
import { gscholarAuthors, scopusAuthors } from './services/authors';
import { streamAllAuthorsPapers } from './services/gscholarService';
import { streamAllScopusPapers } from './services/scopusService';
import { streamCombinedStats } from './services/combinedService';

// Drains an async generator into a gRPC server-streaming call, writing each
// yielded value as a separate message. If the client cancels the stream, the
// 'cancelled' event fires `it.return()`, which runs the generator's `finally`
// block (aborting in-flight fetches) instead of letting them run to
// completion against nothing.
async function pipeStream<T>(call: ServerWritableStream<Empty, T>, gen: AsyncGenerator<T>): Promise<void> {
  const it = gen[Symbol.asyncIterator]();
  call.on('cancelled', () => {
    it.return?.(undefined as never);
  });
  try {
    while (true) {
      const { value, done } = await it.next();
      if (done || call.cancelled) break;
      call.write(value);
    }
  } finally {
    call.end();
  }
}

const serviceImpl: CitationServiceServer = {
  streamGoogleScholarPapers: (call) => {
    void pipeStream(call, streamAllAuthorsPapers(gscholarAuthors));
  },
  streamScopusPapers: (call) => {
    void pipeStream(call, streamAllScopusPapers(scopusAuthors));
  },
  streamCombinedStats: (call) => {
    void pipeStream(call, streamCombinedStats());
  },
};

function serve(): void {
  const server = new grpc.Server();
  server.addService(CitationServiceService, serviceImpl);
  server.bindAsync(`0.0.0.0:${GRPC_PORT}`, grpc.ServerCredentials.createInsecure(), (err, port) => {
    if (err) {
      console.error('Failed to bind gRPC server:', err);
      process.exit(1);
    }
    console.log(`gRPC server starting on port ${port}`);
  });
}

serve();
