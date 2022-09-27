rem Build Arelle GUI using cx_Freeze

@set PYTHONDIR=c:\python32x86
@set NSISDIR=C:\Program Files (x86)\NSIS
@set BUILTDIR=build\exe.win32-3.2

rem rmdir build /s/q
rmdir dist /s/q
mkdir dist
"%PYTHONDIR%\python" distro.py build_exe

"%NSISDIR%\makensis" installWin86.nsi

rem compact /c /f dist\exe.win32-3.2.exe