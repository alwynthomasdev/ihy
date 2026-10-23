# Install the ihy command (Windows PowerShell).
#
#   irm https://raw.githubusercontent.com/alwynthomasdev/ihy/main/install.ps1 | iex
#
# With a custom repo URL or ref (branch or tag such as v0.1.0):
#   & ([scriptblock]::Create((irm https://raw.githubusercontent.com/alwynthomasdev/ihy/main/install.ps1))) -Repo <url> -Ref v0.1.0
# or set $env:IHY_REPO / $env:IHY_REF before running the one-liner.
#
# Errors are thrown rather than calling `exit`, so a failure never closes the
# PowerShell window the one-liner was pasted into.
param(
    [string]$Repo = $(if ($env:IHY_REPO) { $env:IHY_REPO } else { "https://github.com/alwynthomasdev/ihy.git" }),
    [string]$Ref = $(if ($env:IHY_REF) { $env:IHY_REF } else { "" })
)

$ErrorActionPreference = "Stop"
$PythonVersion = "3.12"

function Say([string]$Message) { Write-Host "ihy install: $Message" }
function Fail([string]$Message) { throw "ihy install: ERROR: $Message" }

# Windows PowerShell 5.1 turns any stderr output from a native program (uv
# prints progress there) into an error when ErrorActionPreference is Stop.
# Run native commands with Continue and judge them by their exit code.
function Invoke-Native([scriptblock]$Command) {
    $saved = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try { & $Command } finally { $ErrorActionPreference = $saved }
}

# 1. uv
if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    Say "uv not found, installing it (https://docs.astral.sh/uv/)..."
    Invoke-Native { powershell -NoProfile -ExecutionPolicy ByPass -Command "irm https://astral.sh/uv/install.ps1 | iex" }
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
Invoke-Native { uv tool install --python $PythonVersion $Spec }
if ($LASTEXITCODE -ne 0) { Fail "uv tool install failed (see messages above)" }

# 4. Make sure the tool folder stays on PATH in future shells.
Invoke-Native { uv tool update-shell 2>&1 | Out-Null }

if (-not (Get-Command ihy.exe -ErrorAction SilentlyContinue)) {
    Fail "ihy was installed but is not on PATH; open a new terminal and try again"
}
$Installed = Invoke-Native { ihy.exe --version 2>&1 }
if ($LASTEXITCODE -ne 0) { Fail "ihy was installed but does not run: $Installed" }
Say "done: $Installed"
Write-Host ""
Write-Host "Next step (open a new terminal first):"
Write-Host "  ihy-omr --help              # see what ihy can do"
Write-Host "  ihy-omr --download-models   # optional: fetch the recognition models now (~150 MB)"
Write-Host ""
Write-Host "In PowerShell, plain 'ihy' is a built-in alias for Invoke-History, so use"
Write-Host "'ihy-omr' or 'ihy.exe' there. In Command Prompt, 'ihy' works as normal."
