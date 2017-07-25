
from arelle_c.xerces_framework cimport XMLGrammarPool

cdef class Cntlr:
    cdef XMLGrammarPool* xerces_grammar_pool
