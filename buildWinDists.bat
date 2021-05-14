rem Build Arelle GUI using cx_Freeze
rem both win 32 (x86) and win 64 (x64)

rem arguments may be eiopa, x64 x86, both
rem no argument means both

rem @set PYTHON32DIR=c:\python35x86
rem @set PYTHON64DIR=c:\python35
@set PYTHON32DIR=C:\Users\hermf\AppData\Local\Programs\Python\Python39-32
@set PYTHON64DIR=C:\Users\hermf\AppData\Local\Programs\Python\Python39

rem @set TCL_LIBRARY=c:\python35\tcl\tcl8.6
rem @set TK_LIBRARY=c:\python35\tcl\tk8.6
@set NSISDIR=C:\Program Files (x86)\NSIS

rem @set BUILT32DIR=build\exe.win32-3.5
rem @set BUILT64DIR=build\exe.win-amd64-3.5
@set BUILT32DIR=build\exe.win32-3.9
@set BUILT64DIR=build\exe.win-amd64-3.9

@set ZIP=c:\progra~1\7-zip\7z.exe

@set do64bitBuild=true
@if "%1"=="x86" set do64bitBuild=false
@set do32bitBuild=true
@if "%1"=="x64" set do32bitBuild=false

rem Rebuild messages.pot internationalization file
"%PYTHON64DIR%\python" pygettext.py -v -o arelle\locale\messages.pot arelle\*.pyw arelle\*.py
rem pause "Please check the python gettext string conversions"

rem Regenerate messages catalog (doc/messagesCatalog.xml)
"%PYTHON64DIR%\python" generateMessagesCatalog.py

rmdir %BUILT64DIR% /s/q
rmdir %BUILT32DIR% /s/q
del dist\arelle-win* /q
mkdir build
mkdir dist

@set FILESUFFIX=""


"%PYTHON64DIR%\python" buildVersion.py %FILESUFFIX%

@if "%do64bitBuild%" == "true" (
rem win 64 build
rem set TCL/TK_LIBRARY needed for cx_Freeze > 3.5
rem for 3.5 set TCL_LIBRARY=%PYTHON64DIR%\tcl\tcl8.6
rem for 3.5 set TK_LIBRARY=%PYTHON64DIR%\tcl\tk8.6
"%PYTHON64DIR%\python" setup.py build_exe
rem for 3.5 set TCL_LIBRARY=
rem for 3.5 set TK_LIBRARY=
rem fix missing DLLs for python 3.5 build
rem for 3.5 copy "%PYTHON64DIR%\DLLs\sqlite3.dll" %BUILT64DIR%
rem for 3.5 copy "%PYTHON64DIR%\DLLs\tcl86t.dll" %BUILT64DIR%
rem for 3.5 copy "%PYTHON64DIR%\DLLs\tk86t.dll" %BUILT64DIR%
rem need numpy dlls
rem for 3.5 copy "%PYTHON64DIR%\Lib\site-packages\numpy\core\*.dll" %BUILT64DIR%
rem need matplotlib mpl_toolkits
xcopy "%PYTHON64DIR%\Lib\site-packages\mpl_toolkits" %BUILT64DIR%\lib\mpl_toolkits\ /e

rem for 3.8 rename Tkinter to tkinter
rename %BUILT64DIR%\lib\Tkinter tkinter
rem copy Tktable2.11 to tk library
xcopy ..\libs\win64\Tktable2.11 %BUILT64DIR%\lib\tkinter\tk8.6 /y

rem remove .git subdirectories
FOR /F "tokens=*" %%G IN ('DIR /B /AD /S %BUILT64DIR%\.git') DO RMDIR /S /Q "%%G"

rem sign exe programs
"C:\Program Files (x86)\Windows Kits\8.1\bin\x64\signtool.exe" sign /f \\Mac\Home\Documents\code-signing\Microsoft\2019-11-10\MarkVSystems.pfx /p vZjSXa39@ /tr http://tsa.starfieldtech.com /td SHA256 %BUILT64DIR%\arelleCmdLine.exe
"C:\Program Files (x86)\Windows Kits\8.1\bin\x64\signtool.exe" sign /f \\Mac\Home\Documents\code-signing\Microsoft\2019-11-10\MarkVSystems.pfx /p vZjSXa39@ /tr http://tsa.starfieldtech.com /td SHA256 %BUILT64DIR%\arelleGui.exe

@if not "%1" == "eiopa" (
"%NSISDIR%\makensis" installWin64.nsi
rem silent install win 64 zip
cd "%BUILT64DIR%"
# remove .git subdirectories
FOR /F "tokens=*" %%G IN ('DIR /B /AD /S .git') DO RMDIR /S /Q "%%G"
del ..\..\dist\arelle-win-x64*.zip /q
"%ZIP%" a -tzip ..\..\dist\arelle-win-x64.zip *
cd ..\..
rem sign exe distributable
"C:\Program Files (x86)\Windows Kits\8.1\bin\x64\signtool.exe" sign /f \\Mac\Home\Documents\code-signing\Microsoft\2019-11-10\MarkVSystems.pfx /p vZjSXa39@ /tr http://tsa.starfieldtech.com /td SHA256 dist\arelle-win-x64.exe
rem rename for build date
call buildRenameX64.bat
)
)

