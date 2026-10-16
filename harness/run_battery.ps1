# Run several headless Warzone 2100 games in parallel, each in its own throwaway
# config directory so nothing touches your real profile.
#
#   powershell -ExecutionPolicy Bypass -File harness\run_battery.ps1
#
# Edit $runs to choose which test configs to run, and $wall for the wall-clock
# limit in seconds. Results land in $env:TEMP\wzbattery\<name>.{out,err}.txt --
# note that debug() output goes to the .err file.

$ErrorActionPreference = 'Continue'

# --- adjust these ---------------------------------------------------------
$exe  = $env:WZ_EXE
if (-not $exe) { $exe = 'C:\Program Files\Warzone 2100\bin\warzone2100.exe' }
$wall = 900          # seconds per batch before surviving games are killed
$runs = @(
  @{ n = 'nexus';    c = 'long-nexus.json' },
  @{ n = 'semperfi'; c = 'long-semperfi.json' },
  @{ n = 'thales';   c = 'thales-houses.json' }
)
# --------------------------------------------------------------------------

$user = Join-Path $env:APPDATA 'Warzone 2100 Project\Warzone 2100'
$root = Join-Path $env:TEMP 'wzbattery'
$mod  = Join-Path $user 'mods\4.7.0\autoload'

if (-not (Test-Path $exe))  { Write-Error "game not found: $exe (set WZ_EXE)"; exit 1 }
if (-not (Test-Path $mod))  { Write-Error "no autoload folder: $mod -- build the mod first"; exit 1 }
New-Item -ItemType Directory -Force $root | Out-Null

$procs = @()
foreach ($r in $runs) {
  $h = Join-Path $root $r.n
  if (Test-Path $h) { Remove-Item -Recurse -Force $h }
  $al = Join-Path $h 'mods\4.7.0\autoload'
  New-Item -ItemType Directory -Force $al | Out-Null

  # every .wz currently in autoload, so the run matches what you play
  Get-ChildItem $mod -Filter *.wz | ForEach-Object { Copy-Item $_.FullName $al }
  Copy-Item (Join-Path $user 'tests') (Join-Path $h 'tests') -Recurse

  $out = Join-Path $root ($r.n + '.out.txt')
  $err = Join-Path $root ($r.n + '.err.txt')
  # --configdir is NOT optional: without it, --nosound writes sound=0 into your
  # real config on exit and silently kills your game audio.
  $argv = @('--headless', '--nosound', '--autogame',
            ('--configdir=' + $h), ('--skirmish=' + $r.c))
  $p = Start-Process -FilePath $exe -ArgumentList $argv `
                     -RedirectStandardOutput $out -RedirectStandardError $err -PassThru
  "started $($r.n) pid=$($p.Id) cfg=$($r.c) $(Get-Date -Format HH:mm:ss)"
  $procs += , @{ p = $p; r = $r }
}

$deadline = (Get-Date).AddSeconds($wall)
while ((Get-Date) -lt $deadline) {
  if (@($procs | Where-Object { -not $_.p.HasExited }).Count -eq 0) { break }
  Start-Sleep -Seconds 15
}

foreach ($x in $procs) {
  if (-not $x.p.HasExited) {
    # by PID -- taskkill /IM would kill every Warzone instance including yours
    Stop-Process -Id $x.p.Id -Force -ErrorAction SilentlyContinue
    "killed $($x.r.n) $(Get-Date -Format HH:mm:ss)"
  } else {
    "exited $($x.r.n) code=$($x.p.ExitCode) $(Get-Date -Format HH:mm:ss)"
  }
}
"BATTERY DONE -- results in $root"
