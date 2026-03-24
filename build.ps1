param(
    [switch]$Clean
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$BuildRoot = Join-Path $ProjectRoot ".build"
$DistExe = Join-Path $ProjectRoot "BluetoothResetter.exe"
$IconPath = Join-Path $ProjectRoot "tools_bluetooth_serial_utility_13004.ico"
$EntryPoint = Join-Path $ProjectRoot "app.py"
$SrcRoot = Join-Path $ProjectRoot "src"

if ($Clean) {
    Remove-Item -Path $BuildRoot -Recurse -Force -ErrorAction SilentlyContinue
    Remove-Item -Path $DistExe -Force -ErrorAction SilentlyContinue
}

if (-not (Test-Path -LiteralPath $EntryPoint)) {
    throw "No se encontró app.py en la raíz del proyecto."
}

$arguments = @(
    "-m", "PyInstaller",
    "--noconfirm",
    "--clean",
    "--onefile",
    "--windowed",
    "--name", "BluetoothResetter",
    "--distpath", $ProjectRoot,
    "--workpath", (Join-Path $BuildRoot "work"),
    "--specpath", (Join-Path $BuildRoot "spec"),
    "--paths", $SrcRoot,
    "--add-data", ("{0};scripts" -f (Join-Path $ProjectRoot "scripts")),
    "--add-data", ("{0};." -f $IconPath)
)

if (Test-Path -LiteralPath $IconPath) {
    $arguments += @("--icon", $IconPath)
}

$arguments += $EntryPoint

Write-Host "Ejecutando build con PyInstaller..."
& python $arguments

if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller devolvió código $LASTEXITCODE."
}

Write-Host "Build completado: $DistExe"
