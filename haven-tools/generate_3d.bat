@echo off
setlocal

:: Try to find a real python.exe (not the Windows Store shim)
set "PYTHON_EXE="

:: 1. Check if the AppData Local Python exists
if exist "C:\Users\admin\AppData\Local\Python\bin\python.exe" (
    set "PYTHON_EXE=C:\Users\admin\AppData\Local\Python\bin\python.exe"
)

:: 2. If not found, look up python in PATH but filter out WindowsApps
if not defined PYTHON_EXE (
    for /f "tokens=*" %%i in ('where.exe python 2^>nul') do (
        echo %%i | findstr /i "WindowsApps" >nul
        if errorlevel 1 (
            if not defined PYTHON_EXE (
                set "PYTHON_EXE=%%i"
            )
        )
    )
)

:: 3. Fallback to default python
if not defined PYTHON_EXE (
    set "PYTHON_EXE=python"
)

:: Run generate_3d.py using the resolved Python executable
"%PYTHON_EXE%" "%~dp0generate_3d.py"
