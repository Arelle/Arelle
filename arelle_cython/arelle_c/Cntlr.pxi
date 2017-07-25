from arelle_c.xerces_util cimport Initialize, Terminate, fgMemoryManager
from arelle_c.xerces_framework cimport XMLGrammarPool, XMLGrammarPoolImpl
from libcpp cimport bool

cdef bool _xerces_initialized = False, _xerces_terminated = False
cdef XMLGrammarPool* xerces_grammar_pool = NULL


cdef class Cntlr:
    
    def __init__(self):
        global _xerces_initialized, _xerces_terminated, xerces_grammar_pool
        assert not _xerces_initialized, "xerces already initialized" # can only be one per instance
        if not _xerces_initialized:
            Initialize()
            _xerces_initialized = True
            initialize_constants()
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
    
    
