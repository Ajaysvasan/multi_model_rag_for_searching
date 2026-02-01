@echo off
rem ===============================================================
rem install_tesseract.bat
rem Safely installs Tesseract OCR on Windows if not already present.
rem Uses official Mannheim build.
rem Silent install, no PATH corruption.
rem ===============================================================


rem 1. Check if Tesseract is already available in PATH

where tesseract >nul 2>&1
if %ERRORLEVEL% equ 0 (
    echo Tesseract is already installed and available in PATH.
    goto END
)

rem 2. Check default installation directory

set TESSERACT_DIR=C:\Program Files\Tesseract-OCR
set TESSERACT_EXE=%TESSERACT_DIR%\tesseract.exe

if exist "%TESSERACT_EXE%" (
    echo Tesseract found at:
    echo   %TESSERACT_EXE%
    echo.
    echo NOTE:
    echo Tesseract is installed but not in PATH.
    echo Please add the following directory to PATH manually:
    echo   %TESSERACT_DIR%
    echo.
    goto END
)

rem 3. If tesseract not found Download installer (official Mannheim build)

echo Tesseract not found. Downloading installer...

set INSTALLER_URL=https://digi.bib.uni-mannheim.de/tesseract/tesseract-ocr-w64-setup-5.5.0.20241111.exe
set INSTALLER_PATH=%TEMP%\tesseract-installer.exe

powershell -NoProfile -ExecutionPolicy Bypass ^
    -Command "Invoke-WebRequest -Uri '%INSTALLER_URL%' -OutFile '%INSTALLER_PATH%'" 

if not exist "%INSTALLER_PATH%" (
    echo ERROR: Failed to download Tesseract installer.
    echo Check your internet connection.
    exit /b 1
)

rem 4. Silent installation

echo Installing Tesseract OCR (silent mode)...
"%INSTALLER_PATH%" /S

if %ERRORLEVEL% neq 0 (
    echo ERROR: Installer returned an error.
    exit /b 1
)

rem 5. Cleanup

del /f /q "%INSTALLER_PATH%" >nul 2>&1

echo.
echo Tesseract installation completed.

rem 6. Final verification (new shell required for PATH)

echo.
echo IMPORTANT:
echo - Please open a NEW terminal window.
echo - Then run:  tesseract --version
echo.
echo If Tesseract is not found, add this to PATH:
echo   %TESSERACT_DIR%
echo.

:END
echo ===== Done =====
pause
