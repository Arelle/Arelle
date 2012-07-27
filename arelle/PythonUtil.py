'''
Python version specific utilities

do not convert 3 to 2
'''
import sys

if sys.version[0] >= '3':
    import builtins
    builtins.__dict__['_STR_8BIT'] = str
    builtins.__dict__['_STR_BASE'] = str
    builtins.__dict__['_STR_UNICODE'] = str
    builtins.__dict__['_INT'] = int
    builtins.__dict__['_INT_TYPES'] = int
    builtins.__dict__['_NUM_TYPES'] = (int,float)
    builtins.__dict__['_STR_NUM_TYPES'] = (str,int,float)
    builtins.__dict__['_RANGE'] = range
    def noop(x): return x
    builtins.__dict__['_DICT_SET'] = noop
else:
    __builtins__['_STR_8BIT'] = str
    __builtins__['_STR_BASE'] = basestring
    __builtins__['_STR_UNICODE'] = unicode
    __builtins__['_INT'] = long
    __builtins__['_INT_TYPES'] = (int,long)
    __builtins__['_NUM_TYPES'] = (int,long,float)
    __builtins__['_STR_NUM_TYPES'] = (basestring,int,long,float)
    __builtins__['_RANGE'] = xrange
    __builtins__['_DICT_SET'] = set
   
# python 3 unquote, because py2 unquote doesn't do utf-8 correctly   
def py3unquote(string, encoding='utf-8', errors='replace'):
    """Replace %xx escapes by their single-character equivalent. The optional
    encoding and errors parameters specify how to decode percent-encoded
    sequences into Unicode characters, as accepted by the bytes.decode()
    method.
    By default, percent-encoded sequences are decoded with UTF-8, and invalid
    sequences are replaced by a placeholder character.

    unquote('abc%20def') -> 'abc def'.
    """
    if string == '':
        return string
    res = string.split('%')
    if len(res) == 1:
        return string
    if encoding is None:
        encoding = 'utf-8'
    if errors is None:
        errors = 'replace'
    # pct_sequence: contiguous sequence of percent-encoded bytes, decoded
    pct_sequence = b''
    string = res[0]
    for item in res[1:]:
        try:
            if not item:
                raise ValueError
            pct_sequence += _STR_8BIT(bytearray.fromhex(item[:2]))
            rest = item[2:]
            if not rest:
                # This segment was just a single percent-encoded character.
                # May be part of a sequence of code units, so delay decoding.
                # (Stored in pct_sequence).
                continue
        except ValueError:
            rest = '%' + item
        # Encountered non-percent-encoded characters. Flush the current
        # pct_sequence.
        string += pct_sequence.decode(encoding, errors) + rest
        pct_sequence = b''
    if pct_sequence:
        # Flush the final pct_sequence
        string += pct_sequence.decode(encoding, errors)
    return string

def pyTypeName(object):
    try:
        objectClass = object.__class__
        classModule = objectClass.__module__
        className = objectClass.__name__
        if sys.version[0] >= '3':
            if classModule == 'builtins':
                return className
        else:
            if classModule == '__builtin__':
                return className
        fullname = classModule + '.' + className
        if fullname == 'arelle.ModelValue.DateTime':
            if object.dateOnly:
                fullname += '-dateOnly'
            else:
                fullname += '-dateTime'
        return fullname
    except:
        return str(type(object))