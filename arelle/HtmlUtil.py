'''
See COPYRIGHT.md for copyright information.
'''
from __future__ import annotations


def attrValue(str: str, name: str | None = None) -> str:
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
