rem Build Arelle 27 server distribution

@set PYTHON27DIR=c:\python27
@set CMDLINEZIP=C:\Program Files (x86)\7z\7za.exe
@set BUILT27DIR=build\2.7

mkdir build
rmdir %BUILT27DIR% /s/q
mkdir %BUILT27DIR%
mkdir dist

copy *.py %BUILT27DIR%
mkdir %BUILT27DIR%\arelle
xcopy arelle %BUILT27DIR%\arelle /s
del %BUILT27DIR%\*.pyc /s
rmdir %BUILT27DIR%\arelle\pyparsing /s/q
rmdir %BUILT27DIR%\arelle\scripts-macOS /s/q
rmdir %BUILT27DIR%\arelle\scripts-unix /s/q
rmdir %BUILT27DIR%\arelle\scripts-windows /s/q
copy arelle\scripts-unix\*.* %BUILT27DIR%

rem delete GUI modules
del %BUILT27DIR%\*.pyw /s
del %BUILT27DIR%\arelle\CntlrQuickBooks.py
del %BUILT27DIR%\arelle\CntlrWinMain.py
del %BUILT27DIR%\arelle\CntlrWinTooltip.py
del %BUILT27DIR%\arelle\Dialog*.py
del %BUILT27DIR%\arelle\UiUtil.py
del %BUILT27DIR%\arelle\ViewWin*.py
del %BUILT27DIR%\arelle\WatchRss.py
%PYTHON27DIR%\python %PYTHON27DIR%\Scripts\3to2 -w %BUILT27DIR%
%PYTHON27DIR%\python %PYTHON27DIR%\Scripts\3to2 -w %BUILT27DIR%\webserver
%PYTHON27DIR%\python %PYTHON27DIR%\Scripts\3to2 -w %BUILT27DIR%\xlrd
%PYTHON27DIR%\python %PYTHON27DIR%\Scripts\3to2 -w %BUILT27DIR%\xlwt
del %BUILT27DIR%\*.bak /s

rem copy non-converted PythonUtil.py (to block 3to2 conversions
copy /Y arelle\PythonUtil.py %BUILT27DIR%\arelle\PythonUtil.py
rem copy bottle that works on 2.7
copy /Y arelle\webserver\bottle-no2to3.py %BUILT27DIR%\arelle\webserver\bottle.py

rem "%CMDLINEZIP%" a "%BUILT32DIR%\library.zip" lxml\_elementpath.pyc
