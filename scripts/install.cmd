@echo off
REM ============================================================================
REM Alvarez Agent Installer for Windows (CMD wrapper)
REM ============================================================================
REM This batch file launches the PowerShell installer for users running CMD.
REM
REM Usage (the repo is private -- clone with your GitHub credentials first):
REM   git clone git@github.com:alvarez-agent/alvarez-agent.git
REM   cd alvarez-agent && scripts\install.cmd
REM
REM Or if you're already in PowerShell, run the installer directly instead:
REM   .\scripts\install.ps1
REM ============================================================================

echo.
echo  Alvarez Agent Installer
echo  Launching PowerShell installer...
echo.

powershell -ExecutionPolicy ByPass -NoProfile -File "%~dp0install.ps1"

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo  Installation failed. Please try running PowerShell directly:
    echo    powershell -ExecutionPolicy ByPass -NoProfile -File "%~dp0install.ps1"
    echo.
    pause
    exit /b 1
)
