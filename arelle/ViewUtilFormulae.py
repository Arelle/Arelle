'''
See COPYRIGHT.md for copyright information.
'''
from arelle import XbrlConst
from arelle.ModelObject import ModelObject

def rootFormulaObjects(view):
    # relationship set based on linkrole parameter, to determine applicable linkroles
    view.allFormulaRelationshipsSet = view.modelXbrl.relationshipSet("XBRL-formulae")
    view.varSetFilterRelationshipSet = view.modelXbrl.relationshipSet(XbrlConst.variableSetFilter)
    if view.allFormulaRelationshipsSet is None or len(view.allFormulaRelationshipsSet.modelRelationships) == 0:
        view.modelXbrl.modelManager.addToLog(_("no relationships for XBRL formulae"))
        return set()

    rootObjects = set( view.modelXbrl.modelVariableSets )

    # remove formulae under consistency assertions from root objects
    consisAsserFormulaRelSet = view.modelXbrl.relationshipSet(XbrlConst.consistencyAssertionFormula)
    for modelRel in consisAsserFormulaRelSet.modelRelationships:
        if modelRel.fromModelObject is not None and modelRel.toModelObject is not None:
            rootObjects.add(modelRel.fromModelObject)   # display consis assertion
            rootObjects.discard(modelRel.toModelObject) # remove formula from root objects

    # remove assertions under assertion sets from root objects
    assertionSetRelSet = view.modelXbrl.relationshipSet(XbrlConst.assertionSet)
    for modelRel in assertionSetRelSet.modelRelationships:
        if isinstance(modelRel.fromModelObject, ModelObject) and isinstance(modelRel.toModelObject, ModelObject):
            rootObjects.add(modelRel.fromModelObject)   # display assertion set
            rootObjects.discard(modelRel.toModelObject) # remove assertion from root objects

    return rootObjects

def formulaObjSortKey(obj):
    try:
        return obj.xlinkLabel
    except AttributeError:
        return None