@if "%do32bitBuild%" == "true" (
rem win 32 (x86) build
rem set TCL/TK_LIBRARY needed for cx_Freeze > 3.5
rem for 3.5 set TCL_LIBRARY=%PYTHON32DIR%\tcl\tcl8.6
rem for 3.5 set TK_LIBRARY=%PYTHON32DIR%\tcl\tk8.6
"%PYTHON32DIR%\python" setup.py build_exe
rem for 3.5 set TCL_LIBRARY=
rem for 3.5 set TK_LIBRARY=
rem fix missing DLLs for python 3.5 build
rem for 3.5 copy "%PYTHON32DIR%\DLLs\sqlite3.dll" %BUILT32DIR%
rem for 3.5 copy "%PYTHON32DIR%\DLLs\tcl86t.dll" %BUILT32DIR%
rem for 3.5 copy "%PYTHON32DIR%\DLLs\tk86t.dll" %BUILT32DIR%
rem need numpy dlls
rem for 3.5 copy "%PYTHON32DIR%\Lib\site-packages\numpy\core\*.dll" %BUILT32DIR%
rem need matplotlib mpl_toolkits
xcopy "%PYTHON32DIR%\Lib\site-packages\mpl_toolkits" %BUILT32DIR%\lib\mpl_toolkits\ /e

rem for 3.8 rename Tkinter to tkinter
rename %BUILT32DIR%\lib\Tkinter tkinter
rem copy Tktable2.11 to tk library
xcopy ..\libs\win32\Tktable2.11 %BUILT32DIR%\lib\tkinter\tk8.6 /y

rem remove .git subdirectories
FOR /F "tokens=*" %%G IN ('DIR /B /AD /S %BUILT32DIR%\.git') DO RMDIR /S /Q "%%G"
@if not "%1" == "eiopa" (
rem sign exe programs
"C:\Program Files (x86)\Windows Kits\8.1\bin\x64\signtool.exe" sign /f \\Mac\Home\Documents\code-signing\Microsoft\2019-11-10\MarkVSystems.pfx /p vZjSXa39@ /tr http://tsa.starfieldtech.com /td SHA256 %BUILT32DIR%\arelleCmdLine.exe
"C:\Program Files (x86)\Windows Kits\8.1\bin\x64\signtool.exe" sign /f \\Mac\Home\Documents\code-signing\Microsoft\2019-11-10\MarkVSystems.pfx /p vZjSXa39@ /tr http://tsa.starfieldtech.com /td SHA256 %BUILT32DIR%\arelleGui.exe

"%NSISDIR%\makensis" installWin86.nsi
rem sign exe distributable
"C:\Program Files (x86)\Windows Kits\8.1\bin\x64\signtool.exe" sign /f \\Mac\Home\Documents\code-signing\Microsoft\2019-11-10\MarkVSystems.pfx /p vZjSXa39@ /tr http://tsa.starfieldtech.com /td SHA256 dist\arelle-win-x86.exe
rem rename for build date
call buildRenameX86.bat
)
)

@if "%1" == "eiopa" (
rem win 64 zip
cd "%BUILT64DIR%"
# remove .git subdirectories
FOR /F "tokens=*" %%G IN ('DIR /B /AD /S .git') DO RMDIR /S /Q "%%G"
del ..\..\dist\arelle-cmd64*.zip /q
"%ZIP%" a -tzip ..\..\dist\arelle-cmd64.zip *
cd ..\..
"%ZIP%" d dist\arelle-cmd64.zip arelleGUI.exe tcl86t.dll tk86t.dll tck tcl tk images scripts doc examples locale QuickBooks.qwc msvcrt.dll msvcp100.dll
rem don't remove (for bare machine) MSVCR100.dll
"%ZIP%" d dist\arelle-cmd64.zip plugin\EdgarRenderer numpy*.pyd mkl*.dll matplotlib*.pyd
call buildRenameZip64.bat

rem win 32 zip
cd "%BUILT32DIR%"
# remove .git subdirectories
FOR /F "tokens=*" %%G IN ('DIR /B /AD /S .git') DO RMDIR /S /Q "%%G"
del ..\..\dist\arelle-cmd32*.zip /q
"%ZIP%" a -tzip ..\..\dist\arelle-cmd32.zip *
cd ..\..
"%ZIP%" d dist\arelle-cmd32.zip arelleGUI.exe tcl86t.dll tk86t.dll tck tcl tk images scripts doc examples locale QuickBooks.qwc msvcrt.dll msvcp100.dll
rem don't remove (for bare machine) MSVCR100.dll
"%ZIP%" d dist\arelle-cmd32.zip plugin\EdgarRenderer numpy*.pyd mkl*.dll matplotlib*.pyd
call buildRenameZip32.bat
)

rem rmdir build /s/q
