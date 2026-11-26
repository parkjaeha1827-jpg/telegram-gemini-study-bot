@echo off
title Auto Export to GitHub
cd /d "%~dp0"
powershell -ExecutionPolicy Bypass -File "%~dp0export_to_github.ps1" %*
pause
