# OMMS reproducible Before baseline (2026-08-22)

## Scope

This is the Phase A measurement baseline. No OS API, cache algorithm, SQL pagination,
MQ batching, connection-pool setting, or production performance behavior was changed.
The 50-user deep-saturation stage was not repeated because 25 users already exposed
the knee and pool exhaustion.

## Reconstructing the tested source

The tested worktree was intentionally dirty and cannot be represented by HEAD alone.
Its reconstructible identity is:

- base Git SHA: `5c71c94dd93eb41aa8409f6eda3c10488c686c26`;
- Base64 source patch: `performance-baseline-2026-08-22-source.patch.b64`;
- encoded/decoded patch SHA-256:
  `3147fc6fa63e75b736ec3bec4ca5bf1e6c0e5d0d52bd5e7b650e7b23a7e3829b` /
  `43e7277b251bf5be7fae43a9a7ddd31939ddbc4f783d08b4f77d62b239bc2a7c`;
- source fingerprint SHA-256: `185fa513191569b05500dcd2bf380cd7563c31f83db00c4709388bafee38f13e`.

Reconstruct from a clean checkout with:

```powershell
$encoded = Get-Content docs/performance-baseline-2026-08-22-source.patch.b64 -Raw
git checkout 5c71c94dd93eb41aa8409f6eda3c10488c686c26
[IO.File]::WriteAllBytes('before.patch', [Convert]::FromBase64String($encoded))
git apply before.patch
```

The patch was reverse-checked against the tested tree, applied to a clean checkout,
and all 20 resulting Git blob IDs were compared with the tested files. The complete
manifest is `performance-baseline-2026-08-22-source-manifest.json`. It includes the
tracked runtime changes and the registered untracked WebSocket route and tests; it
excludes credentials and these baseline evidence files.

The dirty changes are material to runtime: startup includes MQ/WebSocket background
tasks, service code includes current OS/process query behavior, and DB/schema files
contain the current pool and indexes. Frontend-only, documentation, and test changes
do not execute in Locust, but remain in the patch so the whole tested source can be
reconstructed. None of the pre-existing dirty files was staged, reset, stashed,
deleted, or overwritten.

## Fixed environment and data

- Windows 10 build 26200; 24 logical CPUs; Python 3.11.15; Locust 2.46.3.
- One uvicorn worker on `127.0.0.1:8004`; each concurrency level starts a fresh
  isolated worker and verifies one RabbitMQ consumer before sampling.
- SQLAlchemy pool size 10, overflow 30, timeout 30 seconds.
- MySQL 8.0.46 in Docker on port 3307.
- Redis 7.4.9 in Docker on port 6380; `maxmemory=0`, `noeviction`.
- Exact rows: `ops_cfg=8,000`, `ops_state=6,009`, `ops_log=125,260`.
- Approximate table bytes: cfg data/index 1,589,248/344,064; state data/index
  2,293,760/0; log data/index 25,755,648/21,610,496.
- Indexes: cfg `(type,status,group)`; state primary
  `(date,type,machine_tag,key,value)`; log primary `(log_id)`, unique `(event_id)`,
  `(date,level,log_id)`, `(date,machine_tag,level,log_id)`, `(level)`, and
  `(machine_tag)`.

The log count is higher than the pre-MQ dataset. All Phase A HTTP stages used the
same 125,260-row log dataset, so they are internally comparable. They must not be
presented as a strict numerical comparison with a baseline that used fewer rows.

The isolated runner is `benchmarks/monitor/run_isolated.ps1`, SHA-256
`acfb502ada740ecc1f9464aa1a10d5a041ac5e0687ec7eead754561e87b05deb`.

## Workload models

- `fallback-warm`: 4.5-5.5 second wait, TTL 300, explicit preload, 120 seconds/stage.
- `fallback-expiry`: 4.5-5.5 second wait, TTL 3, cleared before each stage,
  120 seconds/stage.
- `steady30-expiry`: 29.5-30.5 second wait, TTL 3, cleared before each stage,
  180 seconds/stage. This is the WS-online reconciliation model.

Every refresh follows the frontend call pattern: total, process, default log, and OS
page 1 concurrently, then all remaining OS pages. Random log tasks cover list, level,
`only_error`, and machine filter. The 5-second models are fallback/stress, not the
only normal-user model. Each users level was an independent run.

## Aggregate results

