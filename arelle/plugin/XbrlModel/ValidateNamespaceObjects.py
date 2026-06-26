'''
See COPYRIGHT.md for copyright information.
'''
from typing import GenericAlias
from arelle.ModelValue import QName
from ordered_set import OrderedSet
from .ErrorCatalog import emit_error
from .XbrlConst import reservedPrefixNamespaces, qnXbrlPropertyObj
from .XbrlModule import XbrlModule, XbrlModelType, xbrlObjectQNames


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
                disallowedObjs = set(
                    xbrlObjectQNames.get(propType.__args__[0])
                    for propName, propType in XbrlModule.propertyNameTypes(skipParentProperty=True)
                    if isinstance(propType, GenericAlias) and issubclass(propType.__origin__, OrderedSet) and len(getattr(module, propName, ())) > 0
                ) - modelTpObj.allowedObjects - {qnXbrlPropertyObj}
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

    # object-namespace checks across all module collections
    for txMdlPropName, propType in XbrlModule.propertyNameTypes(skipParentProperty=True):
        if isinstance(propType, GenericAlias) and issubclass(propType.__origin__, OrderedSet):
            for txMdlObj in getattr(module, txMdlPropName, ()):
                name = getattr(txMdlObj, "name", None)
                if isinstance(name, QName):
                    ns = name.namespaceURI
                    if ns != txmyNamespace:
                        if ns in reservedPrefixNamespaces.values():
                            emit_error(compMdl, "oimte:invalidObjectNamespacePrefix",
                                       _("The taxonomy module object %(name)s cannot have a reserved namespace URI."),
                                       xbrlObject=txMdlObj, name=name)
                        if not isCompiledModel:
                            emit_error(compMdl, "oimte:objectNamespaceMismatch",
                                       _("The taxonomy module object %(name)s does not match the namespace %(nsPrefix)s: of the module."),
                                       xbrlObject=txMdlObj, name=name, nsPrefix=module.name.prefix)

    validateProperties(compMdl, oimFile, module, module)
