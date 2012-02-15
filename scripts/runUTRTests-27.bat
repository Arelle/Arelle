@rem Run UTR tests
@set CONFROOT=C:\home\conformance-lrr\trunk\schema\utr\conf

@set FILENAME=ng_DerivedAreaItemType_xacre.xml

@set FILENAME=gd.xml

@set FILENAME=ng_AreaItemType_u1.xml

@set FILENAME=index.xml

@set PYTHONDIR=c:\python27
@set PYTHONPATH=..\build\2.7

"%PYTHONDIR%\python" -m arelle.CntlrCmdLine --file %CONFROOT%\%FILENAME% --validate --utr --csvTestReport foo.csv
@rem | tee "C:\tmp\UTR-test.log" 2>&1

  