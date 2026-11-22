# Local data entrypoint only. Requires offline validation; never writes a database.
$ErrorActionPreference = 'Stop'
$dataRoot=(Resolve-Path -LiteralPath 'D:\Index-Beast\backend\data').Path.TrimEnd('\')
$auditRoot=Join-Path $dataRoot 'research_runs\structured-acceptance'
$verification=Get-Content -LiteralPath (Join-Path $auditRoot 'verification.json') -Raw | ConvertFrom-Json
if ($verification.errors.Count -ne 0 -or $verification.raw_manifest_fingerprints_verified -ne 8330) {throw 'Verification incomplete'}
$newClean=Join-Path $dataRoot 'clean_runs\structured-release'
$newChunk=Join-Path $dataRoot 'chunk_runs\structured-release'
if ($verification.clean_dir -ne $newClean -or $verification.chunk_dir -ne $newChunk) {throw 'Verification belongs to another run'}
if (-not (Test-Path -LiteralPath (Join-Path $newClean 'tables\facts_clean.csv'))) {throw 'Missing clean facts'}
if (-not (Test-Path -LiteralPath (Join-Path $newChunk 'report.json'))) {throw 'Missing chunk acceptance report'}
if ((Get-FileHash -LiteralPath (Join-Path $newChunk 'chunks.jsonl') -Algorithm SHA256).Hash.ToLower() -ne $verification.chunk_artifact_sha256) {throw 'Chunk changed after validation'}
if ((Get-FileHash -LiteralPath (Join-Path $newClean 'report.json') -Algorithm SHA256).Hash.ToLower() -ne $verification.clean_report_sha256) {throw 'Clean changed after validation'}
$obsolete=@()
foreach ($parent in @('clean_runs','chunk_runs')) {
    foreach ($item in Get-ChildItem -LiteralPath (Join-Path $dataRoot $parent) -Directory -Force) {
        if ($item.Name -eq 'structured-release') {continue}
        $absolute=(Resolve-Path -LiteralPath $item.FullName).Path
        if (-not $absolute.StartsWith((Join-Path $dataRoot $parent)+'\')) {throw 'Target escapes artifact root'}
        if ($item.Attributes -band [System.IO.FileAttributes]::ReparsePoint) {throw 'Refuse linked root'}
        if (@(Get-ChildItem -LiteralPath $absolute -Recurse -Force | Where-Object {$_.Attributes -band [System.IO.FileAttributes]::ReparsePoint}).Count) {throw 'Refuse linked tree'}
        $obsolete += $absolute
    }
}
foreach ($target in $obsolete) {Remove-Item -LiteralPath $target -Recurse -Force}
$finalRoot=Join-Path $dataRoot 'delivery\final'
New-Item -ItemType Directory -Path $finalRoot -Force | Out-Null
$links=@{raw=(Join-Path $dataRoot 'raw\wikigg');media=(Join-Path $dataRoot 'media');source=(Join-Path $dataRoot 'crawl_runs\s2-full-20261028');clean=$newClean;facts=(Join-Path $newClean 'tables');chunk=$newChunk;report=$auditRoot}
foreach ($name in $links.Keys) {
    New-Item -ItemType Junction -Path (Join-Path $finalRoot $name) -Target $links[$name] -Force | Out-Null
}
@{status='completed';removed_intermediate_directories=$obsolete;current_clean=$newClean;current_chunk=$newChunk} | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $auditRoot 'cleanup.json') -Encoding utf8
Write-Output 'One current release retained; final entrypoint created.'
