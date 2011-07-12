#!/usr/bin/env bash

if [ -d ".virtualenv" ]; then
   echo "**> virtualenv exists"
else
   echo "**> creating virtualenv"
   virtualenv --distribute --no-site-packages -p `which python3.2` .virtualenv
fi

source .virtualenv/bin/activate

pip install -r requirements.txt

patch .virtualenv/lib/python3.2/site-packages/nose/case.py tests/case.py.patch
patch .virtualenv/lib/python3.2/site-packages/nose/loader.py tests/loader.py.patch

python setup.py test

exit 0
