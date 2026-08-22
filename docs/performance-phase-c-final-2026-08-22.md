# OMMS Phase C final performance benchmark

Date: 2026-08-22

Phase C source: `5f48e089055a8ee7cfaca334d212bc609f1fe9f8` (`main`, clean)

Single-flight change under test: `454e7f89 perf: coalesce concurrent monitor cache misses`

Comparison: accepted Phase B After results at `f87cb81b`

## Conclusion

The process-local single-flight implementation removes the concurrent cache-miss
stampede observed after Phase B. The target expiry and 30-second reconciliation
scenarios improve at both 10 and 25 users, the 41-connection ceiling is no longer
reached, and no SQLAlchemy `QueuePool` timeout is present in the Phase C runtime
logs. No further core performance optimization is justified by this benchmark.

Warm-cache performance remains in the same range as Phase B, as expected because
single-flight only changes the miss path. Warm 25-user latency remains high, but it
does not reproduce the connection-pool failure and is outside the cache-miss defect
addressed by Phase C.

## Fixed environment and method

- Windows 10 host, Python 3.11.15, Locust 2.46.3.
- One freshly started Uvicorn worker per user stage.
- MySQL 8.0.46; SQLAlchemy pool size 10 plus max overflow 30.
- Redis 7.4.9, `maxmemory=0`, `maxmemory-policy=noeviction`.
- Exact rows: `ops_cfg=8000`, `ops_state=6009`, `ops_log=125260`.
- Warm TTL: 300 seconds. Expiry and steady30 TTL: 3 seconds.
- Warm and expiry duration: 2 minutes per user level. Steady30 duration: 3
  minutes, with a 29.5-30.5 second wait between dashboard refreshes.
- Users were run as independent stages at 10 and 25; no 50-user run was made.
- Workload and endpoint mix are the Commit 7 dashboard workload. Refresh
  throughput is the minimum request rate among total, OS snapshot, process list,
  and default log list, because one completed dashboard refresh requires one of
  each after Phase B.

Commands:

```powershell
.\benchmarks\monitor\run_isolated.ps1 -CacheScenario warm -OutputRoot benchmark-results\phase-c-final-warm-v2 -Users 10,25 -RunTime 2m -SpawnRate 5 -StagePrefix warm-phase-c
.\benchmarks\monitor\run_isolated.ps1 -CacheScenario expiry -OutputRoot benchmark-results\phase-c-final-expiry -Users 10,25 -RunTime 2m -SpawnRate 5 -StagePrefix expiry-phase-c
.\benchmarks\monitor\run_isolated.ps1 -CacheScenario expiry -OutputRoot benchmark-results\phase-c-final-steady30 -Users 10,25 -RunTime 3m -SpawnRate 5 -WaitMinSeconds 29.5 -WaitMaxSeconds 30.5 -StagePrefix steady30-phase-c
```

The first warm attempt stopped before load generation because Locust was absent
from the virtual environment. Locust 2.46.3, the version pinned by the benchmark
requirements, was installed and only `phase-c-final-warm-v2` is treated as a valid
warm result.

## Overall Before/After

RPS is aggregate HTTP request throughput. Refresh/s is the completed dashboard
refresh throughput defined above. Latencies are milliseconds.

