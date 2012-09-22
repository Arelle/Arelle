'''
Created on Jan 20, 2012

@author: Mark V Systems Limited
(c) Copyright 2012 Mark V Systems Limited, All rights reserved.
'''
from lxml import etree
from arelle.ModelDtsObject import (ModelConcept, ModelType, ModelGroupDefinition, 
                                   ModelAll, ModelChoice, ModelSequence, 
                                   ModelAny, anonymousTypeSuffix)
from arelle.ModelInstanceObject import ModelInlineFact
from arelle.ModelObject import ModelObject, ModelAttribute
from arelle.XmlValidate import validate

def validateElementSequence(modelXbrl, compositor, children, iNextChild=0):
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
            occurences = 0
            if isinstance(particle, (ModelConcept, ModelAny)):
                elementDeclaration = particle.dereference()
                while iNextChild < len(children):
                    elt = children[iNextChild]
                    if isinstance(elt, ModelObject):
                        # for any, check namespace overlap
                        if (isinstance(particle, ModelAny) or 
                            (elementDeclaration is not None and 
                             (elt.qname == elementDeclaration.qname or 
                              elt.elementDeclaration.substitutesForQname(elementDeclaration.qname)))):
                            occurences += 1
                            validate(modelXbrl, elt)
                            iNextChild += 1
                            if occurences == particle.maxOccurs:
                                break
                        elif not isinstance(particle, ModelAll):
                            break # done with this element
                    else: # comment or processing instruction, skip over it
                        iNextChild += 1
            else:  # group definition or compositor
                while occurences < particle.maxOccurs:
                    iPrevChild = iNextChild
                    iNextChild, occured, errDesc, errArgs = validateElementSequence(modelXbrl, particle, children, iNextChild)
                    if occured:
                        # test if occurence was because of minOccurs zero but no match occured (HF 2012-09-07)
                        if occured and iNextChild == iPrevChild and particle.minOccurs == 0: # nothing really occured
                            break
                        occurences += 1
                        if occurences == particle.maxOccurs or iNextChild >= len(children):
                            break
                    else:
                        break
            if isinstance(compositor, ModelChoice):
                if occurences > 0 and particle.minOccurs <= occurences <= particle.maxOccurs:
                    return (iNextChild, True, None, None)  # choice has been selected
                else: # otherwise start again on next choice
                    if particle.minOccurs == 0:
                        anyChoiceHasMinOccurs0 = True
                    iNextChild = iStartingChild
            elif isinstance(compositor, ModelAll):
                if particle.minOccurs <= occurences <= particle.maxOccurs:
                    allParticles.add(particle)  # particle found
                    moreParticlesPasses = True
                    break # advance to next all particle
            elif particle.minOccurs > 0 and errDesc:
                return (iNextChild, False, errDesc, errArgs)
            elif not particle.minOccurs <= occurences <= particle.maxOccurs:
                return (iNextChild, False,
                        ("xmlSchema:elementOccurencesError", 
                         _("%(compositor)s(%(particles)s) %(element)s occured %(occurences)s times, minOccurs=%(minOccurs)s, maxOccurs=%(maxOccurs)s, within %(parentElement)s")),
                        dict(compositor=compositor, particles=particles, occurences=occurences, minOccurs=particle.minOccursStr, maxOccurs=particle.maxOccursStr))
    if isinstance(compositor, ModelAll):
        missingParticles = set(particles) - allParticles
        if missingParticles:
            return (iNextChild, False,
                    ("xmlSchema:missingParticlesError",
                     _("All(%(particles)s) missing at %(element)s, within %(parentElement)s")),
                    dict(particles=particles))
        occured = True
    elif isinstance(compositor, ModelChoice):
        occured = anyChoiceHasMinOccurs0 # deemed to have occured if any choice had minoccurs=0
    else:
        occured = True
    if isinstance(compositor, ModelType) and iNextChild < len(children):
        elt = children[iNextChild]
        eltChildren = elt.modelTupleFacts if isinstance(elt, ModelInlineFact) else elt
        if any(True for child in eltChildren if isinstance(child, ModelObject)): # any unexpected content elements
            return (iNextChild, False,
                    ("xmlSchema:elementUnexpected",
                     _("%(compositor)s(%(particles)s) %(element)s unexpected, within %(parentElement)s")),
                    dict(compositor=compositor, particles=particles))
    return (iNextChild, occured, None, None)

def modelGroupCompositorTitle(compositor):
    if isinstance(compositor, ModelType):
        return str(compositor.qname).replace(anonymousTypeSuffix, " complexType")
    return compositor.localName.title()

def validateUniqueParticleAttribution(modelXbrl, particles, compositor):
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