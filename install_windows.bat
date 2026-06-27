@echo off
:: Batch Got Admin
:init
setlocal DisableDelayedExpansion
set "batchPath=%~0"
for %%k in (%0) do set batchName=%%~nk
set "vbsGetPrivileges=%temp%\OEgetPriv_%batchName%.vbs"
setlocal EnableDelayedExpansion

:checkPrivileges
NET FILE 1>NUL 2>NUL
if '%errorlevel%' == '0' ( goto gotPrivileges ) else ( goto getPrivileges )

:getPrivileges
if '%1'=='ELEV' (echo ELEV & shift & goto gotPrivileges)
echo **************************************
echo Invoking UAC for Privilege Escalation
echo **************************************

echo Set UAC = CreateObject^("Shell.Application"^) > "%vbsGetPrivileges%"
echo args = "" >> "%vbsGetPrivileges%"
echo For Each strArg in WScript.Arguments >> "%vbsGetPrivileges%"
echo args = args ^& " " ^& strArg >> "%vbsGetPrivileges%"
echo Next >> "%vbsGetPrivileges%"
echo UAC.ShellExecute "!batchPath!", "ELEV" & args, "", "runas", 1 >> "%vbsGetPrivileges%"
"%SystemRoot%\System32\WScript.exe" "%vbsGetPrivileges%" %*
exit /B

:gotPrivileges
setlocal & pushd .
cd /d %~dp0
if exist "%vbsGetPrivileges%" ( del "%vbsGetPrivileges%" )

echo =======================================================
echo          Installing OptiFile Windows Integration
echo =======================================================
echo.

:: Get full path to OptiFile.exe in dist folder
set "EXE_PATH=%~dp0dist\OptiFile.exe"
:: Replace backslashes with double backslashes for reg command
set "ESCAPED_PATH=%EXE_PATH:\=\\%"

if not exist "%EXE_PATH%" (
    echo ❌ Error: "%EXE_PATH%" not found!
    echo Please run build_app.bat first to compile the app.
    echo.
    pause
    exit /b 1
)

:: Stop any running instances of OptiFile.exe
echo Stopping any running instances of OptiFile...
taskkill /IM OptiFile.exe /F 2>nul

:: Add right-click registry entries
echo Adding right-click context menu registry entries...

:: 1. Add context menu for files
reg add "HKEY_CLASSES_ROOT\*\shell\OptiFile" /ve /t REG_SZ /d "Optimize with OptiFile" /f
reg add "HKEY_CLASSES_ROOT\*\shell\OptiFile" /v "Icon" /t REG_SZ /d "\"%ESCAPED_PATH%\"" /f
reg add "HKEY_CLASSES_ROOT\*\shell\OptiFile\command" /ve /t REG_SZ /d "\"%ESCAPED_PATH%\" \"%%1\"" /f

:: 2. Add context menu for directories/folders
reg add "HKEY_CLASSES_ROOT\Directory\shell\OptiFile" /ve /t REG_SZ /d "Optimize with OptiFile" /f
reg add "HKEY_CLASSES_ROOT\Directory\shell\OptiFile" /v "Icon" /t REG_SZ /d "\"%ESCAPED_PATH%\"" /f
reg add "HKEY_CLASSES_ROOT\Directory\shell\OptiFile\command" /ve /t REG_SZ /d "\"%ESCAPED_PATH%\" \"%%1\"" /f

echo.
echo =======================================================
echo 🎉 Installation Successful!
echo Right-click any file or folder to select 'Optimize with OptiFile'
echo =======================================================
echo.
pause
