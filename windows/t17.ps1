<#
T17 on Windows: four commands only (windows/README.md).

  powershell -ExecutionPolicy Bypass -File windows\t17.ps1 probe   -Tier L1
  powershell -ExecutionPolicy Bypass -File windows\t17.ps1 dry-run
  powershell -ExecutionPolicy Bypass -File windows\t17.ps1 smoke   -Tier L1
  powershell -ExecutionPolicy Bypass -File windows\t17.ps1 full    -Tier L1

probe    verify the bundle, (re)render, prepare the working PBIPs, then check the model open in
         Power BI Desktop against the reference numbers. No model call.
dry-run  call counts and cost estimates for the smoke and the full run of DAX-L0/L1/L2. No model call.
smoke    pilot sample (24 questions) x 1 rep on one DAX cell; packs runs/<id> and runs-raw/<id>.
full     every question x 3 reps on one DAX cell (task card T18); packs the same way.

Messages are ASCII on purpose: Windows PowerShell 5.1 reads a BOM-less script as ANSI.
#>
param(
    [Parameter(Mandatory = $true, Position = 0)]
    [ValidateSet('probe', 'dry-run', 'smoke', 'full')]
    [string]$Command,
    [ValidateSet('L0', 'L1', 'L2')]
    [string]$Tier,
    [string]$RunId,
    [string]$SemanticTag = 'semantic-v1.5',
    [string]$EvalTag = 'eval-v1.2',
    [double]$Budget,
    [int]$Concurrency = 4
)

$ErrorActionPreference = 'Stop'
foreach ($v in 'SEMDEBT_MAIN_DIR', 'SEMDEBT_EVAL_DIR', 'SEMDEBT_DATA_DIR') {
    if (-not [Environment]::GetEnvironmentVariable($v)) { throw "Environment variable $v is not set (windows/README.md, step 2)." }
}
$env:PYTHONUTF8 = '1'
$env:PYTHONIOENCODING = 'utf-8'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
Set-Location $env:SEMDEBT_MAIN_DIR

function Invoke-Uv {
    & uv run --group windows @args
    if ($LASTEXITCODE -ne 0) { Write-Host "stopped: exit code $LASTEXITCODE"; exit $LASTEXITCODE }
}

function Need-Tier {
    if (-not $Tier) { throw "-Tier L0 | L1 | L2 is required for '$Command' (one model open in Desktop at a time)." }
}

function Pack-Run([string]$Id) {
    $stage = Join-Path $env:TEMP "t17-pack-$Id"
    if (Test-Path $stage) { Remove-Item -Recurse -Force $stage }
    New-Item -ItemType Directory -Force "$stage\runs", "$stage\runs-raw" | Out-Null
    $log = Join-Path $env:SEMDEBT_MAIN_DIR "runs\$Id"
    $raw = Join-Path $env:SEMDEBT_DATA_DIR "runs-raw\$Id"
    if (Test-Path $log) { Copy-Item -Recurse $log "$stage\runs\" }
    if (Test-Path $raw) { Copy-Item -Recurse $raw "$stage\runs-raw\" }
    $out = Join-Path $env:SEMDEBT_DATA_DIR 't17-return'
    New-Item -ItemType Directory -Force $out | Out-Null
    $zip = Join-Path $out "$Id.zip"
    Compress-Archive -Path "$stage\*" -DestinationPath $zip -Force
    Write-Host "packed: $zip  (bring it back to the Mac; windows/README.md, step 7)"
}

switch ($Command) {
    'probe' {
        Need-Tier
        Invoke-Uv python render/render_all.py
        Invoke-Uv python harness/dax_probe.py prepare
        $pbip = Join-Path $env:SEMDEBT_DATA_DIR "t17-pbip-work\retail-$Tier\retail-$Tier.pbip"
        Write-Host "model for this probe: $pbip  (open it in Power BI Desktop and Refresh; close every other Desktop window)"
        Invoke-Uv python harness/dax_probe.py probe --tier $Tier
    }
    'dry-run' {
        $cells = @('--cell', 'DAX-L0', '--cell', 'DAX-L1', '--cell', 'DAX-L2')
        Write-Host '--- smoke: pilot sample x 1 rep ---'
        Invoke-Uv python harness/run_direct.py --dry-run @cells --pilot --reps 1 --eval-tag $EvalTag --semantic-tag $SemanticTag
        Write-Host '--- full: all questions x 3 reps ---'
        Invoke-Uv python harness/run_direct.py --dry-run @cells --reps 3 --eval-tag $EvalTag --semantic-tag $SemanticTag
    }
    'smoke' {
        Need-Tier
        if (-not $RunId) { $RunId = (Get-Date -Format 'yyyyMMdd') + '-T17-dax-smoke-01' }
        if (-not $Budget) { $Budget = 5 }
        Invoke-Uv python render/render_all.py
        Invoke-Uv python harness/run_direct.py --cell "DAX-$Tier" --pilot --reps 1 --run-id $RunId `
            --eval-tag $EvalTag --semantic-tag $SemanticTag --budget $Budget --concurrency $Concurrency
        Pack-Run $RunId
    }
    'full' {
        Need-Tier
        if (-not $RunId) { $RunId = (Get-Date -Format 'yyyyMMdd') + '-T18-dax-full-01' }
        if (-not $Budget) { $Budget = 15 }
        Invoke-Uv python render/render_all.py
        Invoke-Uv python harness/run_direct.py --cell "DAX-$Tier" --reps 3 --run-id $RunId `
            --eval-tag $EvalTag --semantic-tag $SemanticTag --budget $Budget --concurrency $Concurrency
        Pack-Run $RunId
    }
}
