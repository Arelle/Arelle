"""
See COPYRIGHT.md for copyright information.
"""

from typing import TYPE_CHECKING, Optional

from arelle.ModelValue import QName, qname
from arelle.oim.Load import OIMException
from arelle.PythonUtil import OrderedSet
from .XbrlTypes import XbrlModuleType, SQNameKeyType
from .XbrlObject import XbrlReferencableModelObject

class XbrlUnit(XbrlReferencableModelObject):
    module: XbrlModuleType
    name: SQNameKeyType # (required) The unitQName that identifies the unit so it can be referenced by other objects.
    dataType: QName # (required) Indicates the dataType of the unit. These are provided as a QName based on the datatypes specified in the XBRL 2.1 specification and any custom datatype defined in the taxonomy.
    dataTypeNumerator: Optional[QName] # (optional) Indicates the dataType of the unit numerator when the unit is comprised of a division of two datatypes. This is an optional property and must be used with dataTypeDenominator
    stringRepresentations: OrderedSet[str] # (optional) An ordered set of string representations of the unit. Each string representation is a string as defined in the OIM report specification.

def parseUnitString(uStr, unitObj, reportObj, txmyMdl):
    _mul, _sep, _div = uStr.partition('/')
    if _mul.startswith('('):
        _mul = _mul[1:-1]
    _muls = [u for u in _mul.split('*') if u]
    if _div.startswith('('):
        _div = _div[1:-1]
    _divs = [u for u in _div.split('*') if u]
    if _muls != sorted(_muls) or _divs != sorted(_divs):
        txmyMdl.error("oimce:invalidUnitStringRepresentation",
              _("Unit string representation measures are not in alphabetical order, %(unit)s, %(objectName)s id %(name)s"),
              xbrlObject=unitObj, name=unitObj.name,  objectName=type(unitObj).__name__, unit=uStr)
    try:
        mulQns = tuple(qname(u, reportObj._prefixNamespaces, prefixException=OIMException("oimce:unboundPrefix",
                                                                  _("Unit prefix is not declared: %(unit)s, %(objectName)s id %(name)s"),
                                                                  unit=u, name=unitObj.name, objectName=type(unitObj).__name__))
                       for u in _muls)
        divQns = tuple(qname(u, reportObj._prefixNamespaces, prefixException=OIMException("oimce:unboundPrefix",
                                                                  _("Unit prefix is not declared: %(unit)s, %(objectName)s id %(name)s"),
                                                                  unit=u, name=unitObj.name, objectName=type(unitObj).__name__))
                       for u in _divs)
        return (mulQns,divQns)
    except OIMException as ex:
        txmyMdl.error(ex.code, ex.message, xbrlObject=unitObj, **ex.msgArgs)
    return ((),())
