from arelle.ModelValue import qname
import time
from collections import defaultdict

caNamespace = "http://xbrl.us/corporateActions/2011-05-31"

qnEventOptionsSequenceTypedAxis = qname("{http://xbrl.us/corporateActions/2011-05-31}ca:EventOptionsSequenceTypedAxis")
qnEventTypeAxis = qname("{http://xbrl.us/corporateActions/2011-05-31}ca:EventTypeAxis")
qnIssueTypeAxis = qname("{http://xbrl.us/corporateActions/2011-05-31}ca:IssueTypeAxis")
qnMarketTypeAxis = qname("{http://xbrl.us/corporateActions/2011-05-31}ca:MarketTypeAxis")
qnMandatoryVoluntaryAxis = qname("{http://xbrl.us/corporateActions/2011-05-31}ca:MandatoryVoluntaryAxis")
qnStatusAxis = qname("{http://xbrl.us/corporateActions/2011-05-31}ca:StatusAxis")
qnUnderlyingSecuritiesImpactedTypedAxis = qname("{http://xbrl.us/corporateActions/2011-05-31}ca:UnderlyingSecuritiesImpactedTypedAxis")
qnUnderlyingInstrumentIdentifierSchemeAxis = qname("{http://xbrl.us/corporateActions/2011-05-31}ca:UnderlyingInstrumentIdentifierSchemeAxis")
qnEventOptionsSequenceTypedAxis = qname("{http://xbrl.us/corporateActions/2011-05-31}ca:EventOptionsSequenceTypedAxis")
qnPayoutSequenceTypedAxis = qname("{http://xbrl.us/corporateActions/2011-05-31}ca:PayoutSequenceTypedAxis")
qnPayoutSecurityIdentifierSchemeAxis =  qname("{http://xbrl.us/corporateActions/2011-05-31}ca:PayoutSecurityIdentifierSchemeAxis")

qnCashDividendMember = qname("{http://xbrl.us/corporateActions/2011-05-31}ca:CashDividendMember")
qnStockDividendMember = qname("{http://xbrl.us/corporateActions/2011-05-31}ca:StockDividendMember")
qnUnitedStatesMember = qname("{http://xbrl.us/corporateActions/2011-05-31}ca:UnitedStatesMember")
qnEquityMember = qname("{http://xbrl.us/corporateActions/2011-05-31}ca:EquityMember")
qnMandatoryMember = qname("{http://xbrl.us/corporateActions/2011-05-31}ca:MandatoryMember")
qnCancelMember = qname("{http://xbrl.us/corporateActions/2011-05-31}ca:CancelMember")
qnUnconfirmedMember = qname("{http://xbrl.us/corporateActions/2011-05-31}ca:UnconfirmedMember")
qnPreliminaryMember = qname("{http://xbrl.us/corporateActions/2011-05-31}ca:PreliminaryMember")

