"""
See COPYRIGHT.md for copyright information.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from arelle.ModelDtsObject import (
    ModelConcept,
    ModelType,
    ModelAll,
    ModelChoice,
    ModelAny,
    anonymousTypeSuffix,
    ModelGroupDefinition,
)
from arelle.XbrlConst import xsd
from arelle.XmlValidate import validate
from arelle.typing import TypeGetText

if TYPE_CHECKING:
    from arelle.ModelDtsObject import ModelGroupCompositor, ModelParticle
    from arelle.ModelObject import ModelObject
    from arelle.ModelXbrl import ModelXbrl
    from arelle.ModelValue import QName

_: TypeGetText


def validateElementSequence(
    modelXbrl: ModelXbrl,
    compositor: ModelGroupCompositor | ModelGroupDefinition | ModelType,
    children: list[ModelObject],
    ixFacts: bool,
    setTargetModelXbrl: bool,
    iNextChild: int = 0,
) -> tuple[int, bool, tuple[str, str] | None, dict[str, Any] | None]:
    if compositor.modelDocument.targetNamespace == xsd:
        return iNextChild, True, None, None
    particles = compositor.dereference().particles  # type: ignore[union-attr]
    iStartingChild = iNextChild
    errDesc: tuple[str, str] | None = None
    errArgs: dict[str, Any] | None = None
    if isinstance(compositor, ModelAll):
        allParticles: set[ModelParticle] = set()  # elements required
    elif isinstance(compositor, ModelChoice):
        anyChoiceHasMinOccurs0 = False
    moreParticlesPasses = True
    while moreParticlesPasses:
        moreParticlesPasses = False
        for particle in particles:
            occurrences = 0
            if isinstance(particle, (ModelConcept, ModelAny)):
                elementDeclaration = particle.dereference()  # note that types in structures may share quames with other structures
                while iNextChild < len(children):
                    elt = children[iNextChild]
                    # children now only contains ModelObjects, no comments or other lxml elements
                    vQname = elt.vQname(modelXbrl)  # takes care of elements inside inline or other instances
                    # for any, check namespace overlap
                    if ((isinstance(particle, ModelAny) and
                         particle.allowsNamespace(vQname.namespaceURI)) or
                        (isinstance(particle, ModelConcept) and
                         elementDeclaration is not None and
                         (vQname == elementDeclaration.qname or
                          (vQname in modelXbrl.qnameConcepts and
                           modelXbrl.qnameConcepts[vQname].substitutesForQname(elementDeclaration.qname))))):  # type: ignore[arg-type]
                        occurrences += 1
                        validate(modelXbrl, elt, ixFacts=ixFacts, setTargetModelXbrl=setTargetModelXbrl, elementDeclarationType=getattr(elementDeclaration, "type", None))
                        iNextChild += 1
                        if occurrences == particle.maxOccurs:
                            break
                    elif not isinstance(particle, ModelAll):
                        break  # done with this element
            else:  # group definition or compositor
                while occurrences < particle.maxOccurs:
                    iPrevChild = iNextChild
                    iNextChild, occurred, errDesc, errArgs = validateElementSequence(modelXbrl, particle, children, ixFacts, setTargetModelXbrl, iNextChild)
                    if occurred:
                        # test if occurrence was because of minOccurs zero but no match occurred (HF 2012-09-07)
                        if occurred and iNextChild == iPrevChild and particle.minOccurs == 0:  # nothing really occurred
                            break
                        occurrences += 1
                        if occurrences == particle.maxOccurs or iNextChild >= len(children):
                            break
                    else:
                        break
            if isinstance(compositor, ModelChoice):
                if occurrences > 0 and particle.minOccurs <= occurrences <= particle.maxOccurs:
                    return iNextChild, True, None, None  # choice has been selected
                else:  # otherwise start again on next choice
                    if particle.minOccurs == 0:
                        anyChoiceHasMinOccurs0 = True
                    iNextChild = iStartingChild
            elif isinstance(compositor, ModelAll):
                if particle.minOccurs <= occurrences <= particle.maxOccurs:
                    allParticles.add(particle)  # particle found
                    moreParticlesPasses = True
                    break  # advance to next all particle
            elif particle.minOccurs > 0 and errDesc:
                return iNextChild, False, errDesc, errArgs
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
        occurred = anyChoiceHasMinOccurs0  # deemed to have occurred if any choice had minoccurs=0
    else:
        occurred = True
    if isinstance(compositor, ModelType) and iNextChild < len(children):
        # if any(True for child in children[iNextChild:] if isinstance(child, ModelObject)): # any unexpected content elements
        if len(children) > iNextChild:  # any unexpected content elements
            return (iNextChild, False,
                    ("xmlSchema:elementUnexpected",
                     _("%(compositor)s(%(particles)s) %(element)s unexpected, within %(parentElement)s")),
                    dict(compositor=compositor, particles=particles))
    return iNextChild, occurred, None, None


def modelGroupCompositorTitle(compositor: ModelGroupCompositor | ModelGroupDefinition | ModelType) -> str:
    if isinstance(compositor, ModelType):
        return str(compositor.qname).replace(anonymousTypeSuffix, " complexType")
    return compositor.localName.title()


def validateUniqueParticleAttribution(
    modelXbrl: ModelXbrl,
    particles: list[ModelParticle],
    compositor: ModelGroupCompositor | ModelGroupDefinition | ModelType,
) -> None:
    priorElementParticles: dict[QName | None, int] = {}
    priorAnyParticles: list[int] = []
    for i, particle in enumerate(particles):
        if isinstance(particle, ModelConcept):
            elementDeclaration = particle.dereference()
            if elementDeclaration is not None:  # none if element ref is invalid
                qname = elementDeclaration.qname
                if qname in priorElementParticles:  # look for separating transitions
                    separatingTransitions = 0
                    if not isinstance(compositor, (ModelChoice, ModelAll)):
                        for j in range(i, priorElementParticles[qname], -1):
                            separatingTransitions += particles[j - 1].minOccurs
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
                                separatingTransitions += particles[j - 1].minOccurs
                                if separatingTransitions:
                                    break
                        if not separatingTransitions:
                            modelXbrl.error("xmlSchema:uniqueParticleAttribution",
                                _("Particle of %(compositor)s has non-unique xs:any preceding element %(element)s"),
                                modelObject=particle, compositor=compositor.localName, element=qname)
                priorElementParticles[qname] = i
        elif isinstance(particle, ModelAny):
            if i > 0 and particles[i - 1].minOccurs == 0:
                modelXbrl.error("xmlSchema:uniqueParticleAttribution",
                    _("Particles of %(compositor)s have non-unique xs:any particle"),
                    modelObject=particle, compositor=compositor.localName)
            priorAnyParticles.insert(0, i)
        else:  # recurse
            particleDeclaration = particle.dereference()  # type: ignore[attr-defined]
            if particleDeclaration is not None:  # none if particle ref is invalid
                validateUniqueParticleAttribution(modelXbrl, particleDeclaration.particles, particle)  # type: ignore[arg-type]
