rem Build Arelle 27 server distribution

@set PYTHON27DIR=c:\python27
@set PYTHON64DIR=c:\python32
"%PYTHON64DIR%\python" buildVersion.py

@set CMDLINEZIP=C:\Program Files (x86)\7z\7za.exe
@set BUILT27DIR=build\svr-2.7

mkdir build
rmdir %BUILT27DIR% /s/q
mkdir %BUILT27DIR%
mkdir dist

copy arelleCmdLine.py %BUILT27DIR%
copy arelle_test.py %BUILT27DIR%
copy conftest.py %BUILT27DIR%
copy app.yaml %BUILT27DIR%
copy backends.yaml %BUILT27DIR%
mkdir %BUILT27DIR%\arelle
xcopy arelle %BUILT27DIR%\arelle /s
del %BUILT27DIR%\*.pyc /s
del %BUILT27DIR%\arelle\pyparsing\*.py* /q
rmdir %BUILT27DIR%\arelle\scripts-macOS /s/q
rmdir %BUILT27DIR%\arelle\scripts-unix /s/q
rmdir %BUILT27DIR%\arelle\scripts-windows /s/q
copy arelle\scripts-unix\*.* %BUILT27DIR%

rem delete GUI modules
del %BUILT27DIR%\*.pyw /s
del %BUILT27DIR%\arelle\CntlrQuickBooks.py
del %BUILT27DIR%\arelle\CntlrWinMain.py
del %BUILT27DIR%\arelle\CntlrWinTooltip.py
del %BUILT27DIR%\arelle\Dialog*.py /s
del %BUILT27DIR%\arelle\plugin\Dialog*.py
del %BUILT27DIR%\arelle\UiUtil.py
del %BUILT27DIR%\arelle\ViewWin*.py
del %BUILT27DIR%\arelle\WatchRss.py
%PYTHON27DIR%\python %PYTHON27DIR%\Scripts\3to2 -w %BUILT27DIR%
rem %PYTHON27DIR%\python %PYTHON27DIR%\Scripts\3to2 -w %BUILT27DIR%\webserver
rem %PYTHON27DIR%\python %PYTHON27DIR%\Scripts\3to2 -w %BUILT27DIR%\xlrd
rem %PYTHON27DIR%\python %PYTHON27DIR%\Scripts\3to2 -w %BUILT27DIR%\xlwt
del %BUILT27DIR%\*.bak /s

rem copy non-converted PythonUtil.py (to block 3to2 conversions
copy /Y arelle\PythonUtil.py %BUILT27DIR%\arelle\PythonUtil.py
rem copy bottle that works on 2.7
copy /Y arelle\webserver\bottle.py %BUILT27DIR%\arelle\webserver\bottle.py
rem copy pyparsing that works on 2.7
copy /Y arelle\pyparsing\__init__.py %BUILT27DIR%\arelle\pyparsing
copy /Y arelle\pyparsing\pyparsing_py2.py2 %BUILT27DIR%\arelle\pyparsing\pyparsing_py2.py

del /Q "dist\\arelle-svr-2.7*.zip"
cd build
"%CMDLINEZIP%" a "..\\dist\\arelle-svr-2.7.zip" svr-2.7
cd ..

rem rename for build date
call buildRenameSvr27.bat