eventTypeMap = { 
"CashDividendMember": {"Cash Dividend", "Sale Of Rights"},
"StockDividendMember": {"Stock Dividend"},
"SpecialDividendMember": {"Special Dividend"},
"CashDividendWithCurrencyOptionMember": {"Cash Dividend with Currency Option"},
"DividendwithOptionMember": {"Dividend with Option"},
"CancelMember": {"Sale Of Rights", "Annual General Meeting", "Assimilation", "Attachment",
                "Automatic Dividend Reinvestment",
                "Bankruptcy Note", "Bankruptcy Vote", "Bankruptcy",
                "Bearer to Registered Form",
                "Bid Tender / Sealed Tender",
                "Bonus Issue", "Bonus Rights Issue",
                "Buy Up",
                "Capital Distribution", "Capital Gains Distribution", "Capitalisation",
                "Cash and Securities Merger",
                "Cash Dividend with Currency Option", "Cash Dividend",
                "Cash in Lieu", "Cash Merger",
                "Change in Board Lot", "Change in Domicile", "Change in Name",
                "Change in Place of Incorporation", "Change in Place of Listing",
                "Change In Security Term",
                "Change Resulting in Decrease of Par Value", "Change Resulting in Increase of Par Value",
                "Class Action",
                "Consent for Plan of Reorganization", "Consent Tender", "Consent with No Payout", "Consent with Payout",
                "Convert And Tender",
                "Convertible Security Issue",
                "Coupon Distribution",
                "Credit Event",
                "Decimalisation",
                "Default",
                "Dematerialised to Physical Form",
                "Dissent",
                "Distribution on Recapitalization", "Distribution",
                "Dividend Reinvestment", "Dividend with Option",
                "Drawing",
                "Dutch Auction Tender", "Dutch Auction",
                "Exchange Offer with Consent Fee", "Exchange Offer",
                "Exchange on 144a Type Securities", "Exchange on Reg S Type Securities",
                "Exercise",
                "Extraordinary General Meeting",
                "Final Paydown",
                "Full Call on Convertible Security", "Full Call",
                "Full Pre-refunding",
                "General Information",
                "Global Permanent to Physical Form",
                "Global Temporary to Global Permanent Form", "Global Temporary to Physical Form",
                "Holdings Disclosure",
                "Interest",
                "Issue Fraction",
                "Liquidation",
                "Mandatory (Put) Tender", "Mandatory (Put) With Option to Retain",
                "Mandatory Exchange", "Mandatory Redemption of Shares",
                "Mandatory Tender", "Maturity Extension",
                "Maturity",
                "Meeting",
                "Merger",
                "Mini Tender",
                "Mortgage Backed",
                "Non US TEFRAD Certification",
                "Odd Lot Offer",
                "Offer To Purchase",
                "Ordinary Meeting",
                "Par Value Change",
                "Partial Call on Convertible Security", "Partial Call With Reduction in Nominal Value",
                "Partial Call",
                "Partial Defeasance",
                "Partial Mandatory (Put) Tender", "Partial Mandatory Tender",
                "Partial Prerefunding",
                "Pay in Kind",
                "Physical to Dematerialised Form", "Physical to Dematerialized Form",
                "Principal",
                "Put",
                "Redemption",
                "Redenomination",
                "Registered to Bearer Form",
                "Remarketing Agreement", "Remarketing",
                "Reorganization",
                "Return of Capital",
                "Reverse Stock Split",
                "Rights Issue", "Rights Subscription",
                "Round Down", "Round to Nearest", "Round Up",
                "Sale of Assets",
                "Securities Merger", "Security Delisted", "Security Separation", "Security to Certificate ",
                "Self Tender",
                "Share Exchange", "Share Premium Dividend",
                "Special Dividend Reinvestment", "Special Dividend",
                "Special Meeting",
                "Special Memorial Dividend",
                "Spinoff",
                "Standard Exchange",
                "Stock Dividend",
                "Stock Split with Mandatory Redemption of Shares", "Stock Split",
                "Subscription Offer Open Offer", "Subscription Offer Share Purchase Plan",
                "Subscription Offer",
                "Survivor Option",
                "Temporary Rate/Price Change",
                "Tender With Rights",
                "Termination",
                "Trading Status Active",
                "Transfer",
                "Unknown",
                "Warrants Issue"}
                }

