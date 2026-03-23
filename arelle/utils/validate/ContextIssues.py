"""
See COPYRIGHT.md for copyright information.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, cast

from arelle import XbrlConst
from arelle.ModelInstanceObject import ModelContext
from arelle.ModelXbrl import ModelXbrl
from arelle.XmlValidate import lexicalPatterns


@dataclass(frozen=True)
class ContextIssues:
    """
    Result of structural context validation. Contains sets of contexts that
    violate common XBRL/ESEF context rules (period format, segment/scenario usage).
    """
    contextsWithImproperContent: set[ModelContext]
    contextsWithPeriodTime: set[ModelContext]
    contextsWithPeriodTimeZone: set[ModelContext]
    contextsWithSegments: set[ModelContext]
    contextsWithWrongInstantDate: set[ModelContext]


def getContextIssues(modelXbrl: ModelXbrl, esefYear: int | None = None, ) -> ContextIssues:
    """
    Iterate all contexts and collect those with common issues:
    - Period elements (startDate, endDate, instant) with time or timezone
    - Contexts using xbrli:segment (disallowed in ESEF/NL/GFM)
    - Scenario elements with non-dimensional content
    - Optional: int indicating the year of the ESEF taxonomy and whether to check for instant dates on January 1st.
    """
    contextsWithImproperContent: set[ModelContext] = set()
    contextsWithPeriodTime: set[ModelContext] = set()
    contextsWithPeriodTimeZone: set[ModelContext] = set()
    contextsWithSegments: set[ModelContext] = set()
    contextsWithWrongInstantDate: set[ModelContext] = set()

    datetimePattern = lexicalPatterns["XBRLI_DATEUNION"]
    for context in modelXbrl.contexts.values():
        for uncast_elt in context.iterdescendants(*XbrlConst.xbrliPeriodElementTags):
            elt = cast(Any, uncast_elt)
            m = datetimePattern.match(elt.stringValue)
            if m:
                if m.group(1):
                    contextsWithPeriodTime.add(context)
                if m.group(3):
                    contextsWithPeriodTimeZone.add(context)
        if context.hasSegment:
            contextsWithSegments.add(context)
        if context.nonDimValues("scenario"):
            contextsWithImproperContent.add(context)
        if esefYear is not None and esefYear >= 2024:
            if context.instantDate and context.instantDate.day == 1 and context.instantDate.month == 1:
                contextsWithWrongInstantDate.add(context)

    return ContextIssues(
        contextsWithImproperContent=contextsWithImproperContent,
        contextsWithPeriodTime=contextsWithPeriodTime,
        contextsWithPeriodTimeZone=contextsWithPeriodTimeZone,
        contextsWithSegments=contextsWithSegments,
        contextsWithWrongInstantDate=contextsWithWrongInstantDate,
    )
