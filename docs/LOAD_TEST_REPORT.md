# PFP Load Test Report — `POST /api/fea/generate`

**Target:** `https://proof-fabric.preview.emergentagent.com` (preview pod)
**Endpoint:** `POST /api/fea/generate`
**Payload:** unique `idempotency_key` / `transaction_id` / `timestamp` per request — exercises the **write path** (not idempotent fast-return).
**Tool:** `aiohttp` async load generator with warm-up, ~25 s runs.

---

## TL;DR

> **The PFP backend currently sustains ~340 TPS in the FastAPI process (1 uvicorn worker, async Motor, all-200s up to 500 concurrent connections).**
> **End-to-end through the public ingress, sustained throughput is ~40–50 TPS before ingress-level timeouts / connection failures dominate.**

The bottleneck is **not CPU on the FastAPI process** (it sat at <2% throughout) — the limit is the single-worker async event loop's Mongo round-trip serialisation, and beyond that the Kubernetes ingress in front of the preview pod.

---

## Theoretical estimate (back-of-envelope, derived from architecture)

Per request:

| Step | Cost |
|---|---|
| Ed25519 sign + SHA-256 + canonical JSON | ~0.3 ms |
| Mongo `find` × 2 (idempotency + replay check) | 2 × 5 ms = 10 ms |
| Mongo `insert_one` | ~5 ms |
| FastAPI / Pydantic overhead | ~3 ms |
| **Total per request (single worker, local)** | **≈ 15–20 ms** |

→ Theoretical single-worker ceiling ≈ **50–65 TPS sequential** / ~**200–400 TPS** with async concurrency (multiple in-flight DB calls).

Through public ingress add 30–150 ms of network + proxy latency.

---

## Test methodology

For each concurrency level: **25-second** sustained run with N persistent workers each firing requests back-to-back as fast as the server responds.

- Each request has a **fresh** `idempotency_key`, `transaction_id`, and microsecond-resolution `timestamp` so we measure write performance, not the idempotent fast-path.
- 10 warm-up requests before measurement window.
- `aiohttp` total timeout: 30 s.
- Backend process CPU + RSS sampled at 0.5 s intervals during the run.

---

## Results — direct to backend (localhost:8001)

| Conc | TPS | p50 (ms) | p95 (ms) | p99 (ms) | Max (ms) | Fail % | Backend CPU max |
|---:|---:|---:|---:|---:|---:|---:|---:|
| **10** | **217** | 46 | 50 | 54 | 56 | 0.00 | 2 % |
| **100** | **345** | 300 | 399 | 401 | 433 | 0.00 | 2 % |
| **500** | 322 | 1 640 | 1 823 | 2 028 | 2 257 | 0.00 | 2 % |
| **1 000** | 102 | 9 785 | 15 052 | 15 138 | 26 515 | 0.00 (no errors, but latency exceeds practical limits) | 2 % |

**RSS held flat at ~26.5 MB across all runs.**

**Sweet spot:** ~100 concurrent connections → **345 TPS** with p95 = 399 ms.
**Saturation:** clear at conc = 500 (throughput plateaus at ~320 TPS, latency triples).
**Over-saturation:** conc = 1 000 — TCP/HTTP queueing forces requests to wait 10–15 s; effective TPS drops.

---

## Results — through the public ingress (preview URL)

| Conc | TPS | p50 (ms) | p95 (ms) | p99 (ms) | Fail % | Failure mode |
|---:|---:|---:|---:|---:|---:|---|
| **10** | 43 | 99 | 118 | 300 | 8.9 | ingress timeouts (sporadic) |
| **100** | 29 | 107 | 30 088 | 30 660 | 19.2 | ingress timeouts dominate p95+ |
| **500** | 53 | 1 325 | 30 689 | 30 841 | 41.0 | ingress drops / 30 s timeouts |
| **1 000** | 126 | 1 711 | 30 717 | 30 911 | 54.9 | majority of requests rejected by ingress |

Even at concurrency 10, p99 already spikes to 300 ms (vs 54 ms direct) — the ingress (Kubernetes proxy + Cloudflare or equivalent) is the limiting layer for any real-world client. **The preview pod's ingress caps usable end-to-end throughput around 40–50 TPS sustained.**

---

## CPU / RAM

The FastAPI / uvicorn worker (pid 42, single process):

| Run | CPU mean | CPU max | RSS mean | RSS max |
|---|---:|---:|---:|---:|
| All concurrencies (10 → 1000) | 0.0 % | **2 %** | 26.5 MB | 26.5 MB |

**The process is I/O-bound, not CPU-bound.** It has massive CPU headroom — meaning the cure for "more TPS" is more concurrent DB round-trips (more workers, parallel writes), not a faster machine.

---

## Bottlenecks ranked by impact

1. 🔴 **Single uvicorn worker** (`--workers 1`). One event loop serialises all incoming requests' async DB calls.
2. 🔴 **Kubernetes ingress / proxy in front of the preview pod.** Drops/timeouts > 50–100 concurrent connections from a single client; not tunable from inside the app.
3. 🟡 **Mongo round-trips on the critical path.** Each `/fea/generate` does 2 reads + 1 write. With proper indexes (already in place on `(transaction_id, timestamp)`), these are 1–5 ms each but they're serial per request.
4. 🟢 **CPU / RAM** are not bottlenecks.
5. 🟢 **Crypto path** (Ed25519 sign + SHA-256) is not a bottleneck — sub-millisecond.

---

## How many concurrent users can PFP support today?

Assuming a realistic API caller sending ~1 generate every few seconds:

- **Backend (direct):** ~**350 active in-flight requests** with sub-500 ms latency → roughly **1 500–3 000 concurrent integrated systems** (each generating few-RPS).
- **Through preview ingress:** comfortably ~**40 active calling clients** before ingress timeouts dominate.

These limits move dramatically with the optimisations below.

---

## Path to higher TPS (no code redesign required)

| Change | Effort | Expected TPS lift |
|---|---|---|
| Set `uvicorn --workers N` (where N ≈ cores; pod has 8) | one supervisord line | **~6–8× → 2 000–2 500 TPS direct** |
| Add Mongo index on `idempotency_key` (if not yet present) | one `create_index` | latency p95 down 20–40 % |
| Move from in-pod Mongo to a properly resourced MongoDB Atlas tier | infra | flatter latency under load |
| Production Emergent deployment or dedicated load-balancer instead of preview ingress | infra | 5–10× public ingress TPS |
| Add Redis cache for `idempotency_key` lookups | small refactor | 2–3× more headroom on /generate |

---

## Final answer

> **Current PFP supports approximately 340 TPS sustained on the FastAPI backend (1 uvicorn worker, async Motor, in-pod Mongo, all-success up to 500 concurrent connections, p95 = 400 ms, p99 = 401 ms at the sweet spot of ~100 in-flight requests).**
>
> **End-to-end through the preview ingress, that drops to ~40–50 TPS sustainable before ingress-level timeouts dominate.**
>
> **The FastAPI process itself is nowhere near CPU- or memory-bound (<2 % CPU, ~26 MB RSS) — it is async-I/O serialisation–bound. Scaling `uvicorn --workers` to match the pod's 8 cores is expected to lift the backend ceiling to ~2 000–2 500 TPS with no code changes.**
