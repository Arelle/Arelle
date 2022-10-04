'''
See COPYRIGHT.md for copyright information.
'''
import os
from collections import defaultdict
from arelle import XbrlConst
from arelle.ModelDtsObject import ModelConcept

# check if concept is behaving as a total based on role, deed, or circumstances
def presumptionOfTotal(val, rel, siblingRels, iSibling, isStatementSheet, nestedInTotal, checkLabelRoleOnly):
    """
    A numeric concept target of a parent-child relationship is presumed total if:

    (i) its preferredLabel role is a total role (pre XbrlConst static function of
    current such total roles) or

    (ii) if not in a nested total (abstract child relationship to a known total's
    contributing siblings):

    the parent is not SupplementalCashFlowInformationAbstract and the preceding
    sibling relationship is monetary and it's on a statement sheet and it's the
    last of more than one monetary item

    (a) Last monetary parented by an abstract or non-monetary and not in a nested
    (breakdown) total, or
    (b) effective label (en-US of preferred role) has "Total" in its wording.
    (c) (commented out for now due to false positives: Concept name has "Total"
    in its name)
    (d) last monetary (may be sub level) whose immediate sibling is a calc LB child
    """
    concept = rel.toModelObject
    if isinstance(concept, ModelConcept) and concept.isNumeric:
        preferredLabel = rel.preferredLabel
        if XbrlConst.isTotalRole(preferredLabel):
            return _("preferredLabel {0}").format(os.path.basename(preferredLabel))
        if concept.isMonetary and not checkLabelRoleOnly:
            effectiveLabel = concept.label(lang="en-US", fallbackToQname=False, preferredLabel=preferredLabel)
            ''' word total in label/name does not seem to be a good indicator,
                e.g., Google Total in label for ShareBasedCompensationArrangementByShareBasedPaymentAwardGrantDateFairValueOfOptionsVested followed by
                label with Aggregate but name has Total
                ... so only perform this test on last monetary in a Note
            if 'Total' in effectiveLabel: # also check for Net ???
                return _("word 'Total' in effective label {0}").format(effectiveLabel)
            if 'Total' in concept.name: # also check for Net ???
                return _("word 'Total' in concept name {0}").format(concept.name)
            '''
            parent = rel.fromModelObject
            if (len(siblingRels) > 1 and
                iSibling == len(siblingRels) - 1 and
                parent is not None and
                parent.name not in {
                    "SupplementalCashFlowInformationAbstract"
                }):
                preceedingSibling = siblingRels[iSibling - 1].toModelObject
                if preceedingSibling is not None and preceedingSibling.isMonetary:
                    # last fact, may be total
                    if isStatementSheet:
                        # check if facts add up??
                        if (parent.isAbstract or not parent.isMonetary) and not nestedInTotal:
                            return _("last monetary item in statement sheet monetary line items parented by nonMonetary concept")
                        elif effectiveLabel and 'Total' in effectiveLabel:
                            return _("last monetary item in statement sheet monetary line items with word 'Total' in effective label {0}").format(effectiveLabel)
                        elif 'Total' in concept.name:
                            return _("last monetary item in statement sheet monetary line items with word 'Total' in concept name {0}").format(concept.name)
                        elif val.summationItemRelsSetAllELRs.isRelated(concept, "child", preceedingSibling):
                            return _("last monetary item in statement sheet monetary line items is calc sum of previous line item")
                    ''' for now unreliable to use total words for notes
                    else:
                        if 'Total' in effectiveLabel: # also check for Net ???
                            return _("last monetary item in note with word 'Total' in effective label {0}").format(effectiveLabel)
                        if 'Total' in concept.name: # also check for Net ???
                            return _("last monetary item in note with word 'Total' in concept name {0}").format(concept.name)
                    '''
    return None

