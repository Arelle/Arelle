rem Start Arelle XBRL COM server

@set PYTHONDIR=c:\python27
@set PYTHONPATH=..\build\svr-2.7

"%PYTHONDIR%\python" -m arelle.CntlrCmdLine --webserver localhost:8080
