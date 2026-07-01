'''
See COPYRIGHT.md for copyright information.
'''
from arelle.ModelValue import QName
from .ErrorCatalog import emit_error
from .XbrlConst import reservedPrefixNamespaces, qnXbrlPropertyObj
from .XbrlModule import XbrlModule, XbrlModelType, xbrlObjectQNames
from .XbrlTypes import collectionInfo


def validateNamespaceFamily(compMdl, module, oimFile, *, assertObjectType, validateQNameReference, validateProperties):
    """Validate module-level namespace, modelType and self-properties of the taxonomy module."""
    txmyNamespace = module.name.namespaceURI
    isCompiledModel = module.modelForm == "compiled"

    # Taxonomy object
    assertObjectType(compMdl, module, XbrlModule)

    # modelType
    if module.modelType:
        modelTpObj = validateQNameReference(compMdl, module, "modelType", XbrlModelType)
        if modelTpObj:
            if modelTpObj.allowedObjects:
                disallowedObjs = set()
                for propName, propType in XbrlModule.propertyNameTypes(skipParentProperty=True):
                    cInfo = collectionInfo(propType)
                    if cInfo is not None and len(getattr(module, propName, None) or ()) > 0:
                        eltType = cInfo[1]
                        objTypeQn = xbrlObjectQNames.get(eltType)
                        if objTypeQn is not None:
                            disallowedObjs.add(objTypeQn)
                disallowedObjs -= modelTpObj.allowedObjects | {qnXbrlPropertyObj}
                if disallowedObjs:
                    emit_error(compMdl, "oimte:disallowedObjectModelType",
                               _("The modelType %(moduleType)s does not allow objects %(objNames)s."),
                               xbrlObject=module, moduleType=module.modelType,
                               objNames=", ".join(str(p) for p in disallowedObjs))
            if modelTpObj.requiredProperties:
                missingReqProps = modelTpObj.requiredProperties - set(p.property for p in module.properties or ())
                if missingReqProps:
                    emit_error(compMdl, "oimte:missingRequiredModelTypeProperty",
                               _("The modelType %(moduleType)s requires properties %(propNames)s."),
                               xbrlObject=module, moduleType=module.modelType,
                               propNames=", ".join(str(p) for p in missingReqProps))

    # object-namespace checks across all module collections.
    # Use the resolved documentNamespaceURI when available; fall back to the module name's namespace.
    # When documentNamespacePrefix was absent (documentNamespaceNotDefined already raised),
    # _documentNamespaceURI is None and we skip the per-object mismatch check.
    documentNamespaceURI = getattr(module, "_documentNamespaceURI", None) or txmyNamespace
    hasDefinedDocumentNamespace = getattr(module, "_documentNamespaceURI", None) is not None
    for txMdlPropName, propType in XbrlModule.propertyNameTypes(skipParentProperty=True):
        if collectionInfo(propType) is not None:
            for txMdlObj in getattr(module, txMdlPropName, None) or ():
                name = getattr(txMdlObj, "name", None)
                if isinstance(name, QName):
                    ns = name.namespaceURI
                    if ns != documentNamespaceURI and not isCompiledModel and hasDefinedDocumentNamespace:
                        if ns in reservedPrefixNamespaces.values():
                            emit_error(compMdl, "oimce:invalidURIForReservedAlias",
                                       _("The taxonomy module object %(name)s cannot have a reserved namespace URI."),
                                       xbrlObject=txMdlObj, name=name)
                        else:
                            emit_error(compMdl, "oimte:objectNamespaceMismatch",
                                       _("The taxonomy module object %(name)s does not match the namespace %(nsPrefix)s: of the module."),
                                       xbrlObject=txMdlObj, name=name, nsPrefix=module.name.prefix)

    validateProperties(compMdl, oimFile, module, module)
