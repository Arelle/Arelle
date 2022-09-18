from arelle_c.xerces_util cimport Initialize, Terminate, fgMemoryManager, gXercesMajVersion, gXercesMinVersion, gXercesRevision
from arelle_c.xerces_framework cimport XMLGrammarPool, XMLGrammarPoolImpl
from libcpp cimport bool

cdef bool _xerces_initialized = False, _xerces_terminated = False
cdef XMLGrammarPool* xerces_grammar_pool = NULL

cdef void assureXercesIsInitialized():
    global _xerces_initialized
    if not _xerces_initialized:
        Initialize()
        _xerces_initialized = True

cdef bool traceToStdout = False

cdef class Cntlr:
    
    def __init__(self):
        global _xerces_terminated, xerces_grammar_pool
        assureXercesIsInitialized()
        xerces_grammar_pool = new XMLGrammarPoolImpl(fgMemoryManager)
    
    def close(self):
        global _xerces_initialized, _xerces_terminated, xerces_grammar_pool
        assert _xerces_initialized, "xerces termination but not initialized"
        assert not _xerces_terminated, "xerces terminated or not started"
        if _xerces_initialized and not _xerces_terminated:
            Terminate()
            _xerces_terminated = True
            _xerces_initialized = False
        del xerces_grammar_pool
        xerces_grammar_pool = NULL
            
    def xerces_initialized(self):
        return _xerces_initialized
            
    def xerces_terminated(self):
        return _xerces_terminated
    
    @property
    def xerces_version(self):
        return [gXercesMajVersion, gXercesMinVersion, gXercesRevision]
        
    @property
    def arelle_c_version(self):
        return uDateCompiled
    
    @property
    def traceToStdout(self):
        return traceToStdout
    
    @traceToStdout.setter
    def traceToStdout(self, value):
        global traceToStdout
        traceToStdout = value
    
    
