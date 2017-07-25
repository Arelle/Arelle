cdef cppclass ModelXbrlErrorHandler(templateSAX2Handler):  
    ModelXbrlErrorHandler()
    void logError(const SAXParseException& exc, level)
    void error(const SAXParseException& exc)
    void fatalError(const SAXParseException& exc)
    void warning(const SAXParseException& exc)

cdef cppclass ModelXbrlEntityResolver(EntityResolver):
    ModelXbrlEntityResolver(void* modelXbrlPtr)

