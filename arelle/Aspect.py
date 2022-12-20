from arelle import XbrlConst
from arelle.ModelValue import QName

class Aspect:
    LOCATION = 1; LOCATION_RULE = 101
    CONCEPT = 2
    ENTITY_IDENTIFIER = 3; VALUE = 31; SCHEME = 32
    PERIOD = 4; PERIOD_TYPE = 41; START = 42; END = 43; INSTANT = 44; INSTANT_END = 45
    UNIT = 5; UNIT_MEASURES = 51; MULTIPLY_BY = 52; DIVIDE_BY = 53; AUGMENT = 54
    COMPLETE_SEGMENT = 6
    COMPLETE_SCENARIO = 7
    NON_XDT_SEGMENT = 8
    NON_XDT_SCENARIO = 9
    DIMENSIONS = 10  # all dimensions; individual dimensions by their QNames
    OMIT_DIMENSIONS = 11 # dimensions with omit specified
    PRECISION = 95  # not real aspects, just for common processing
    DECIMALS = 96

    label = {
        LOCATION: "location",
        CONCEPT: "concept",
        ENTITY_IDENTIFIER: "entity identifier",  VALUE:"identifier value", SCHEME: "scheme",
        PERIOD: "period", PERIOD_TYPE: "period type", START: "period start", END: "period end", INSTANT: "period instant",
        UNIT: "unit", MULTIPLY_BY: "multiply by", DIVIDE_BY: "divide by", AUGMENT: "augment",
        COMPLETE_SEGMENT: "complete segment",
        COMPLETE_SCENARIO: "complete scenario",
        NON_XDT_SEGMENT: "nonXDT segment",
        NON_XDT_SCENARIO: "nonXDT scenario",
        DIMENSIONS: "all dimensions",
        OMIT_DIMENSIONS: "omit dimensions",
        PRECISION: "precision",
        DECIMALS: "decimals",
    }

def aspectStr(aspect):
    if aspect in Aspect.label:
        return Aspect.label[aspect]
    else:
        return str(aspect)

def isDimensionalAspect(aspect):
    return aspect in (Aspect.DIMENSIONS, Aspect.OMIT_DIMENSIONS) or isinstance(aspect, QName)

aspectModelAspect = {   # aspect of the model that corresponds to retrievable aspects
    Aspect.VALUE: Aspect.ENTITY_IDENTIFIER, Aspect.SCHEME:Aspect.ENTITY_IDENTIFIER,
    Aspect.PERIOD_TYPE: Aspect.PERIOD,
    Aspect.START: Aspect.PERIOD, Aspect.END: Aspect.PERIOD,
    Aspect.INSTANT: Aspect.PERIOD, Aspect.INSTANT_END: Aspect.PERIOD,
    Aspect.UNIT_MEASURES: Aspect.UNIT, Aspect.MULTIPLY_BY: Aspect.UNIT, Aspect.DIVIDE_BY: Aspect.UNIT
}

aspectRuleAspects = {   # aspect correspondence to rule-retrievable aspects
    Aspect.ENTITY_IDENTIFIER: (Aspect.VALUE, Aspect.SCHEME),
    Aspect.PERIOD: (Aspect.PERIOD_TYPE, Aspect.START, Aspect.END, Aspect.INSTANT),
    Aspect.UNIT: (Aspect.UNIT_MEASURES, Aspect.MULTIPLY_BY, Aspect.DIVIDE_BY)
}

aspectModels = {
    "dimensional": {  # order by likelyhood of short circuting aspect match tests
        Aspect.CONCEPT, Aspect.PERIOD, Aspect.UNIT, Aspect.LOCATION, Aspect.ENTITY_IDENTIFIER,
        Aspect.DIMENSIONS,
        Aspect.NON_XDT_SEGMENT, Aspect.NON_XDT_SCENARIO},
    "non-dimensional": {
        Aspect.CONCEPT, Aspect.PERIOD, Aspect.UNIT, Aspect.LOCATION, Aspect.ENTITY_IDENTIFIER,
        Aspect.COMPLETE_SEGMENT, Aspect.COMPLETE_SCENARIO},
}

