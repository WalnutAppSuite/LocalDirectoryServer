@echo off
REM Windows Installer for Local Directory Server
REM Installs to C:\DirectoryServer and sets up as Windows Service

setlocal enabledelayedexpansion

echo ============================================================
echo   Local Directory Server - Windows Installer
echo ============================================================
echo.

REM Check for admin privileges
net session >nul 2>&1
if %errorLevel% neq 0 (
    echo ERROR: This installer requires Administrator privileges.
    echo Please right-click and select "Run as administrator"
    pause
    exit /b 1
)

set INSTALL_DIR=C:\DirectoryServer
set NSSM_URL=https://nssm.cc/release/nssm-2.24.zip
set SERVICE_NAME=LocalDirectoryServer

echo Installation directory: %INSTALL_DIR%
echo.

REM Get user input for content directory
echo.
set /p CONTENT_DIR="Enter Google Drive content folder path (e.g., G:\My Drive\Content): "
if "!CONTENT_DIR!"=="" (
    set CONTENT_DIR=G:\My Drive\Content
    echo Using default: !CONTENT_DIR!
)

REM Validate the directory exists
if not exist "!CONTENT_DIR!" (
    echo WARNING: Directory "!CONTENT_DIR!" does not exist.
    echo Make sure Google Drive is synced before starting the server.
)
echo.

REM Get Certbot directory
set /p CERT_DIR="Enter Certbot directory path (e.g., C:\Certbot): "
if "!CERT_DIR!"=="" (
    set CERT_DIR=C:\Certbot
    echo Using default: !CERT_DIR!
)

REM Get subdomain for SSL certificate
set /p SUBDOMAIN="Enter subdomain for SSL cert (e.g., shivanelocal.walnutedu.in): "
if "!SUBDOMAIN!"=="" (
    set SUBDOMAIN=shivanelocal.walnutedu.in
    echo Using default: !SUBDOMAIN!
)

REM Get Python path
for /f "delims=" %%i in ('where python 2^>nul') do set DEFAULT_PYTHON=%%i
if not defined DEFAULT_PYTHON set DEFAULT_PYTHON=python
echo.
echo Detected Python: !DEFAULT_PYTHON!
set /p PYTHON_PATH="Enter Python executable path (press Enter to use detected): "
if "!PYTHON_PATH!"=="" (
    set PYTHON_PATH=!DEFAULT_PYTHON!
)
echo Using: !PYTHON_PATH!

REM Check if archive folder has certs (live folder often has broken symlinks)
set CERT_PATH=%CERT_DIR%\live\!SUBDOMAIN!
if exist "%CERT_DIR%\archive\!SUBDOMAIN!\fullchain1.pem" (
    set CERT_PATH=%CERT_DIR%\archive\!SUBDOMAIN!
    set CERT_FILE=fullchain1.pem
    set KEY_FILE=privkey1.pem
    echo Using archive certs: !CERT_PATH!
) else (
    set CERT_FILE=fullchain.pem
    set KEY_FILE=privkey.pem
)
echo.

REM Create installation directory
if not exist "%INSTALL_DIR%" (
    echo Creating directory: %INSTALL_DIR%
    mkdir "%INSTALL_DIR%"
)

REM Copy files
echo Copying files...
copy /Y "%~dp0directory_server.py" "%INSTALL_DIR%\" >nul
copy /Y "%~dp0load_test.py" "%INSTALL_DIR%\" >nul
copy /Y "%~dp0README.md" "%INSTALL_DIR%\" >nul
if exist "%~dp0nssm.exe" copy /Y "%~dp0nssm.exe" "%INSTALL_DIR%\" >nul

REM Check if NSSM is available
if not exist "%INSTALL_DIR%\nssm.exe" (
    echo.
    echo NSSM ^(service manager^) not found.
    echo Please download NSSM from: https://nssm.cc/download
    echo Extract nssm.exe to: %INSTALL_DIR%\nssm.exe
    echo Then run this installer again.
    echo.
    echo Alternatively, place nssm.exe in the same folder as this installer.
    echo.
)

REM Create config file
echo Creating default configuration...
(
echo # Local Directory Server Configuration
echo # Edit these values for your setup
echo.
echo PORT=8050
echo CONTENT_DIR=!CONTENT_DIR!
echo CERT_FILE=!CERT_PATH!\!CERT_FILE!
echo KEY_FILE=!CERT_PATH!\!KEY_FILE!
echo SKIP_DRIVE_CHECK=0
) > "%INSTALL_DIR%\config.env"

REM Create the service runner script
echo Creating service runner script...
(
echo @echo off
echo cd /d "%INSTALL_DIR%"
echo python directory_server.py -p 8050 -d "!CONTENT_DIR!" --cert "!CERT_PATH!\!CERT_FILE!" --key "!CERT_PATH!\!KEY_FILE!"
) > "%INSTALL_DIR%\run_service.bat"

REM Create manual startup script
(
echo @echo off
echo cd /d "%INSTALL_DIR%"
echo echo Starting Local Directory Server manually...
echo python directory_server.py -p 8050 -d "!CONTENT_DIR!" --cert "!CERT_PATH!\!CERT_FILE!" --key "!CERT_PATH!\!KEY_FILE!"
echo pause
) > "%INSTALL_DIR%\start_server.bat"

