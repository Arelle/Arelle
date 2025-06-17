'''
See COPYRIGHT.md for copyright information.
'''
from __future__ import annotations

from enum import Enum

from arelle import XbrlConst
from arelle.ModelValue import QName


class LinkbaseType(Enum):
    CALCULATION = "calculation"
    DEFINITION = "definition"
    LABEL = "label"
    PRESENTATION = "presentation"
    REFERENCE = "reference"

    @staticmethod
    def fromRefUri(refUri: str | None) -> LinkbaseType | None:
        """
        Returns the LinkbaseType corresponding to the given ref URI.
        If the URI does not match any known linkbase reference type, returns None.
        """
        if refUri is None:
            return None
        return LINKBASE_TYPE_BY_REF_URI.get(refUri, None)

    def getArcQn(self) -> QName:
        """
        Returns the qname of the arc associated with this LinkbaseType.
        """
        return LINKBASE_ARC_QN[self]

    def getArcroles(self) -> frozenset[str]:
        """
        Returns the standard arcrole URIs associated with this LinkbaseType.
        """
        return LINKBASE_ARCROLES[self]

    def getLinkQn(self) -> QName:
        """
        Returns the qname of the link associated with this LinkbaseType.
        """
        return LINKBASE_LINK_QN[self]

    def getLowerName(self) -> str:
        """
        Returns the lower-case name of this LinkbaseType.
        """
        return self.value.lower()

    def getRefUri(self) -> str:
        """
        Returns the ref URI associated with this LinkbaseType.
        """
        return LINKBASE_REF_URIS[self]


LINKBASE_ARC_QN = {
    LinkbaseType.CALCULATION: XbrlConst.qnLinkCalculationArc,
    LinkbaseType.DEFINITION: XbrlConst.qnLinkDefinitionArc,
    LinkbaseType.LABEL: XbrlConst.qnLinkLabelArc,
    LinkbaseType.PRESENTATION: XbrlConst.qnLinkPresentationArc,
    LinkbaseType.REFERENCE: XbrlConst.qnLinkReferenceArc,
}

LINKBASE_ARCROLES = {
    LinkbaseType.CALCULATION: frozenset({
        XbrlConst.summationItem,
        XbrlConst.summationItem11,
    }),
    LinkbaseType.DEFINITION: XbrlConst.standardDefinitionArcroles,
    LinkbaseType.LABEL: frozenset({XbrlConst.conceptLabel}),
    LinkbaseType.PRESENTATION: frozenset({XbrlConst.parentChild}),
    LinkbaseType.REFERENCE: frozenset({XbrlConst.conceptReference}),
}

LINKBASE_LINK_QN = {
    LinkbaseType.CALCULATION: XbrlConst.qnLinkCalculationLink,
    LinkbaseType.DEFINITION: XbrlConst.qnLinkDefinitionLink,
    LinkbaseType.LABEL: XbrlConst.qnLinkLabelLink,
    LinkbaseType.PRESENTATION: XbrlConst.qnLinkPresentationLink,
    LinkbaseType.REFERENCE: XbrlConst.qnLinkReferenceLink,
}

LINKBASE_REF_URIS = {
    LinkbaseType.CALCULATION: "http://www.xbrl.org/2003/role/calculationLinkbaseRef",
    LinkbaseType.DEFINITION: "http://www.xbrl.org/2003/role/definitionLinkbaseRef",
    LinkbaseType.LABEL: "http://www.xbrl.org/2003/role/labelLinkbaseRef",
    LinkbaseType.PRESENTATION: "http://www.xbrl.org/2003/role/presentationLinkbaseRef",
    LinkbaseType.REFERENCE: "http://www.xbrl.org/2003/role/referenceLinkbaseRef",
}
LINKBASE_TYPE_BY_REF_URI = {v: k for k, v in LINKBASE_REF_URIS.items()}
