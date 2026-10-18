param([int]$TargetPid,[string]$GameExe,[string]$OutputRoot)
$expectedExe=[IO.Path]::GetFullPath($GameExe)
$startedProcess=Get-Process -Id $TargetPid -ErrorAction Stop
if (-not $startedProcess.Path.Equals($expectedExe,[StringComparison]::OrdinalIgnoreCase)) { throw 'Wrong game process path' }
$creation=$startedProcess.StartTime.ToUniversalTime().Ticks
$file=Join-Path $OutputRoot 'gpu-memory-snapshots.jsonl'
$identity=Join-Path $OutputRoot 'gpu-memory-identity.json'
if ((Test-Path -LiteralPath $file) -or (Test-Path -LiteralPath $identity)) { throw 'Sampler output already exists' }
@{pid=$TargetPid;exe=$expectedExe;creation_ticks=$creation;source_sha256=(Get-FileHash -LiteralPath $PSCommandPath).Hash.ToLowerInvariant()} | ConvertTo-Json | Set-Content -LiteralPath $identity -Encoding utf8
$watch=[Diagnostics.Stopwatch]::StartNew()
while ($watch.Elapsed.TotalSeconds -lt 3900) {
  $gameProcess=Get-Process -Id $TargetPid -ErrorAction SilentlyContinue
  if (-not $gameProcess -or $gameProcess.StartTime.ToUniversalTime().Ticks -ne $creation -or -not $gameProcess.Path.Equals($expectedExe,[StringComparison]::OrdinalIgnoreCase)) { break }
  $active=$null
  try {
    $progressText=Get-Content -LiteralPath (Join-Path $OutputRoot 'endurance-progress.txt') -Raw -ErrorAction Stop
    if ($progressText -match '(?m)^active_seconds=([^\r\n]+)') { $active=[Double]::Parse($Matches[1],[Globalization.CultureInfo]::InvariantCulture) }
  } catch { $active=$null }
  $sample=@{pid=$TargetPid;creation_ticks=$creation;utc=[DateTime]::UtcNow.ToString('o');active_seconds=$active;source='Win32_PerfFormattedData_GPUPerformanceCounters_GPUProcessMemory';available=$false;rows=@();scope='Owned PID/creation-time bound GPU memory counters; not GPU frame timing or complete allocation leak proof'}
  try {
    $gpuRows=@(Get-CimInstance -ClassName Win32_PerfFormattedData_GPUPerformanceCounters_GPUProcessMemory -Filter "Name LIKE 'pid_${TargetPid}_%'" -ErrorAction Stop | Where-Object { $_.Name -match "^pid_${TargetPid}_" } | Select-Object Name,DedicatedUsage,SharedUsage,TotalCommitted)
    $sample.rows=$gpuRows;$sample.available=$gpuRows.Count -gt 0
  } catch { $sample.reason=$_.Exception.Message }
  $after=Get-Process -Id $TargetPid -ErrorAction SilentlyContinue
  if (-not $after -or $after.StartTime.ToUniversalTime().Ticks -ne $creation -or -not $after.Path.Equals($expectedExe,[StringComparison]::OrdinalIgnoreCase)) { break }
  $sample | ConvertTo-Json -Depth 5 -Compress | Add-Content -LiteralPath $file -Encoding utf8
  Write-Output "Owned GPU sample active=$active available=$($sample.available)"
  Start-Sleep -Seconds 30
}
Write-Output 'Owned GPU memory sampler stopped'
