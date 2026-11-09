@echo off
title SON V3 - Personal AI Desktop Assistant
cd /d "C:\AI\SON"

echo =================================================================
echo             STARTING SON DESKTOP AI ASSISTANT (.NET 8 WPF)
echo =================================================================
echo.

if exist "SON.Desktop\bin\Debug\net8.0-windows\SON.Desktop.exe" (
    start "" "SON.Desktop\bin\Debug\net8.0-windows\SON.Desktop.exe"
) else (
    echo Starting SON Desktop via dotnet...
    dotnet run --project "SON.Desktop\SON.Desktop.csproj"
)
