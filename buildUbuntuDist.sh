#!/bin/sh

# this file must have unix newlines (to prevent extraneous errors when running)
# must run sudo on ubuntu

# create version with date and a shell file to name output with the date

# private version of python and library
export PATH=${PATH}:/home/parallels/Python39/bin
export LD_LIBRARY_PATH=/home/parallels/Python39/lib

python3.9 buildVersion.py ubuntu

LIBDIR=/home/parallels/Python39/lib
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

rm -f dist/arelle-ubuntu*

# run cx_Freeze setup
python3.9 setup.py build_exe
cp arelle/scripts-unix/* build/${BUILT64}
cp -pR ${LIBDIR}/Tktable2.11 build/${BUILT64}/lib
cp -pR ${LIBDIR}/python3.9/site-packages/mpl_toolkits build/${BUILT64}/lib
cp -pR ${LIBDIR}/python3.9/site-packages/numpy.libs build/${BUILT64}/lib
cp -pR ${LIBDIR}/python3.9/site-packages/Pillow.libs build/${BUILT64}/lib

cd build/${BUILT64}
tar -czf ../../dist/${BUILT64}.tgz .
cd ../..

/bin/sh buildRenameLinux-x86_64.sh
# rm -R build2
