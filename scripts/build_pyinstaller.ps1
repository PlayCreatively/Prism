# Build script for PyInstaller (Windows PowerShell)
# Usage: powershell -ExecutionPolicy Bypass -File .\scripts\build_pyinstaller.ps1
#
# This script builds PRISM as a folder distribution (not single-file) for NiceGUI compatibility.
# The output will be in dist/PRISM/ with external folders (db/, prompts/) copied alongside.

Write-Host "[build] Starting PyInstaller build..."

# Ensure PyInstaller is installed
Write-Host "[build] Checking for PyInstaller..."
python -m pip show pyinstaller > $null 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "[build] PyInstaller not found. Installing..."
    python -m pip install --upgrade pip
    python -m pip install pyinstaller
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
    
    # Copy prompts folder (user-editable)
    if (Test-Path 'prompts') {
        Copy-Item -Path "prompts" -Destination "$distDir\prompts" -Recurse -Force
        Write-Host "[build] Copied prompts/ folder"
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
- config.json - Your settings (auto-created)
"@
    Set-Content -Path "$distDir\README.txt" -Value $readmeContent
    Write-Host "[build] Created README.txt"
    
    Write-Host "[build] Build succeeded! Output: $distDir" -ForegroundColor Green
} else {
    Write-Host "[build] Could not find output directory: $distDir" -ForegroundColor Yellow
}

Write-Host "[build] Done."