REM Create HTTP-only startup script
(
echo @echo off
echo cd /d "%INSTALL_DIR%"
echo echo Starting Local Directory Server ^(HTTP only^)...
echo python directory_server.py -p 8050 -d "!CONTENT_DIR!" --skip-drive-check
echo pause
) > "%INSTALL_DIR%\start_server_http.bat"

REM Add firewall rule
echo Adding Windows Firewall rule for port 8050...
netsh advfirewall firewall delete rule name="Local Directory Server" >nul 2>&1
netsh advfirewall firewall add rule name="Local Directory Server" dir=in action=allow protocol=tcp localport=8050 >nul

REM Install Windows Service using NSSM
if exist "%INSTALL_DIR%\nssm.exe" (
    echo.
    echo Setting up Windows Service...

    REM Stop and remove existing service if present
    "%INSTALL_DIR%\nssm.exe" stop %SERVICE_NAME% >nul 2>&1
    "%INSTALL_DIR%\nssm.exe" remove %SERVICE_NAME% confirm >nul 2>&1

    REM Install the service
    "%INSTALL_DIR%\nssm.exe" install %SERVICE_NAME% "!PYTHON_PATH!" "%INSTALL_DIR%\directory_server.py" -p 8050 -d "!CONTENT_DIR!" --cert "!CERT_PATH!\!CERT_FILE!" --key "!CERT_PATH!\!KEY_FILE!"

    REM Configure service
    "%INSTALL_DIR%\nssm.exe" set %SERVICE_NAME% AppDirectory "%INSTALL_DIR%"
    "%INSTALL_DIR%\nssm.exe" set %SERVICE_NAME% DisplayName "Local Directory Server"
    "%INSTALL_DIR%\nssm.exe" set %SERVICE_NAME% Description "Serves local Google Drive content over HTTPS for classroom access"
    "%INSTALL_DIR%\nssm.exe" set %SERVICE_NAME% Start SERVICE_AUTO_START
    "%INSTALL_DIR%\nssm.exe" set %SERVICE_NAME% AppStdout "%INSTALL_DIR%\logs\service.log"
    "%INSTALL_DIR%\nssm.exe" set %SERVICE_NAME% AppStderr "%INSTALL_DIR%\logs\error.log"
    "%INSTALL_DIR%\nssm.exe" set %SERVICE_NAME% AppRotateFiles 1
    "%INSTALL_DIR%\nssm.exe" set %SERVICE_NAME% AppRotateBytes 1048576

    REM Create logs directory
    if not exist "%INSTALL_DIR%\logs" mkdir "%INSTALL_DIR%\logs"

    echo.
    echo Service '%SERVICE_NAME%' installed successfully!
    echo.

    REM Ask to start service
    set /p START_NOW="Start the service now? (Y/N): "
    if /i "!START_NOW!"=="Y" (
        echo Starting service...
        "%INSTALL_DIR%\nssm.exe" start %SERVICE_NAME%
        timeout /t 2 >nul
        "%INSTALL_DIR%\nssm.exe" status %SERVICE_NAME%
    )
) else (
    echo.
    echo NSSM not found - service installation skipped.
    echo You can run start_server.bat manually or set up Task Scheduler.
)

REM Create service management scripts
echo Creating service management scripts...

(
echo @echo off
echo echo Starting Local Directory Server service...
echo "%INSTALL_DIR%\nssm.exe" start %SERVICE_NAME%
echo pause
) > "%INSTALL_DIR%\service_start.bat"

(
echo @echo off
echo echo Stopping Local Directory Server service...
echo "%INSTALL_DIR%\nssm.exe" stop %SERVICE_NAME%
echo pause
) > "%INSTALL_DIR%\service_stop.bat"

(
echo @echo off
echo echo Restarting Local Directory Server service...
echo "%INSTALL_DIR%\nssm.exe" restart %SERVICE_NAME%
echo pause
) > "%INSTALL_DIR%\service_restart.bat"

(
echo @echo off
echo echo Service Status:
echo "%INSTALL_DIR%\nssm.exe" status %SERVICE_NAME%
echo.
echo echo.
echo echo Service Logs ^(last 20 lines^):
echo type "%INSTALL_DIR%\logs\service.log" 2^>nul ^| more +n-20
echo pause
) > "%INSTALL_DIR%\service_status.bat"

(
echo @echo off
echo echo Uninstalling Local Directory Server service...
echo "%INSTALL_DIR%\nssm.exe" stop %SERVICE_NAME%
echo "%INSTALL_DIR%\nssm.exe" remove %SERVICE_NAME% confirm
echo echo Service removed.
echo pause
) > "%INSTALL_DIR%\service_uninstall.bat"

echo.
echo ============================================================
echo   Installation Complete!
echo ============================================================
echo.
echo Files installed to: %INSTALL_DIR%
echo.
echo Service Management:
echo   service_start.bat     - Start the service
echo   service_stop.bat      - Stop the service
echo   service_restart.bat   - Restart the service
echo   service_status.bat    - Check service status
echo   service_uninstall.bat - Remove the service
echo.
echo Manual Start:
echo   start_server.bat      - Run server manually with HTTPS
echo   start_server_http.bat - Run server manually without HTTPS
echo.
echo IMPORTANT: Before starting, ensure:
echo   1. Python is installed and in PATH
echo   2. Google Drive is synced to: !CONTENT_DIR!
echo   3. SSL certificates exist in: !CERT_PATH!
echo.
pause
