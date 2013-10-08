rem Build Arelle GUI using cx_Freeze
rem both win 32 (x86) and win 64 (x64)

@set PYTHON32DIR=c:\python33x86
@set PYTHON64DIR=c:\python33
@set NSISDIR=C:\Program Files (x86)\NSIS
@set CMDLINEZIP=C:\Program Files (x86)\7z\7za.exe
@set BUILT32DIR=build\exe.win32-3.3
@set BUILT64DIR=build\exe.win-amd64-3.3

"%PYTHON64DIR%\python" buildVersion.py

rem Rebuild messages.pot internationalization file
"%PYTHON64DIR%\python" pygettext.py -v -o arelle\locale\messages.pot arelle\*.pyw arelle\*.py
pause "Please check the python gettext string conversions"

rem Regenerate messages catalog (doc/messagesCatalog.xml)
"%PYTHON64DIR%\python" generateMessagesCatalog.py

rmdir build /s/q
rmdir dist /s/q
mkdir build
mkdir dist

rem win 32 (x86) build
"%PYTHON32DIR%\python" setup.py build_exe
rem fix up lxml missing modules in cx_freeze build
mkdir lxml
copy "%PYTHON32DIR%\Lib\site-packages\lxml\__pycache__\_elementpath.cpython-33.pyc" lxml\_elementpath.pyc
"%CMDLINEZIP%" a "%BUILT32DIR%\library.zip" lxml\_elementpath.pyc
rmdir lxml/s/q
rem fix up pg8000 missing modules in cx_freeze build
mkdir pg8000
xcopy "%PYTHON32DIR%\Lib\site-packages\pg8000\__pycache__\*.cpython-33.pyc" pg8000 /s
"%CMDLINEZIP%" a "%BUILT32DIR%\library.zip" pg8000
rmdir pg8000/s/q
mkdir rdflib
xcopy "%PYTHON32DIR%\Lib\site-packages\rdflib-4.0.1-py3.3.egg\rdflib\__pycache__\*.cpython-33.pyc" rdflib /s
"%CMDLINEZIP%" a "%BUILT32DIR%\library.zip" rdflib
rmdir rdflib/s/q
"%NSISDIR%\makensis" installWin86.nsi
rem rename for build date
call buildRenameX86.bat

rem win 64 build
"%PYTHON64DIR%\python" setup.py build_exe
rem fix up lxml missing modules in cx_freeze build
mkdir lxml
copy "%PYTHON64DIR%\Lib\site-packages\lxml\__pycache__\_elementpath.cpython-33.pyc" lxml\_elementpath.pyc
"%CMDLINEZIP%" a "%BUILT64DIR%\library.zip" lxml\_elementpath.pyc
rmdir lxml/s/q
rem fix up pg8000 missing modules in cx_freeze build
mkdir pg8000
xcopy "%PYTHON64DIR%\Lib\site-packages\pg8000\__pycache__\*.cpython-33.pyc" pg8000 /s
"%CMDLINEZIP%" a "%BUILT64DIR%\library.zip" pg8000
rmdir pg8000/s/q
mkdir rdflib
xcopy "%PYTHON64DIR%\Lib\site-packages\rdflib-4.0.1-py3.3.egg\rdflib\__pycache__\*.cpython-33.pyc" rdflib /s
"%CMDLINEZIP%" a "%BUILT32DIR%\library.zip" rdflib
rmdir rdflib/s/q
"%NSISDIR%\makensis" installWin64.nsi
rem rename for build date
call buildRenameX64.bat

rem rmdir build /s/q
