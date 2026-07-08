'''
See COPYRIGHT.md for copyright information.
'''
from .ErrorCatalog import emit_error
from .XbrlEntity import XbrlEntity
from .XbrlGroup import XbrlGroupTree
from .XbrlImportTaxonomy import XbrlImportTaxonomy, XbrlFinalTaxonomy
from .XbrlLabel import XbrlLabel
from .XbrlModule import XbrlModule, xbrlObjectTypes, xbrlObjectQNames, referencableObjectTypes
from .XbrlObject import XbrlReferencableModelObject
from .XbrlFact import XbrlFact, XbrlFootnote

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
    for impTxObj in module.importedTaxonomies or ():
        assertObjectType(compMdl, impTxObj, XbrlImportTaxonomy)
        impMdlName = impTxObj.xbrlModelName
        for qnObjType in impTxObj.importObjectTypes or ():
            if qnObjType in xbrlObjectTypes:
                clsForObjType = xbrlObjectTypes[qnObjType]
                if clsForObjType == XbrlLabel:
                    emit_error(compMdl, "oimte:invalidImportObjectType",
                               _("The importObjectTypes property MUST not include the label object."),
                               xbrlObject=impTxObj)
                elif clsForObjType == XbrlModule:
                    emit_error(compMdl, "oimte:invalidImportObjectType",
                               _("The importObjectTypes property MUST not include the xbrlModelObject (taxonomy root): %(qname)s."),
                               xbrlObject=impTxObj, qname=qnObjType)
                elif clsForObjType == XbrlFinalTaxonomy:
                    emit_error(compMdl, "oimte:invalidImportObjectType",
                               _("The importObjectTypes property MUST not include the finalTaxonomyObject: %(qname)s."),
                               xbrlObject=impTxObj, qname=qnObjType)
                elif clsForObjType == XbrlGroupTree:
                    emit_error(compMdl, "oimte:groupTreeNotImportable",
                               _("The importObjectTypes property MUST not include the groupTreeObject: %(qname)s."),
                               xbrlObject=impTxObj, qname=qnObjType)
                elif qnObjType not in referencableObjectTypes:
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

        finalTxObj = compMdl.namedObjects.get(impMdlName)
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
