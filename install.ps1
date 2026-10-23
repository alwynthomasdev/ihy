# Install the ihy command (Windows PowerShell).
#
#   irm https://raw.githubusercontent.com/<owner>/ihy/main/install.ps1 | iex
#
# With a custom repo URL or ref (branch or tag such as v0.1.0):
#   & ([scriptblock]::Create((irm https://raw.githubusercontent.com/<owner>/ihy/main/install.ps1))) -Repo <url> -Ref v0.1.0
# or set $env:IHY_REPO / $env:IHY_REF before running the one-liner.
#
# Errors are thrown rather than calling `exit`, so a failure never closes the
# PowerShell window the one-liner was pasted into.
param(
    [string]$Repo = $(if ($env:IHY_REPO) { $env:IHY_REPO } else { "https://github.com/<owner>/ihy.git" }),
    [string]$Ref = $(if ($env:IHY_REF) { $env:IHY_REF } else { "" })
)

$ErrorActionPreference = "Stop"
$PythonVersion = "3.12"

function Say([string]$Message) { Write-Host "ihy install: $Message" }
function Fail([string]$Message) { throw "ihy install: ERROR: $Message" }

# 1. uv
if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    Say "uv not found, installing it (https://docs.astral.sh/uv/)..."
    powershell -NoProfile -ExecutionPolicy ByPass -Command "irm https://astral.sh/uv/install.ps1 | iex"
    if ($LASTEXITCODE -ne 0) { Fail "could not install uv" }
}

# 2. Make uv and installed tools visible in this session.
$LocalBin = Join-Path $HOME ".local\bin"
if (($env:Path -split ";") -notcontains $LocalBin) { $env:Path = "$LocalBin;$env:Path" }
if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    Fail "uv was installed but is not on PATH; open a new terminal and run this again"
}

# 3. Install ihy in its own environment, with a Python uv downloads itself.
#    Installing from git+ needs git; without git, fall back to GitHub's zip archive.
if (Get-Command git -ErrorAction SilentlyContinue) {
    $Spec = "git+$Repo"
    if ($Ref) { $Spec = "$Spec@$Ref" }
} elseif ($Repo -like "https://github.com/*") {
    $Base = $Repo -replace "\.git$", ""
    $Archive = if ($Ref) { $Ref } else { "refs/heads/main" }
    $Spec = "ihy-omr @ $Base/archive/$Archive.zip"
    Say "git not found, installing from $Base/archive/$Archive.zip"
} else {
    Fail "git is required to install from $Repo"
}

Say "installing $Spec with Python $PythonVersion..."
uv tool install --python $PythonVersion $Spec
if ($LASTEXITCODE -ne 0) { Fail "uv tool install failed (see messages above)" }

# 4. Make sure the tool folder stays on PATH in future shells.
uv tool update-shell *> $null

if (-not (Get-Command ihy -ErrorAction SilentlyContinue)) {
    Fail "ihy was installed but is not on PATH; open a new terminal and try again"
}
Say "done: $(ihy --version)"
Write-Host ""
Write-Host "Next step:"
Write-Host "  ihy --help              # see what ihy can do"
Write-Host "  ihy --download-models   # optional: fetch the recognition models now (~150 MB)"