aspectFromToken = {
    "location": Aspect.LOCATION, "concept": Aspect.CONCEPT,
    "entityIdentifier": Aspect.ENTITY_IDENTIFIER, "entity-identifier": Aspect.ENTITY_IDENTIFIER,
    "period": Aspect.PERIOD, "unit": Aspect.UNIT,
    "nonXDTSegment": Aspect.NON_XDT_SEGMENT, "non-XDT-segment": Aspect.NON_XDT_SEGMENT,
    "nonXDTScenario": Aspect.NON_XDT_SCENARIO, "non-XDT-scenario": Aspect.NON_XDT_SCENARIO,
    "dimension": Aspect.DIMENSIONS, "dimensions": Aspect.DIMENSIONS,
    "segment": Aspect.COMPLETE_SEGMENT, "complete-segment": Aspect.COMPLETE_SEGMENT,
    "scenario": Aspect.COMPLETE_SCENARIO, "complete-scenario": Aspect.COMPLETE_SCENARIO,
}

aspectToToken = {
    Aspect.LOCATION: "location", Aspect.CONCEPT: "concept",
    Aspect.ENTITY_IDENTIFIER: "entityIdentifier", Aspect.ENTITY_IDENTIFIER: "entity-identifier",
    Aspect.PERIOD: "period", Aspect.UNIT:"unit",
    Aspect.NON_XDT_SEGMENT: "non-XDT-segment",
    Aspect.NON_XDT_SCENARIO: "non-XDT-scenario",
    Aspect.DIMENSIONS: "dimension", Aspect.DIMENSIONS: "dimensions" ,
    Aspect.COMPLETE_SEGMENT: "complete-segment",
    Aspect.COMPLETE_SCENARIO: "complete-scenario",
}

aspectElementNameAttrValue = {
    Aspect.LOCATION_RULE: ("location", XbrlConst.tuple, None, None),
    Aspect.CONCEPT: ("concept", XbrlConst.formula, None, None),
    Aspect.ENTITY_IDENTIFIER: ("entityIdentifier", XbrlConst.formula, None, None),
    Aspect.SCHEME: ("entityIdentifier", XbrlConst.formula, None, None),
    Aspect.VALUE: ("entityIdentifier", XbrlConst.formula, None, None),
    Aspect.PERIOD: ("period", XbrlConst.formula, None, None),
    Aspect.PERIOD_TYPE: ("period", XbrlConst.formula, None, None),
    Aspect.INSTANT: ("period", XbrlConst.formula, None, None),
    Aspect.START: ("period", XbrlConst.formula, None, None),
    Aspect.END: ("period", XbrlConst.formula, None, None),
    Aspect.INSTANT_END: ("period", XbrlConst.formula, None, None),
    Aspect.UNIT: ("unit", XbrlConst.formula, None, None),
    Aspect.UNIT_MEASURES: ("unit", XbrlConst.formula, None, None),
    Aspect.MULTIPLY_BY: ("multiplyBy", XbrlConst.formula, "source", "*"),
    Aspect.DIVIDE_BY: ("divideBy", XbrlConst.formula, "source", "*"),
    Aspect.COMPLETE_SEGMENT: (("occFragments", "occXpath"), XbrlConst.formula, "occ", "segment"),
    Aspect.COMPLETE_SCENARIO: (("occFragments", "occXpath"), XbrlConst.formula, "occ", "scenario"),
    Aspect.NON_XDT_SEGMENT: (("occFragments", "occXpath"), XbrlConst.formula, "occ", "segment"),
    Aspect.NON_XDT_SCENARIO: (("occFragments", "occXpath"), XbrlConst.formula, "occ", "scenario"),
}
