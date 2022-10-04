'''
See COPYRIGHT.md for copyright information.

This module encodes a source python file (from utf-8 to ascii with \\u escapes).

'''
import datetime, sys

if __name__ == "__main__":
    with open(sys.argv[1], "rt", encoding="utf-8") as fIn:
        with open(sys.argv[2], "wb") as fOut:
            while True:
                line = fIn.readline()
                if not line:
                    break
                if '# -*- coding: utf-8 -*-' not in line:
                    fOut.write(line.encode('ascii', 'backslashreplace'))

