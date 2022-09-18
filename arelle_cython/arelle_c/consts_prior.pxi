from arelle_c.xerces_util cimport XMLCh, transcode, hash
#from lxbrl.consts cimport nsXsd, nsXbrli, nsLink, nsXlink, nsXhtml, nsIxbrl, nsIxbrl11, \
#    lnXbrl, lnLinkbase, lnSchema, lnXhtml, lnHtml, lnLinkbaseRef, lnSchemaRef, lnHref

cdef XMLCh* nsXsd
cdef XMLCh* nsXbrli
cdef XMLCh* nsLink
cdef XMLCh* nsXlink
cdef XMLCh* nsXhtml
cdef XMLCh* nsIxbrl
cdef XMLCh* nsIxbrl11
cdef XMLCh* nsVer
cdef XMLCh* nsRegistry
cdef XMLCh* nsNoNamespace

cdef XMLCh* lnXbrl
cdef XMLCh* lnLinkbase
cdef XMLCh* lnSchema
cdef XMLCh* lnElement
cdef XMLCh* lnId
cdef XMLCh* lnName
cdef XMLCh* lnXhtml
cdef XMLCh* lnHtml
cdef XMLCh* lnLinkbaseRef
cdef XMLCh* lnSchemaRef
cdef XMLCh* lnRoleRef
cdef XMLCh* lnArcroleRef
cdef XMLCh* lnHref
cdef XMLCh* lnReport
cdef XMLCh* lnRss
cdef XMLCh* lnTestcases
cdef XMLCh* lnDocumentation
cdef XMLCh* lnTestSuite
cdef XMLCh* lnTestcase
cdef XMLCh* lnTestSet
cdef XMLCh* lnRegistry
cdef XMLCh* lnPtvl
cdef XMLCh* lnFacts
cdef XMLCh* lnTargetNamespace
cdef XMLCh* lnAnnotation
cdef XMLCh* lnNamespace
cdef XMLCh* lnSchemaLocation
cdef XMLCh* lnRoleType
cdef XMLCh* lnArcroleType
cdef XMLCh* lnRoleRef
cdef XMLCh* lnArcroleRef
cdef XMLSize_t hRoleType
cdef XMLSize_t hArcroleType
cdef XMLSize_t hRootElement

cdef XMLCh* xmlnsPrefix
cdef XMLCh* xmlns
cdef XMLCh* syntheticAnnotation

cdef XMLCh* xmlchPipe
cdef XMLCh* xmlchLBrace
cdef XMLCh* xmlchRBrace

cdef object schemaLocationsListForLinkbases

cdef initialize_constants():
    global nsXsd, nsXbrli, nsLink, nsXlink, nsXhtml, nsIxbrl, nsIxbrl11, nsVer, nsRegistry, nsNoNamespace
    nsXsd = transcode("http://www.w3.org/2001/XMLSchema")
    nsXbrli = transcode("http://www.xbrl.org/2003/instance")
    nsLink = transcode("http://www.xbrl.org/2003/linkbase")
    nsXlink = transcode("http://www.w3.org/1999/xlink")
    nsXhtml = transcode("http://www.w3.org/1999/xhtml")
    nsIxbrl = transcode("http://www.xbrl.org/2008/inlineXBRL")
    nsIxbrl11 = transcode("http://www.xbrl.org/2013/inlineXBRL")
    nsVer = transcode("http://xbrl.org/2013/versioning-base")
    nsRegistry = transcode("http://xbrl.org/2008/registry")
    nsNoNamespace = transcode("")

    global lnXbrl, lnLinkbase, lnSchema, lnXhtml, lnHtml, lnLinkbaseRef, lnSchemaRef, lnHref, lnReport, lnRss, \
            lnTestcases, lnDocumentation, lnTestSuite, lnTestcase, lnTestSet, lnRegistry, lnPtvl, lnFacts, \
            lnTargetNamespace, lnRoleType, lnArcroleType, lnRoleRef, lnArcroleRef, lnAnnotation, \
            lnElement, lnId, lnName
    lnXbrl = transcode("xbrl")
    lnLinkbase = transcode("linkbase")
    lnSchema = transcode("schema")
    lnElement = transcode("element")
    lnId = transcode("id")
    lnName = transcode("name")
    lnXhtml = transcode("xhtml")
    lnHtml = transcode("html")
    lnLinkbaseRef = transcode("linkbaseRef")
    lnSchemaRef = transcode("schemaRef")
    lnRoleType = transcode("roleType")
    lnArcroleType = transcode("arcroleType")
    lnRoleRef = transcode("roleRef")
    lnArcroleRef = transcode("arcroleRef")
    lnHref = transcode("href")
    lnReport = transcode("report")
    lnRss = transcode("rss")
    lnTestcases = transcode("testcases")
    lnDocumentation = transcode("documentation")
    lnTestSuite = transcode("testSuite")
    lnTestcase = transcode("testcase")
    lnTestSet = transcode("testSet")
    lnRegistry = transcode("registry")
    lnPtvl = transcode("ptvl")
    lnFacts = transcode("facts")
    lnTargetNamespace = transcode("targetNamespace")
    lnAnnotation = transcode("annotation")
    
    global hashModulus, hRoleType, hArcroleType, hRootElement
    cdef XMLSize_t hashModulus = 9223372036854775807 # = 0x7fffffffffffffff
    hRoleType = hash(<char*>b'roleType', hashModulus)
    hArcroleType = hash(<char*>b'arcroleType', hashModulus)
    hRootElement = hash(<char*>b'@rootElement@', hashModulus)
    
    global xmlnsPrefix, xmlns, syntheticAnnotation, xmlchPipe, xmlchLBrace, xmlchRBrace
    xmlnsPrefix = transcode("xmlns:")
    xmlns = transcode("xmlns")
    syntheticAnnotation = transcode("Synthetic_Annotation")
    xmlchPipe = transcode("|")
    xmlchLBrace = transcode("{")
    xmlchRBrace = transcode("}")
    
    global schemaLocationsListForLinkbases
    schemaLocationsListForLinkbases = [
        "http://www.xbrl.org/2003/linkbase", "http://www.xbrl.org/2003/xbrl-linkbase-2003-12-31.xsd",
        "http://www.w3.org/1999/xlink", "http://www.xbrl.org/2003/xlink-2003-12-31.xsd",
        "http://xbrl.org/2008/generic", "http://www.xbrl.org/2008/generic-link.xsd"
        ]

