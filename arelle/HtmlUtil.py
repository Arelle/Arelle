'''
Created on April 14, 2011

@author: Mark V Systems Limited
(c) Copyright 2011 Mark V Systems Limited, All rights reserved.
'''
try:
    import regex as re
except ImportError:
    import re

def attrValue(str, name):
    # retrieves attribute in a string, such as xyz="abc" or xyz='abc' or xyz=abc; 
    prestuff, matchedName, valuePart = str.lower().partition("charset")
    value = []
    endSep = None
    beforeEquals = True
    for c in valuePart:
        if value:
            if c == endSep or c.isspace() or c in (';'):
                break
            value.append(c)
        elif beforeEquals:
            if c == '=':
                beforeEquals = False
        else:
            if c in ('"', "'"):
                endSep = c
            elif c == ';':
                break
            elif not c.isspace():
                value.append(c)
    return ''.join(value)
