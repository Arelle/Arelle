rem Start Arelle XBRL COM server

@set PYTHONDIR=c:\python32
@set PYTHONPATH=..

"%PYTHONDIR%\python" -m arelle.CntlrCmdLine --webserver localhost:8080
