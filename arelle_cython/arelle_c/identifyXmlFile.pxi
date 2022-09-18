from arelle_c.xerces_util cimport compareString, compareIString, transcode, release, XMLCh, XMLSize_t
from arelle_c.xerces_sax cimport SAXParseException, ErrorHandler
from arelle_c.xerces_framework cimport XMLPScanToken
from arelle_c.xerces_sax2 cimport createXMLReader, SAX2XMLReader, ContentHandler, LexicalHandler, DefaultHandler
from cython.operator cimport dereference as deref
from libcpp cimport bool
from arelle_c.xerces_sax cimport InputSource, DocumentHandler, ErrorHandler, SAXParseException, Locator
from arelle_c.xerces_sax2 cimport Attributes
from arelle_c.xerces_uni cimport fgXercesLoadSchema
#from arelle_c.utils cimport templateSAX2Handler

        