# 6.15.02, 6.15.03
def checkCalcsTreeWalk(val, parentChildRels, concept, isStatementSheet, inNestedTotal, conceptsUsed, visited):
    """
    -  EFM-strict validation 6.15.2/3: finding presumed totals in presentation and inspecting for
       equivalents in calculation (noted as error-semantic, in efm-strict mode).

    -  Best practice approach: inspecting for calcuations in the UGT calculations that would hint
       that like filing constructs should have presentation (noted as warning-semantic in best practices plug-in, when loaded and enabled)

    EFM-strict missing-calcs

    a. Presumption of total

    The presentation linkbase is tree-walked to find items presumed to be totals and their contributing
    items.  (see description of presumptionOfTotal, above)

    b. Finding calculation link roles with least mis-fit to presumed total and its contributing items
    (presumptionOfTotal in ValidateFiling.py).

    For each presumed total (checkForCalculations in ValidateFiling.py):

    b.1 Contributing items are found for the presumed total as follows:

    From the presumed total, walking back through its preceding sibilings (with caution to avoid
    looping on allowed direct cycles), a preceding sibling is a contributing item if it has facts,
    same period type, and numeric.  If a preceding sibling is abstract, the abstract's children are
    likewise recursively checked (as they often represent a breakdown, and such children of an
    abstract sibling to the total are also contributing items (except for such children preceding
    a total at the child level).

    If a preceding sibling is presumed total (on same level), it is a running subtotal (in subsequent
    same-level total) unless it's independent in the calc LB (separate totaled stuff preceding these
    siblings) or related to grandparent sum.

    b.2 Finding the facts of these total/contributing item sets

    Sets of total and compatible contributing facts that match the sets of total concept and
    contributing concept must next be found, because each of these different sets (of total
    and compatible contributing facts) may fit different calculation link roles (according to
    which compatible contributing facts are present for each total).  This is particularly
    important when totals and contributing items exist both on face statements and notes, but
    the contributing compatible fact population is different).

    For each fact of the total concept, that has a specified end/instant datetime and unit, if
    (i) it's not on a statement or
    (ii) required context is absent or
    (iii) the fact's end/instant is within the required context's duration, the contributing
    item facts are those unit and context equivalent to such total fact.

    b.3 Finding least-mis-matched calculation link role

    Each link role in calculation produces a different set of summation-item arc-sets, and
    each set of presumed-total facts and compatible contributing item facts is separately
    considered to find the least-mismatched calculation summation-item arc-set.

    The link roles are not intermixed or aggregated, each link role produces independent
    summation-item arc-sets (XBRL 2.1 section 5.2.5.2).

    For each total fact and compatible contributing item facts, the calculation link roles
    are examined one-by-one for that link-role where the total has children missing the
    least of the compatible contributing item fact children, and reported either as 6.15.02
    (for statement sheet presentation link roles) or 6.15.03 (for non-statement link roles).
    The determination of statement sheet is according to the presentation tree walk.  The
    search for least-misfit calculation link role does not care or consider the value of the
    calculation link role, just the summation-item arc-set from the presumed-total concept.
    """
    if concept not in visited:
        visited.add(concept)
        siblingRels = parentChildRels.fromModelObject(concept)
        foundTotalAtThisLevel = False
        for iSibling, rel in enumerate(siblingRels):
            reasonPresumedTotal = presumptionOfTotal(val, rel, siblingRels, iSibling, isStatementSheet, False, inNestedTotal)
            if reasonPresumedTotal:
                foundTotalAtThisLevel = True
                checkForCalculations(val, parentChildRels, siblingRels, iSibling, rel.toModelObject, rel, reasonPresumedTotal, isStatementSheet, conceptsUsed, False, set())
        if foundTotalAtThisLevel: # try nested tree walk to look for lower totals
            inNestedTotal = True
        for rel in siblingRels:
            checkCalcsTreeWalk(val, parentChildRels, rel.toModelObject, isStatementSheet, inNestedTotal, conceptsUsed, visited)
        visited.remove(concept)

