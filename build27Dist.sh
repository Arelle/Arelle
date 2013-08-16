#!/bin/sh

# Build Arelle 27 server distribution

# create version with date and a shell file to name output with the date
python3.2 buildVersion.py

BUILT27DIR=../svr-2.7

rm -f -r ${BUILT27DIR}
mkdir ${BUILT27DIR}

cp arelleCmdLine.py arelle_test.py conftest.py app.yaml backends.yaml ${BUILT27DIR}
mkdir ${BUILT27DIR}/arelle
cp -R arelle ${BUILT27DIR}
rm -f -r ${BUILT27DIR}/*.pyc
rm -f -r ${BUILT27DIR}/arelle/pyparsing/*
rm -f -r ${BUILT27DIR}/arelle/scripts-macOS
rm -f -r ${BUILT27DIR}/arelle/scripts-unix
rm -f -r ${BUILT27DIR}/arelle/scripts-windows
cp arelle/scripts-unix/* ${BUILT27DIR}

# defer processing plugins
rm -f -r  ${BUILT27DIR}/arelle/plugin

# delete GUI modules
rm -f -r ${BUILT27DIR}/*.pyw
rm -f ${BUILT27DIR}/arelle/CntlrQuickBooks.py
rm -f ${BUILT27DIR}/arelle/CntlrWinMain.py
rm -f ${BUILT27DIR}/arelle/CntlrWinTooltip.py
find ${BUILT27DIR}/arelle -name 'Dialog*.py' -print0 | xargs -0 rm -f
rm -f ${BUILT27DIR}/arelle/UiUtil.py
rm -f ${BUILT27DIR}/arelle/ViewWin*.py
rm -f ${BUILT27DIR}/arelle/WatchRss.py
# convert all except plugins
python2.7 /usr/local/bin/3to2 -w ${BUILT27DIR}
# convert plugins
cp -R arelle/plugin ${BUILT27DIR}/arelle
# encode programs with utf-8 source
python3.2 encodeUtf8PySource.py arelle/plugin/loadFromExcel.py ${BUILT27DIR}/arelle/plugin/loadFromExcel.py
python3.2 encodeUtf8PySource.py arelle/plugin/saveLoadableExcel.py ${BUILT27DIR}/arelle/plugin/saveLoadableExcel.py
python2.7 /usr/local/bin/3to2 -w ${BUILT27DIR}/arelle/plugin
#python2.7 /usr/local/bin/3to2 -w ${BUILT27DIR}/webserver
#python2.7 /usr/local/bin/3to2 -w ${BUILT27DIR}/xlrd
#python2.7 /usr/local/bin/3to2 -w ${BUILT27DIR}/xlwt
rm -f -r ${BUILT27DIR}/*.bak

# copy non-converted PythonUtil.py (to block 3to2 conversions
cp arelle/PythonUtil.py ${BUILT27DIR}/arelle/PythonUtil.py
# copy bottle that works on 2.7
cp arelle/webserver/bottle.py ${BUILT27DIR}/arelle/webserver/bottle.py
# copy pyparsing that works on 2.7
cp arelle/pyparsing/__init__.py ${BUILT27DIR}/arelle/pyparsing/__init__.py
cp arelle/pyparsing/pyparsing_py2.py2 ${BUILT27DIR}/arelle/pyparsing/pyparsing_py2.py