| Scenario | Users | Phase | RPS | Refresh/s | P50 | P95 | P99 | Failure |
|---|---:|---|---:|---:|---:|---:|---:|---:|
| warm | 10 | Phase B | 6.072 | 1.397 | 390 | 1,500 | 2,300 | 1.653% |
| warm | 10 | Phase C | 5.735 | 1.341 | 510 | 2,700 | 3,400 | 1.176% |
| warm | 25 | Phase B | 9.206 | 2.101 | 2,800 | 7,900 | 9,800 | 7.364% |
| warm | 25 | Phase C | 8.418 | 1.896 | 3,100 | 8,700 | 9,700 | 4.404% |
| expiry | 10 | Phase B | 1.283 | 0.245 | 2,500 | 39,000 | 45,000 | 0.000% |
| expiry | 10 | Phase C | 3.938 | 0.898 | 1,600 | 6,900 | 8,600 | 1.720% |
| expiry | 25 | Phase B | 1.100 | 0.151 | 31,000 | 115,000 | 118,000 | 6.870% |
| expiry | 25 | Phase C | 6.995 | 1.486 | 2,400 | 14,000 | 17,000 | 1.681% |
| steady30 | 10 | Phase B | 0.922 | 0.181 | 1,500 | 19,000 | 35,000 | 0.000% |
| steady30 | 10 | Phase C | 1.096 | 0.229 | 1,000 | 6,700 | 8,400 | 0.000% |
| steady30 | 25 | Phase B | 1.267 | 0.270 | 41,000 | 76,000 | 80,000 | 3.111% |
| steady30 | 25 | Phase C | 3.118 | 0.698 | 940 | 4,500 | 6,200 | 0.000% |

Target-path changes:

- expiry 10 P95: 39.0 s to 6.9 s (-82.3%); RPS +206.9%; refresh/s +266.5%.
- expiry 25 P95: 115 s to 14 s (-87.8%); RPS +535.9%; refresh/s +884.1%.
- steady30 10 P95: 19.0 s to 6.7 s (-64.7%); RPS +18.9%; refresh/s +26.5%.
- steady30 25 P95: 76.0 s to 4.5 s (-94.1%); RPS +146.1%; refresh/s +158.5%.

The Phase C expiry failures were Locust `response is not JSON` failures (1.720%
at 10 users, 1.681% at 25 users). Runtime logs contain no application traceback,
HTTP 4xx/5xx marker, or QueuePool timeout for those stages. The same failure class
also occurs in warm runs and is consistent with local Windows transport/reset
noise; it should not be presented as an application correctness improvement.

## Snapshot endpoint latency

Values are P50/P95/P99 milliseconds.

| Scenario | Users | Phase | total | OS snapshot | process list |
|---|---:|---|---:|---:|---:|
| warm | 10 | Phase B | 430/1,400/2,300 | 210/1,100/2,300 | 390/1,400/2,400 |
| warm | 10 | Phase C | 520/2,500/2,700 | 320/2,100/2,400 | 480/2,400/2,600 |
| warm | 25 | Phase B | 2,100/5,900/8,000 | 2,700/9,600/10,000 | 2,700/6,100/8,000 |
| warm | 25 | Phase C | 2,300/5,700/7,900 | 2,800/8,800/10,000 | 3,100/7,100/7,600 |
| expiry | 10 | Phase B | 26,000/45,000/46,000 | 5,700/13,000/13,000 | 15,000/26,000/26,000 |
| expiry | 10 | Phase C | 4,600/8,500/9,800 | 750/4,400/5,100 | 2,100/6,400/7,000 |
| expiry | 25 | Phase B | 82,000/118,000/118,000 | 43,000/111,000/112,000 | 41,000/43,000/43,000 |
| expiry | 25 | Phase C | 6,000/17,000/18,000 | 2,000/7,000/8,500 | 2,500/14,000/14,000 |
| steady30 | 10 | Phase B | 13,000/35,000/35,000 | 1,000/10,000/10,000 | 3,900/19,000/19,000 |
| steady30 | 10 | Phase C | 5,400/8,400/8,400 | 600/2,900/3,100 | 3,000/6,600/6,700 |
| steady30 | 25 | Phase B | 65,000/80,000/85,000 | 41,000/65,000/70,000 | 41,000/74,000/76,000 |
| steady30 | 25 | Phase C | 2,200/6,200/7,400 | 650/2,400/2,600 | 1,100/2,800/4,500 |

## Connections and resources

CPU columns are sampled average/maximum percentages. Backend memory is sampled
average/maximum working set in MiB.

