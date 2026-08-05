@echo off
REM native/build.bat — One-click build for SON V3 C acceleration module
REM Builds the _son_accel Python C extension (.pyd on Windows)
REM
REM Usage:
REM     cd C:\AI\SON
REM     native\build.bat
REM

echo ============================================
echo  SON V3 — Building Native Acceleration Layer
echo  Target: Ryzen 7 7840HS (AVX2/FMA/Zen 4)
echo ============================================
echo.

REM Build from project root
cd /d "%~dp0\.."

echo [1/3] Cleaning previous builds...
if exist build rmdir /s /q build 2>nul
if exist _son_accel*.pyd del /q _son_accel*.pyd 2>nul

echo [2/3] Building C extension with AVX2 optimizations...
python native\setup.py build_ext --inplace

if %ERRORLEVEL% neq 0 (
    echo.
    echo [ERROR] Build failed!
    echo.
    echo Possible fixes:
    echo   1. Install Visual Studio Build Tools:
    echo      https://visualstudio.microsoft.com/visual-cpp-build-tools/
    echo   2. Or install MinGW-w64 and add to PATH
    echo.
    pause
    exit /b 1
)

echo [3/3] Verifying module...
python -c "import _son_accel; print('  OK: _son_accel loaded successfully'); print('  Functions:', [x for x in dir(_son_accel) if not x.startswith('_')])"

if %ERRORLEVEL% neq 0 (
    echo [WARNING] Module built but failed to import. Check Python version compatibility.
) else (
    echo.
    echo ============================================
    echo  BUILD SUCCESSFUL
    echo  _son_accel.pyd is ready for use
    echo ============================================
)

echo.
pause
