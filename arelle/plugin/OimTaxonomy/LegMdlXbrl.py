'''
See COPYRIGHT.md for copyright information.
'''

# Legacy ModelXbrl emulated upon OIM Taxonomy Objects

class LegMdlXbrl(XbrlTaxonomyModel):

    @property
    def qnameConcepts(self, qname):
        concept = self.namedObjects(qname)
        if isinstance(self, (XbrlConcept, XbrlAbstract, XbrlDimension, XbrlDomain, XbrlMember)):
            return LegMdlConcept(concept)
        return None

    @property
    def dimensionDefaultConcepts(self):
        return dict((dim, dim.domainRoot)
                    for dim in self.filterNamedObjects(XbrlDimension)
                    if dim.isExplicitDimension )