| Scenario | Users | Phase | Connected max | Running max | Backend CPU | Backend memory | MySQL CPU | Redis CPU |
|---|---:|---|---:|---:|---:|---:|---:|---:|
| warm | 10 | Phase B | 9 | 3 | 42.1/58.3 | 177.5/188.1 | 13.66/33.79 | 1.55/3.18 |
| warm | 10 | Phase C | 11 | 3 | 45.6/63.9 | 179.5/187.5 | 15.24/33.66 | 1.22/5.05 |
| warm | 25 | Phase B | 20 | 3 | 81.8/96.2 | 230.5/256.6 | 11.24/28.80 | 1.51/2.93 |
| warm | 25 | Phase C | 26 | 3 | 74.4/101.2 | 214.0/237.6 | 17.41/34.85 | 1.56/3.07 |
| expiry | 10 | Phase B | 29 | 3 | 109.3/128.8 | 469.6/658.2 | 10.35/29.58 | 0.84/2.86 |
| expiry | 10 | Phase C | 13 | 4 | 68.7/102.5 | 219.3/254.0 | 17.44/48.08 | 1.38/3.86 |
| expiry | 25 | Phase B | 41 | 3 | 106.9/124.3 | 791.4/948.8 | 7.68/32.33 | 0.92/2.65 |
| expiry | 25 | Phase C | 23 | 3 | 86.7/100.6 | 265.7/307.9 | 15.51/49.29 | 1.18/2.28 |
| steady30 | 10 | Phase B | 23 | 3 | 78.2/132.5 | 278.6/486.3 | 8.37/24.93 | 0.86/2.10 |
| steady30 | 10 | Phase C | 11 | 3 | 32.0/76.5 | 180.0/185.6 | 9.28/20.79 | 0.79/1.69 |
| steady30 | 25 | Phase B | 41 | 2 | 97.5/134.6 | 760.0/1,076.6 | 5.16/26.02 | 0.84/4.22 |
| steady30 | 25 | Phase C | 15 | 4 | 26.9/100.0 | 224.0/268.0 | 9.51/29.93 | 0.73/1.60 |

At 25 users, expiry connected sessions fall from 41 to 23 and steady30 from
41 to 15. Backend average working set falls by 66.4% and 70.5% respectively.
Backend average CPU falls by 18.9% and 72.4% while useful throughput rises.
MySQL and Redis remain unsaturated; the higher Phase C MySQL average in expiry is
consistent with substantially more completed work, while `Threads_running` never
exceeds 4.

Phase B expiry and steady30 runtime logs contain SQLAlchemy QueuePool timeout
signatures. All six Phase C runtime logs contain zero QueuePool timeout signatures.
The only Phase C runtime traceback is one Windows asyncio accept `WinError 64` in
warm 25; it is not a database-pool or domain-reconstruction failure.

## Decision

The results directly support the Phase C mechanism: identical-key cache misses no
longer multiply total/process/OS domain reconstruction, connection demand, backend
CPU, or retained working set. The strongest gains appear exactly in expiry and
30-second reconciliation, while warm-cache results remain broadly unchanged.

There is no remaining blocker that warrants another OMMS core optimization phase.
Residual concerns are benchmark/release-validation concerns only: warm 25 remains
latency-heavy, and the Windows-local non-JSON/reset noise should be separated from
application failures if a production SLO is later established. Per the project
stop condition, core feature and performance development ends here.

## Raw evidence

Raw artifacts are intentionally ignored by Git and remain locally under:

- `benchmark-results/phase-c-final-warm-v2`
- `benchmark-results/phase-c-final-expiry`
- `benchmark-results/phase-c-final-steady30`

Environment JSON SHA-256:

- warm: `E048C424E23862E757071734A390EED6A61431B88E0C8A406EC8B0D911A5E9A2`
- expiry: `2D967668BD170830A746A465FC374DC6530305413144CA11C2069A3A28FDBAF9`
- steady30: `4AF0269F53B8A2CDD4973354CD6363FDFB7C85D68CC9E7AD908DB95B2C1073B2`