| Scenario | Users | Requests | RPS | P50 ms | P95 ms | P99 ms | Failure |
|---|---:|---:|---:|---:|---:|---:|---:|
| fallback-warm | 1 | 365 | 3.06 | 1,700 | 2,000 | 2,100 | 0.00% |
| fallback-warm | 10 | 1,404 | 11.80 | 5,300 | 8,700 | 9,800 | 0.78% |
| fallback-warm | 25 | 1,215 | 10.22 | 19,000 | 32,000 | 37,000 | 0.33% |
| fallback-expiry | 1 | 242 | 2.03 | 2,100 | 5,000 | 6,400 | 0.00% |
| fallback-expiry | 10 | 111 | 1.35 | 44,000 | 81,000 | 81,000 | 1.80% |
| fallback-expiry | 25 | 164 | 1.48 | 106,000 | 109,000 | 110,000 | 27.44% |
| steady30-expiry | 1 | 102 | 0.57 | 2,300 | 5,300 | 7,300 | 0.00% |
| steady30-expiry | 10 | 152 | 1.35 | 107,000 | 111,000 | 111,000 | 26.97% |
| steady30-expiry | 25 | 243 | 1.43 | 71,000 | 128,000 | 128,000 | 12.35% |
| steady30-expiry repeat | 10 | 284 | 1.65 | 36,000 | 98,000 | 98,000 | 1.06% |

The 10-user steady repeat is retained rather than selecting the better run. It shows
large phase-sensitive variance in failure rate and median, while both samples have
very high tail latency and reach the same 41-connection ceiling. Percentiles for
rare random filter tasks are directional; sample counts are retained in
`performance-baseline-2026-08-22-endpoints.csv`.

## Endpoint evidence and request amplification

- A complete 1-user expiry sample made 210 OS requests for 10 process refreshes:
  one dashboard refresh expands into 21 OS list requests at page size 100.
- Warm 1-user OS list was 316/365 requests, with P50/P95/P99 1.7/2.0/2.1 seconds.
- Warm 10-user OS list was 1,187/1,404 requests, with P50/P95/P99
  5.8/8.8/9.9 seconds.
- Expiry 10-user total was 79/81/81 seconds, process 81/81/81 seconds, and OS
  44/79/79 seconds. Default log was 2.1/65/65 seconds in this synchronized sample.
- Steady 10-user repeat still produced 223 OS calls and OS 43/98/98-second
  P50/P95/P99, despite the lower average reconciliation frequency.

The practical knee remains between 1 and 10 dashboard users. Warm throughput reaches
about 11 RPS and then stops scaling while latency rises. On cache expiry, 10 users
already collapse to about 1.4-1.7 RPS with long connection waits.

## Resource attribution

| Scenario/users | DB connected max | DB running max | App CPU (% one core) | App WS MiB | MySQL CPU avg/max | Redis CPU avg/max |
|---|---:|---:|---:|---:|---:|---:|
| warm/1 | 3 | 3 | 24.1 | 186.0 | 5.2/16.9% | 1.2/2.1% |
| warm/10 | 8 | 3 | 91.8 | 296.6 | 9.2/23.6% | 1.5/2.5% |
| warm/25 | 11 | 3 | 90.9 | 322.6 | 11.8/26.1% | 1.5/2.5% |
| expiry/1 | 6 | 3 | 45.4 | 222.6 | 7.9/22.1% | 1.3/2.6% |
| expiry/10 | 41 | 3 | 69.6 | 602.0 | 3.8/31.4% | 1.2/2.2% |
| expiry/25 | 41 | 2 | 70.2 | 698.3 | 3.7/17.1% | 0.9/2.2% |
| steady30/1 | 5 | 3 | 14.6 | 209.8 | 5.4/15.5% | 1.0/2.7% |
| steady30/10 | 41 | 2 | 47.4 | 675.3 | 1.8/8.7% | 1.1/2.8% |
| steady30/25 | 41 | 2 | 82.0 | 632.9 | 3.9/30.0% | 0.8/1.9% |
| steady30/10 repeat | 41 | 3 | 77.9 | 638.5 | 3.3/17.8% | 0.6/1.8% |

`Threads_connected=41` equals the 40-connection application ceiling plus the sampler.
Backend traces contain `QueuePool limit of size 10 overflow 30 reached` and the
30-second timeout for the observed HTTP 500/non-JSON responses. At the same time,
`Threads_running` never exceeded 3, MySQL CPU remained low, and Redis CPU stayed
below 3%. This is application-side connection retention/queueing during repeated
domain reconstruction, not MySQL or Redis saturation. Full resource samples are
summarized in `performance-baseline-2026-08-22-resources.csv`.

## Comparison and Phase A decision

The previous run and this reconstructible run agree on all three decision-level
observations:

1. one refresh creates 21 OS list calls;
2. the knee occurs between 1 and 10 users;
3. concurrent cache misses exhaust/wait on the application pool while MySQL running
   threads and MySQL/Redis CPU remain low.

Warm headline values are close to the previous run. Expiry and steady medians/failure
rates vary with synchronized request phase, but their long tails, 41 connections,
pool-timeout signatures, and idle database/Redis are reproducible. Therefore OS
request amplification remains the first optimization target. Cache-miss
single-flight remains the next bounded step after an OS before/after measurement.
Increasing the pool or tuning Redis is not supported by this evidence.

Phase A stops here. No Phase B implementation is included.
