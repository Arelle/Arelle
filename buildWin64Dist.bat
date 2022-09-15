rem Build Arelle GUI using cx_Freeze

@set PYTHONDIR=c:\python32
@set NSISDIR=C:\Program Files (x86)\NSIS
@set BUILTDIR=build\exe.win-amd64-3.2

rem rmdir build /s/q
rmdir dist /s/q
mkdir dist
"%PYTHONDIR%\python" distro.py build_exe

"%NSISDIR%\makensis" installWin64.nsi

rem compact /c /f dist\arelle-win-x64.exe