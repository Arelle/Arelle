#!/bin/sh

# this file must have unix newlines (to prevent extraneous errors when running)
# must run sudo on ubuntu

# specify python version to build with
PYTHON=python3.5
# specify locally build python prefixed lib
LD_LIBRARY_PATH=/usr/local/lib/sparcv9
# specify latest gcc tools
PATH=/usr/local/bin:/opt/csw/bin:/usr/bin:/bin:/usr/xpg4/bin:/usr/ccs/bin:/usr/sfw/bin

# create version with date and a shell file to name output with the date
${PYTHON} buildVersion.py

# clean all previously compiled pyc files
find arelle -name '*.cpython-3?.pyc' -exec rm {} \;

BUILT64=exe.solaris-2.10-sun4v.64bit-3.5

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
${PYTHON} setup.py build_exe
# builds into sparcv9 but ziploader expects lib
cd build/${BUILT64}
mv sparcv9 lib
mkdir sparcv9
cd sparcv9
ln -s ../lib/*.zip .
cd ../../..

# add utility scripts for Arelle
cp arelle/scripts-unix/* build/${BUILT64}

ls build/${BUILT64}

# remove .git subdirectories
find build/${BUILT64} -name .git -exec rm -fR {} \;

cd build/${BUILT64}

# for now there's no tkinter on solaris sun4 (intended for server only)
rm arelle

# add missing libraries
# no longer needed when specifying LD_LIBRARY_PATH
# cp /usr/local/lib/sparcv9/libiconv.so* .
# cp /usr/local/lib/sparcv9/libintl.so* .
# cp /usr/local/lib/sparcv9/libexslt.so* .
# cp /usr/local/lib/sparcv9/libxslt.so* .
# cp /usr/local/lib/sparcv9/libxml2.so* .
# cp /usr/local/lib/sparcv9/libxslt.so* .
# cp /usr/local/lib/sparcv9/libgdbm.so* .
# cp /usr/local/lib/sparcv9/libsqlite3.so* .
# cp /usr/local/lib/sparcv9/libreadline.so* .
# cp /usr/local/lib/sparcv9/libhistory.so* .
# cp /usr/local/lib/sparcv9/libz.so* .

rm -f ../../dist/${BUILT64}.tgz 
gtar -czf ../../dist/${BUILT64}.tgz .
cd ../..

# add arelle into SEC XBRL.JAR
cd build
rm -fR arelle
mv ${BUILT64} arelle
rm -fr arelle/examples
cp /export/home/edgar/xbrl.jar ../dist
echo updating xbrl.jar
rm ../dist/xbrl.jar
cp ../dist/xbrl-without-arelle.jar ../dist/xbrl.jar
jar tvf ../dist/xbrl.jar | grep python35.zip
jar uf ../dist/xbrl.jar arelle
jar tvf ../dist/xbrl.jar | grep python35.zip
mv arelle ${BUILT64}
cd ..

/bin/sh buildRenameSol10Sun4.sh
# rm -R build2
