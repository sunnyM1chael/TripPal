param(
    [string]$TargetPath = 'F:\Projoct-code\hmdp-plus-master',
    [switch]$CheckOnly
)

$ErrorActionPreference = 'Stop'
$sourceRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..\hmdp-plus'))
$targetRoot = [IO.Path]::GetFullPath($TargetPath)
if ($sourceRoot -eq $targetRoot) { throw 'Source and target must differ.' }
if (-not (Test-Path -LiteralPath (Join-Path $targetRoot 'pom.xml'))) { throw 'Target is not the Java project root.' }

$files = @(
    'hmdp-core-service\src\main\java\org\javaup\controller\TravelPreferenceController.java',
    'hmdp-core-service\src\main\java\org\javaup\dto\TravelPreferencePatch.java',
    'hmdp-core-service\src\main\java\org\javaup\dto\TravelPreferenceView.java',
    'hmdp-core-service\src\main\java\org\javaup\entity\TravelPreference.java',
    'hmdp-core-service\src\main\java\org\javaup\mapper\TravelPreferenceMapper.java',
    'hmdp-core-service\src\main\java\org\javaup\service\TravelPreferenceService.java',
    'hmdp-core-service\src\test\java\org\javaup\TravelPreferenceTest.java',
    'sql\2_travel_preferences.sql'
)
$configRelative = 'hmdp-core-service\src\main\resources\shardingsphere.yaml'
$targetConfig = Join-Path $targetRoot $configRelative
$sourceYaml = [IO.File]::ReadAllText((Join-Path $sourceRoot $configRelative))
$targetYaml = [IO.File]::ReadAllText($targetConfig)
$originalYaml = $targetYaml

# Insert only the two preference blocks. Never replace dataSources/passwords.
foreach ($rule in @(
    @{ Name = 'tb_travel_preference'; Anchor = 'tb_seckill_voucher' },
    @{ Name = 'tableTravelPreferenceModModel'; Anchor = 'databaseSeckillVoucherModModel' }
)) {
    $pattern = '(?ms)^      ' + [regex]::Escape($rule.Name) + ':\r?\n.*?(?=^      \S|\z)'
    $block = [regex]::Match($sourceYaml, $pattern)
    if (-not $block.Success) { throw "Source rule missing: $($rule.Name)" }
    $existing = [regex]::Match($targetYaml, $pattern)
    if ($existing.Success) {
        if ($existing.Value.Replace("`r`n", "`n").TrimEnd() -ne $block.Value.Replace("`r`n", "`n").TrimEnd()) {
            throw "Conflicting target rule: $($rule.Name). No files changed."
        }
    } else {
        $anchor = [regex]::Match($targetYaml, '(?m)^      ' + [regex]::Escape($rule.Anchor) + ':\r?$')
        if (-not $anchor.Success) { throw "Target anchor missing: $($rule.Anchor). No files changed." }
        $targetYaml = $targetYaml.Insert($anchor.Index, $block.Value)
    }
}

foreach ($relative in $files) {
    if (-not (Test-Path -LiteralPath (Join-Path $sourceRoot $relative))) { throw "Source file missing: $relative" }
    $destination = [IO.Path]::GetFullPath((Join-Path $targetRoot $relative))
    if (-not $destination.StartsWith($targetRoot.TrimEnd('\') + '\', [StringComparison]::OrdinalIgnoreCase)) {
        throw 'Destination is outside target project.'
    }
    # A backup is not permission to overwrite user changes. These additive files
    # have no common baseline: only accept an absent or already identical target.
    if ((Test-Path -LiteralPath $destination) -and
        (Get-FileHash -LiteralPath (Join-Path $sourceRoot $relative)).Hash -ne
        (Get-FileHash -LiteralPath $destination).Hash) {
        throw "Conflicting target file: $relative. No files changed; merge it manually first."
    }
}

Write-Output "Target: $targetRoot"
Write-Output 'Plan: copy 6 Java classes, 1 Java test, 1 SQL file; merge 2 sharding blocks.'
if ($CheckOnly) { Write-Output 'PASS: preflight; no files changed.'; return }

# Backups are outside the Git project; config backups may contain local credentials.
$backupRoot = Join-Path ([IO.Path]::GetTempPath()) ('trippal-java-backup-' + [guid]::NewGuid().ToString('N'))
foreach ($relative in @($files) + @($configRelative)) {
    $existingFile = Join-Path $targetRoot $relative
    if (Test-Path -LiteralPath $existingFile) {
        $backup = Join-Path $backupRoot $relative
        New-Item -ItemType Directory -Path (Split-Path -Parent $backup) -Force | Out-Null
        Copy-Item -LiteralPath $existingFile -Destination $backup
    }
}
foreach ($relative in $files) {
    $destination = Join-Path $targetRoot $relative
    New-Item -ItemType Directory -Path (Split-Path -Parent $destination) -Force | Out-Null
    Copy-Item -LiteralPath (Join-Path $sourceRoot $relative) -Destination $destination -Force
}
if ($targetYaml -ne $originalYaml) {
    [IO.File]::WriteAllText($targetConfig, $targetYaml, (New-Object Text.UTF8Encoding($false)))
}
foreach ($relative in $files) {
    if ((Get-FileHash -LiteralPath (Join-Path $sourceRoot $relative)).Hash -ne
        (Get-FileHash -LiteralPath (Join-Path $targetRoot $relative)).Hash) { throw "Copy verification failed: $relative" }
}
Write-Output 'PASS: preference files synchronized; database connection settings preserved.'
Write-Output "Backup: $backupRoot"
Write-Output 'Next: execute sql\2_travel_preferences.sql in MySQL, then restart this Java project in IDEA.'
