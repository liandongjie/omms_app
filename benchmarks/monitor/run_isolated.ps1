param(
    [Parameter(Mandatory = $true)]
    [ValidateSet('warm', 'expiry')]
    [string]$CacheScenario,
    [Parameter(Mandatory = $true)]
    [string]$OutputRoot,
    [double]$WaitMinSeconds = 4.5,
    [double]$WaitMaxSeconds = 5.5,
    [int[]]$Users = @(1, 10, 25),
    [string]$RunTime = '2m',
    [double]$SpawnRate = 5,
    [string]$StagePrefix = $CacheScenario,
    [string]$HostUrl = 'http://127.0.0.1:8004',
    [string]$Python = '.\.venv\Scripts\python.exe',
    [string]$ExtraPythonPath = ''
)

$ErrorActionPreference = 'Stop'
$PSNativeCommandUseErrorActionPreference = $true
$root = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$pythonPath = (Resolve-Path (Join-Path $root $Python)).Path
$output = Join-Path $root $OutputRoot
$runtimeDir = Join-Path $output 'runtime'
New-Item -ItemType Directory -Force -Path $output, $runtimeDir | Out-Null

# 固定本地 benchmark 基础设施，避免误读开发机上的远端 .env 配置。
$env:ENVIRONMENT = 'development'
$env:DB_HOST = '127.0.0.1'
$env:DB_PORT = '3307'
$env:DB_NAME = 'omms_app'
$env:DB_USER = 'omms'
$env:DB_PASSWORD = 'omms_dev'
$env:REDIS_URL = 'redis://127.0.0.1:6380/0'
$env:RABBITMQ_URL = 'amqp://omms:omms_dev@127.0.0.1:5672/%2F'
$env:OPS_CACHE_TTL_SECONDS = if ($CacheScenario -eq 'warm') { '300' } else { '3' }
$env:OMMS_WAIT_MIN_SECONDS = [string]$WaitMinSeconds
$env:OMMS_WAIT_MAX_SECONDS = [string]$WaitMaxSeconds
$env:OMMS_CACHE_SCENARIO = $CacheScenario
$env:PYTHONPATH = if ($ExtraPythonPath) { "$root;$ExtraPythonPath" } else { $root }

$basic = [Convert]::ToBase64String([Text.Encoding]::ASCII.GetBytes('omms:omms_dev'))
$rabbitHeaders = @{ Authorization = "Basic $basic" }
$queueUrl = 'http://127.0.0.1:15672/api/queues/%2F/omms.ops.data'

function Wait-ConsumerCount([int]$Expected) {
    $deadline = (Get-Date).AddSeconds(30)
    do {
        Start-Sleep -Seconds 1
        $queue = Invoke-RestMethod $queueUrl -Headers $rabbitHeaders
    } until ($queue.consumers -eq $Expected -or (Get-Date) -gt $deadline)
    if ($queue.consumers -ne $Expected) {
        throw "Expected RabbitMQ consumers=$Expected, got $($queue.consumers)."
    }
}

function Start-BenchmarkBackend([string]$Label) {
    $existing = Get-CimInstance Win32_Process | Where-Object {
        $_.CommandLine -match '-m uvicorn app\.main:app --host 0\.0\.0\.0 --port 8004'
    }
    if ($existing) {
        throw "Pre-existing benchmark backend before $Label."
    }
    Wait-ConsumerCount 0

    $launcher = Start-Process -FilePath $pythonPath `
        -ArgumentList '-m', 'uvicorn', 'app.main:app', '--host', '0.0.0.0', '--port', '8004' `
        -WorkingDirectory $root -WindowStyle Hidden -PassThru `
        -RedirectStandardOutput (Join-Path $runtimeDir "$Label.stdout.log") `
        -RedirectStandardError (Join-Path $runtimeDir "$Label.stderr.log")
    $deadline = (Get-Date).AddSeconds(30)
    do {
        Start-Sleep -Milliseconds 500
        try { $health = Invoke-RestMethod "$HostUrl/health" -TimeoutSec 2 } catch { $health = $null }
    } until ($health -or (Get-Date) -gt $deadline)
    if (-not $health) {
        throw "Backend failed before $Label."
    }

    $line = netstat -ano | Select-String '0.0.0.0:8004\s+0.0.0.0:0\s+LISTENING'
    $workerId = [int](($line -split '\s+')[-1])
    $worker = Get-CimInstance Win32_Process -Filter "ProcessId=$workerId"
    if ($worker.ParentProcessId -ne $launcher.Id) {
        throw "Launcher/worker mismatch before $Label."
    }
    Wait-ConsumerCount 1
    return @{ Launcher = $launcher.Id; Worker = $workerId }
}

function Stop-BenchmarkBackend($Processes) {
    Stop-Process -Id $Processes.Launcher -Force -ErrorAction SilentlyContinue
    Stop-Process -Id $Processes.Worker -Force -ErrorAction SilentlyContinue
    Wait-ConsumerCount 0
}

$bootstrap = Start-BenchmarkBackend 'environment'
try {
    & $pythonPath (Join-Path $PSScriptRoot 'capture_environment.py') `
        --output (Join-Path $output "environment-$CacheScenario.json") `
        --host $HostUrl --cache-scenario $CacheScenario --users ($Users -join ',')
} finally {
    Stop-BenchmarkBackend $bootstrap
}

foreach ($userCount in $Users) {
    $label = "$StagePrefix-users-$userCount"
    $backend = Start-BenchmarkBackend $label
    try {
        & $pythonPath (Join-Path $PSScriptRoot 'prepare_cache.py') `
            --mode $CacheScenario --host $HostUrl
        $stage = Join-Path $output $label
        $metrics = Start-Job -ScriptBlock {
            param($Script, $Path, $WorkerId)
            & $Script -OutputPath $Path -IntervalSeconds 5 -BackendPid $WorkerId
        } -ArgumentList (Join-Path $PSScriptRoot 'collect_metrics.ps1'), "$stage-metrics.csv", $backend.Worker
        try {
            & $pythonPath -m locust -f (Join-Path $PSScriptRoot 'locustfile.py') `
                --host $HostUrl --headless --users $userCount --spawn-rate $SpawnRate `
                --run-time $RunTime --csv $stage --csv-full-history --html "$stage.html" `
                --only-summary --loglevel ERROR --exit-code-on-error 0
            & $pythonPath (Join-Path $PSScriptRoot 'summarize.py') `
                --stats "${stage}_stats.csv" --output "$stage-summary.json" `
                --scenario $CacheScenario --users $userCount
        } finally {
            Stop-Job $metrics -ErrorAction SilentlyContinue
            Receive-Job $metrics -ErrorAction SilentlyContinue | Out-Null
            Remove-Job $metrics -Force -ErrorAction SilentlyContinue
        }
    } finally {
        Stop-BenchmarkBackend $backend
    }
}
