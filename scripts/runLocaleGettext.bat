@rem Run Internationalizable string extraction
@set PYTHONDIR=C:\python31

%PYTHONDIR%\python %PYTHONDIR%\Tools\i18n\pygettext.py --verbose --output-dir=..\locale arelle\*.pyw arelle\*.py

  