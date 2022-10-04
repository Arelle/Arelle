'''
See COPYRIGHT.md for copyright information.
'''
from lxml import etree
from arelle.ModelDtsObject import (ModelConcept, ModelType, ModelGroupDefinition,
                                   ModelAll, ModelChoice, ModelSequence,
                                   ModelAny, anonymousTypeSuffix)
from arelle.ModelObject import ModelObject, ModelAttribute
from arelle.XbrlConst import xsd
from arelle.XmlValidate import validate


def validateElementSequence(modelXbrl, compositor, children, ixFacts, iNextChild=0):
    if compositor.modelDocument.targetNamespace == xsd:
        return (iNextChild, True, None, None)
    particles = compositor.dereference().particles
    iStartingChild = iNextChild
    errDesc = None
    if isinstance(compositor, ModelAll):
        allParticles = set() # elements required
        iNextAfterAll = iStartingChild
    elif isinstance(compositor, ModelChoice):
        anyChoiceHasMinOccurs0 = False
    moreParticlesPasses = True
    while moreParticlesPasses:
        moreParticlesPasses = False
        for particle in particles:
            occurrences = 0
            if isinstance(particle, (ModelConcept, ModelAny)):
                elementDeclaration = particle.dereference()
                while iNextChild < len(children):
                    elt = children[iNextChild]
                    # children now only contains ModelObjects, no comments or other lxml elements
                    vQname = elt.vQname(modelXbrl) # takes care of elements inside inline or other instances
                    # for any, check namespace overlap
                    if ((isinstance(particle, ModelAny) and
                         particle.allowsNamespace(vQname.namespaceURI)) or
                        (isinstance(particle, ModelConcept) and
                         elementDeclaration is not None and
                         (vQname == elementDeclaration.qname or
                          (vQname in modelXbrl.qnameConcepts and
                           modelXbrl.qnameConcepts[vQname].substitutesForQname(elementDeclaration.qname))))):
                        occurrences += 1
                        validate(modelXbrl, elt, ixFacts=ixFacts)
                        iNextChild += 1
                        if occurrences == particle.maxOccurs:
                            break
                    elif not isinstance(particle, ModelAll):
                        break # done with this element
            else:  # group definition or compositor
                while occurrences < particle.maxOccurs:
                    iPrevChild = iNextChild
                    iNextChild, occurred, errDesc, errArgs = validateElementSequence(modelXbrl, particle, children, ixFacts, iNextChild)
                    if occurred:
                        # test if occurrence was because of minOccurs zero but no match occurred (HF 2012-09-07)
                        if occurred and iNextChild == iPrevChild and particle.minOccurs == 0: # nothing really occurred
                            break
                        occurrences += 1
                        if occurrences == particle.maxOccurs or iNextChild >= len(children):
                            break
                    else:
                        break
            if isinstance(compositor, ModelChoice):
                if occurrences > 0 and particle.minOccurs <= occurrences <= particle.maxOccurs:
                    return (iNextChild, True, None, None)  # choice has been selected
                else: # otherwise start again on next choice
                    if particle.minOccurs == 0:
                        anyChoiceHasMinOccurs0 = True
                    iNextChild = iStartingChild
            elif isinstance(compositor, ModelAll):
                if particle.minOccurs <= occurrences <= particle.maxOccurs:
                    allParticles.add(particle)  # particle found
                    moreParticlesPasses = True
                    break # advance to next all particle
            elif particle.minOccurs > 0 and errDesc:
                return (iNextChild, False, errDesc, errArgs)
            elif not particle.minOccurs <= occurrences <= particle.maxOccurs:
                return (iNextChild, False,
                        ("xmlSchema:elementOccurrencesError",
                         _("%(compositor)s(%(particles)s) %(element)s occurred %(occurrences)s times, minOccurs=%(minOccurs)s, maxOccurs=%(maxOccurs)s, within %(parentElement)s")
                        if occurrences > 0 else
                         _("%(compositor)s(%(particles)s) content occurred %(occurrences)s times, minOccurs=%(minOccurs)s, maxOccurs=%(maxOccurs)s, within %(parentElement)s")
                         ),
                        dict(compositor=compositor, particles=particles, occurrences=occurrences, minOccurs=particle.minOccursStr, maxOccurs=particle.maxOccursStr))
    if isinstance(compositor, ModelAll):
        missingParticles = set(particles) - allParticles
        if missingParticles:
            return (iNextChild, False,
                    ("xmlSchema:missingParticlesError",
                     _("All(%(particles)s) missing at %(element)s, within %(parentElement)s")),
                    dict(particles=particles))
        occurred = True
    elif isinstance(compositor, ModelChoice):
        occurred = anyChoiceHasMinOccurs0 # deemed to have occurred if any choice had minoccurs=0
    else:
        occurred = True
    if isinstance(compositor, ModelType) and iNextChild < len(children):
        #if any(True for child in children[iNextChild:] if isinstance(child, ModelObject)): # any unexpected content elements
        if len(children) > iNextChild: # any unexpected content elements
            return (iNextChild, False,
                    ("xmlSchema:elementUnexpected",
                     _("%(compositor)s(%(particles)s) %(element)s unexpected, within %(parentElement)s")),
                    dict(compositor=compositor, particles=particles))
    return (iNextChild, occurred, None, None)

def modelGroupCompositorTitle(compositor):
    if isinstance(compositor, ModelType):
        return str(compositor.qname).replace(anonymousTypeSuffix, " complexType")
    return compositor.localName.title()

def validateUniqueParticleAttribution(modelXbrl, particles, compositor) -> None:
    priorElementParticles = {}
    priorAnyParticles = []
    for i, particle in enumerate(particles):
        if isinstance(particle, ModelConcept):
            elementDeclaration = particle.dereference()
            if elementDeclaration is not None:  # none if element ref is invalid
                qname = elementDeclaration.qname
                if qname in priorElementParticles: # look for separating transitions
                    separatingTransitions = 0
                    if not isinstance(compositor, (ModelChoice, ModelAll)):
                        for j in range(i, priorElementParticles[qname], -1):
                            separatingTransitions += particles[j-1].minOccurs
                            if separatingTransitions:
                                break
                    if not separatingTransitions:
                        modelXbrl.error("xmlSchema:uniqueParticleAttribution",
                            _("Particles of %(compositor)s have non-unique attribution of element %(element)s"),
                            modelObject=particle, compositor=compositor.localName, element=qname)
                else:
                    for priorAnyIndex in priorAnyParticles:
                        # TBD check namespace overlap
                        separatingTransitions = 0
                        if not isinstance(compositor, (ModelChoice, ModelAll)):
                            for j in range(i, priorAnyIndex, -1):
                                separatingTransitions += particles[j-1].minOccurs
                                if separatingTransitions:
                                    break
                        if not separatingTransitions:
                            modelXbrl.error("xmlSchema:uniqueParticleAttribution",
                                _("Particle of %(compositor)s has non-unique xs:any preceding element %(element)s"),
                                modelObject=particle, compositor=compositor.localName, element=qname)
                priorElementParticles[qname] = i
        elif isinstance(particle, ModelAny):
            if i > 0 and particles[i-1].minOccurs == 0:
                modelXbrl.error("xmlSchema:uniqueParticleAttribution",
                    _("Particles of %(compositor)s have non-unique xs:any particle"),
                    modelObject=particle, compositor=compositor.localName)
            priorAnyParticles.insert(0, i)
        else:   # recurse
            particleDeclaration = particle.dereference()
            if particleDeclaration is not None:  # none if particle ref is invalid
                validateUniqueParticleAttribution(modelXbrl, particleDeclaration.particles, particle)