def checkForCalculations(val, parentChildRels, siblingRels, iSibling, totalConcept, totalRel, reasonPresumedTotal, isStatementSheet, conceptsUsed, nestedItems, contributingItems):
    # compatible preceding sibling facts must have calc relationship to toal
    for iContributingRel in range(iSibling - 1, -1, -1):
        contributingRel = siblingRels[iContributingRel]
        siblingConcept = contributingRel.toModelObject
        if siblingConcept is not None:
            if siblingConcept is totalConcept: # direct cycle loop likely, possibly among children of abstract sibling
                break
            if val.summationItemRelsSetAllELRs.isRelated(totalConcept, 'ancestral-sibling', siblingConcept):
                break # sibling independently contributes as sibling of totalConcept to grandfather total
            if any(val.summationItemRelsSetAllELRs.isRelated(contributingItem, 'child', siblingConcept)
                   for contributingItem in contributingItems):
                break # this subtotal is a breakdown of something already being considered
            isContributingTotal = presumptionOfTotal(val, contributingRel, siblingRels, iContributingRel, isStatementSheet, True, False)
            # contributing total may actually be separate non-running subtotal, if so don't include it here
            if isContributingTotal:
                if (val.summationItemRelsSetAllELRs.fromModelObject(siblingConcept) and not
                    val.summationItemRelsSetAllELRs.toModelObject(siblingConcept)):
                    break # sibling independently contributes as sibling of totalConcept as a root in another hierarchy
            if siblingConcept.isAbstract:
                childRels = parentChildRels.fromModelObject(siblingConcept)
                checkForCalculations(val, parentChildRels, childRels, len(childRels), totalConcept, totalRel, reasonPresumedTotal, isStatementSheet, conceptsUsed, True, contributingItems)
            elif (siblingConcept in conceptsUsed and
                  siblingConcept.isNumeric and
                  siblingConcept.periodType == totalConcept.periodType):
                contributingItems.add(siblingConcept)
            if isContributingTotal:
                break
    if not nestedItems and contributingItems:
        # must check each totalFact and compatible items for a relationship set separately
        # (because different sets of sums/items could, on edge case, be in different ELRs)
        compatibleItemsFacts = defaultdict(set)
        for totalFact in val.modelXbrl.factsByQname[totalConcept.qname]:
            totalFactContext = totalFact.context
            totalFactUnit = totalFact.unit
            if (totalFactContext is not None and totalFactUnit is not None and totalFactContext.endDatetime is not None and
                (not isStatementSheet or
                 (val.requiredContext is None or
                  val.requiredContext.startDatetime <= totalFactContext.endDatetime <= val.requiredContext.endDatetime))):
                compatibleItemConcepts = set()
                compatibleFacts = {totalFact}
                for itemConcept in contributingItems:
                    for itemFact in val.modelXbrl.factsByQname[itemConcept.qname]:
                        if (totalFactContext.isEqualTo(itemFact.context) and
                            totalFactUnit.isEqualTo(itemFact.unit)):
                            compatibleItemConcepts.add(itemConcept)
                            compatibleFacts.add(itemFact)
                if len(compatibleItemConcepts) >= 2: # 6.15.2 requires 2 or more line items along with their net or total
                    compatibleItemsFacts[frozenset(compatibleItemConcepts)].update(compatibleFacts)
        for compatibleItemConcepts, compatibleFacts in compatibleItemsFacts.items():
            foundSummationItemSet = False
            leastMissingItemsSet = compatibleItemConcepts
            for ELR in val.summationItemRelsSetAllELRs.linkRoleUris:
                relSet = val.modelXbrl.relationshipSet(XbrlConst.summationItem,ELR)
                missingItems = (compatibleItemConcepts -
                                frozenset(r.toModelObject
                                          for r in relSet.fromModelObject(totalConcept)))
                # may be slow, but must remove sibling or descendants to avoid annoying false positives
                # such as in http://www.sec.gov/Archives/edgar/data/1341439/000119312512129918/orcl-20120229.xml
                missingItems -= set(concept
                                    for concept in missingItems
                                    if relSet.isRelated(totalConcept, "sibling-or-descendant", concept))
                # items not required in sum
                unrequiredItems = set(concept
                                      for concept in missingItems
                                      if concept.name in ("CommitmentsAndContingencies"))
                missingItems -= unrequiredItems
                if missingItems:
                    if len(missingItems) < len(leastMissingItemsSet):
                        leastMissingItemsSet = missingItems
                else:
                    foundSummationItemSet = True
            '''
            # testing with DH (merge all calc ELRs instead of isolating calc ELRs)...
            relSet = val.modelXbrl.relationshipSet(XbrlConst.summationItem)
            missingItems = (compatibleItemConcepts -
                            frozenset(r.toModelObject
                                      for r in relSet.fromModelObject(totalConcept)))
            foundSummationItemSet = len(missingItems) == 0
            '''
            if not foundSummationItemSet:
                linkroleDefinition = val.modelXbrl.roleTypeDefinition(contributingRel.linkrole)
                reasonIssueIsWarning = ""
                msgCode = "ERROR-SEMANTIC"
                if isStatementSheet:
                    errs = ("EFM.6.15.02,6.13.02,6.13.03", "GFM.2.06.02,2.05.02,2.05.03")
                    msg = _("Financial statement calculation relationship missing from total concept to item concepts, based on required presentation of line items and totals.  "
                            "%(reasonIssueIsWarning)s"
                            "\n\nPresentation link role: \n%(linkrole)s \n%(linkroleDefinition)s. "
                            "\n\nTotal concept: \n%(conceptSum)s.  "
                            "\n\nReason presumed total: \n%(reasonPresumedTotal)s.  "
                            "\n\nSummation items missing: \n%(missingConcepts)s.  "
                            "\n\nExpected item concepts: \n%(itemConcepts)s.  "
                            "\n\nCorresponding facts in contexts: \n%(contextIDs)s\n")
                else:
                    errs = ("EFM.6.15.03,6.13.02,6.13.03", "GFM.2.06.03,2.05.02,2.05.03")
                    msg = _("Notes calculation relationship missing from total concept to item concepts, based on required presentation of line items and totals. "
                            "%(reasonIssueIsWarning)s"
                            "\n\nPresentation link role: \n%(linkrole)s \n%(linkroleDefinition)s."
                            "\n\nTotal concept: \n%(conceptSum)s.  "
                            "\n\nReason presumed total: \n%(reasonPresumedTotal)s.  "
                            "\n\nSummation items missing \n%(missingConcepts)s.  "
                            "\n\nExpected item concepts \n%(itemConcepts)s.  "
                            "\n\nCorresponding facts in contexts: \n%(contextIDs)s\n")
                # cases causing this issue to be a warning instead of an error
                if all(f.isNil for f in compatibleFacts if f.concept in leastMissingItemsSet):
                    reasonIssueIsWarning = _("\n\nMissing items are nil, which doesn't affect validity but may impair analysis of concept semantics from calculation relationships.  ")
                    msgCode = "WARNING-SEMANTIC"
                    errs = tuple(e + '.missingItemsNil' for e in errs)
                if "parenthetical" in linkroleDefinition.lower():
                    reasonIssueIsWarning += _("\n\nLink role is parenthetical.  ")
                    msgCode = "WARNING-SEMANTIC"
                    errs = tuple(e + '.parenthetical' for e in errs)
                """@messageCatalog=[
[["EFM.6.15.02,6.13.02,6.13.03", "GFM.2.06.02,2.05.02,2.05.03"],
"Financial statement calculation relationship missing from total concept to item concepts, based on required presentation of line items and totals.
%(reasonIssueIsWarning)s

Presentation link role:
%(linkrole)s
%(linkroleDefinition)s.

Total concept:
%(conceptSum)s.

Reason presumed total: n%(reasonPresumedTotal)s.

Summation items missing n%(missingConcepts)s.

Expected item concepts
%(itemConcepts)s.

Corresponding facts in contexts:
%(contextIDs)s
"],
[["EFM.6.15.03,6.13.02,6.13.03", "GFM.2.06.03,2.05.02,2.05.03"],
"Notes calculation relationship missing from total concept to item concepts, based on required presentation of line items and totals.
%(reasonIssueIsWarning)s

Presentation link role:
%(linkrole)s
%(linkroleDefinition)s.

Total concept:
%(conceptSum)s.

Reason presumed total:
%(reasonPresumedTotal)s.

Summation items missing
%(missingConcepts)s.

Expected item concepts
%(itemConcepts)s.

Corresponding facts in contexts:
%(contextIDs)s"]]"""
                val.modelXbrl.log(msgCode, errs, msg,
                    modelObject=[totalConcept, totalRel, siblingConcept, contributingRel] + [f for f in compatibleFacts],
                    reasonIssueIsWarning=reasonIssueIsWarning,
                    conceptSum=totalConcept.qname, linkrole=contributingRel.linkrole, linkroleDefinition=linkroleDefinition,
                    reasonPresumedTotal=reasonPresumedTotal,
                    itemConcepts=', \n'.join(sorted(set(str(c.qname) for c in compatibleItemConcepts))),
                    missingConcepts = ', \n'.join(sorted(set(str(c.qname) for c in leastMissingItemsSet))),
                    contextIDs=', '.join(sorted(set(f.contextID for f in compatibleFacts))))
            leastMissingItemsSet = None #dereference, can't delete with Python 3.1
            del foundSummationItemSet
        del compatibleItemsFacts # dereference object references
