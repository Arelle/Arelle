#!/bin/sh

# this file must have unix newlines (to prevent extraneous errors when running)
# must run sudo on ubuntu

if [ ! -d log ]
  then
    mkdir log
fi

# run tests
#python3.2 /usr/local/bin/py.test --tests=myIniWithPassword.ini -junittests=foo.xml
#nice python3.2 /usr/local/bin/py.test-3.2 -n 8 --junitxml=/var/www/hermf/pyTestResults.xml
nohup nice python3.3 /usr/local/bin/py.test-3.3  --junitxml=/var/www/hermf/pyTestResults.xml > log/pyTest33.log &

# run 2.7
nohup nice ./build27Dist.sh > log/build27.log; ./runPyTest27.sh > log/pyTest27.log &
