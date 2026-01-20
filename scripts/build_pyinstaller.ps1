# Build script for PyInstaller (Windows PowerShell)
# Usage: powershell -ExecutionPolicy Bypass -File .\scripts\build_pyinstaller.ps1
#
# This script builds PRISM as a folder distribution (not single-file) for NiceGUI compatibility.
# The output will be in dist/PRISM/ with external folders (db/, prompts/) copied alongside.
# Uses a dedicated virtual environment for minimal build size.

Write-Host "[build] Starting PyInstaller build..."

# Check for or create virtual environment
$venvPath = ".venv"
if (-Not (Test-Path "$venvPath\Scripts\Activate.ps1")) {
    Write-Host "[build] Creating virtual environment..."
    python -m venv $venvPath
    & "$venvPath\Scripts\Activate.ps1"
    Write-Host "[build] Installing dependencies..."
    pip install --upgrade pip
    pip install nicegui networkx openai python-dotenv pywebview pyinstaller
} else {
    Write-Host "[build] Using existing virtual environment..."
    & "$venvPath\Scripts\Activate.ps1"
}

# Ensure PyInstaller is available
pip show pyinstaller > $null 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "[build] Installing PyInstaller..."
    pip install pyinstaller
}

# Use the spec file for the build
$specFile = "prism.spec"
if (-Not (Test-Path $specFile)) {
    Write-Host "[build] ERROR: $specFile not found. Please ensure it exists in the project root." -ForegroundColor Red
    exit 1
}

Write-Host "[build] Building with spec file: $specFile"
pyinstaller $specFile --noconfirm

$exit = $LASTEXITCODE
if ($exit -ne 0) {
    Write-Host "[build] PyInstaller failed with exit code $exit" -ForegroundColor Red
    exit $exit
}

# Copy external folders to dist/PRISM/
$distDir = "dist\PRISM"
if (Test-Path $distDir) {
    Write-Host "[build] Copying external folders..."
    
    # Copy node_types folder (user-editable custom node definitions)
    if (Test-Path 'node_types') {
        Copy-Item -Path "node_types" -Destination "$distDir\node_types" -Recurse -Force
        Write-Host "[build] Copied node_types/ folder"
    }
    
    # Create empty db folder
    $dbDir = "$distDir\db"
    if (-Not (Test-Path $dbDir)) {
        New-Item -ItemType Directory -Path $dbDir | Out-Null
        Write-Host "[build] Created empty db/ folder"
    }
    
    # Create README
    $readmeContent = @"
PRISM - Collaborative Consensus & Interest Mapping

Getting Started:
1. Run PRISM.exe
2. Enter your OpenAI API key when prompted
3. Create your first project

Folders:
- db/ - Your project data (auto-created)
- prompts/ - AI prompt templates (editable)
- node_types/ - Custom node type definitions (editable)
- config.json - Your settings (auto-created)
"@
    Set-Content -Path "$distDir\README.txt" -Value $readmeContent
    Write-Host "[build] Created README.txt"
    
    Write-Host "[build] Build succeeded! Output: $distDir" -ForegroundColor Green
} else {
    Write-Host "[build] Could not find output directory: $distDir" -ForegroundColor Yellow
}

Write-Host "[build] Done."