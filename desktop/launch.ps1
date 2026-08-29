# Native window launcher (pywebview). Fallback only.
$ErrorActionPreference = "Stop"
$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $Root

$pyw = $null
$cmd = Get-Command pythonw -ErrorAction SilentlyContinue
if ($cmd) { $pyw = $cmd.Source }
if (-not $pyw) {
    $py = Get-Command python -ErrorAction SilentlyContinue
    if ($py) {
        $cand = Join-Path (Split-Path $py.Source) "pythonw.exe"
        if (Test-Path $cand) { $pyw = $cand }
    }
}
if (-not $pyw) { throw "找不到 pythonw。请先安装 Python 并加入 PATH。" }

Start-Process -FilePath $pyw -ArgumentList "`"$PSScriptRoot\app.py`"" -WorkingDirectory $Root
