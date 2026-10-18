param([Parameter(Mandatory=$true)][string]$OutputRoot,[ValidateRange(30,600)][int]$Seconds=480)
$ErrorActionPreference='Stop'
$repoRoot=Split-Path $PSScriptRoot -Parent
$traceRoot=[IO.Path]::GetFullPath($OutputRoot)
$allowedRoot=[IO.Path]::GetFullPath((Join-Path $repoRoot 'build'))+[IO.Path]::DirectorySeparatorChar
if (-not $traceRoot.StartsWith($allowedRoot,[StringComparison]::OrdinalIgnoreCase)) { throw 'Trace output must be inside this repository build directory' }
$principal=New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) { throw 'Only this WPR recorder needs elevation; run the game controller normally' }
[IO.Directory]::CreateDirectory($traceRoot) | Out-Null
foreach ($name in @('recording.json','session-result.json','trace.etl','stop.requested')) {
    if (Test-Path -LiteralPath (Join-Path $traceRoot $name)) { throw "Refusing existing recorder output: $name" }
}
$profile=Join-Path $repoRoot 'tests/runtime_gpu_trace.wprp'
$profileHash=(Get-FileHash -LiteralPath $profile).Hash.ToLowerInvariant()
$traceInstance='RGSSXP_'+[Guid]::NewGuid().ToString('N')
$wpr=Join-Path $env:SystemRoot 'System32/wpr.exe'
$watch=[Diagnostics.Stopwatch]::StartNew()
$stopReason='deadline'
$startCode=$null;$stopCode=$null
# A private WPR instance prevents this recorder from stopping another user's trace.
& $wpr -start ($profile+'!RGSSXPGpuWait') -filemode -instancename $traceInstance 2>&1 | Set-Content -LiteralPath (Join-Path $traceRoot 'start.log') -Encoding utf8
$startCode=$LASTEXITCODE
if ($startCode -ne 0) { throw "WPR start failed: $startCode" }
try {
    $recorder=Get-Process -Id $PID
    $created=[DateTimeOffset]$recorder.StartTime.ToUniversalTime()
    $ready=@{recorder_pid=$PID;recorder_creation_unix=$created.ToUnixTimeMilliseconds()/1000.0;instance=$traceInstance;profile_sha256=$profileHash;start_exit_code=$startCode;started_utc=[DateTime]::UtcNow.ToString('o')} | ConvertTo-Json
    [IO.File]::WriteAllText((Join-Path $traceRoot 'recording.json.tmp'),$ready,(New-Object Text.UTF8Encoding($false)))
    [IO.File]::Move((Join-Path $traceRoot 'recording.json.tmp'),(Join-Path $traceRoot 'recording.json'))
    while ($watch.Elapsed.TotalSeconds -lt $Seconds) {
        if (Test-Path -LiteralPath (Join-Path $traceRoot 'stop.requested')) { $stopReason='controller';break }
        Start-Sleep -Milliseconds 500
    }
} finally {
    & $wpr -stop (Join-Path $traceRoot 'trace.etl') -skipPdbGen -instancename $traceInstance 2>&1 |
        Set-Content -LiteralPath (Join-Path $traceRoot 'stop.log') -Encoding utf8
    $stopCode=$LASTEXITCODE
    @{instance=$traceInstance;start_exit_code=$startCode;stop_exit_code=$stopCode;stop_reason=$stopReason;elapsed_seconds=$watch.Elapsed.TotalSeconds;profile_sha256=$profileHash;scope='Private WPR instance only; game must remain unprivileged; Win32k display events filtered to 201/301, no input or stack events'} |
        ConvertTo-Json | Set-Content -LiteralPath (Join-Path $traceRoot 'session-result.json') -Encoding utf8
}
if ($stopCode -ne 0) { throw "WPR stop failed: $stopCode" }
