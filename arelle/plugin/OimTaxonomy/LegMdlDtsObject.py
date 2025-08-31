'''
See COPYRIGHT.md for copyright information.
'''

# Legacy ModelXbrl emulated upon OIM Taxonomy Objects

class LegMdlConcept(XbrlNamedObject):

    @property
    def isAbstract(self):
        return isinstance(self, XbrlAbstract)

    @property
    def isExplicitDimension(self):
        return isinstance(self, XbrlDimension) and self.isExplicitDimension

