#!/bin/sh

# this file must have unix newlines (to prevent extraneous errors when running)
# must run sudo on ubuntu

# create version with date and a shell file to name output with the date
PYTHON=/home/hermf/Python39/bin/python3.9
export LD_LIBRARY_PATH=/home/hermf/Python39/lib

$PYTHON buildVersion.py redhat

BUILT64=exe.linux-x86_64-3.9

if [ -d build/${BUILT64} ]
  then
    rm -fR build/${BUILT64}
fi
mkdir build/${BUILT64}

if [ ! -d dist ]
  then
    mkdir dist
fi

rm -f dist/arelle-redhat*

# run cx_Freeze setup
$PYTHON setup.py build_exe
cp arelle/scripts-unix/* build/${BUILT64}

# remove .git subdirectories
find build/${BUILT64} -name .git -exec rm -fR {} \;

# copy red hat libraries needed
cp -p /usr/lib64/libexslt.so.0 build/${BUILT64}
cp -p /usr/lib64/libxml2.so build/${BUILT64}
# for some reason redhat needs libxml2.so.2 as well
cp -p /usr/lib64/libxml2.so.2 build/${BUILT64}
cp -p /usr/lib64/libxslt.so.1 build/${BUILT64}
cp -p /lib64/libz.so.1 build/${BUILT64}
cp -pR ${LD_LIBRARY_PATH}/Tktable2.11 build/${BUILT64}
cp -pR ${LD_LIBRARY_PATH}/python3.9/site-packages/mpl_toolkits build/${BUILT64}/lib
cp -pR ${LD_LIBRARY_PATH}/python3.9/site-packages/numpy.libs build/${BUILT64}/lib
cp -pR ${LD_LIBRARY_PATH}/python3.9/site-packages/Pillow.libs build/${BUILT64}/lib

cd build/${BUILT64}
tar -czf ../../dist/${BUILT64}.tgz .
cd ../..

/bin/sh buildRenameLinux-x86_64.sh
# rm -R build2
