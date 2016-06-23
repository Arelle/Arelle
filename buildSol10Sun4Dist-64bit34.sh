#!/bin/sh

# this file must have unix newlines (to prevent extraneous errors when running)
# must run sudo on ubuntu

PYTHON=python3.4

# create version with date and a shell file to name output with the date
${PYTHON} buildVersion.py

# clean all previously compiled pyc files
find arelle -name '*.cpython-3?.pyc' -exec rm {} \;

BUILT64=exe.solaris-2.10-sun4v.64bit-3.4

if [ -d build/${BUILT64} ]
  then
    rm -fR build/${BUILT64}
fi
mkdir build/${BUILT64}

if [ ! -d dist ]
  then
    mkdir dist
fi

# run cx_Freeze setup
${PYTHON} setup.py build
cp arelle/scripts-unix/* build/${BUILT64}

# remove .git subdirectories
find $BUILT64 -name .git -exec rm -fR {} \;

cd build/${BUILT64}

# for now there's no tkinter on solaris sun4 (intended for server only)
# rm arelleGUI

# add missing libraries
cp /usr/local/lib/sparcv9/libiconv.so* .
cp /usr/local/lib/sparcv9/libintl.so* .
cp /usr/local/lib/sparcv9/libexslt.so* .
cp /usr/local/lib/sparcv9/libxslt.so* .
cp /usr/local/lib/sparcv9/libxml2.so* .
cp /usr/local/lib/sparcv9/libxslt.so* .
cp /usr/local/lib/sparcv9/libgdbm.so* .
cp /usr/local/lib/sparcv9/libsqlite3.so* .
cp /usr/local/lib/sparcv9/libreadline.so* .
cp /usr/local/lib/sparcv9/libhistory.so* .
cp /usr/local/lib/sparcv9/libz.so* .

tar -cf ../../dist/${BUILT64}.tar .
gzip ../../dist/${BUILT64}.tar
cd ../..

# add arelle into SEC XBRL.JAR
cd build
mv ${BUILT64} arelle
rm -fr arelle/examples
cp /export/home/edgar/xbrl.jar ../dist
echo updating xbrl.jar
jar tvf ../dist/xbrl.jar | grep library.zip
jar uf ../dist/xbrl.jar arelle
jar tvf ../dist/xbrl.jar | grep library.zip
jar uf ../dist/xbrl.jar arelle
mv arelle ${BUILT64}
cd ..

/bin/sh buildRenameSol10Sun4.sh
# rm -R build2
