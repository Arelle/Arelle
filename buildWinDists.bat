rem Build Arelle GUI using cx_Freeze
rem both win 32 (x86) and win 64 (x64)

rem arguments may be eiopa, x86, and er3
rem build x86 only for eiopa or x86

@set PYTHON32DIR=c:\python34x86
@set PYTHON64DIR=c:\python34
rem @set TCL_LIBRARY=c:\python35\tcl\tcl8.6
rem @set TK_LIBRARY=c:\python35\tcl\tk8.6
@set NSISDIR=C:\Program Files (x86)\NSIS
@set BUILT32DIR=build\exe.win32-3.4
@set BUILT64DIR=build\exe.win-amd64-3.4
@set ZIP=c:\progra~1\7-zip\7z.exe

@set do32bitBuild=true
@if not "%1"=="eiopa" if not "%1"=="x86" set do32bitBuild=false

rem Rebuild messages.pot internationalization file
"%PYTHON64DIR%\python" pygettext.py -v -o arelle\locale\messages.pot arelle\*.pyw arelle\*.py
rem pause "Please check the python gettext string conversions"

rem Regenerate messages catalog (doc/messagesCatalog.xml)
"%PYTHON64DIR%\python" generateMessagesCatalog.py

rmdir build /s/q
rmdir dist /s/q
mkdir build
mkdir dist

@set FILESUFFIX=""

rem @if "%1" == "er3.814" (
rem echo Copying EdgarRenderer
rem @set ER3DIR=Z:\Documents\mvsl\projects\SEC\RenderingEngine\github_plugin_3_3_0_814
rem xcopy "%ER3DIR%" arelle\plugin\EdgarRenderer/s/i
rem @set FILESUFFIX="ER3"
rem )

"%PYTHON64DIR%\python" buildVersion.py %FILESUFFIX%

rem win 64 build
"%PYTHON64DIR%\python" setup.py build_exe
rem @if "%1" == "er3.814" (
rem rmdir arelle\plugin\EdgarRenderer/s/q
rem )

rem remove .git subdirectories
FOR /F "tokens=*" %%G IN ('DIR /B /AD /S %BUILT64DIR%\.git') DO RMDIR /S /Q "%%G"


@if not "%1" == "eiopa" (
"%NSISDIR%\makensis" installWin64.nsi
rem rename for build date
call buildRenameX64.bat
)

@if "%do32bitBuild%" == "true" (
rem win 32 (x86) build
"%PYTHON32DIR%\python" setup.py build_exe
rem remove .git subdirectories
FOR /F "tokens=*" %%G IN ('DIR /B /AD /S %BUILT32DIR%\.git') DO RMDIR /S /Q "%%G"
@if not "%1" == "eiopa" (
"%NSISDIR%\makensis" installWin86.nsi
rem rename for build date
call buildRenameX86.bat
)
)

@if "%1" == "eiopa" (
rem win 64 zip
cd "%BUILT64DIR%"
# remove .git subdirectories
FOR /F "tokens=*" %%G IN ('DIR /B /AD /S .git') DO RMDIR /S /Q "%%G"
"%ZIP%" a -tzip ..\..\dist\arelle-cmd64.zip *
cd ..\..
"%ZIP%" d dist\arelle-cmd64.zip arelleGUI.exe tcl86t.dll tk86t.dll tck tcl tk images scripts doc examples locale QuickBooks.qwc msvcrt.dll msvcp100.dll
rem don't remove (for bare machine) MSVCR100.dll
call buildRenameZip64.bat

rem win 32 zip
cd "%BUILT32DIR%"
# remove .git subdirectories
FOR /F "tokens=*" %%G IN ('DIR /B /AD /S .git') DO RMDIR /S /Q "%%G"
"%ZIP%" a -tzip ..\..\dist\arelle-cmd32.zip *
cd ..\..
"%ZIP%" d dist\arelle-cmd32.zip arelleGUI.exe tcl86t.dll tk86t.dll tck tcl tk images scripts doc examples locale QuickBooks.qwc msvcrt.dll msvcp100.dll
rem don't remove (for bare machine) MSVCR100.dll
call buildRenameZip32.bat
)

rem rmdir build /s/q
