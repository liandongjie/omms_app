# OMMS Monitor HTTP Benchmark

This harness records a reproducible HTTP baseline without changing production
business logic. Run each concurrency level as a separate Locust process so its
RPS, failure rate, and P50/P95/P99 are not mixed with another level.

## Workload model

One Locust user represents one visible dashboard:

- dashboard refresh, weight 12: concurrently requests `total`, OS page 1,
  process page 1, and log page 1;
- OS follows the frontend behavior and fetches every remaining page concurrently
  after reading `total/page_size` from page 1;
- process uses `page_no=1,page_size=100`;
- log uses `page_no=1,page_size=20`;
- level, `only_error`, and exact machine filters each have weight 1 and use the
  same log request structure as the frontend/backend contract;
- group list is requested once when a user starts.

The default wait is 4.5–5.5 seconds, matching the frontend's 5-second fallback
polling. Override it only when the benchmark record explains why:

```powershell
$env:OMMS_WAIT_MIN_SECONDS = "4.5"
$env:OMMS_WAIT_MAX_SECONDS = "5.5"
```

## Install

Install the normal project requirements first, then the isolated benchmark
dependency:

```powershell
.\.venv\Scripts\python.exe -m pip install -r benchmarks\monitor\requirements.txt
.\.venv\Scripts\python.exe -m locust -f benchmarks\monitor\locustfile.py --list
```

## Fixed data

Start the local infrastructure and generate one explicitly dated data set.
`--truncate` destroys the three local benchmark tables, so only use it against
the disposable Docker database:

```powershell
docker compose up -d
.\.venv\Scripts\python.exe -m scripts.generate_data `
  --states 6000 `
  --logs 100000 `
  --machines 2000 `
  --date 20260822 `
  --seed 42 `
  --truncate
```

The runner writes an environment JSON containing the Git SHA/dirty flag, MySQL
version, exact table counts, table/index sizes, every index column, initial
MySQL status, Redis version/config/hit counters, cache TTL, target URL, and
workload selectors. This snapshot, rather than the generator arguments alone,
is the authoritative record of a run.

Set selectors to values present in that fixed data set:

```powershell
$env:OMMS_BENCH_DATE = "20260822"
$env:OMMS_BENCH_MACHINE_TAG = "fut-col-002"
$env:OMMS_BENCH_LEVEL = "error"
```

## Cache scenarios

Never aggregate these scenarios.

### Warm cache

Start the backend with a TTL longer than the complete run. The runner deletes
only `omms:os:*`, `omms:process:*`, and `omms:log_stats:*`, then preloads the
real dashboard requests before every concurrency level.

```powershell
$env:OPS_CACHE_TTL_SECONDS = "900"
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8004
```

### Cache expiry

Restart the backend with the production TTL. The runner deletes the same OMMS
keys before every level but does not preload them. With the real 5-second user
cadence and a 3-second TTL, each refresh crosses an expiry boundary; the result
therefore measures the real miss/repopulation window rather than warm hits.

```powershell
$env:OPS_CACHE_TTL_SECONDS = "3"
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8004
```

Changing TTL requires restarting the backend. Do not run warm and expiry
against the same still-running backend process.

## Run the independent concurrency gradient

Export local Docker connection settings so the snapshot connects to the same
database as the backend:

```powershell
$env:DB_HOST = "127.0.0.1"
$env:DB_PORT = "3307"
$env:DB_NAME = "omms_app"
$env:DB_USER = "omms"
$env:DB_PASSWORD = "omms_dev"
$env:REDIS_URL = "redis://127.0.0.1:6380/0"
```

Find the backend PID if application CPU/memory is required:

```powershell
Get-Process python | Select-Object Id,ProcessName,CPU,WorkingSet64
```

Run one scenario after starting the backend with its matching TTL:

```powershell
.\benchmarks\monitor\run.ps1 `
  -CacheScenario warm `
  -Users 1,10,25,50 `
  -RunTime 2m `
  -SpawnRate 5 `
  -BackendPid 12345
```

Restart the backend with TTL 3, then run `-CacheScenario expiry` into the same
root. Output names include scenario and user count, so files cannot overwrite
or silently merge the two cache states.

## Outputs and interpretation

For every level Locust writes:

- `*-summary.json`: explicit RPS, P50/P95/P99, request/failure counts, and
  failure-rate percentage for that one scenario and concurrency level;
- `*-stats.csv`: request count, failure count/rate inputs, RPS, average and
  P50/P95/P99 response times;
- `*-stats_history.csv`: time-series RPS, failures, and latency percentiles;
- `*-failures.csv` and `*-exceptions.csv`;
- `*.html`: standalone report.

The companion `*-metrics.csv` samples every five seconds:

- MySQL `Threads_connected`, `Threads_running`, cumulative connections,
  questions, and slow queries;
- MySQL and Redis container CPU/memory from `docker stats`;
- optional backend process cumulative CPU seconds, working set, and private
  memory.

Use the timestamps to align Locust history with MySQL/application metrics. This
stage records baselines only; it does not define pass/fail thresholds or make
optimization claims.
