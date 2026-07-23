'''
See COPYRIGHT.md for copyright information.
'''
from .ErrorCatalog import emit_error
from .XbrlEntity import XbrlEntity
from .XbrlGroup import XbrlGroupTree, XbrlGroupContent
from .XbrlImportTaxonomy import XbrlImportTaxonomy, XbrlFinalTaxonomy
from .XbrlLabel import XbrlLabel
from .XbrlModule import XbrlModule, xbrlObjectTypes, xbrlObjectQNames, referencableObjectTypes
from .XbrlObject import XbrlReferencableModelObject
from .XbrlFact import XbrlFact, XbrlFootnote
from .XbrlConst import builtInPrefixTaxonomies

qnXbrlLabelObject = None

def _qnLabelObj():
    global qnXbrlLabelObject
    if qnXbrlLabelObject is None:
        from arelle.ModelValue import qname
        from .XbrlConst import xbrl
        qnXbrlLabelObject = qname(xbrl, "xbrl:labelObject")
    return qnXbrlLabelObject


def validateImportFamily(compMdl, module, oimFile, *, assertObjectType, validateQNameReference, validateProperties):
    """Validate importedTaxonomies on the taxonomy module: importObjectTypes correctness and
       finalTaxonomy-driven extension restrictions."""
    # oim-taxonomy §322: import mappings MUST NOT be defined for built-in models. Any importMapping
    # entry whose xbrlModelName resolves to a built-in taxonomy prefix is illegal.
    for mapQn in getattr(module, "_importMapping", None) or ():
        if mapQn.prefix in builtInPrefixTaxonomies:
            emit_error(compMdl, "oimte:illegalImportMappingForBuiltInTaxonomy",
                       _("The importMapping MUST NOT define an entry for the built-in taxonomy %(qname)s."),
                       xbrlObject=module, qname=mapQn)
    for impTxObj in module.importedTaxonomies or ():
        assertObjectType(compMdl, impTxObj, XbrlImportTaxonomy)
        impMdlName = impTxObj.xbrlModelName
        for qnObjType in impTxObj.importObjectTypes or ():
            if qnObjType in xbrlObjectTypes:
                clsForObjType = xbrlObjectTypes[qnObjType]
                # xbrl:labelObject is explicitly importable (oim-taxonomy §5919 — used to side-load
                # labels, e.g. in additional languages); it is not in the forbidden list (§5966-5968)
                # even though it is a non-referencable object type. xbrl:groupContentObject is likewise
                # importable by type (selective group-content import): an imported group content object
                # does not import the object QName in its forObject as a dependent object, so an orphaned
                # group content is dropped by orphan cleanup rather than pulling in its forObject target.
                # (xbrl:referenceObject is already referencable, so it passes the check below.)
                if clsForObjType in (XbrlLabel, XbrlGroupContent):
                    pass
                elif clsForObjType == XbrlModule:
                    emit_error(compMdl, "oimte:invalidImportObjectType",
                               _("The importObjectTypes property MUST not include the xbrlModelObject (taxonomy root): %(qname)s."),
                               xbrlObject=impTxObj, qname=qnObjType)
                elif clsForObjType == XbrlFinalTaxonomy:
                    emit_error(compMdl, "oimte:invalidImportObjectType",
                               _("The importObjectTypes property MUST not include the finalTaxonomyObject: %(qname)s."),
                               xbrlObject=impTxObj, qname=qnObjType)
                elif clsForObjType == XbrlGroupTree:
                    # The groupTree is a singleton, imported automatically with the model (unless
                    # excludeGroupTree); it MUST NOT be named in importObjectTypes (oim-taxonomy
                    # §5593). The former oimte:groupTreeNotImportable code was removed when the tree
                    # became importable, so this reuses the generic invalidImportObjectType.
                    emit_error(compMdl, "oimte:invalidImportObjectType",
                               _("The importObjectTypes property MUST not include the groupTreeObject: %(qname)s."),
                               xbrlObject=impTxObj, qname=qnObjType)
                elif qnObjType not in referencableObjectTypes and clsForObjType != XbrlLabel:
                    emit_error(compMdl, "oimte:invalidImportObjectType",
                               _("The importObjectTypes property MUST specify a referencable taxonomy component object: %(qname)s is non-referencable."),
                               xbrlObject=impTxObj, qname=qnObjType)
            else:
                emit_error(compMdl, "oimte:invalidImportObjectType",
                           _("The importObjectTypes property MUST specify valid OIM object types, %(qname)s is not valid."),
                           xbrlObject=impTxObj, qname=qnObjType)
        # conflicting import properties: excludeLabels with label selections
        if getattr(impTxObj, "excludeLabels", False) and getattr(impTxObj, "selections", None):
            for selObj in impTxObj.selections:
                if getattr(selObj, "objectType", None) == _qnLabelObj():
                    emit_error(compMdl, "oimte:conflictingImportProperties",
                               _("The importTaxonomy %(moduleName)s has excludeLabels=true but also has a selection for label objects."),
                               xbrlObject=impTxObj, moduleName=impMdlName)
                    break

        # The finalTaxonomy object no longer carries a name (removed from the spec); it is a nameless
        # nested object on the imported module, so read it from the module rather than namedObjects.
        _impModule = compMdl.xbrlModels.get(impMdlName)
        finalTxObj = getattr(_impModule, "finalTaxonomy", None)
        if isinstance(finalTxObj, XbrlFinalTaxonomy):
            def extendsFinalTaxonomy(obj, _impTxObj=impTxObj, _finalTxObj=finalTxObj, _impMdlName=impMdlName):
                if _finalTxObj.finalTaxonomyFlag:
                    if isinstance(obj, XbrlReferencableModelObject) and not isinstance(obj, (XbrlFact, XbrlFootnote, XbrlEntity)):
                        emit_error(compMdl, "oimte:invalidFinalTaxonomyModification",
                                   _("The importTaxonomy %(moduleName)s cannot be extended by object %(qname)s due to a finalTaxonomyFlag."),
                                   xbrlObject=_impTxObj, moduleName=_impMdlName, qname=obj.name)
                elif _finalTxObj.finalObjectTypes and xbrlObjectQNames[type(obj)] in _finalTxObj.finalObjectTypes:
                    emit_error(compMdl, "oimte:invalidFinalTaxonomyObjectType",
                               _("The importTaxonomy %(moduleName)s cannot be extended by object %(qname)s due to it's type, %(type)s, being in finalObjectTypes."),
                               xbrlObject=_impTxObj, moduleName=_impMdlName, qname=obj.name, type=xbrlObjectQNames[type(obj)])
                elif _finalTxObj.finalObjects and getattr(obj, "extends", None) in _finalTxObj.finalObjects:
                    emit_error(compMdl, "oimte:invalidFinalTaxonomyObject",
                               _("The importTaxonomy %(moduleName)s cannot be extended by object %(qname)s due to having %(name)s in finalObjects."),
                               xbrlObject=_impTxObj, moduleName=_impMdlName, qname=xbrlObjectQNames[type(obj)], name=obj.extends)
                elif _finalTxObj.selections:
                    for i, selObj in enumerate(_impTxObj.selections or ()):
                        if xbrlObjectQNames[type(obj)] == selObj.objectType and (
                            all((eval(obj, whereObj) for whereObj in selObj.where))):
                            emit_error(compMdl, "oimte:invalidFinalTaxonomyObject",
                                       _("The importTaxonomy %(moduleName)s cannot be extended by object %(qname)s due matching selection %(i)s."),
                                       xbrlObject=_impTxObj, moduleName=_impMdlName, qname=xbrlObjectQNames[type(obj)], i=i)
                            break
            module.referencedObjectsAction(compMdl, extendsFinalTaxonomy)
