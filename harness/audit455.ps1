# First-ever 4.5.5 playtest: the shipped 4.5.5 archive has never been run in a game.
$ErrorActionPreference = 'Continue'
$exe  = 'C:\Program Files\Warzone 2100-4.5.5\bin\warzone2100.exe'
$user = Join-Path $env:APPDATA 'Warzone 2100 Project\Warzone 2100'
$root = Join-Path $env:TEMP 'wzaudit455'
$wz   = Join-Path $env:TEMP 'doctrine_455_tel.wz'
$wall = 600

if (-not (Test-Path $exe)) { "NO 4.5.5 BINARY at $exe"; exit 1 }
New-Item -ItemType Directory -Force $root | Out-Null

$runs = @(
  @{ n = 'a455_nexus';    c = 'long-nexus.json' },
  @{ n = 'a455_semperfi'; c = 'long-semperfi.json' },
  @{ n = 'a455_mixed';    c = 'mixed.json' },
  @{ n = 'a455_thales';   c = 'thales-houses.json' }
)

$procs = @()
foreach ($r in $runs) {
  $h = Join-Path $root $r.n
  if (Test-Path $h) { Remove-Item -Recurse -Force $h }
  # 4.5.5 reads mods from mods\4.5.5\autoload
  $al = Join-Path $h 'mods\4.5.5\autoload'
  New-Item -ItemType Directory -Force $al | Out-Null
  Copy-Item $wz (Join-Path $al 'doctrine.wz')
  Copy-Item (Join-Path $user 'tests') (Join-Path $h 'tests') -Recurse
  $out = Join-Path $root ($r.n + '.out.txt'); $err = Join-Path $root ($r.n + '.err.txt')
  $argv = @('--headless','--nosound','--autogame',('--configdir=' + $h),('--skirmish=' + $r.c))
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
    Stop-Process -Id $x.p.Id -Force -ErrorAction SilentlyContinue
    "killed $($x.r.n) $(Get-Date -Format HH:mm:ss)"
  } else { "exited $($x.r.n) code=$($x.p.ExitCode) $(Get-Date -Format HH:mm:ss)" }
}
"AUDIT455 DONE -- $root"
