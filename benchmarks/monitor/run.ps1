param(
    [Parameter(Mandatory = $true)]
    [ValidateSet("warm", "expiry")]
    [string]$CacheScenario,
    [int[]]$Users = @(1, 10, 25, 50),
    [string]$RunTime = "2m",
    [double]$SpawnRate = 5,
    [string]$HostUrl = "http://127.0.0.1:8004",
    [string]$OutputRoot = "benchmark-results/monitor",
    [int]$MetricsIntervalSeconds = 5,
    [int]$BackendPid = 0,
    [string]$Python = ".\.venv\Scripts\python.exe"
)

$ErrorActionPreference = "Stop"
$root = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$locustFile = Join-Path $PSScriptRoot "locustfile.py"
$prepareCache = Join-Path $PSScriptRoot "prepare_cache.py"
$captureEnvironment = Join-Path $PSScriptRoot "capture_environment.py"
$summarize = Join-Path $PSScriptRoot "summarize.py"
$collector = Join-Path $PSScriptRoot "collect_metrics.ps1"
$output = Join-Path $root $OutputRoot
New-Item -ItemType Directory -Force -Path $output | Out-Null

$cacheTtl = if ($env:OPS_CACHE_TTL_SECONDS) { [int]$env:OPS_CACHE_TTL_SECONDS } else { 3 }
if ($CacheScenario -eq "warm" -and $cacheTtl -lt 300) {
    throw "Warm scenario requires OPS_CACHE_TTL_SECONDS >= 300 and a restarted backend."
}
if ($CacheScenario -eq "expiry" -and $cacheTtl -ne 3) {
    throw "Expiry scenario requires OPS_CACHE_TTL_SECONDS=3 and a restarted backend."
}

& $Python -c "import locust" | Out-Null
if ($LASTEXITCODE -ne 0) {
    throw "Locust is unavailable; install benchmarks/monitor/requirements.txt first."
}

$env:OMMS_CACHE_SCENARIO = $CacheScenario
$userList = ($Users -join ",")
& $Python $captureEnvironment `
    --output (Join-Path $output "environment-$CacheScenario.json") `
    --host $HostUrl `
    --cache-scenario $CacheScenario `
    --users $userList
if ($LASTEXITCODE -ne 0) {
    throw "Environment snapshot failed."
}

foreach ($userCount in $Users) {
    $stage = Join-Path $output "$CacheScenario-users-$userCount"
    & $Python $prepareCache --mode $CacheScenario --host $HostUrl
    if ($LASTEXITCODE -ne 0) {
        throw "Cache preparation failed for $userCount users."
    }

    $metricsPath = "$stage-metrics.csv"
    $metricsJob = Start-Job -ScriptBlock {
        param($script, $path, $interval, $processId)
        & $script -OutputPath $path -IntervalSeconds $interval -BackendPid $processId
    } -ArgumentList $collector, $metricsPath, $MetricsIntervalSeconds, $BackendPid

    try {
        & $Python -m locust `
            -f $locustFile `
            --host $HostUrl `
            --headless `
            --users $userCount `
            --spawn-rate $SpawnRate `
            --run-time $RunTime `
            --csv $stage `
            --csv-full-history `
            --html "$stage.html"
        if ($LASTEXITCODE -ne 0) {
            throw "Locust failed for $userCount users."
        }
        & $Python $summarize `
            --stats "${stage}_stats.csv" `
            --output "${stage}-summary.json" `
            --scenario $CacheScenario `
            --users $userCount
        if ($LASTEXITCODE -ne 0) {
            throw "Locust summary failed for $userCount users."
        }
    } finally {
        Stop-Job $metricsJob -ErrorAction SilentlyContinue
        Receive-Job $metricsJob -ErrorAction SilentlyContinue | Out-Null
        Remove-Job $metricsJob -Force -ErrorAction SilentlyContinue
    }
}