def checkCorporateActions(val):
    modelXbrl = val.modelXbrl
    if not caNamespace in modelXbrl.namespaceDocs:
        return # no corporate actions taxonomy

    startedAt = time.time()
    caFacts = defaultdict(list)
    hasUsEquityCashDiv = False
    hasUsEquityStockDiv = False
    hasCancel = False
    for f in modelXbrl.facts:
        if f.qname.namespaceURI == caNamespace:
            caFacts[f.qname.localName].append(f)
            context = f.context
            qnEventTypeMember = context.dimMemberQname(qnEventTypeAxis)
            qnMarketTypeMember = context.dimMemberQname(qnMarketTypeAxis)
            qnIssueTypeMember = context.dimMemberQname(qnIssueTypeAxis)
            qnMandatoryVoluntaryMember = context.dimMemberQname(qnMandatoryVoluntaryAxis) 
            if (not hasUsEquityCashDiv and 
                qnEventTypeMember == qnCashDividendMember and
                qnMarketTypeMember == qnUnitedStatesMember and
                qnIssueTypeMember == qnEquityMember and
                qnMandatoryVoluntaryMember == qnMandatoryMember):
                hasUsEquityCashDiv = True
            if (not hasUsEquityStockDiv and 
                qnEventTypeMember == qnStockDividendMember and
                qnMarketTypeMember == qnUnitedStatesMember and
                qnIssueTypeMember == qnEquityMember and
                qnMandatoryVoluntaryMember == qnMandatoryMember):
                hasUsEquityStockDiv = True
            if (not hasCancel and 
                qnEventTypeMember == qnCancelMember and
                qnMarketTypeMember == qnCancelMember and
                qnIssueTypeMember == qnCancelMember and
                qnMandatoryVoluntaryMember == qnCancelMember):
                hasUsEquityStockDiv = True

    hasEventComplete = any(f.xValue == "Complete"
                           for f in caFacts["EventCompleteness"])
    
    if hasEventComplete:
        facts = [f for f in modelXbrl.facts 
                 if f.context.dimMemberQname(qnStatusAxis) == qnPreliminaryMember]
        if facts:
            modelXbrl.log('ERROR-SEMANTIC', "US-CA.PreliminaryAndComplete.100",
                _("Facts have a preliminary status, but the event is indicated to be complete: %(facts)s"),
                modelObject=facts, facts=", ".join(f.localName for f in facts))

        facts = [f for f in modelXbrl.facts 
                 if f.context.dimMemberQname(qnStatusAxis) == qnUnconfirmedMember]
        if facts:
            modelXbrl.log('ERROR-SEMANTIC', "US-CA.UnconfirmedAndComplete.101",
                _("Facts have an unconfirmed status, but the event is indicated to be complete: %(facts)s"),
                modelObject=facts, facts=", ".join(f.localName for f in facts))

    for i, localName in ((1, "AnnouncementDate"), (2, "EventCompleteness"), (3, "UniqueUniversalEventIdentifier"),
                         (4, "AnnouncementIdentifier"), (5, "AnnouncementType"), (6, "EventType"),
                         (7, "MandatoryVoluntaryChoiceIndicator"), (9, "RecordDate")):
        if localName not in caFacts:
            modelXbrl.log('ERROR-SEMANTIC', "US-CA.Exists.{0}".format(i),
                _("A %(fact)s must exist in the document."),
                modelObject=modelXbrl, fact=localName)
    if not any(f.context.hasDimension(qnUnderlyingSecuritiesImpactedTypedAxis) and
               f.context.hasDimension(qnUnderlyingInstrumentIdentifierSchemeAxis) 
               for f in caFacts["InstrumentIdentifier"]):
        modelXbrl.log('ERROR-SEMANTIC', "US-CA.Exists.7",
            _("A InstrumentIdentifier must exist in the document for the security impacted by the corporate action."),
            modelObject=modelXbrl, fact="InstrumentIdentifier")
        
    if hasEventComplete:
        if not caFacts["EventConfirmationStatus"]:
            modelXbrl.log('ERROR-SEMANTIC', "US-CA.Exists.10",
                _("An EventConfirmationStatus must exist in the document if the document is Complete."),
                modelObject=modelXbrl, fact="EventConfirmationStatus")
        if hasUsEquityCashDiv:
            for i, localName in ((12, "CountryOfIssuer"), (14, "PaymentDate")):
                if not caFacts[localName]:
                    modelXbrl.log('ERROR-SEMANTIC', "US-CA.Exists.{0}".format(i),
                        _("A %(fact)s must exist in the document if the document is Complete."),
                        modelObject=modelXbrl, fact=localName)
            if not any(f.context.hasDimension(qnEventOptionsSequenceTypedAxis)
                       for f in caFacts["OptionType"]):
                modelXbrl.log('ERROR-SEMANTIC', "US-CA.Exists.15",
                    _("A OptionType must exist in the document for the security impacted by the corporate action."),
                    modelObject=modelXbrl, fact="InstrumentIdentifier")
    
    dupFacts = defaultdict(list)
    for localName, facts in caFacts.items():
        for f in facts:
            dupFacts[f.context.contextDimAwareHash].append(f)
        for dups in dupFacts.values():
            if len(dups) > 1:
                modelXbrl.log('ERROR-SEMANTIC', "US-CA.DuplicateValue.11",
                    _("Fact %(fact)s exists %(count)s times in the document."),
                    modelObject=dups, fact=localName, count=len(dups))
        dupFacts.clear()
    del dupFacts

    if hasUsEquityCashDiv:
        countOptions = len(caFacts["OptionType"])
        if not countOptions:
            modelXbrl.log('ERROR-SEMANTIC', "US-CA.atLeastOneOptionIsRequired.16",
                _("At least one %(fact)s must be defined for a mandatory cash dividend."),
                modelObject=modelXbrl, fact="OptionType")
        countWithholdingRates = len(caFacts["WithholdingTaxPercentage"])
        if (countOptions != len(caFacts["TaxRateDescription"]) and
            countOptions > 1 and
            countWithholdingRates != countOptions):
            modelXbrl.log('ERROR-SEMANTIC', "US-CA.noMoreThanOnOption.16a",
                _("More than one option has been defined for a cash dividend only one Option can be defined for a mandatory cash dividend unless there is multiple tax rates defined. In the file there are %(countOfWithholdingRates)s unique withholding rates defined but %(countOfOptions)s options defined."),
                modelObject=modelXbrl, fact="OptionType", 
                countOfWithholdingRates=countWithholdingRates, countOfOptions=countOptions)
        for f in caFacts["OptionType"]:
            if f.xValue != "Cash":
                modelXbrl.log('ERROR-SEMANTIC', "US-CA.onlyOneOptionAllowed.26",
                    _("The Option Type for a mandatory cash dividend, %(value)s must be defined as \"Cash\"."),
                    modelObject=f, fact="OptionType", value=f.value)
        for f in caFacts["PayoutType"]:
            if f.xValue != "Dividend":
                modelXbrl.log('ERROR-SEMANTIC', "US-CA.paymentOptions.17",
                    _("The Payout Type for a cash dividend, %(value)s must be defined as \"Dividend\"."),
                    modelObject=f, fact="PayoutType", value=f.value)
    
    for f1 in caFacts["PayoutAmount"]:
        for f2 in caFacts["PayoutAmountNetOfTax"]:
            if f1.xValue < f2.xValue:
                modelXbrl.log('ERROR-SEMANTIC', "US-CA.gte.18",
                    _("The PayoutType %(value1)s must be greater than PayoutAmountNetOfTax %(value2)s."),
                    modelObject=(f1,f2), fact="PayoutAmount", value1=f1.value, value2=f2.value)
    
    for i, localName in ((19, "PayoutAmount"), (21, "PayoutAmountNetOfTax")):
        for f in caFacts[localName]:
            if f.xValue < 0:
                modelXbrl.log('ERROR-SEMANTIC', "US-CA.nonNeg.{0}".format(i),
                    _("The %(fact)s, %(value)s must be positive."),
                    modelObject=f, fact=localName, value=f.value)
    
    for i, localName1, localName2 in ((22, "PaymentDate", "RecordDate"),
                                      (23, "OrdPaymentDate", "OrdRecordDate")):
        for f1 in caFacts[localName1]:
            for f2 in caFacts[localName2]:
                if f1.context.endDatetime < f2.context.endDatetime:
                    modelXbrl.log('ERROR-SEMANTIC', "US-CA.date.{0}".format(i),
                        _("The %(fact1)s %(value1)s must be later than the %(fact2)s %(value2)s."),
                        modelObject=(f1,f2), fact1=localName1, fact2=localName2, value1=f1.value, value2=f2.value)
            

    if hasUsEquityCashDiv:
        for f in caFacts["EventType"]:
            eventTypeMember = f.context.dimMemberQname(qnEventTypeAxis)
            if eventTypeMember:
                if f.xValue not in eventTypeMap[eventTypeMember.localName]:
                    modelXbrl.log('ERROR-SEMANTIC', "US-CA.eventTypeMatch.20",
                        _("The %(fact)s, %(value)s must be defined as \"Cash Dividend\" or \"Sale Of Rights\"."),
                        modelObject=f, fact="EventType", value=f.value)
        paymentDateFacts = caFacts["PaymentDate"]
        for fEvent in paymentDateFacts:
            if (qnEventOptionsSequenceTypedAxis not in fEvent.context.qnameDims and
                qnPayoutSequenceTypedAxis not in fEvent.context.qnameDims):
                for fDetail in paymentDateFacts:
                    if (f.context.hasDimension(qnEventOptionsSequenceTypedAxis) and
                        f.context.hasDimension(qnPayoutSequenceTypedAxis) and
                        fEvent.xValue != fDetail.xValue):
                        modelXbrl.log('ERROR-SEMANTIC', "US-CA.us-equity-cashDiv-mand.dupValues.24",
                            _("The PaymentDate %(detailValue)s at the detail level must equal the PaymentDate %(eventValue)s at the event level."),
                            modelObject=(fDetail,fEvent), fact="PaymentDate", detailValue=fDetail.value, eventValue=fEvent.value)
                        
        for i, f1 in enumerate(paymentDateFacts):
            if (not f.context.hasDimension(qnEventOptionsSequenceTypedAxis) and
                not f.context.hasDimension(qnPayoutSequenceTypedAxis)):
                for f2 in paymentDateFacts[i+1:]:
                    if (f.context.hasDimension(qnEventOptionsSequenceTypedAxis) and
                        f.context.hasDimension(qnPayoutSequenceTypedAxis) and
                        f1.xValue != f2.xValue):
                        modelXbrl.log('ERROR-SEMANTIC', "US-CA.us-equity-cashDiv-mand.multPayouts.25",
                            _("The PaymentDate %(detailValue)s at the detail level must equal the PaymentDate %(eventValue)s at the detail level."),
                            modelObject=(f1, f2), fact="PaymentDate", detailValue=f1.value, eventValue=f2.value)
                        
        if (hasEventComplete and
            len(caFacts["OptionType"]) > len(caFacts["PayoutType"])):
                modelXbrl.log('ERROR-SEMANTIC', "US-CA.us-equity-cashDiv-mand.missingPayouts.25a",
                    _("The number of payouts associated with a cash dividend must match the number of options on a complete corporate action event.  Each option must have at least one payout associated with it."),
                    modelObject=(caFacts["OptionType"] + caFacts["PayoutType"]))
            
        if len(caFacts["OptionType"]) > 1:
            fmax = None
            maxValue = max((f.xValue for f in caFacts["WithholdingTaxPercentage"]))
            f1 = None
            for f in caFacts["WithholdingTaxPercentage"]:
                if fmax is None or f.xValue > fmax.xValue:
                    fmax = f
                if (f.context.hasDimension(qnEventOptionsSequenceTypedAxis) and
                    f.context.dimValue(qnEventOptionsSequenceTypedAxis).typedMember.xValue == 1):
                    f1 = f
            if f1 is not None and fmax.xValue != f1.xValue:
                modelXbrl.log('ERROR-SEMANTIC', "US-CA.noMoreThanOnOption.16b",
                    _("In those cases where multiple tax rates are defined the highest rate typically represents the payout rate associated with the "
                      "corporate action to the clearing and settlement organization. The first option should represent the distribution made for settlement. "
                      "In this case the withholding tax rate for option 1 is %(seq1Value)s. This is not the maximium withholding rate assoicated with the "
                      "action which is %(maxValue)s. Make the payout with the highest withholding rate the first option."),
                    modelObject=(fmax,f1),maxValue=fmax.value, seq1Value=f1.value)
            

    for fPayoutAmt in caFacts["PayoutAmount"]:
        for fPayoutAmtNetOfTax in caFacts["PayoutAmountNetOfTax"]:
            if fPayoutAmt.context.contextDimAwareHash == fPayoutAmtNetOfTax.context.contextDimAwareHash:
                for fTax in caFacts["TaxAmountWithheldFromPayout"]:
                    if (fPayoutAmt.context.contextDimAwareHash == fTax.context.contextDimAwareHash and
                        fPayoutAmt.xValue < fPayoutAmtNetOfTax.xValue + fTax.xValue):
                        modelXbrl.log('ERROR-SEMANTIC', "US-CA.ne.26",
                            _("The PayoutAmount of %(payoutAmt)s must always be greater than or equal to the sum of PayoutAmountNetOfTax with a value of "
                              "%(payoutNetOfTax)s and TaxAmountWithheldFromPayout with a value of %(taxAmt)s."),
                            modelObject=(fPayoutAmt, fPayoutAmtNetOfTax, fTax), 
                            payoutAmt=fPayoutAmt.xValue,
                            payoutNetOfTax=fPayoutAmtNetOfTax.xValue,
                            taxAmt=fTax.xValue)

    # stock dividend
    if hasUsEquityStockDiv:
        if len(caFacts["OptionType"]) != 1:
            modelXbrl.log('ERROR-SEMANTIC', "US-CA.stockDiv.onlyOneOptionAllowed.41",
                _("Only one Option Type can be defined for a mandatory stock dividend."),
                modelObject=caFacts["OptionType"],) 

        if (len(caFacts["OptionType"]) != len(caFacts["TaxRateDescription"]) and
            len(caFacts["OptionType"]) > 1 and
            len(set(f.xValue
                    for f in caFacts["WithholdingTaxPercentage"])) != len(caFacts["OptionType"])):
            modelXbrl.log('ERROR-SEMANTIC', "US-CA.noMoreThanOnOption.41a",
                _("More than one option has been defined for a stock dividend. Only one Option can be defined for a mandatory stock dividend unless there is multiple tax rates defined.\n(id:41a)\n$"),
                modelObject=caFacts["OptionType"]) 
    
        if hasEventComplete and not caFacts["CountryOfIssuer"]:
            modelXbrl.log('ERROR-SEMANTIC', "US-CA.completedExists.50",
                _("The Country Of Issuer must be populated in the document for a stock Dividend if the document is complete."),
                modelObject=val.modeXbrl, fact="CountryOfIssuer") 
                        
        if (hasEventComplete and 
            not any(f.context.hasDimension(qnEventOptionsSequenceTypedAxis) 
                    for f in caFacts["OptionType"])):
            modelXbrl.log('ERROR-SEMANTIC', "US-CA.completedExists.48",
                _("The Option Type must be populated in the document if the document is complete."),
                modelObject=val.modeXbrl, fact="OptionType") 
            
        if not any(f.context.hasDimension(qnUnderlyingSecuritiesImpactedTypedAxis) and
                   f.context.hasDimension(qnUnderlyingInstrumentIdentifierSchemeAxis) 
                   for f in caFacts["InstrumentIdentifier"]):
            modelXbrl.log('ERROR-SEMANTIC', "US-CA.exists.40",
                _("An InstrumentIdentifier fact must exist in the document for the security impacted by the corporate action."),
                modelObject=val.modeXbrl, fact="InstrumentIdentifier") 
            
        if not caFacts["RecordDate"]:
            modelXbrl.log('ERROR-SEMANTIC', "US-CA.exists.42",
                _("A RecordDate fact must exist in the document."),
                modelObject=val.modeXbrl, fact="RecordDate") 
                        
        if hasEventComplete and not caFacts["PaymentDate"]:
            modelXbrl.log('ERROR-SEMANTIC', "US-CA.completedExists.43",
                _("The PaymentDate must be populated in the document if the document is complete."),
                modelObject=val.modeXbrl, fact="PaymentDate")
             
        for f in caFacts["PayoutType"]:
            if f.xValue != "Dividend":
                modelXbrl.log('ERROR-SEMANTIC', "US-CA.stockDiv.paymentOptions.44",
                    _("The Payout Type for a cash dividend must be defined as a \"Dividend\"."),
                    modelObject=f, fact="PayoutType")

        for f in caFacts["OptionType"]:
            if f.xValue != "Securities":
                modelXbrl.log('ERROR-SEMANTIC', "US-CA.stockDiv.optionType.45",
                    _("The Option Type for a cash dividend must be defined as a \"Securities\"."),
                    modelObject=f, fact="OptionType")

        for f in caFacts["EventType"]:
            eventTypeMember = f.context.dimMemberQname(qnEventTypeAxis)
            if eventTypeMember:
                if f.xValue not in eventTypeMap[eventTypeMember.localName]:
                    modelXbrl.log('ERROR-SEMANTIC', "US-CA.stockDiv-mand.eventTypeMatch.46",
                        _("The %(fact)s, %(value)s must be defined as \"Stock Dividend\"."),
                        modelObject=f, fact="EventType", value=f.value)

        paymentDateFacts = caFacts["PaymentDate"]
        for i, f1 in paymentDateFacts:
            if (not f.context.hasDimension(qnEventOptionsSequenceTypedAxis) and
                not f.context.hasDimension(qnPayoutSequenceTypedAxis)):
                for f2 in paymentDateFacts[i+1:]:
                    if (f.context.hasDimension(qnEventOptionsSequenceTypedAxis) and
                        f.context.hasDimension(qnPayoutSequenceTypedAxis) and
                        f1.xValue != f2.xValue):
                        modelXbrl.log('ERROR-SEMANTIC', "US-CA.stockDiv-mand.dupValues.47",
                            _("The PaymentDate %(detailValue)s at the detail level must equal the PaymentDate %(eventValue)s at the detail level."),
                            modelObject=(f1, f2), fact="PaymentDate", detailValue=f1.value, eventValue=f2.value)
          
        if (hasEventComplete and
            not any(f.context.hasDimension(qnPayoutSequenceTypedAxis) and
                    not f.context.hasDimension(qnPayoutSecurityIdentifierSchemeAxis)
                    for f in caFacts["InstrumentIdentifier"])):
            modelXbrl.log('ERROR-SEMANTIC', "US-CA.completedExists.49",
                _("An InstrumentIdentifier fact must exist in the document for the security paid out as part of the corporate action if the event is complete"),
                modelObject=modelXbrl, fact="InstrumentIdentifier")
                        
        if (hasEventComplete and
            len(caFacts["OptionType"]) > len(caFacts["PayoutType"])):
                modelXbrl.log('ERROR-SEMANTIC', "US-CA.stockDiv-mand.missingPayouts.49a",
                    _("The number of payouts associated with a stock dividend must match the number of options on a complete corporate action event.  Each option must have at least one payout associated with it."),
                    modelObject=(caFacts["OptionType"] + caFacts["PayoutType"]))
                
        if (hasEventComplete and
            not any(f.context.hasDimension(qnPayoutSequenceTypedAxis)
                    for f in caFacts["DisbursedQuantity"])):
            modelXbrl.log('ERROR-SEMANTIC', "US-CA.stockDiv-mand.missingPayouts.49b",
                _("An DisbursedQuantity fact must exist in the document for the security paid out as part of the corporate action if the event is complete."),
                modelObject=modelXbrl, fact="DisbursedQuantity")

        if (hasEventComplete and
            not any(f.context.hasDimension(qnPayoutSequenceTypedAxis)
                    for f in caFacts["BaseQuantity"])):
            modelXbrl.log('ERROR-SEMANTIC', "US-CA.stockDiv-mand.missingPayouts.49c",
                _("An BaseQuantity fact must exist in the document for the security paid out as part of the corporate action if the event is complete."),
                modelObject=modelXbrl, fact="BaseQuantity")
            
    if hasCancel:
        if not hasEventComplete:
            modelXbrl.log('ERROR-SEMANTIC', "US-CA.cancelComplete.30",
                _("The Details Completness Status (EventCompletenes) must have a value of Complete for a cancel event."),
                modelObject=modelXbrl, fact="EventCompleteness")
            
        if not caFacts["EventCompleteness"]:
            modelXbrl.log('ERROR-SEMANTIC', "US-CA.exists.31",
                _("The Details Completness Status must must be tagged in the cancel document with a value of Complete."),
                modelObject=modelXbrl, fact="EventCompleteness")
            
        if not (caFacts["EventConfirmationStatus"] and
                all(f.xValue == "Confirmed" 
                    for f in caFacts["EventConfirmationStatus"])):
            modelXbrl.log('ERROR-SEMANTIC', "US-CA.cancelComplete.32",
                _("The Event Confirmation Status must be tagged with a value of Confirmed for a cancel event."),
                modelObject=modelXbrl, fact="EventConfirmationStatus")

        facts = [f for f in modelXbrl.facts 
                 if f.context.dimValue(qnStatusAxis) == qnUnconfirmedMember]
        if facts:
            modelXbrl.log('ERROR-SEMANTIC', "US-CA.cancel.invalid_member.33",
                _("Facts have been reported with the UnconfirmedMember on the StatusAxis for a cancel event: %(facts)s."),
                modelObject=facts, facts=", ".join(f.localName for f in facts))
            
        facts = [f for f in modelXbrl.facts
                 if f.context.dimValue(qnStatusAxis) == qnPreliminaryMember and
                    f.context.dimValue(qnEventTypeAxis) == qnCancelMember]
        if facts:
            modelXbrl.log('ERROR-SEMANTIC', "US-CA.cancel.invalid_member.34",
                _("Facts have been reported with the PreliminaryMember on the StatusAxis for a cancel event: %(facts)s. "
                  "A cancel event must use the ConfirmedMember on the StatusAxis."),
                modelObject=facts, facts=", ".join(f.localName for f in facts))
            
        facts = [f for f in modelXbrl.facts
                 if f.context.dimValue(qnStatusAxis) == qnUnconfirmedMember and
                    f.context.dimValue(qnEventTypeAxis) == qnCancelMember]
        if facts:
            modelXbrl.log('ERROR-SEMANTIC', "US-CA.cancel.invalid_member.36",
                _("Facts have been reported with the UnconfirmedMember on the StatusAxis for a cancel event: %(facts)s. "
                  "A cancel event must use the ConfirmedMember on the StatusAxis."),
                modelObject=facts, facts=", ".join(f.localName for f in facts))
            
      
        for f in caFacts["EventType"]:
            eventTypeMember = f.context.dimMemberQname(qnEventTypeAxis)
            if eventTypeMember:
                if f.xValue not in eventTypeMap[eventTypeMember.localName]:
                    modelXbrl.log('ERROR-SEMANTIC', "US-CA.cancel.eventTypeMatch.37",
                        _("The %(fact)s, %(value)s must be defined as \"Stock Dividend\"."),
                        modelObject=f, fact="EventType", value=f.value)

    if 'facts' in locals():
        del facts
    del caFacts  # dereference explicitly
                        
    modelXbrl.profileStat(_("validate US Corporate Actions"), time.time() - startedAt)     
            
__pluginInfo__ = {
    # Do not use _( ) in pluginInfo itself (it is applied later, after loading
    'name': 'Validate XBRL-US Corporate Actions',
    'version': '0.9',
    'description': '''XBRL-US Corporate Actions Validation.''',
    'license': 'Apache-2',
    'author': 'Ewe S. Gap',
    'copyright': '(c) Copyright 2012 Mark V Systems Limited, All rights reserved.',
    # classes of mount points (required)
    'Validate.XBRL.Finally': checkCorporateActions,
}
