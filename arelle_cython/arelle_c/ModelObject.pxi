from arelle_c.xerces_ctypes cimport uint32_t

ctypedef enum MODEL_OBJECT_VALIDITY_STATE:
    UNVALIDATED = 0 # note that these values may be used a constants in code for better efficiency
    UNKNOWN = 1
    INVALID = 2
    NONE = 3
    VALID = 4 # values >= VALID are valid
    VALID_ID = 5
    VALID_NO_CONTENT = 6 # may be a complex type with children, must be last (after VALID with content enums)

ctypedef enum MODEL_OBJECT_SETVALUE_TYPE:
    OBJECT_VALUE = 0 # note that these enumerations may be used a constants in code for better efficiency
    SPECIFIED_ATTRIBUTE = 1 # an attribute which is not fixed or default value
    DEFAULTED_ATTRIBUTE = 2 # a value which is constraint fixed or default
    OBJECT_PROPERTY = 3 # property of object which isn't an xml-visible attribute

cdef class ModelObject:
    cdef readonly ModelDocument modelDocument
    cdef readonly uint32_t sourceline, sourcecol, elementSequence
    cdef readonly QName qname
    cdef readonly unicode id, _xmlLang, xmlBase
    cdef public bool isNil
    cdef readonly unicode _text # only provided for inline html source documents to preserve source text and white spacing
    cdef readonly unicode tail # based on input or untransformed inline source
    cdef readonly object xValue # based on PSVI of input or transformed inline values, for xsd:list, list of PSVI values
    cdef readonly MODEL_OBJECT_VALIDITY_STATE xValid
    cdef bool hasNoBase
    cdef readonly dict attrs, nsmap
    cdef readonly set defaultedAttrs
    cdef readonly long objectIndex, _elementSequence
    cdef readonly ModelObject _parent, _firstChild, _lastChild, _previousSibling, _nextSibling
    
    def __init__(self, ModelDocument modelDocument, QName qname=None, dict attrs=None, dict nsmap=None):
        cdef ModelXbrl modelXbrl = modelDocument.modelXbrl
        self.modelDocument = modelDocument
        self.qname = qname
        if attrs: # if not null and non-empty
            self.attrs = attrs
        if nsmap: # if not null and non-empty
            self.nsmap = nsmap
        self.objectIndex = len(modelXbrl.modelObjects)
        modelXbrl.modelObjects.append(self)
        self.xValid = UNVALIDATED
                    
    def __iter__(self):
        return _ModelObjectIterator(self, None, None) # children-only iterator
    
    cdef setValue(self, const XMLCh *namespace, const XMLCh *localName, object pyValue, int isAttribute):
        #print("mdlObj setV {}#{} isAttr {}".format("NULL" if namespace is NULL else transcode(namespace), transcode(localName), isAttribute))
        cdef unicode attrClarkName
        if isAttribute:
            if namespace == nElementQName:
                self.qname = pyValue
                return
            elif namespace == nValidity:
                self.xValid = pyValue
                return
            elif namespace == nNsmap:
                if self.nsmap == None:
                    self.nsmap = dict()
                self.nsmap[self.modelDocument.modelXbrl.internXMLChString(<XMLCh*>localName)] = pyValue # localName = prefix; pyValue = namespace
                return
            elif namespace[0] == chNull and equals(localName, lnId):
                self.id = pyValue
                self.modelDocument.idObjects[pyValue] = self
                return
            elif equals(namespace, nsXml):
                if equals(localName, lnBase):
                    self.xmlBase = str(pyValue) # typed value is an AnyURI
                    return
                elif equals(localName, lnLang):
                    self._xmlLang = pyValue
                    return
            elif equals(namespace, nsXsi):
                if equals(localName, lnNil):
                    if pyValue == "true" or pyValue == "1":
                        self.isNil = True
            elif equals(namespace, nElementSequence):
                self.elementSequence = pyValue
                self.modelDocument.elementSequenceObjects[pyValue] = self # only for schemas
                return
            if self.attrs is None:
                self.attrs = dict()
            attrClarkName = self.modelDocument.modelXbrl.internClarkName(namespace,NULL,localName)
            self.attrs[attrClarkName] = pyValue
            if isAttribute == DEFAULTED_ATTRIBUTE:
                if self.defaultedAttrs is None:
                    self.defaultedAttrs = set()
                self.defaultedAttrs.add(attrClarkName)
            return
        elif namespace == nElementTail:
            self.tail = pyValue
        elif namespace == nElementText: # only set for inline documents
            self._text = pyValue
        else: # namespace and localName match qname of this element
            self.xValue = pyValue
            
    cdef setSourceLineCol(self, XMLFileLoc sourceLine, XMLFileLoc sourceCol):
        self.sourceline = sourceLine
        self.sourcecol = sourceCol
                
    cdef setup(self):
        return # element and its attributes have been set
    
    def get(self, unicode clarkName, object defaultValue=None):
        if self.attrs is None:
            return defaultValue
        return self.attrs.get(clarkName, defaultValue)
    
    def set(self, unicode clarkName, object value):
        if self.attrs is None:
            self.attrs = dict()
        self.attrs[clarkName] = value
        
    def hasAttr(self, unicode clarkName):
        return self.attrs is not None and clarkName in self.attrs
        
    def delAttr(self, unicode clarkName):
        if self.attrs is not None and clarkName in self.attrs:
            del self.attrs[clarkName]
            
    def setProperty(self, name, value):
        if name == "xValue":
            self.xValue = value
        elif name == "text":
            self.text = value
        
    # note: there is no "items()" defined.  Use attrs, but it does not contain id and other built-in attributes
        
    cdef tuple keySortedAttrValues(self):
        if self.attrs is None:
            return ()
        return tuple(pyValue for 
                     clarkName, pyValue in sorted(self.attrs.items(), key=lambda k:k[0]) 
                     if not clarkName.startswith("="))
                
    cdef append(self, ModelObject child):
        if child == self:
            print("ModelObject appending to self: {}".format(self.qname))
        if child._parent is not None:
            print("ModelObject {} appending to {} already had a parent parent".format(self.qname, child.qname, child._parent.qname))
        assert child != self, "Append model object to itself"
        assert child._parent is None and child._nextSibling is None, "Append model object which already has a parent or sibling"
        child._parent = self
        if self._lastChild is None:
            self._firstChild = child
            self._lastChild = child
            child._previousSibling = None
            child._nextSibling = None
        else:
            self._lastChild._nextSibling = child
            child._previousSibling = self._lastChild
            child._nextSibling = None
            self._lastChild = child
            child._elementSequence = child._previousSibling._elementSequence + 1
                
    cdef addprevious(self, ModelObject sibling):
        assert sibling != self, "Addprevious object to itself"
        assert sibling._parent is None and sibling._nextSibling is None, "Addprevious model object which already has a parent or sibling"
        sibling._parent = self._parent
        if self._previousSibling is None:
            self._parent._firstChild = sibling
            self._previousSibling = sibling
            sibling._previousSibling = None
            sibling._nextSibling = self
        else:
            sibling._nextSibling = self
            if self._parent._firstSibling == self:
                self._parent._firstSibling = sibling
            sibling._previousSibling = self._previousSibling
            self._previousSibling = sibling
                
    cdef addnext(self, ModelObject sibling):
        assert sibling != self, "Addnext object to itself"
        assert sibling._parent is None and sibling._nextSibling is None, "Addnext model object which already has a parent or sibling"
        sibling._parent = self._parent
        if self._nextSibling is None:
            self._parent._lastChild = sibling
            self._nextSibling = sibling
            sibling._previousSibling = self
            sibling._nextSibling = None
        else:
            sibling._previousSibling = self
            if self._parent._lastSibling == self:
                self._parent._lastSibling = sibling
            sibling._nextSibling = self._nextSibling
            self._nextSibling = sibling
            
    cpdef unicode baseForElement(self):
        if self.hasNoBase:
            return None
        cdef unicode base = None
        cdef unicode _xmlBase
        cdef ModelObject baseElt = self
        cdef unicode _baseAttr
        while baseElt is not None and not baseElt.hasNoBase:
            _xmlBase = baseElt.xmlBase
            if _xmlBase:
                if base is None or _xmlBase.startswith("/"):
                    base = _xmlBase
                else:
                    base = _xmlBase + base
            baseElt = baseElt._parent
        self.hasNoBase = not base
        return base
            
    cpdef resolveUri(self, hrefObject=None, uri=None, dtsModelXbrl=None):
        """Returns the modelObject within modelDocment that resolves a URI based on arguments relative
        to this element
        
        :param hrefObject: an optional tuple of (hrefElement, modelDocument, id), or
        :param uri: An (element scheme pointer), and dtsModelXbrl (both required together if for a multi-instance href)
        :type uri: str
        :param dtsModelXbrl: DTS of href resolution (default is the element's own modelXbrl)
        :type dtsModelXbrl: ModelXbrl
        :returns: ModelObject -- Document node corresponding to the href or resolved uri
        """
        cdef ModelDocument doc
        cdef object hrefElt, xpointedElement
        cdef unicode id, url, normalizedUrl
        if dtsModelXbrl is None:
            dtsModelXbrl = self.modelXbrl
        doc = None
        if hrefObject:
            hrefElt,doc,id = hrefObject
        elif uri:
            from arelle import UrlUtil
            url, id = UrlUtil.splitDecodeFragment(uri)
            if url == "":
                doc = self.modelDocument
            else:
                normalizedUrl = self.modelXbrl.modelManager.cntlr.webCache.normalizeUrl(
                                   url, 
                                   self.modelDocument.baseForElement(self))
                doc = dtsModelXbrl.urlDocs.get(normalizedUrl)
        if isinstance(doc, ModelDocument):
            if id is None:
                return doc
            elif id in doc.idObjects:
                return doc.idObjects[id]
            else:
                from arelle.XmlUtil import xpointerElement
                return xpointerElement(doc,id)
        return None

    cpdef elementDeclaration(self, validationModelXbrl=None):
        if validationModelXbrl is not None: 
            return validationModelXbrl.qnameConcepts.get(self.qname) # use element declaration from specified modelXbr
        return self.modelDocument.modelXbrl.qnameConcepts.get(self.qname) # use this modelXbrl's element declaration
    
    cpdef isOrSubstitutesForQName(self, qn):
        cdef ModelConcept concept = self.elementDeclaration()
        if concept is not None:
            return qn == concept.qname or concept.substitutesFor(qn)
        return False
    
    def isdescendantof(self, possibleAncestor):
        cdef ModelObject e
        for e in _ModelObjectIterator(self, None, None, ancestors=True, includeSelf=False):
            if e is possibleAncestor: # reference, not __eq__ check of ob
                return True
        return False
    
    def getparent(self):
        return self._parent
                
    def getroottree(self):
        cdef ModelObject node = self
        while (node._parent is not None):
            node = node._parent
        return node
                
    def iter(self, tag=None, *tags):
        #Iterate over all elements in the subtree in document order (depth first pre-order), starting with this element.
        #
        #Can be restricted to find only elements with specific tags: pass "{ns}localname" as tag. Either or both of ns 
        #and localname can be * for a wildcard; ns can be empty for no namespace. "localname" is equivalent to 
        #"{}localname" (i.e. no namespace) but "*" is "{*}*" (any or no namespace), not "{}*".
        #
        #You can also pass the Element, Comment, ProcessingInstruction and Entity types to look only for 
        #the specific element type (e.g., ModelXlinkSimple or ModelFact).
        #
        #Passing multiple tags (or a sequence of tags) instead of a single tag will let the iterator return all e
        #lements matching any of these tags, in document order.
        #
        #For inline elements, tag is the source element QName, not the extracted element QName
        return _ModelObjectIterator(self, tag, tags, depthFirst=True, includeSelf=True)

    def iterancestors(self, tag=None, *tags):
        #Iterate over the ancestors of this element (from parent to parent).
        #Can be restricted to find only elements with specific tags, see iter.
        return _ModelObjectIterator(self, tag, tags, ancestors=True)

    def iterattrs(self):
        #Iterate over the xml attribute items of this element (from parent to parent).
        #Yields tuples of attribute clark name and xValue
        #Can use svalue function to retrieve svalue of attribute
        if self.id is not None: 
            yield (uId, self.id)
        if self.xmlBase is not None: 
            yield (uClarkXmlBase, self.xmlBase)
        if self._xmlLang is not None: 
            yield (uClarkXmlLang, self._xmlLang)
        if self.isNil == True:
            yield (uClarkXsiNil, self.isNil)
        if self.attrs is not None:
            for clarkName, pyValue in self.attrs.items():
                if not clarkName.startswith('='): # internal temp attrs start with =
                    yield (clarkName, pyValue)

    def iterchildren(self, tag=None, reversed=False, *tags):
        #Iterate over the children of this element.
        #As opposed to using normal iteration on this element, the returned elements can be reversed with the 
        #'reversed' keyword and restricted to find only elements with specific tags, see iter.
        return _ModelObjectIterator(self, tag, tags, reversed=reversed)

    def iterdescendants(self, tag=None, *tags):
        #Iterate over the descendants of this element in document order.
        #As opposed to iter(), this iterator does not yield the element itself. The returned elements can 
        #be restricted to find only elements with specific tags, see iter.
        return _ModelObjectIterator(self, tag, tags, depthFirst=True)

    def itersiblings(self, tag=None, preceding=False, *tags):
        #Iterate over the following or preceding siblings of this element.
        #The direction is determined by the 'preceding' keyword which defaults to False, i.e. forward 
        #iteration over the following siblings. When True, the iterator yields the preceding siblings in 
        #reverse document order, i.e. starting right before the current element and going backwards.
        #Can be restricted to find only elements with specific tags, see iter.
        return _ModelObjectIterator(self, tag, tags, reversed=preceding, siblings=True)
    
    def itertext(self, tag=None, with_tail=True, *tags): 
        #Iterates over the text content of a subtree.
        #You can pass tag names to restrict text content to specific elements, see iter.
        #You can set the with_tail keyword argument to False to skip over tail text.
        return _ModelObjectTextIterator(self, tag, tags, withTail=with_tail)

    @property
    def elementQName(self):
        # where qname is overridden such as by inline fact, this provides the xml element qname vs fact qname
        return self.qname

    @property
    def parentQName(self):
        # where qname is overridden such as by inline fact, this provides the xml element qname vs fact qname
        return None if self._parent is None else self._parent.qname
 
    @property
    def localName(self):
        if self.qname is not None:
            return self.qname.localName
        return None
        
    @property
    def namespaceURI(self):
        if self.qname is not None:
            return self.qname.namespaceURI
        return None
        
    @property
    def tag(self):
        if self.qname is not None:
            return self.qname.clarkNotation
        return None
        
    @property
    def prefix(self):
        if self.qname is not None:
            return self.qname.prefix
        return None
            
    @property
    def prefixedName(self):
        if self.qname is not None:
            return self.qname.prefixedName
        return None
            
    @property
    def modelXbrl(self):
        return self.modelDocument.modelXbrl
    
    def objectId(self,refId=""):
        """Returns a string surrogate representing the object index of the model document, 
        prepended by the refId string.
        :param refId: A string to prefix the refId for uniqueless (such as to use in tags for tkinter)
        :type refId: str
        """
        return "_{0}_{1}".format(refId, self.objectIndex)
    
    def prefixedNameQName(self, prefixedName):
        """Returns ModelValue.QName of prefixedName using this element and its ancestors' xmlns.
        
        :param prefixedName: A prefixed name string
        :type prefixedName: str
        :returns: QName -- the resolved prefixed name, or None if no prefixed name was provided
        """
        cdef unicode prefix, _sep, localName
        cdef ModelObject nsMdlObj
        if prefixedName:    # passing None would return element qname, not prefixedName None Qname
            prefix, _sep, localName = prefixedName.strip().rpartition(":")
            for nsMdlObj in _ModelObjectIterator(self, None, None, ancestors=True, includeSelf=True):
                if nsMdlObj.nsmap and prefix in nsMdlObj.nsmap:
                    return QName(nsMdlObj.nsmap[prefix], prefix or None, localName) # use None for absent prefix
        return None
    
    def sValue(self, xValue):
        """Returns imputed s-value for x-value argument
        :param xValue:  Typed value relative to this element
        :returns: s-value appropriate for typed value
        """
        if isinstance(xValue, list): # xs list values
            return " ".join(xValue)
        if isinstance(xValue, QName):
            return str(xValue) # if no prefix, find element's prefix for namespace
        if isinstance(xValue, (int,float,Decimal)):
            return xValue
        return str(xValue)
    
    def xmlnsPrefixNamespace(self, prefix):
        for nsMdlObj in _ModelObjectIterator(self, None, None, ancestors=True, includeSelf=True):
            if nsMdlObj.nsmap and prefix in nsMdlObj.nsmap:
                return nsMdlObj.nsmap[prefix]
        if prefix == uXml: # not normally declared explicitly
            return uriXml
        return None
    
    def xmlnsNamespacePrefix(self, namespace):
        for nsMdlObj in _ModelObjectIterator(self, None, None, ancestors=True, includeSelf=True):
            if nsMdlObj.nsmap:
                for prefix, _namespace in nsMdlObj.nsmap.items():
                    if _namespace == namespace:
                        return prefix
        if namespace == uriXml:
            return uXml
        return None
    
    def setXmlns(self, prefix, namespace):
        if self.nsmap is None:
            self.nsmap = dict()
        self.nsmap[prefix] = namespace

    @property
    def text(self): # text of just this element for inline html source documents, else determined from xValue and not stored
        if self._text is not None:
            return self._text
        elif self.xValue is None:
            return uEmptyStr
        else:
            return str(self.xValue)
    
    @property
    def stringValue(self): # recurse on descendants, overridden for inline by ModelInlineValueObject value
        return "".join(t for t in self.itertext()) # includes tail

    @property
    def textValue(self): # recurse on children, overridden for inline by ModelInlineValueObject value
        if self.text is None:
            return uEmptyStr
        return self.text

    def genLabel(self,role=None,fallbackToQname=False,fallbackToXlinkLabel=False,lang=None,strip=False,linkrole=None):
        from arelle import XbrlConst
        if role is None: role = XbrlConst.genStandardLabel
        if role == XbrlConst.conceptNameLabelRole: return str(self.qname)
        #labelsRelationshipSet = self.modelXbrl.relationshipSet(XbrlConst.elementLabel,linkrole)
        #if labelsRelationshipSet:
        #    label = labelsRelationshipSet.label(self, role, lang)
        #    if label is not None:
        #        if strip: return label.strip()
        #        return Locale.rtlString(label, lang=lang)
        if fallbackToQname:
            return str(self.qname)
        elif fallbackToXlinkLabel and self.get("xlinkLabel"):
            return self.get("xlinkLabel")
        else:
            return None

    @property
    def xmlLang(self): # xml:lang from this element or a parent of this element (html parent for inline)
        if self._xmlLang is not None:
            return self._xmlLang
        if self._parent is not None:
            return self._parent.xmlLang
        return None

    @property
    def hasXmlLang(self): # xml:lang is declared on this element
        return self._xmlLang is not None

    @xmlLang.setter
    def xmlLang(self, value): # set xml:lang onto this element
        self._xmlLang = value

    @property
    def propertyView(self):
        return (("QName", self.eqname),) + tuple(
                (XmlUtil.clarkNotationToPrefixedName(self, _tag, isAttribute=True), _value)
                for _tag, _value in self.attrs())
        
    def __repr__(self):
        return self.__str__()

    def __str__(self):
        return ("{}[{}, __{}, {}]"
                .format(type(self).__name__, self.qname, self.objectIndex, self.id))

