param(
    [switch]$InstallDeps,
    [switch]$Deploy,
    [switch]$SkipBuild
)

$ErrorActionPreference = "Stop"

$projectDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectDir = [System.IO.Path]::GetFullPath($projectDir)
$wslDistro = "Ubuntu-24.04"

function Ensure-WslDistro {
    if (-not (Get-Command wsl -ErrorAction SilentlyContinue)) {
        throw "WSL não está instalado. Instale o WSL2 e o Ubuntu antes de continuar."
    }

    $distros = wsl --list --quiet 2>$null
    if ($LASTEXITCODE -ne 0) {
        throw "Não foi possível listar distribuições WSL. Verifique a instalação do WSL."
    }

    $registeredDistros = @(
        $distros | ForEach-Object {
            ($_ -replace "`0", "").Trim().TrimStart("*").Trim()
        }
    )
    if ($wslDistro -notin $registeredDistros) {
        Write-Host "Distribuição Ubuntu não encontrada. Instalando..." -ForegroundColor Yellow
        wsl --install -d $wslDistro
        if ($LASTEXITCODE -ne 0) {
            throw "Falhou ao instalar a distribuição Ubuntu via WSL."
        }
    }

    $escapedDistro = [regex]::Escape($wslDistro)
    $distroLine = wsl --list --verbose 2>$null |
        ForEach-Object { ($_ -replace "`0", "").Trim() } |
        Where-Object { $_ -match "^\*?\s*$escapedDistro\s+(Running|Stopped)\s+\d+\s*$" } |
        Select-Object -First 1
    $versionMatch = [regex]::Match([string]$distroLine, "\s(\d+)\s*$")
    if (-not $distroLine -or -not $versionMatch.Success) {
        throw "Não consegui determinar a versão WSL da distribuição $wslDistro."
    }

    if ([int]$versionMatch.Groups[1].Value -eq 1) {
        Write-Host "Convertendo $wslDistro para WSL 2..." -ForegroundColor Yellow
        & wsl --set-version $wslDistro 2
        if ($LASTEXITCODE -ne 0) {
            throw "Não foi possível converter para WSL 2. Ative a virtualização Intel VT-x/AMD-V na BIOS/UEFI e o recurso 'Plataforma de Máquina Virtual' do Windows; reinicie e rode o script novamente."
        }
    }

    & wsl --distribution $wslDistro --exec /bin/true
    if ($LASTEXITCODE -ne 0) {
        throw "A distribuição $wslDistro está registrada, mas não inicializa. Abra-a com 'wsl -d $wslDistro' e conclua a configuração."
    }
}

function Invoke-WslCommand {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Command,
        [string]$WorkingDirectory = $projectDir
    )

    $drivePath = $WorkingDirectory.Replace('C:\', '/mnt/c/')
    $drivePath = $drivePath.Replace('\', '/')

    $fullCommand = "cd '$drivePath'; $Command"
    $fullCommand = $fullCommand -replace "`r`n", "`n"
    $encodedCommand = [Convert]::ToBase64String(
        [System.Text.Encoding]::UTF8.GetBytes($fullCommand)
    )

    Write-Host "[wsl] $Command" -ForegroundColor Cyan
    & wsl --distribution $wslDistro --exec bash -lc "echo '$encodedCommand' | base64 -d | bash"

    if ($LASTEXITCODE -ne 0) {
        throw "Comando WSL falhou: $Command"
    }
}

Ensure-WslDistro

Write-Host "Diretório do projeto: $projectDir" -ForegroundColor Yellow

$desktopPong = Join-Path (Split-Path -Parent $projectDir) "pong.py"
$androidPong = Join-Path $projectDir "pong.py"
if (-not (Test-Path $desktopPong -PathType Leaf)) {
    throw "Não encontrei o código principal do jogo em: $desktopPong"
}
Copy-Item -Path $desktopPong -Destination $androidPong -Force
Write-Host "Código do Pong sincronizado para Android." -ForegroundColor Green

$linuxScript = @'
set -e
cd "$(pwd)"

python3 --version >/dev/null 2>&1 || { echo "Python 3 não encontrado em WSL."; exit 1; }

if [ "$(id -u)" -eq 0 ]; then
    SUDO=""
else
    SUDO="sudo"
fi

$SUDO apt-get update
export DEBIAN_FRONTEND=noninteractive
$SUDO apt-get install -y python3-venv python3-pip git zip unzip cmake openjdk-17-jdk zlib1g-dev libncurses5-dev libstdc++6 libc6-dev-i386 build-essential libbz2-dev libffi-dev libssl-dev libsqlite3-dev liblzma-dev uuid-dev libgmp-dev libgl1-mesa-dev libglu1-mesa-dev

if [ ! -d .venv ]; then
    python3 -m venv .venv
fi

. .venv/bin/activate
python -m pip install --upgrade pip setuptools wheel cython
python -m pip install --upgrade buildozer

if [ ! -f buildozer.spec ]; then
    echo "buildozer.spec não encontrado na pasta do projeto."
    exit 1
fi
'@

if ($InstallDeps) {
    Write-Host "Instalando dependências do Android/Buildozer no WSL..." -ForegroundColor Yellow
    Invoke-WslCommand -Command $linuxScript
    Write-Host "Dependências instaladas com sucesso." -ForegroundColor Green
}

if (-not $SkipBuild) {
    Write-Host "Gerando APK em debug..." -ForegroundColor Yellow
    Invoke-WslCommand -Command ". .venv/bin/activate && printf 'y\n' | buildozer -v android debug"

    $apkPath = Join-Path $projectDir "bin"
    if (Test-Path $apkPath) {
        $files = Get-ChildItem $apkPath -Filter *.apk -File | Sort-Object LastWriteTime -Descending
        if ($files.Count -gt 0) {
            Write-Host "APK gerado em: $($files[0].FullName)" -ForegroundColor Green
        }
    }
}

if ($Deploy) {
    Write-Host "Tentando instalar no dispositivo Android conectado..." -ForegroundColor Yellow
    Invoke-WslCommand -Command ". .venv/bin/activate && adb devices && adb install -r ./bin/*.apk"
    Write-Host "Instalação concluída." -ForegroundColor Green
}

Write-Host "Tudo pronto. Se o APK não foi gerado, rode: .\build_android.ps1 -InstallDeps" -ForegroundColor Cyan
