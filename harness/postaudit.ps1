# Post-audit smoke test: both engines, with the lastHit-prune and scav-guard fixes.
$ErrorActionPreference = 'Continue'
$user = Join-Path $env:APPDATA 'Warzone 2100 Project\Warzone 2100'
$root = Join-Path $env:TEMP 'wzpostaudit'
$wall = 700
New-Item -ItemType Directory -Force $root | Out-Null

$runs = @(
  @{ n = 'pa470_thales'; c = 'thales-houses.json'; v = '4.7.0'; exe = 'C:\Program Files\Warzone 2100\bin\warzone2100.exe' },
  @{ n = 'pa470_nexus';  c = 'long-nexus.json';    v = '4.7.0'; exe = 'C:\Program Files\Warzone 2100\bin\warzone2100.exe' },
  @{ n = 'pa455_thales'; c = 'thales-houses.json'; v = '4.5.5'; exe = 'C:\Program Files\Warzone 2100-4.5.5\bin\warzone2100.exe' },
  @{ n = 'pa455_mixed';  c = 'mixed.json';         v = '4.5.5'; exe = 'C:\Program Files\Warzone 2100-4.5.5\bin\warzone2100.exe' }
)

$procs = @()
foreach ($r in $runs) {
  if (-not (Test-Path $r.exe)) { "SKIP $($r.n): no binary"; continue }
  $h = Join-Path $root $r.n
  if (Test-Path $h) { Remove-Item -Recurse -Force $h }
  $al = Join-Path $h ('mods\' + $r.v + '\autoload')
  New-Item -ItemType Directory -Force $al | Out-Null
  Copy-Item (Join-Path $env:TEMP ('doctrine_pa_' + $r.v + '.wz')) (Join-Path $al 'doctrine.wz')
  # 4.7.0 also gets the scavenger archive, matching how it is actually played
  if ($r.v -eq '4.7.0') {
    $scav = Join-Path $user 'mods\4.7.0\autoload\uuscav2.wz'
    if (Test-Path $scav) { Copy-Item $scav $al }
  }
  Copy-Item (Join-Path $user 'tests') (Join-Path $h 'tests') -Recurse
  $out = Join-Path $root ($r.n + '.out.txt'); $err = Join-Path $root ($r.n + '.err.txt')
  $argv = @('--headless','--nosound','--autogame',('--configdir=' + $h),('--skirmish=' + $r.c))
  $p = Start-Process -FilePath $r.exe -ArgumentList $argv `
       -RedirectStandardOutput $out -RedirectStandardError $err -PassThru
  "started $($r.n) [$($r.v)] pid=$($p.Id) cfg=$($r.c) $(Get-Date -Format HH:mm:ss)"
  $procs += , @{ p = $p; r = $r }
}

$deadline = (Get-Date).AddSeconds($wall)
while ((Get-Date) -lt $deadline) {
  if (@($procs | Where-Object { -not $_.p.HasExited }).Count -eq 0) { break }
  Start-Sleep -Seconds 15
}
foreach ($x in $procs) {
  if (-not $x.p.HasExited) {
    Stop-Process -Id $x.p.Id -Force -ErrorAction SilentlyContinue
    "killed $($x.r.n) $(Get-Date -Format HH:mm:ss)"
  } else { "exited $($x.r.n) code=$($x.p.ExitCode) $(Get-Date -Format HH:mm:ss)" }
}
"POSTAUDIT DONE -- $root"
