"""
@author: Mark V Systems Limited
(c) Copyright 2011 Mark V Systems Limited, All rights reserved.
"""
import six
#import lxml.etree
import arelle.ModelObject

def qname(value, name=None, noPrefixIsNoNamespace=False, castException=None, prefixException=None):
    # either value can be an etree ModelObject element: if no name then qname is element tag quanem
    #     if name provided qname uses element as xmlns reference and name as prefixed name
    # value can be namespaceURI and name is localname or prefix:localname
    # value can be prefix:localname (and localname omitted)
    # for xpath qnames which do not take default namespace if no prefix, specify noPrefixIsNoNamespace
    if isinstance(value, arelle.ModelObject.ModelObject):
        if name:
            element = value  # may be an attribute
            value = name
            name = None
        else:
            return QName(value.prefix, value.namespaceURI, value.localName)
    elif isinstance(name, arelle.ModelObject.ModelObject):
        element = name
        name = None
    elif value is None:
        element = None
        value = name
    else:
        element = None
    if isinstance(value, QName):
        return value
    elif not isinstance(value, six.string_types):
        if castException: raise castException
        return None
    if value.startswith('{'): # clark notation (with optional prefix)
        namespaceURI, sep, prefixedLocalName = value[1:].partition('}')
        prefix, sep, localName = prefixedLocalName.partition(':')
        if len(localName) == 0:
            localName = prefix
            prefix = None
    else:
        if name is not None:
            if name:  # len > 0
                namespaceURI = value
            else:
                namespaceURI = None
            value = name
        else:
            namespaceURI = None
        prefix,sep,localName = value.partition(":")
        if len(localName) == 0:
            #default namespace
            localName = prefix
            prefix = None
            if noPrefixIsNoNamespace:
                return QName(None, None, localName)
    if namespaceURI:
        return QName(prefix, namespaceURI, localName)
    elif element is not None:
        namespaceURI = element.nsmap.get(prefix)
    if not namespaceURI:
        if prefix: 
            if castException: raise castException
            return None  # error, prefix not found
    if not namespaceURI:
        namespaceURI = None # cancel namespace if it is a zero length string
    return QName(prefix, namespaceURI, localName)

#class QName(lxml.etree.QName):
#    def __init__(self, prefix, namespaceURI, localName):
#        super(QName, self).__init__(namespaceURI, localName)
#        self.prefix = prefix
#        
#    @property
#    def localName(self):
#        return self.localname
#    
#    @property
#    def namespaceURI(self):
#        return self.namespace
#    
#    @property
#    def clarkNotation(self):
#        if self.namespaceURI:
#            return '{{{0}}}{1}'.format(self.namespaceURI, self.localName)
#        else:
#            return self.localName
#    def __repr__(self):
#        return self.__str__() 
#    def __str__(self):
#        if self.prefix and self.prefix != '':
#            return self.prefix + ':' + self.localName
#        else:
#            return self.localName

class QName(object):
    def __init__(self, prefix, namespaceURI, localName):
        self.prefix = prefix
        self.namespaceURI = namespaceURI
        self.localName = localName
        self.hash = ((hash(namespaceURI) * 1000003) & 0xffffffff) ^ hash(localName)
    def __hash__(self):
        return self.hash
    @property
    def clarkNotation(self):
        if self.namespaceURI:
            return '{{{0}}}{1}'.format(self.namespaceURI, self.localName)
        else:
            return self.localName
    def __repr__(self):
        return self.__str__() 
    def __str__(self):
        if self.prefix and self.prefix != '':
            return self.prefix + ':' + self.localName
        else:
            return self.localName
    def __eq__(self,other):
        ''' don't think this is used any longer
        if isinstance(other,str):
            # only compare nsnames {namespace}localname format, if other has same hash
            return self.__hash__() == other.__hash__() and self.clarkNotation == other
        el
        '''
        if isinstance(other, QName):
            return self.hash == other.hash and \
                    self.namespaceURI == other.namespaceURI and self.localName == other.localName
        elif isinstance(other, arelle.ModelObject.ModelObject):
            return self.namespaceURI == other.namespaceURI and self.localName == other.localName
        return False
    def __ne__(self,other):
        return not self.__eq__(other)
    def __lt__(self,other):
        return (self.namespaceURI is None and other.namespaceURI) or \
                (self.namespaceURI and other.namespaceURI and self.namespaceURI < other.namespaceURI) or \
                (self.namespaceURI == other.namespaceURI and self.localName < other.localName)
    def __le__(self,other):
        return (self.namespaceURI is None and other.namespaceURI) or \
                (self.namespaceURI and other.namespaceURI and self.namespaceURI < other.namespaceURI) or \
                (self.namespaceURI == other.namespaceURI and self.localName <= other.localName)
    def __gt__(self,other):
        return (self.namespaceURI and other.namespaceURI is None) or \
                (self.namespaceURI and other.namespaceURI and self.namespaceURI > other.namespaceURI) or \
                (self.namespaceURI == other.namespaceURI and self.localName > other.localName)
    def __ge__(self,other):
        return (self.namespaceURI and other.namespaceURI is None) or \
                (self.namespaceURI and other.namespaceURI and self.namespaceURI > other.namespaceURI) or \
                (self.namespaceURI == other.namespaceURI and self.localName >= other.localName)