cdef tagMatches(tag, elt): # tag is QName object, clark name string or ModelObject type (e.g., XLinkSimple)
    cdef unicode ns, _sep, ln
    if isinstance(tag, type):
        return isinstance(elt, tag)
    if tag == "*" or tag == "{*}*":
        return True
    cdef QName qname = elt.elementQName # for inline elements qname is the extracted xbrl qname, not source element quane
    if isinstance(tag, QName):
        return tag == qname
    if tag.startswith("{*}"): 
        return tag[3:] == qname.localName
    elif tag.startswith("{"):
        ns, sep, ln = tag.partition("}")
        return ns[1:] == qname.namespaceURI and (ln == "*" or ln == qname.localName)
    else: # no namespace in order to match
        return (not qname.namespaceURI) and qname.localName == tag

cdef class _ModelObjectIterator:
    cdef ModelObject _topElt
    cdef ModelObject _nextElt
    cdef tag  # tag or tags can be QName object, clark name string or ModelObject types
    cdef tags
    cdef bool reversed, siblings, ancestors, depthFirst
    def __init__(self, startingElt, tag, tags, reversed=False, ancestors=False, siblings=False, depthFirst=False, includeSelf=False):
        self.reversed = reversed
        self.siblings = siblings
        self.ancestors = ancestors
        self.depthFirst = depthFirst
        self.tag = tag
        self.tags = tags
        if startingElt is None:
            self._nextElt = None
        elif ancestors:
            if includeSelf:
                self._nextElt = startingElt
            else:
                self._nextElt = startingElt._parent
        elif siblings:
            if reversed:
                self._nextElt = startingElt._previousSibling
            else:
                self._nextElt = startingElt._nextSibling
        elif depthFirst:                     
            self._topElt = startingElt
            if includeSelf:
                self._nextElt = startingElt
            else:
                self._nextElt = startingElt._firstChild
        else: # children
            if reversed:
                self._nextElt = startingElt._lastChild
            else:
                self._nextElt = startingElt._firstChild
                    
    def __iter__(self):
        return self
    
    def __next__(self):
        cdef ModelObject _thisElt
        while self._nextElt is not None:
            _thisElt = self._nextElt
            if self.ancestors:
                self._nextElt = _thisElt._parent
            elif self.siblings or not self.depthFirst:
                if self.reversed:
                    self._nextElt = _thisElt._previousSibling
                else:
                    self._nextElt = _thisElt._nextSibling
            elif self.depthFirst:
                if _thisElt._firstChild is not None:
                    self._nextElt = _thisElt._firstChild
                elif _thisElt._nextSibling is not None:
                    self._nextElt = _thisElt._nextSibling
                elif _thisElt is self._topElt:
                    self._nextElt = None 
                else:
                    self._nextElt = _thisElt._parent
                    while self._nextElt is not None:
                        if self._nextElt is self._topElt:
                            self._nextElt = None
                            break
                        if self._nextElt._nextSibling is not None:
                            self._nextElt = self._nextElt._nextSibling
                            break
                        self._nextElt = self._nextElt._parent
            if self.tag is None:
                if not self.tags:
                    return _thisElt
            elif tagMatches(self.tag, _thisElt):
                return _thisElt
            if any(tagMatches(tag, _thisElt) for tag in self.tags):
                return _thisElt                      
        raise StopIteration
    
