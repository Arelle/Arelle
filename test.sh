#!/usr/bin/env bash -x

if [ -d ".env" ]; then
   echo "**> virtualenv exists"
else
   echo "**> creating virtualenv"
   virtualenv-3.2 .env
fi

source .env/bin/activate

pip install -r requirements.txt

python setup.py test
