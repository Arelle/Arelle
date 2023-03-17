'''
Sample custom functions plugin for formula XML Element, Attribute creation functions

>>> note that this function has been renamed xfi:create-element and moved to FunctionXfi.py <<<

See COPYRIGHT.md for copyright information.
'''
from arelle import XbrlUtil
from arelle.formula import XPathContext
from arelle.ModelValue import qname, QName
from arelle.ModelInstanceObject import ModelDimensionValue, XmlUtil
from arelle.FunctionUtil import qnameArg, nodeArg, atomicArg
from arelle.Version import authorLabel, copyrightLabel
from arelle import XmlValidate
from lxml import etree

'''
Create an XML element in a "scratchpad" in-memory XML document, to behave like the results
of an fn:doc() that would provide XML elements which can be consumed by formula typed
dimension and OCC constructs.

The element may be created with attributes and descendant elements, as needed.

xfxc:element(
    qname,  // qname of element
    (name-value pairs for creating attributes if any),
    value, if any, otherwise () or ''
    optional nested elements (e.g., xfc:element( ) ... of child nodes)
    )

Attributes may be pairs of string name, value, or pairs of QName, value when attribute
name is qualified.

A function definition is required in the formula linkbase:
<variable:function name="xfxc:element" output="element()" xlink:type="resource" xlink:label="cust-fn-xfxc-create">
  <variable:input type="xs:QName" />  <!-- qname of element to create -->
  <variable:input type="xs:anyAtomicType*" /> <!-- sequence of name, value pairs for creating attributes (name can be string or QName) -->
  <variable:input type="xs:anyAtomicType" /> <!-- optional value, () or '' if none -->
  <variable:input type="element()*" /> <!-- optional sequence of child elements, this parameter can be omitted if no child elements -->
</variable:function>
'''
def  xfxc_element(xc, p, contextItem, args):
    if not 2 <= len(args) <= 4: raise XPathContext.FunctionNumArgs()
    qn = qnameArg(xc, p, args, 0, 'QName', emptyFallback=None)
    attrArg = args[1] if isinstance(args[1],(list,tuple)) else (args[1],)
    # attributes have to be pairs
    if attrArg:
        if len(attrArg) & 1 or any(not isinstance(attrArg[i], (QName, str))
                                   for i in range(0, len(attrArg),2)):
            raise XPathContext.FunctionArgType(1,"((xs:qname|xs:string),xs:anyAtomicValue)", errCode="xfxce:AttributesNotNameValuePairs")
        else:
            attrParam = [(attrArg[i],attrArg[i+1]) # need name-value pairs for XmlUtil function
                         for i in range(0, len(attrArg),2)]
    else:
        attrParam = None

    value = atomicArg(xc, p, args, 2, "xs:anyAtomicType", emptyFallback='')
    if not value: # be sure '' is None so no text node is created
        value = None
    if len(args) < 4:
        childElements = None
    else:
        childElements = xc.flattenSequence(args[3])

    # scratchpad instance document emulates fn:doc( ) to hold XML nodes
    scratchpadXmlDocUrl = "http://www.xbrl.org/2012/function/creation/xml_scratchpad.xml"
    if scratchpadXmlDocUrl in xc.modelXbrl.urlDocs:
        modelDocument = xc.modelXbrl.urlDocs[scratchpadXmlDocUrl]
    else:
        # create scratchpad xml document
        # this will get the fake instance document in the list of modelXbrl docs so that it is garbage collected
        from arelle import ModelDocument
        modelDocument = ModelDocument.create(xc.modelXbrl,
                                             ModelDocument.Type.UnknownXML,
                                             scratchpadXmlDocUrl,
                                             initialXml="<xfc:dummy xmlns:xfc='http://www.xbrl.org/2012/function/creation'/>")

    newElement = XmlUtil.addChild(modelDocument.xmlRootElement,
                                  qn,
                                  attributes=attrParam,
                                  text=value)
    if childElements:
        for element in childElements:
            if isinstance(element, etree.ElementBase):
                newElement.append(element)

    # node myst be validated for use in instance creation (typed dimension references)
    XmlValidate.validate(xc.modelXbrl, newElement)

    return newElement

def xfxcFunctions():
    return {
        qname("{http://www.xbrl.org/2012/function/xml-creation}xfxc:element"): xfxc_element,
    }

__pluginInfo__ = {
    'name': 'Formula Xml Creation Functions',
    'version': '1.0',
    'description': "This plug-in adds a custom function to create xml elements, such as for typed dimensions, implemented by a plug-in.  ",
    'license': 'Apache-2',
    'author': authorLabel,
    'copyright': copyrightLabel,
    # classes of mount points (required)
    'Formula.CustomFunctions': xfxcFunctions,
}
