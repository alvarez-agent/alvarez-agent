# Smoke tests for install.ps1 local-checkout-aware install.
#
# Run from a PowerShell prompt (Windows; needs git on PATH):
#
#   powershell -NoProfile -ExecutionPolicy Bypass -File scripts/tests/test-install-ps1-local-source.ps1
#
# Builds a minimal stand-in for a user checkout (git repo + alvarez-agent
# pyproject.toml + a copy of install.ps1) in %TEMP%, then drives ONLY the
# "repository" stage against it.  That stage needs nothing but git -- no
# winget, no pip, no PATH writes -- so this is safe to run on a dev box.
#
# Covers, end to end:
#   * a fresh install clones from the local checkout (not GitHub),
#   * the installed clone's origin is re-pointed at the checkout's remote,
#   * without -Branch the checkout's current branch is installed,
#   * a checkout with no origin remote keeps the local path (with a warning),
#   * -Manifest output from inside a checkout still parses as JSON.

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent (Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path))
$installScript = Join-Path $repoRoot "scripts\install.ps1"

if (-not (Test-Path $installScript)) {
    throw "Could not locate install.ps1 at $installScript"
}
if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    throw "These tests need git on PATH"
}

$failures = 0
function Assert-Equal {
    param([Parameter(Mandatory=$true)] $Expected,
          [Parameter(Mandatory=$true)] $Actual,
          [Parameter(Mandatory=$true)] [string]$Label)
    if ($Expected -ne $Actual) {
        Write-Host "FAIL: $Label" -ForegroundColor Red
        Write-Host "  expected: $Expected"
        Write-Host "  actual:   $Actual"
        $script:failures++
    } else {
        Write-Host "OK: $Label" -ForegroundColor Green
    }
}
function Assert-True {
    param([Parameter(Mandatory=$true)] $Condition,
          [Parameter(Mandatory=$true)] [string]$Label)
    if (-not $Condition) {
        Write-Host "FAIL: $Label" -ForegroundColor Red
        $script:failures++
    } else {
        Write-Host "OK: $Label" -ForegroundColor Green
    }
}

function Invoke-Git {
    param([string]$Dir, [string[]]$GitArgs)
    & git -C $Dir -c user.email=t@t -c user.name=t @GitArgs 2>&1 | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "git $($GitArgs -join ' ') failed in $Dir" }
}

# A minimal stand-in for the repo checkout a user just cloned.
function New-SourceCheckout {
    param([string]$Root, [string]$Origin)
    $src = Join-Path $Root "checkout"
    New-Item -ItemType Directory -Force -Path (Join-Path $src "scripts") | Out-Null
    Set-Content -Path (Join-Path $src "pyproject.toml") -Value "[project]`nname = `"alvarez-agent`"`nversion = `"0.0.1`"" -Encoding ascii
    Copy-Item $installScript (Join-Path $src "scripts\install.ps1")
    Invoke-Git $src @("init", "-b", "main")
    Invoke-Git $src @("add", "-A")
    Invoke-Git $src @("commit", "-m", "init")
    if ($Origin) { Invoke-Git $src @("remote", "add", "origin", $Origin) }
    return $src
}

function Get-HeadSha { param([string]$Dir) (& git -C $Dir rev-parse HEAD 2>$null).Trim() }
function Get-OriginUrl { param([string]$Dir) (& git -C $Dir remote get-url origin 2>$null).Trim() }

$testRoot = Join-Path $env:TEMP ("alvarez-ps1-local-source-" + (Get-Date -Format "yyyyMMdd-HHmmss"))
New-Item -ItemType Directory -Force -Path $testRoot | Out-Null
$prevAlvarezHome = $env:ALVAREZ_HOME

try {
    # ---------------------------------------------------------------------
    # Test: fresh install clones from the local checkout, follows its branch,
    #       and re-points origin at the checkout's remote
    # ---------------------------------------------------------------------
    Write-Host ""
    Write-Host "-- local-source install (with origin remote) --"
    $fakeOrigin = "https://github.com/alvarez-agent/alvarez-agent.git"
    $src = New-SourceCheckout -Root (Join-Path $testRoot "a") -Origin $fakeOrigin
    Invoke-Git $src @("checkout", "-b", "feature/fresh-install")
    Set-Content -Path (Join-Path $src "extra.txt") -Value "x" -Encoding ascii
    Invoke-Git $src @("add", "-A")
    Invoke-Git $src @("commit", "-m", "feature commit")

    $env:ALVAREZ_HOME = Join-Path $testRoot "a\home"
    $installDir = Join-Path $env:ALVAREZ_HOME "alvarez-agent"
    & powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $src "scripts\install.ps1") -Stage repository -NonInteractive
    Assert-Equal -Expected 0 -Actual $LASTEXITCODE -Label "repository stage exits 0"
    Assert-True (Test-Path (Join-Path $installDir ".git")) -Label "managed install dir is a git repo"
    Assert-Equal -Expected (Get-HeadSha $src) -Actual (Get-HeadSha $installDir) -Label "installed HEAD matches checkout HEAD"
    Assert-True ((Test-Path (Join-Path $installDir "extra.txt"))) -Label "checkout branch content was installed"
    Assert-Equal -Expected $fakeOrigin -Actual (Get-OriginUrl $installDir) -Label "origin re-pointed at the checkout's remote"

    # ---------------------------------------------------------------------
    # Test: checkout without an origin remote keeps the local path as origin
    # ---------------------------------------------------------------------
    Write-Host ""
    Write-Host "-- local-source install (no origin remote) --"
    $src2 = New-SourceCheckout -Root (Join-Path $testRoot "b") -Origin ""

    $env:ALVAREZ_HOME = Join-Path $testRoot "b\home"
    $installDir2 = Join-Path $env:ALVAREZ_HOME "alvarez-agent"
    & powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $src2 "scripts\install.ps1") -Stage repository -NonInteractive
    Assert-Equal -Expected 0 -Actual $LASTEXITCODE -Label "repository stage exits 0 without a source remote"
    # Find-LocalSource gets the checkout path from `git rev-parse --show-toplevel`,
    # which uses forward slashes on Windows -- normalize before comparing.
    Assert-Equal -Expected ($src2 -replace '\\', '/') -Actual ((Get-OriginUrl $installDir2) -replace '\\', '/') `
        -Label "origin falls back to the local checkout path"

    # ---------------------------------------------------------------------
    # Test: -Manifest from inside a checkout still emits clean JSON
    # ---------------------------------------------------------------------
    Write-Host ""
    Write-Host "-- -Manifest stays clean inside a checkout --"
    $manifestJson = & powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $src "scripts\install.ps1") -Manifest
    Assert-Equal -Expected 0 -Actual $LASTEXITCODE -Label "-Manifest exits 0"
    try {
        $manifest = $manifestJson | ConvertFrom-Json
        Assert-True ($manifest.stages.Count -gt 0) -Label "-Manifest output parses as JSON"
    } catch {
        Assert-True $false -Label "-Manifest output parses as JSON (parse error: $_)"
    }
} finally {
    $env:ALVAREZ_HOME = $prevAlvarezHome
    Remove-Item -Recurse -Force $testRoot -ErrorAction SilentlyContinue
}

# -----------------------------------------------------------------------------
# Summary
# -----------------------------------------------------------------------------
Write-Host ""
if ($failures -gt 0) {
    Write-Host "FAILED: $failures assertion(s) failed" -ForegroundColor Red
    exit 1
} else {
    Write-Host "All smoke tests passed." -ForegroundColor Green
    exit 0
}
