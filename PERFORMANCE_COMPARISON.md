# REST (OldCode) vs gRPC (NewCode) — Speed & Load-Time Comparison

Live benchmark of the Flask/REST implementation (repo root: `app.py` + `services/`) against the Node.js/TypeScript gRPC implementation (`NewCode/`), run back-to-back against the **same live Google Scholar and Scopus data** on 2026-07-02.

## TL;DR

- **Time to first result: gRPC wins by ~1000-15000x.** REST returns nothing until the *entire* batch of ~53-56 authors finishes — the client stares at a blank screen for 20 seconds to 2.5 minutes. gRPC streams each author's data the moment it's ready: **8-47 milliseconds** to the first author, every time.
- **Payload size (clean data, Scopus): gRPC is ~42% smaller.** 309,359 bytes of JSON vs 179,299 bytes of protobuf for the same 56 authors' full paper lists.
- **Total completion time was confounded by Google Scholar rate-limiting mid-benchmark** (see Data Quality Note below) — those specific numbers should not be read as "gRPC fetches faster than REST." The two systems run *identical* fetch logic (same semaphores, same retry/backoff, same pagination), so total completion time is fundamentally bound by upstream response time, not by REST vs gRPC.

## Methodology

- Both servers ran locally on the same machine, benchmarked sequentially (REST first, then gRPC, per operation) via `NewCode/scripts/benchmark.ts`, driven with Node's native `fetch` (REST) and `@grpc/grpc-js` (gRPC).
- Three operation pairs, chosen to mirror OldCode's REST `source` values against NewCode's three RPCs:

  | Comparison | REST (`POST /generate_report`) | gRPC |
  |---|---|---|
  | Google Scholar paper details | `{"source": "paperDetails"}` | `StreamGoogleScholarPapers` |
  | Scopus paper details | `{"source": "paperDetailsScopus"}` | `StreamScopusPapers` |
  | Combined GS + Scopus stats | `{"source": "both"}` | `StreamCombinedStats` |

- **"Time to first result" only applies to gRPC.** REST's Flask handler does `asyncio.run(fetch_all(...))` then a single `jsonify(...)` — by construction there is no partial response; the number reported for REST is the same as its total completion time.
- Payload size = REST: raw response body bytes (JSON text). gRPC: sum of each streamed message's protobuf-encoded byte length (via the generated `.encode(...).finish().length`), i.e. wire size, not counting gRPC/HTTP2 framing overhead on either side.
- Single run per pair, not averaged — see limitations below.

## Results

| Operation | System | Total time | Time to first result | Authors returned | Payload (bytes) |
|---|---|---:|---:|---:|---:|
| Google Scholar paper details ⚠️ | REST | 149.97s | — (atomic) | 53 | 3,033 |
| Google Scholar paper details ⚠️ | gRPC | 53.99s | **47ms** | 53 | 12,241 |
| Scopus paper details ✅ | REST | 20.72s | — (atomic) | 56 | 309,359 |
| Scopus paper details ✅ | gRPC | 22.07s | **9ms** | 56 | 179,299 |
| Combined GS + Scopus stats ⚠️ | REST | 162.36s | — (atomic) | 56 | 19,014 |
| Combined GS + Scopus stats ⚠️ | gRPC | 69.63s | **11ms** | 56 | 1,297 |

✅ = clean run, no external rate-limiting observed. ⚠️ = Google Scholar rate-limited most requests during this run (see below) — total time and payload size for these two rows are **not representative** of steady-state performance; time-to-first-result is still valid and, if anything, more dramatic under degraded conditions.

## Data quality note: Google Scholar rate-limiting

Before this benchmark ran, this session had already made several live Google Scholar requests (interactive smoke-testing while building NewCode). By the time the benchmark started, Google Scholar was rate-limiting this IP: **50 of 53 authors returned 0 papers in the REST run, and 49 of 50 in the gRPC run** (server logs: `Fetched 0 papers for <name>`, repeated). Only 3 of the 54 authors are expected to legitimately have 0 Google Scholar papers (no `gscholar_id` on file) — so this is rate-limiting, not real data. Scopus (an authenticated, official API, not scraped) was unaffected beyond a handful of transient `429`s that the existing retry logic absorbed correctly — every author with a `scopus_id` on file got real data back in both systems.

Because REST ran first in each pair, and Google's blocking behavior can shift over the course of a run (e.g. failing faster once an IP is flagged, rather than timing out through full retries), **the REST-vs-gRPC total-time gap in the two ⚠️ rows is likely an artifact of run order against a degrading external service, not a genuine protocol difference.** Both systems execute the same semaphore-bounded, retry+backoff fetch logic (ported line-for-line — see `NewCode/src/services/gscholarService.ts` vs `services/gscholar_service.py`), so under identical network conditions total completion time should converge to similar magnitudes; any residual gap would be attributable to JSON vs protobuf (de)serialization cost, which is small relative to network-bound scraping.

## What's actually being measured

1. **Time to first result is a structural property of the transport, not the network conditions.** REST's single-blob-at-the-end design means a user staring at OldCode's UI gets *zero* feedback for up to 2.5 minutes in this run. gRPC's streaming design delivered the first author in single-digit-to-double-digit milliseconds in all three operations, regardless of how degraded the rest of the run was. This is the clearest, most reproducible finding here.
2. **Protobuf is meaningfully smaller on the wire than JSON for the same data** — confirmed on the one clean (non-rate-limited) comparison, Scopus paper details: 179KB vs 309KB, a ~42% reduction, consistent with protobuf's binary encoding and lack of repeated field-name strings.
3. **Total completion time is not a fair REST-vs-gRPC comparison in this run** — it mostly reflects Google Scholar's response to repeated scraping within the same session, which affected both systems (unequally, due to run order).

## Limitations of this benchmark

- Single run per operation/system, not averaged over multiple trials — no variance/confidence interval.
- REST and gRPC were benchmarked sequentially against the same live, rate-limited external service, not simultaneously or against a stable/mocked backend — this confounds total-time comparisons for the two Google-Scholar-involving operations (see above).
- Both servers ran on the same machine as the client (no real network hop between client and server), so these numbers exclude any client-server network latency a real deployment would add on top.
- No repeat run was attempted after Google Scholar's rate limit reset, to get a clean total-time comparison for the GS-based operations — re-running immediately would likely hit the same limiting.

Raw numbers backing the table above are in [`benchmark-results.json`](./benchmark-results.json) at repo root.

## Reproducing

```bash
# Terminal 1 — REST (repo root)
python app.py          # http://127.0.0.1:5000

# Terminal 2 — gRPC
cd NewCode && npm run build && node dist/server.js   # localhost:50051

# Terminal 3
cd NewCode && npx tsx scripts/benchmark.ts > benchmark-results.json
```