cdef class _ModelObjectTextIterator:
    cdef ModelObject _topElt
    cdef ModelObject _nextElt
    cdef tag
    cdef tags
    cdef unicode _nextTail
    cdef bool withTail, tailIsNext
    def __init__(self, startingElt, tag, tags, withTail=False):
        self.tag = tag
        self.tags = tags
        if startingElt is None:
            self._nextElt = None
        self._topElt = startingElt
        self._nextElt = startingElt
        self.tailIsNext = False
                    
    def __iter__(self):
        return self
    
    def __next__(self):
        cdef ModelObject _thisElt
        if self.tailIsNext:
            self.tailIsNext = False
            return self._nextTail
        if self.withTail:
            self.tailIsNext = True
        while self._nextElt is not None:
            _thisElt = self._nextElt
            if _thisElt._firstChild is not None:
                self._nextElt = _thisElt._firstChild
            elif _thisElt._nextSibling is not None:
                self._nextElt = _thisElt._nextSibling
            elif _thisElt is self._topElt:
                self._nextElt = None 
            else:
                self._nextElt = _thisElt._parent
                while self._nextElt is not None:
                    if self._nextElt is self._topElt:
                        self._nextElt = None
                        break
                    if self._nextElt._nextSibling is not None:
                        self._nextElt = self._nextElt._nextSibling
                        break
                    self._nextElt = self._nextElt._parent
            if self.tag is None:
                if not self.tags:
                    self._nextTail = _thisElt.tail
                    return _thisElt.text
            elif tagMatches(self.tag, _thisElt):
                self._nextTail = _thisElt.tail
                return _thisElt.text
            if any(tagMatches(tag, _thisElt) for tag in self.tags):
                self._nextTail = _thisElt.tail
                return _thisElt.text                     
        raise StopIteration
        
cdef class ModelComment:
    cdef readonly ModelDocument modelDocument
    cdef readonly unicode text

    def __init__(self, ModelDocument modelDocument, unicode text):
        self.modelDocument = modelDocument
        self.text = text
        
cdef class ModelProcessingInstruction:
    cdef readonly ModelDocument modelDocument
    cdef readonly unicode target, data

    def __init__(self, ModelDocument modelDocument, unicode target, unicode data):
        self.modelDocument = modelDocument
        self.target = target
        self.data = data
        
        
        
