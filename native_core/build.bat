@echo off
rem native_core/build.bat — Build Script for SON Native C++ Engine
echo =================================================================
echo        BUILDING SON V3 NATIVE C++ ENGINE (GCC / CLANG / MSVC)
echo =================================================================

set CXX=g++
where.exe g++ >nul 2>nul
if %errorlevel% neq 0 (
    if exist "C:\MinGW\bin\g++.exe" (
        set CXX=C:\MinGW\bin\g++.exe
    )
)

echo Using Compiler: %CXX%
echo.

if not exist "bin" mkdir bin

echo Compiling C++ Native Engine Shared Library (son_core.dll)...
%CXX% -O3 -std=c++14 -shared -DSON_CORE_EXPORTS -mavx2 -mfma -ffast-math src/audio_dsp.cpp src/vector_engine.cpp src/fast_intent.cpp -o bin/son_core.dll

echo Compiling C++ Standalone Runner (son_core.exe)...
%CXX% -O3 -std=c++14 -DSON_CORE_STATIC -mavx2 -mfma -ffast-math src/main.cpp src/audio_dsp.cpp src/vector_engine.cpp src/fast_intent.cpp -o bin/son_core.exe

if exist "bin\son_core.exe" (
    echo.
    echo =================================================================
    echo                 BUILD SUCCESSFUL: bin\son_core.exe
    echo =================================================================
    echo Running Native Diagnostics:
    bin\son_core.exe
) else (
    echo Build failed. Please ensure g++ is installed and in PATH.
)
