'''
See COPYRIGHT.md for copyright information.
'''
from hashlib import md5
from arelle.ModelObject import ModelObject
from arelle.ModelValue import QName, DateTime
from datetime import date, datetime
from arelle import XmlUtil

class Md5Sum:
    MAXMd5SUM = 0xffffffffffffffffffffffffffffffff
    def __init__(self, initialValue=0):
        if isinstance(initialValue, int):
            self.value = initialValue & Md5Sum.MAXMd5SUM
        elif isinstance(initialValue, str): # includes Md5HexValue, unicode string, py2.7 string
            self.value = int(initialValue, 16) & Md5Sum.MAXMd5SUM
        else:
            raise ValueError("MD5Sum called with {} but must be an MD5Sum or hex number"
                             .format(initialValue.__class__.__name__))
    def toHex(self):
        s = hex(self.value)[2:]
        if s.endswith('L'):
            return s[:-1]
        return s

    def __str__(self):
        return self.toHex()

    def __add__(self, other):
        if not isinstance(other, Md5Sum):
            other = Md5Sum(other)
        return Md5Sum(self.value + other.value)

    def __eq__(self, other):
        if not isinstance(other, Md5Sum):
            other = Md5Sum(other)
        return self.value == other.value

    def __ne__(self, other):
        return not (self.value == other.value)

MD5SUM0 = Md5Sum()

def md5hash(argList):
    if not isinstance(argList, (list, tuple, set)): argList = (argList,)
    _md5 = md5()
    nestedSum = MD5SUM0
    firstMd5arg = True
    for _arg in argList:
        if isinstance(_arg, Md5Sum):
            nestedSum += _arg
        else:
            if firstMd5arg:
                firstMd5arg = False;
            else:
                _md5.update(b'\x1E')
            if isinstance(_arg, QName):
                if _arg.namespaceURI:
                    _md5.update(_arg.namespaceURI.encode('utf-8','replace'))
                    _md5.update(b'\x1F')
                _md5.update(_arg.localName.encode('utf-8','replace'))
            elif isinstance(_arg, str):
                _md5.update(_arg.encode('utf-8','replace'))
            elif isinstance(_arg, datetime): # always in isodate format
                _md5.update("{0.year:04}-{0.month:02}-{0.day:02}T{0.hour:02}:{0.minute:02}:{0.second:02}".format(_arg).encode('utf-8','replace'))
            elif isinstance(_arg, date):
                _md5.update("{0.year:04}-{0.month:02}-{0.day:02}".format(_arg).encode('utf-8','replace'))
            elif isinstance(_arg, ModelObject):
                # use inner text list
                _md5.update('\x1F'.join(text.strip()
                                        for text in XmlUtil.innerTextNodes(_arg, True, False, True, False))
                            .encode('utf-8','replace'))
    if firstMd5arg:
        md5sum = MD5SUM0
    else:
        md5sum = Md5Sum(_md5.hexdigest())
    if nestedSum == MD5SUM0:
        return md5sum # no multiple terms
    return md5sum + nestedSum
