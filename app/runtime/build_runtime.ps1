# Build the relocatable Python runtime that ships inside the Musicoma installer.
#
#   powershell -ExecutionPolicy Bypass -File app\runtime\build_runtime.ps1 [-SkipTest]
#
# Result (git-ignored, picked up by electron-builder extraResources):
#   app\runtime\dist\python\   standalone CPython 3.13 (python-build-standalone via uv) + CORE deps
#   app\runtime\dist\uv.exe    uv, used on the user's PC by `setup_assets --ai`
#
# The runtime is NOT a venv: it is a full standalone interpreter with packages installed
# straight into its own Lib\site-packages, so it keeps working after being copied anywhere.
# AI modules (torch etc.) are NOT included; they are installed later by setup_assets --ai.
param(
    [string]$PythonVersion = "3.13.12",
    [switch]$SkipTest
)
$ErrorActionPreference = "Stop"

$Here   = Split-Path -Parent $MyInvocation.MyCommand.Path      # app\runtime
$Repo   = Resolve-Path (Join-Path $Here "..\..")                # repo root
$Dist   = Join-Path $Here "dist"
$PyDir  = Join-Path $Dist "python"
$Cache  = Join-Path $Here ".cache"
$PyStore = Join-Path $Cache "python"                            # private uv python store

function Find-Uv {
    $c = Get-Command uv -ErrorAction SilentlyContinue
    if ($c) { return $c.Source }
    $w = Get-ChildItem "$env:LOCALAPPDATA\Microsoft\WinGet\Packages" -Filter uv.exe -Recurse -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($w) { return $w.FullName }
    throw "uv.exe not found (winget install astral-sh.uv)"
}
$Uv = Find-Uv
Write-Host "uv: $Uv  ($(& $Uv --version))"

# 1) standalone CPython into a private store (does not touch the user's uv pythons)
$env:UV_PYTHON_INSTALL_DIR = $PyStore
& $Uv python install $PythonVersion --no-bin
if ($LASTEXITCODE) { throw "uv python install failed" }
$src = Get-ChildItem $PyStore -Directory | Where-Object { $_.Name -like "cpython-$PythonVersion-windows-x86_64-*" } | Select-Object -First 1
if (-not $src) { throw "installed python not found under $PyStore" }

# 2) fresh copy -> dist\python
if (Test-Path $PyDir) { Remove-Item $PyDir -Recurse -Force }
New-Item -ItemType Directory -Force $Dist | Out-Null
Copy-Item $src.FullName $PyDir -Recurse
Get-ChildItem $PyDir -Recurse -Filter EXTERNALLY-MANAGED -ErrorAction SilentlyContinue | Remove-Item -Force
$Py = Join-Path $PyDir "python.exe"

# 3) core deps, copied (not hard-linked) into the runtime's own site-packages
& $Uv pip install --python $Py --break-system-packages --link-mode copy --only-binary ":all:" `
    -r (Join-Path $Here "requirements-core.txt")
if ($LASTEXITCODE) { throw "uv pip install (core) failed" }

# 4) trim things the app never uses (keeps tkinter out; matplotlib runs on Agg)
foreach ($p in @("Lib\test", "Lib\idlelib", "Lib\tkinter", "Lib\turtledemo", "tcl", "DLLs\_tkinter.pyd", "DLLs\tcl86t.dll", "DLLs\tk86t.dll")) {
    $t = Join-Path $PyDir $p
    if (Test-Path $t) { Remove-Item $t -Recurse -Force }
}
Get-ChildItem $PyDir -Recurse -Directory -Filter __pycache__ | Remove-Item -Recurse -Force
# console-script launchers hard-code this build path; the app never calls them
Get-ChildItem (Join-Path $PyDir "Scripts") -Filter *.exe -ErrorAction SilentlyContinue | Remove-Item -Force

# 5) ship uv.exe beside the runtime (setup_assets --ai uses it on the user's PC)
Copy-Item $Uv (Join-Path $Dist "uv.exe") -Force

# 6) refresh the AI glue scripts snapshot from third_party (they are git-ignored there)
$glue = @{
    "third_party\soulx-singer\musicoma_bridge.py" = "ai\soulx-singer\musicoma_bridge.py";
    "third_party\soulx-singer\musicoma_prompt.py" = "ai\soulx-singer\musicoma_prompt.py";
    "third_party\soulx-singer\musicoma_svc.py"    = "ai\soulx-singer\musicoma_svc.py";
    "third_party\voxcpm\musicoma_voxcpm.py"       = "ai\voxcpm\musicoma_voxcpm.py";
}
foreach ($k in $glue.Keys) {
    $s = Join-Path $Repo $k
    if (Test-Path $s) { Copy-Item $s (Join-Path $Here $glue[$k]) -Force }
}

# 7) smoke test from a copy in a different folder (proves relocatability)
if (-not $SkipTest) {
    $tmp = Join-Path ([IO.Path]::GetTempPath()) ("musicoma-rt-" + [guid]::NewGuid().ToString("N").Substring(0, 8))
    Copy-Item $PyDir $tmp -Recurse
    try {
        & (Join-Path $tmp "python.exe") -I -c "import sys,numpy,scipy,librosa,numba,soundfile,pyloudnorm,pyworld,matplotlib,mcp,websockets,httpx,yaml; matplotlib.use('Agg'); import matplotlib.pyplot; print('runtime ok', sys.version.split()[0], sys.prefix)"
        if ($LASTEXITCODE) { throw "relocated runtime import test failed" }
    } finally {
        Remove-Item $tmp -Recurse -Force -ErrorAction SilentlyContinue
    }
}

$size = (Get-ChildItem $PyDir -Recurse -File | Measure-Object Length -Sum).Sum
Write-Host ("runtime: {0}  ({1:N0} MB, {2} files)" -f $PyDir, ($size / 1MB), (Get-ChildItem $PyDir -Recurse -File).Count)
