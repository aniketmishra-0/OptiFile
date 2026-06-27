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
echo        Uninstalling OptiFile Windows Integration
echo =======================================================
echo.

:: Stop any running instances of OptiFile.exe
echo Stopping any running instances of OptiFile...
taskkill /IM OptiFile.exe /F 2>nul

:: Delete registry entries
echo Removing registry entries...
reg delete "HKEY_CLASSES_ROOT\*\shell\OptiFile" /f 2>nul
reg delete "HKEY_CLASSES_ROOT\Directory\shell\OptiFile" /f 2>nul

echo.
echo =======================================================
echo 🎉 Uninstallation Successful!
echo Context menu integration has been removed.
echo =======================================================
echo.
pause
