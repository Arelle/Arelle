Xerces c-dev mailing list http://mail-archives.apache.org/mod_mbox/xerces-c-dev/
       c-users http://mail-archives.apache.org/mod_mbox/xerces-c-users/
Bug report to JIRA http://issues.apache.org/jira/browse/XERCESC



Xerces changes needed

xmlns on element holding QName data https://issues.apache.org/jira/browse/XERCESC-2193

1) Testcase 160 V08 <xsd readMeFirst="true">UsedOnSEquality-valid.xsd</xsd>

<link:usedOn xmlns:this="http://example.com/this">this:someArc</link:usedOn>
<link:usedOn xmlns:this="http://example.com/that">this:someArc</link:usedOn>

Unexpected error for this: [xmlSchema:xerces] undefined prefix in QName value 'this:someArc' - /Users/hermf/Documents/mvsl/projects/XBRL.org/conformance-svn/trunk/Common/100-schema/UsedOnSEquality-valid.xsd 16[81]

In xercesc\validators\datatype\QNameDatatypeValidator.cpp in isPrefixUnknown
            if (context->isPrefixUnknown(prefix)) {
                ThrowXMLwithMemMgr1(InvalidDatatypeValueException
                    , XMLExcepts::VALUE_QName_Invalid2
                    , content
                    , manager);             
            }                                  
In xercesc\internal\ValidationContextImpl.cpp
 not checking current element
    else if (!XMLString::equals(prefix, XMLUni::fgXMLString)) {
        if(fElemStack && !fElemStack->isEmpty())
            fElemStack->mapPrefixToURI(prefix, unknown);
        else if(fNamespaceScope)
            unknown = (fNamespaceScope->getNamespaceForPrefix(prefix)==fNamespaceScope->getEmptyNamespaceId());
    }

2) Testcase 214-lax-validation-02.xsd does not validate xml:space when LAX

3) 214-lax-validation-04.xsd xml:lang (same)

4) PATCH for xsi:nil allow 0 and 1 (in addition to true/false

in xercesc\internal\SGXMLScanner2.cpp method scanRawAttrListforNameSpaces
line 3555 add 0/1 and fix emitError attr name ptr

from:
                        if(XMLString::equals(fXsiNil.getRawBuffer(), SchemaSymbols::fgATTVAL_TRUE))
                            ((SchemaValidator*)fValidator)->setNillable(true);
                        else if(XMLString::equals(fXsiNil.getRawBuffer(), SchemaSymbols::fgATTVAL_FALSE))
                            ((SchemaValidator*)fValidator)->setNillable(false);
                        else
                            emitError(XMLErrs::InvalidAttValue, fXsiNil.getRawBuffer(), valuePtr);

to:
                        if(XMLString::equals(fXsiNil.getRawBuffer(), SchemaSymbols::fgATTVAL_TRUE))
                            ((SchemaValidator*)fValidator)->setNillable(true);
                        else if(XMLString::equals(fXsiNil.getRawBuffer(), XMLUni::fgValueOne))
                            ((SchemaValidator*)fValidator)->setNillable(true);
                        else if(XMLString::equals(fXsiNil.getRawBuffer(), SchemaSymbols::fgATTVAL_FALSE))
                            ((SchemaValidator*)fValidator)->setNillable(false);
                        else if(XMLString::equals(fXsiNil.getRawBuffer(), XMLUni::fgValueZero))
                            ((SchemaValidator*)fValidator)->setNillable(false);
                        else
                            emitError(XMLErrs::InvalidAttValue, fXsiNil.getRawBuffer(), rawPtr);

