param(
    [Parameter(Mandatory = $true)][string]$ConvertedProject,
    [string]$Output,
    [string]$Ruby
)
$ErrorActionPreference = 'Stop'
if (-not $Output) { $Output = Join-Path $PSScriptRoot 'output\LunetileMMO-Windows' }
if (-not $Ruby) { $Ruby = Join-Path $PSScriptRoot '..\build\runtime-native\bin\Release\rgssxp-ruby.exe' }
if (Test-Path -LiteralPath $Output) { throw 'Output already exists. Choose a NEW folder; never overwrite player data.' }
& cargo test --locked --manifest-path "$PSScriptRoot\server\Cargo.toml"
if ($LASTEXITCODE -ne 0) { throw 'Server tests failed.' }
& cargo build --locked --release --target x86_64-pc-windows-msvc --manifest-path "$PSScriptRoot\server\Cargo.toml"
if ($LASTEXITCODE -ne 0) { throw 'Windows server build failed.' }
& python -X utf8 -B "$PSScriptRoot\tools\prepare_example.py" $ConvertedProject $Output --ruby $Ruby
if ($LASTEXITCODE -ne 0) { throw 'Example packaging failed.' }
Write-Host "Ready: $Output"
