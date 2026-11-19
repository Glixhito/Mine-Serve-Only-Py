# Construye la app y, si encuentra Inno Setup, el instalador de Windows.
# Uso (PowerShell, en la carpeta del proyecto):
#   .\build.ps1
#   .\build.ps1 -IsccPath "C:\ruta\completa\ISCC.exe"
param([string]$IsccPath = "")
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

if (-not (Test-Path "assets\icono.ico")) {
    throw "Falta assets\icono.ico. Ejecuta primero: python tools\convertir_icono.py"
}

function Find-Iscc {
    param([string]$Manual)
    if ($Manual -and (Test-Path $Manual)) { return $Manual }
    $candidatos = @(
        "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
        "$env:ProgramFiles\Inno Setup 6\ISCC.exe"
    )
    $candidatos += Get-ChildItem -Path "$env:LOCALAPPDATA\Programs\Inno Setup *\ISCC.exe",
        "$env:ProgramFiles\Inno Setup *\ISCC.exe", "${env:ProgramFiles(x86)}\Inno Setup *\ISCC.exe" `
        -ErrorAction SilentlyContinue | ForEach-Object { $_.FullName }
    $claves = @(
        "HKLM:\SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\*",
        "HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\*",
        "HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\*"
    )
    foreach ($clave in $claves) {
        $programas = Get-ItemProperty $clave -ErrorAction SilentlyContinue |
            Where-Object { $_.DisplayName -like "Inno Setup*" -and $_.InstallLocation }
        foreach ($programa in $programas) {
            $candidatos += (Join-Path $programa.InstallLocation "ISCC.exe")
        }
    }
    return ($candidatos | Where-Object { $_ -and (Test-Path $_) } | Select-Object -First 1)
}

Get-Process MinecraftServerManager -ErrorAction SilentlyContinue | Stop-Process -Force

foreach ($carpeta in "build", "dist", "dist-installer") {
    for ($intento = 1; $intento -le 5; $intento++) {
        if (-not (Test-Path $carpeta)) { break }
        try {
            Remove-Item -Recurse -Force $carpeta
            break
        } catch {
            Write-Warning "No se pudo borrar '$carpeta' (intento $intento). Cierra el Explorador o espera..."
            Start-Sleep -Seconds 2
        }
    }
}

pyinstaller --noconfirm --clean --windowed --name MinecraftServerManager `
    --icon "assets\icono.ico" --add-data "assets\icono.ico;assets" main.py
if ($LASTEXITCODE -ne 0) { throw "PyInstaller fallo (codigo $LASTEXITCODE). Revisa el mensaje anterior." }

$iscc = Find-Iscc -Manual $IsccPath
if (-not $iscc) {
    Write-Warning 'No se encontro Inno Setup. Ejecuta: .\build.ps1 -IsccPath "C:\ruta\ISCC.exe"'
    Write-Host "La app compilada esta en dist\MinecraftServerManager\" -ForegroundColor Yellow
    exit 0
}
Write-Host "Usando Inno Setup en: $iscc" -ForegroundColor Cyan
& $iscc "installer\MinecraftServerManager.iss"
if ($LASTEXITCODE -ne 0) { throw "Inno Setup fallo (codigo $LASTEXITCODE)." }
Write-Host "Listo: dist-installer\MinecraftServerManager-Setup-1.0.0.exe" -ForegroundColor Green