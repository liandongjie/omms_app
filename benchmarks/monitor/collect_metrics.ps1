param(
    [Parameter(Mandatory = $true)]
    [string]$OutputPath,
    [int]$IntervalSeconds = 5,
    [int]$BackendPid = 0,
    [string]$MySqlContainer = "omms-mysql",
    [string]$RedisContainer = "omms-redis",
    [string]$MySqlUser = "omms",
    [string]$MySqlPassword = "omms_dev"
)

$ErrorActionPreference = "Stop"
$parent = Split-Path -Parent $OutputPath
if ($parent) {
    New-Item -ItemType Directory -Force -Path $parent | Out-Null
}

while ($true) {
    $mysqlStatus = @{}
    try {
        $mysqlRows = & docker exec -e "MYSQL_PWD=$MySqlPassword" $MySqlContainer mysql `
            --user=$MySqlUser --batch --skip-column-names `
            --execute="SHOW GLOBAL STATUS WHERE Variable_name IN ('Connections','Threads_connected','Threads_running','Questions','Slow_queries')"
        foreach ($line in $mysqlRows) {
            $parts = $line -split "`t", 2
            if ($parts.Count -eq 2) {
                $mysqlStatus[$parts[0]] = $parts[1]
            }
        }
    } catch {
        $mysqlStatus["error"] = $_.Exception.Message
    }

    $containerStats = @{}
    try {
        $rows = & docker stats --no-stream --format "{{json .}}" $MySqlContainer $RedisContainer
        foreach ($line in $rows) {
            $item = $line | ConvertFrom-Json
            $containerStats[$item.Name] = $item
        }
    } catch {
        $containerStats["error"] = $_.Exception.Message
    }

    $app = $null
    if ($BackendPid -gt 0) {
        $app = Get-Process -Id $BackendPid -ErrorAction SilentlyContinue
    }
    $mysql = $containerStats[$MySqlContainer]
    $redis = $containerStats[$RedisContainer]
    $record = [pscustomobject]@{
        timestamp_utc = [DateTime]::UtcNow.ToString("o")
        mysql_threads_connected = $mysqlStatus["Threads_connected"]
        mysql_threads_running = $mysqlStatus["Threads_running"]
        mysql_connections_total = $mysqlStatus["Connections"]
        mysql_questions_total = $mysqlStatus["Questions"]
        mysql_slow_queries_total = $mysqlStatus["Slow_queries"]
        mysql_cpu = $mysql.CPUPerc
        mysql_memory = $mysql.MemUsage
        redis_cpu = $redis.CPUPerc
        redis_memory = $redis.MemUsage
        app_cpu_seconds = if ($app) { [math]::Round($app.CPU, 3) } else { $null }
        app_working_set_mb = if ($app) { [math]::Round($app.WorkingSet64 / 1MB, 2) } else { $null }
        app_private_memory_mb = if ($app) { [math]::Round($app.PrivateMemorySize64 / 1MB, 2) } else { $null }
    }
    if (Test-Path -LiteralPath $OutputPath) {
        $record | Export-Csv -LiteralPath $OutputPath -NoTypeInformation -Append
    } else {
        $record | Export-Csv -LiteralPath $OutputPath -NoTypeInformation
    }
    Start-Sleep -Seconds $IntervalSeconds
}
