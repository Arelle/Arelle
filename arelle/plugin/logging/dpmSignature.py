'''
See COPYRIGHT.md for copyright information.
'''
from arelle.ModelDtsObject import ModelConcept
from arelle.ModelInstanceObject import ModelFact
from arelle.Version import authorLabel, copyrightLabel
from arelle.XmlUtil import xmlstring

# key for use in dFact only when there's a dim that behaves as or is typed
def metDimTypedKey(fact):
    cntx = fact.context
    key = "MET({})".format(fact.qname)
    if cntx is not None and cntx.qnameDims:
        key += '|' + '|'.join(sorted("{}({})".format(dim.dimensionQname,
                                                     dim.memberQname if dim.isExplicit
                                                     else "nil" if dim.typedMember.get("{http://www.w3.org/2001/XMLSchema-instance}nil") in ("true", "1")
                                                     else xmlstring(dim.typedMember, stripXmlns=True))
                                    for dim in cntx.qnameDims.values()))
    return key

def loggingRefAttributes(arg, refAttributes, codedArgs, *args, **kwargs):
    # arg may be a ModelFact, or any other ModelObject
    if isinstance(arg, ModelFact):
        refAttributes["dpmSignature"] = metDimTypedKey(arg)
    elif isinstance(arg, ModelConcept):
        refAttributes["dpmSignature"] = "MET({})".format(arg.qname)
    elif "dpmSignature" in codedArgs: # signature may be passed in as arg for non-fact error
        refAttributes["dpmSignature"] = codedArgs["dpmSignature"]

__pluginInfo__ = {
    # Do not use _( ) in pluginInfo itself (it is applied later, after loading
    'name': 'Logging - DPM Signature',
    'version': '1.0',
    'description': '''DPM Signature, for data points (facts), concepts, dimensions, and members.
For a data point (fact): MET(conceptQName)|dimQName(mem)... (does not include period, unit, or entity identifier)
For a concept, MET(conceptQName).''',
    'license': 'Apache-2',
    'author': authorLabel,
    'copyright': copyrightLabel,
    # classes of mount points (required)
    'Logging.Ref.Attributes': loggingRefAttributes
}
