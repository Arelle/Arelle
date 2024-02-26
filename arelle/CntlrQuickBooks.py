'''
This module implements Quick Books server mode

See COPYRIGHT.md for copyright information.
'''
from __future__ import annotations

from lxml import etree
import uuid, io, datetime
from arelle import XmlUtil

clientVersion = None
userName = None
sessions = {}  # use when interactive session started by Quickbooks side (not used now)
qbRequests = []  # used by rest API or GUI requests for QB data
qbRequestStatus = {}
xbrlInstances = {}
cntlr = None

# report in url path request and type of query to QB
supportedQbReports = {'trialBalance':'GeneralSummary',
                      'generalLedger':'GeneralDetail',
                      'journal':'GeneralDetail'
                     }
# some reports don't provide the needed columns, request explicitly
includeQbColumns = {'trialBalance': '',
                    'generalLedger': '''
<IncludeColumn>TxnType</IncludeColumn>
<IncludeColumn>Date</IncludeColumn>
<IncludeColumn>RefNumber</IncludeColumn>
<IncludeColumn>Name</IncludeColumn>
<IncludeColumn>Memo</IncludeColumn>
<IncludeColumn>SplitAccount</IncludeColumn>
<IncludeColumn>Credit</IncludeColumn>
<IncludeColumn>Debit</IncludeColumn>
<IncludeColumn>RunningBalance</IncludeColumn>
''',
                 'journal': ''
                 }
glEntriesType = {'trialBalance':'trialbalance',
                 'generalLedger':'balance',
                 'journal':'journal'
                }

qbTxnTypeToGL = {# QB code is case insensitive comparision (lowercase, some QBs do not have expected camel case)
                 'bill':'voucher', # bills from vendors
                 'billpayment':'check', # credits from vendors
                 'billpaymentcheck':'check', # payments to vendors from bank account
                 'billpmt-check':'check',  # QB 2009
                 'billpaymentcreditcard':'payment-other',  # payments to vendor from credit card account
                 'buildassembly':'other',
                 'charge':'other',
                 'check':'check', # checks written on bank account
                 'credit':'credit-memo',
                 'creditcardcharge':'payment-other', # credit card account charge
                 'creditcardcredit':'other', # credit card account credit
                 'creditmemo':'credit-memo', # credit memo to customer
                 'deposit':'check', # GL calls it check whether sent or received
                 'discount':'credit-memo',
                 'estimate':'other',
                 'generaljournal':'manual-adjustment',
                 'inventoryadjustment':'other',
                 'invoice':'invoice',
                 'itemreceipt':'receipt',
                 'journalentry':'manual-adjustment',
                 'liabilitycheck': 'check',
                 'payment': 'check',
                 'paycheck': 'check',
                 'purchaseorder':'order-vendor',
                 'receivepayment':'payment-other',
                 'salesorder':'order-customer',
                 'salesreceipt':'other',
                 'salestaxpaymentcheck':'check',
                 'statementcharge':'other',
                 'transfer':'payment-other',
                 'vendorcredit':'credit-memo',
                 }

def server(_cntlr, soapFile, requestUrlParts) -> str:
    global cntlr
    if cntlr is None: cntlr = _cntlr
    soapDocument = etree.parse(soapFile)
    soapBody = soapDocument.find("{http://schemas.xmlsoap.org/soap/envelope/}Body")
    if soapBody is None:
        return ""
    else:
        for request in soapBody.iterchildren():
            requestName = request.tag.partition("}")[2]
            print ("request {0}".format(requestName))
            response = None
            if request.tag == "{http://developer.intuit.com/}serverVersion":
                response = "Arelle 1.0"
            elif request.tag == "{http://developer.intuit.com/}clientVersion":
                global clientVersion
                clientVersion = request.find("{http://developer.intuit.com/}strVersion").text
            elif request.tag == "{http://developer.intuit.com/}authenticate":
                #global userName  # not needed for now
                #userName = request.find("{http://developer.intuit.com/}strUserName").text
                #password is ignored
                ticket = str(uuid.uuid1())
                global qbRequests
                if qbRequests: # start a non-interactive session
                    response = [ticket, ""]
                    sessions[ticket] = qbRequests
                    qbRequests = []
                else:
                    # to start an interactive session automatically from QB side, uncomment
                    #response = [ticket, "" if not sessions else "none"] # don't start session if one already there
                    #sessions[ticket] = [{"request":"StartInteractiveMode"}]
                    response = [ticket, "none"]  # response to not start interactive mode
            elif request.tag == "{http://developer.intuit.com/}sendRequestXML":
                ticket = request.find("{http://developer.intuit.com/}ticket").text
                _qbRequests = sessions.get(ticket)
                if _qbRequests:
                    _qbRequest = _qbRequests[0]
                    action = _qbRequest["request"]
                    if action == "StartInteractiveMode":
                        response = ''
                    elif action in supportedQbReports:
                        # add company info to request dict
                        _qbRequest["strHCPResponse"] = request.find("{http://developer.intuit.com/}strHCPResponse").text
                        response = ('''<?xml version="1.0"?>
<?qbxml version="8.0"?>
<QBXML>
  <QBXMLMsgsRq onError="stopOnError">
    <{1}ReportQueryRq>
      <{1}ReportType>{0}</{1}ReportType>
      <ReportPeriod>
        <FromReportDate>{2}</FromReportDate>
        <ToReportDate>{3}</ToReportDate>
      </ReportPeriod>{4}
    </{1}ReportQueryRq>
  </QBXMLMsgsRq>
</QBXML>''').format(action[0].upper() + action[1:],
                    supportedQbReports[action],
                    _qbRequest["fromDate"],
                    _qbRequest["toDate"],
                    includeQbColumns[action],
                    ).replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")

            elif request.tag == "{http://developer.intuit.com/}connectionError":
                ticket = request.find("{http://developer.intuit.com/}ticket").text
                hresult = request.find("{http://developer.intuit.com/}hresult").text
                if hresult and hresult.startswith("0x"):
                    hresult = hresult[2:] # remove 0x if present
                message = request.find("{http://developer.intuit.com/}message").text
                print ("connection error message: [{0}] {1}".format(hresult, message))
                _qbRequests = sessions.get(ticket)
                if _qbRequests:
                    qbRequestTicket = _qbRequests[0]["ticket"]
                    qbRequestStatus[qbRequestTicket] = "ConnectionErrorMessage: [{0}] {1}".format(hresult, message)
                response = "done"
            elif request.tag == "{http://developer.intuit.com/}receiveResponseXML":
                ticket = request.find("{http://developer.intuit.com/}ticket").text
                responseXml = (request.find("{http://developer.intuit.com/}response").text or "").replace("&lt;","<").replace("&gt;",">")
                _qbRequests = sessions.get(ticket)
                if _qbRequests:
                    if responseXml:
                        processQbResponse(_qbRequests[0], responseXml)
                    else:
                        print ("no response from QuickBooks")
                    response = str(100 / len(_qbRequests))
                    sessions[ticket] = _qbRequests[1:]
            elif request.tag == "{http://developer.intuit.com/}getLastError":
                ticket = request.find("{http://developer.intuit.com/}ticket").text
                _qbRequests = sessions.get(ticket)
                if _qbRequests:
                    _qbRequest = _qbRequests[0]
                    action = _qbRequest["request"]
                    if action == "StartInteractiveMode":
                        response = "Interactive mode"
                    else:
                        response = "NoOp"
                else:
                    response = "NoOp"
            elif request.tag == "{http://developer.intuit.com/}getInteractiveURL":
                ticket = request.find("{http://developer.intuit.com/}wcTicket").text
                response = "{0}://{1}/quickbooks/server.html?ticket={2}".format(
                            requestUrlParts.scheme,
                            requestUrlParts.netloc,
                            ticket)
                sessions[ticket] = [{"request":"WaitForInput"}]
            elif request.tag == "{http://developer.intuit.com/}isInteractiveDone":
                ticket = request.find("{http://developer.intuit.com/}wcTicket").text
                _qbRequests = sessions.get(ticket)
                if _qbRequests:
                    _qbRequest = _qbRequests[0]
                    action = _qbRequest["request"]
                    if action == "Done":
                        response = "Done"
                    else:
                        response = "Not done"
                else:
                    response = "Not done"
            elif request.tag == "{http://developer.intuit.com/}interactiveRejected":
                ticket = request.find("{http://developer.intuit.com/}wcTicket").text
                response = "Interactive session timed out or canceled"
                sessions.pop(ticket, None)
            elif request.tag == "{http://developer.intuit.com/}closeConnection":
                response = "OK"

            soapResponse = qbResponse(requestName, response)
            return soapResponse

def qbRequest(qbReport: str | None, fromDate: str | None, toDate: str | None, file: str | None) -> str:
    ticket = str(uuid.uuid1())
    qbRequests.append({"ticket":ticket,
                       "request":qbReport,
                       "fromDate":fromDate,
                       "toDate":toDate,
                       "xbrlFile":file})
    qbRequestStatus[ticket] = _("Waiting for QuickBooks")
    return ticket

def qbResponse(responseName, content=None):
    if not content:
        result = ""
    elif isinstance(content, list):
        result = '<{0}Result>{1}</{0}Result>'.format(
                 responseName,
                 '\n'.join("<string>{0}</string>".format(l) for l in content))
    else:
        result = '<{0}Result>{1}</{0}Result>'.format(responseName, content)

    return ('<?xml version="1.0" encoding="utf-8"?>'
            '<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xsd="http://www.w3.org/2001/XMLSchema">'
            '<soap:Body>'
            '<{0}Response xmlns="http://developer.intuit.com/">'
            '{1}'
            '</{0}Response>'
            '</soap:Body>'
            '</soap:Envelope>'.format(responseName, result))

def docEltText(doc, tag, defaultValue=""):
    for elt in doc.iter(tag):
        return elt.text
    return defaultValue

def processQbResponse(qbRequest, responseXml):
    from arelle import ModelXbrl, XbrlConst
    from arelle.ModelValue import qname
    ticket = qbRequest["ticket"]
    qbRequestStatus[ticket] = _("Generating XBRL-GL from QuickBooks response")
    qbReport = qbRequest["request"]
    xbrlFile = qbRequest["xbrlFile"]
    fromDate = qbRequest["fromDate"]
    toDate = qbRequest["toDate"]
    strHCPResponse = qbRequest.get("strHCPResponse", "")

    # uncomment to dump out QB responses
    '''
    with open("c:/temp/test.xml", "w") as fh:
        fh.write(responseXml)
    with open("c:/temp/testC.xml", "w") as fh:
        fh.write(strHCPResponse)
    # qb responses dump
    '''

    companyQbDoc = etree.parse(io.StringIO(initial_value=strHCPResponse))
    responseQbDoc = etree.parse(io.StringIO(initial_value=responseXml))
    # columns table
    colTypeId = {}
    colIdType = {}
    for colDescElt in responseQbDoc.iter("ColDesc"):
        colTypeElt = colDescElt.find("ColType")
        if colTypeElt is not None:
            colID = colDescElt.get("colID")
            colType = colTypeElt.text
            if colType == "Amount": # check if there's a credit or debit colTitle
                for colTitleElt in colDescElt.iter("ColTitle"):
                    title = colTitleElt.get("value")
                    if title in ("Credit", "Debit"):
                        colType = title
                        break
            colTypeId[colType] = colID
            colIdType[colID] = colType

    # open new result instance document

    # load GL palette file (no instance)
    instance = cntlr.modelManager.load("http://www.xbrl.org/taxonomy/int/gl/2006-10-25/plt/case-c-b-m-u-t/gl-plt-2006-10-25.xsd")
    if xbrlFile is None:
        xbrlFile = "sampleInstance.xbrl"
        saveInstance = False
    else:
        saveInstance = True
    instance.createInstance(xbrlFile) # creates an instance as this modelXbrl's entrypoing
    newCntx = instance.createContext("http://www.xbrl.org/xbrlgl/sample", "SAMPLE",
                  "instant", None, datetime.date.today() + datetime.timedelta(1), # today midnight
                  None, {}, [], [], afterSibling=ModelXbrl.AUTO_LOCATE_ELEMENT)

    monetaryUnit = qname(XbrlConst.iso4217, "iso4217:USD")
    newUnit = instance.createUnit([monetaryUnit],[], afterSibling=ModelXbrl.AUTO_LOCATE_ELEMENT)

    nonNumAttr = [("contextRef", newCntx.id)]
    monetaryAttr = [("contextRef", newCntx.id), ("unitRef", newUnit.id), ("decimals", "2")]

    isoLanguage = qname("{http://www.xbrl.org/2005/iso639}iso639:en")

    # root of GL is accounting entries tuple
    xbrlElt = instance.modelDocument.xmlRootElement

    '''The container for XBRL GL, accountingEntries, is not the root of an XBRL GL file - the root,
    as with all XBRL files, is xbrl. This means that a single XBRL GL file can store one or more
    virtual XBRL GL files, through one or more accountingEntries structures with data inside.
    The primary key to understanding an XBRL GL file is the entriesType. A single physical XBRL GL
    file can have multiple accountingEntries structures to represent both transactions and
    master files; the differences are signified by the appropriate entriesType enumerated values.'''
    accountingEntries = instance.createFact(qname("{http://www.xbrl.org/int/gl/cor/2006-10-25}gl-cor:accountingEntries"))

    # Because entriesType is strongly suggested, documentInfo will be required
    docInfo = instance.createFact(qname("{http://www.xbrl.org/int/gl/cor/2006-10-25}gl-cor:documentInfo"), parent=accountingEntries)
    # This field, entriesType, provides the automated guidance on the purpose of the XBRL GL information.
    instance.createFact(qname("{http://www.xbrl.org/int/gl/cor/2006-10-25}gl-cor:entriesType"), parent=docInfo, attributes=nonNumAttr,
                        text=glEntriesType[qbReport])
    '''Like a serial number, this field, uniqueID, provides a place to uniquely identify/track
    a series of entries. It is like less relevant for ad-hoc reports. XBRL GL provides for later
    correction through replacement or augmentation of transferred information.'''
    instance.createFact(qname("{http://www.xbrl.org/int/gl/cor/2006-10-25}gl-cor:uniqueID"), parent=docInfo, attributes=nonNumAttr,
                        text="001")
    instance.createFact(qname("{http://www.xbrl.org/int/gl/cor/2006-10-25}gl-cor:language"), parent=docInfo, attributes=nonNumAttr,
                        text=XmlUtil.addQnameValue(xbrlElt, isoLanguage))
    '''The date associated with the creation of the data reflected within the associated
    accountingEntries section. Somewhat like a "printed date" on a paper report'''
    instance.createFact(qname("{http://www.xbrl.org/int/gl/cor/2006-10-25}gl-cor:creationDate"), parent=docInfo, attributes=nonNumAttr,
                        text=str(datetime.date.today()))
    instance.createFact(qname("{http://www.xbrl.org/int/gl/cor/2006-10-25}gl-cor:periodCoveredStart"), parent=docInfo, attributes=nonNumAttr,
                        text=fromDate)
    instance.createFact(qname("{http://www.xbrl.org/int/gl/cor/2006-10-25}gl-cor:periodCoveredEnd"), parent=docInfo, attributes=nonNumAttr,
                        text=toDate)
    instance.createFact(qname("{http://www.xbrl.org/int/gl/bus/2006-10-25}gl-bus:sourceApplication"), parent=docInfo, attributes=nonNumAttr,
                        text=docEltText(companyQbDoc, "ProductName","QuickBooks (version not known)"))
    instance.createFact(qname("{http://www.xbrl.org/int/gl/muc/2006-10-25}gl-muc:defaultCurrency"), parent=docInfo, attributes=nonNumAttr,
                        text=XmlUtil.addQnameValue(xbrlElt, monetaryUnit))

    '''Typically, an export from an accounting system does not carry with it information
    specifically about the company. However, the name of the company would be a very good
    thing to include with the file, making the entityInformation tuple necessary.'''
    entityInfo = instance.createFact(qname("{http://www.xbrl.org/int/gl/cor/2006-10-25}gl-cor:entityInformation"), parent=accountingEntries)
    '''The name of the company would be a very good thing to include with the file;
    this structure and its content are where that would be stored.'''
    orgIds = instance.createFact(qname("{http://www.xbrl.org/int/gl/bus/2006-10-25}gl-bus:organizationIdentifiers"), parent=entityInfo)
    instance.createFact(qname("{http://www.xbrl.org/int/gl/bus/2006-10-25}gl-bus:organizationIdentifier"), parent=orgIds, attributes=nonNumAttr,
                        text=docEltText(companyQbDoc, "CompanyName"))
    instance.createFact(qname("{http://www.xbrl.org/int/gl/bus/2006-10-25}gl-bus:organizationDescription"), parent=orgIds, attributes=nonNumAttr,
                        text=docEltText(companyQbDoc, "LegalCompanyName"))

    if qbReport == "trialBalance":
        qbTxnType = "trialbalance"
    else:
        qbTxnType = None
    qbTxnNumber = None
    qbDate = None
    qbRefNumber = None
    isFirst = True
    entryNumber = 1
    lineNumber = 1

    for dataRowElt in responseQbDoc.iter("DataRow"):
        cols = dict((colIdType[colElt.get("colID")], colElt.get("value")) for colElt in dataRowElt.iter("ColData"))
        if qbReport == "trialBalance" and "Label" in cols:
            cols["SplitAccount"] = cols["Label"]

        hasRowDataAccount = False
        for rowDataElt in dataRowElt.iter("RowData"):
            rowType = rowDataElt.get("rowType")
            if rowType == "account":
                hasRowDataAccount = True
                if "SplitAccount" not in cols:
                    cols["SplitAccount"] = rowDataElt.get("value")
        if qbReport == "trialBalance" and not hasRowDataAccount:
            continue  # skip total lines or others without account information
        elif qbReport in ("generalLedger", "journal"):
            if "TxnType" not in cols:
                continue  # not a reportable entry

        # entry header fields only on new item that generates an entry header
        if "TxnType" in cols:
            qbTxnType = cols["TxnType"]
        if "TxnNumber" in cols:
            qbTxnNumber = cols["TxnNumber"]
        if "Date" in cols:
            qbDate = cols["Date"]
        if "RefNumber" in cols:
            qbRefNumber = cols["RefNumber"]
        # entry details provided on every entry
        qbName = cols.get("Name")
        qbMemo = cols.get("Memo")
        qbAccount = cols.get("SplitAccount")
        qbAmount = cols.get("Amount")
        qbDebitAmount = cols.get("Debit")
        qbCreditAmount = cols.get("Credit")
        runningBalance = cols.get("RunningBalance")

        if qbAmount is not None:
            drCrCode = None
            amt = qbAmount
        elif qbDebitAmount is not None:
            drCrCode = "D"
            amt = qbDebitAmount
        elif qbCreditAmount is not None:
            drCrCode = "C"
            amt = qbCreditAmount
        else:
            # no amount, skip this transaction
            continue

        if isFirst or qbTxnNumber:
            '''Journal entries require entry in entryHeader and entryDetail.
            Few files can be represented using only documentInfo and entityInformation sections,
            but it is certainly possible.'''
            entryHdr = instance.createFact(qname("{http://www.xbrl.org/int/gl/cor/2006-10-25}gl-cor:entryHeader"), parent=accountingEntries)
            #instance.createFact(qname("{http://www.xbrl.org/int/gl/cor/2006-10-25}gl-cor:enteredBy"), parent=entryHdr, attributes=nonNumAttr, text="")
            instance.createFact(qname("{http://www.xbrl.org/int/gl/cor/2006-10-25}gl-cor:enteredDate"), parent=entryHdr, attributes=nonNumAttr,
                                text=str(datetime.date.today()))
            '''This is an enumerated entry that ties the source journal from the reporting
            organization to a fixed list that helps in data interchange.'''
            instance.createFact(qname("{http://www.xbrl.org/int/gl/cor/2006-10-25}gl-cor:sourceJournalID"), parent=entryHdr, attributes=nonNumAttr,
                                text="gj")
            '''Since sourceJournalID is enumerated (you must pick one of the entries already
            identified within XBRL GL), sourceJournalDescription lets you capture the actual
            code or term used to descibe the source journal by the organization.'''
            # instance.createFact(qname("{http://www.xbrl.org/int/gl/cor/2006-10-25}gl-cor:sourceJournalDescription"), parent=entryHdr, attributes=nonNumAttr, text="JE")
            '''An enumerated field to differentiate between details that represent actual accounting
            entries - as opposed to entries for budget purposes, planning purposes, or other entries
            that may not contribute to the financial statements.'''
            instance.createFact(qname("{http://www.xbrl.org/int/gl/cor/2006-10-25}gl-cor:entryType"), parent=entryHdr, attributes=nonNumAttr,
                                text="standard")
            '''When capturing journal entries, you have a series of debits and credits that (normally)
            add up to zero. The hierarchical nature of XBRL GL keeps the entry detail lines associated
            with the entry header by a parent-child relationship. The unique identifier of each entry
            is entered here.'''
            instance.createFact(qname("{http://www.xbrl.org/int/gl/cor/2006-10-25}gl-cor:entryNumber"), parent=entryHdr, attributes=nonNumAttr,
                                text=str(entryNumber))
            entryNumber += 1
            # The reason for making an entry goes here.
            if qbRefNumber:
                instance.createFact(qname("{http://www.xbrl.org/int/gl/cor/2006-10-25}gl-cor:entryComment"), parent=entryHdr, attributes=nonNumAttr,
                                    text=qbRefNumber)

        '''Individual lines of journal entries will normally require their own entryDetail section -
        one primary amount per entryDetail line. However, you can list different accounts within
        the same entryDetail line that are associated with that amount. For example, if you
        capitalize for US GAAP and expense for IFRS'''
        entryDetail = instance.createFact(qname("{http://www.xbrl.org/int/gl/cor/2006-10-25}gl-cor:entryDetail"), parent=entryHdr)
        # A unique identifier for each entry detail line within an entry header, this should at the least be a counter.
        instance.createFact(qname("{http://www.xbrl.org/int/gl/cor/2006-10-25}gl-cor:lineNumber"), parent=entryDetail, attributes=nonNumAttr,
                            text=str(lineNumber))
        lineNumber += 1

        '''If account information is represented elsewhere or as a master file, some of the
        fields below would not need to be here (signified by *)'''
        account = instance.createFact(qname("{http://www.xbrl.org/int/gl/cor/2006-10-25}gl-cor:account"), parent=entryDetail)
        '''The account number is the basis for posting journal entries. In some cases,
        accounting systems used by small organizations do not use account numbers/codes,
        but only use a descriptive name for the account.'''
        # QB does not have account numbers
        # instance.createFact(qname("{http://www.xbrl.org/int/gl/cor/2006-10-25}gl-cor:accountMainID"), parent=account, attributes=nonNumAttr, text="10100")
        '''In most cases, the description is given to help a human reader; the accountMainID would
        be sufficient for data exchange purposes. As noted previously, some implementations use the
        description as the primary identifier of the account.'''
        if qbAccount:
            instance.createFact(qname("{http://www.xbrl.org/int/gl/cor/2006-10-25}gl-cor:accountMainDescription"), parent=account, attributes=nonNumAttr,
                                text=qbAccount)
        '''Accounts serve many purposes, and in a large company using more sophisticated software,
        the company may wish to record the account used for the original entry and a separate
        consolidating account. The Japanese system may require a counterbalancing account for
        each line item. And an entry may be recorded differently for US GAAP, IFRS and other purposes.
        This code is an enumerated code to help identify accounts for those purposes.'''
        instance.createFact(qname("{http://www.xbrl.org/int/gl/cor/2006-10-25}gl-cor:accountPurposeCode"), parent=account, attributes=nonNumAttr,
                            text="usgaap")
        '''In an international environment, the "chart of accounts" will include not only
        traditional accounts, like Cash, Accounts Payable/Due to Creditors or Retained Earnings,
        but also extensions to some of the accounts. Accounts Payable may be extended to
        include the creditors/vendors themselves. Therefore, in XBRL GL, accounts can be
        specifically identified as the "traditional" accountm or to identify a customer,
        vendor, employee, bank, job or fixed asset. While this may overlap with the customers,
        vendors and employees of the identifier structure, fixed-assets in the measurable
        structure, jobs in the jobInfo structure and other representations, they can also be
        represented here as appropriate to the jurisidiction.'''
        instance.createFact(qname("{http://www.xbrl.org/int/gl/cor/2006-10-25}gl-cor:accountType"), parent=account, attributes=nonNumAttr, text="account")

        '''What is a journal entry without a (monetary) amount? While XBRL GL may usher in journal
        entries that also incorporate quantities, to reflect the detail of business metrics, the
        (monetary) amount is another key and obvious fields. XBRL GL has been designed to reflect
        how popular accounting systems store amounts - some combination of a signed amount (e.g., 5, -10),
        a separate sign (entered into signOfAmount) and a separate place to indicate the number is
        associated with a debit or credit (debitCreditCode).'''
        instance.createFact(qname("{http://www.xbrl.org/int/gl/cor/2006-10-25}gl-cor:amount"), parent=entryDetail, attributes=monetaryAttr,
                            text=amt)
        '''Depending on the originating system, this field may contain whether the amount is
        associated with a debit or credit. Interpreting the number correctly for import requires
        an understanding of the three related amount fields - amount, debitCreditCode and sign of amount.'''
        if drCrCode:
            instance.createFact(qname("{http://www.xbrl.org/int/gl/cor/2006-10-25}gl-cor:debitCreditCode"), parent=entryDetail, attributes=nonNumAttr,
                                text=drCrCode)
        '''Depending on the originating system, this field may contain whether the amount is
        signed (+ or -) separately from the amount field itself. Interpreting the number correctly
        for import requires an understanding of the three related amount fields - amount,
        debitCreditCode and sign of amount.'''
        # instance.createFact(qname("{http://www.xbrl.org/int/gl/cor/2006-10-25}gl-cor:signOfAmount"), parent=entryDetail, attributes=nonNumAttr, text="+")
        # This date is the accounting significance date, not the date that entries were actually entered or posted to the system.
        if qbDate:
            instance.createFact(qname("{http://www.xbrl.org/int/gl/cor/2006-10-25}gl-cor:postingDate"), parent=entryDetail, attributes=nonNumAttr,
                                text=qbDate)

        if qbName or qbMemo:
            identRef = instance.createFact(qname("{http://www.xbrl.org/int/gl/cor/2006-10-25}gl-cor:identifierReference"), parent=entryDetail)
            if qbMemo:
                instance.createFact(qname("{http://www.xbrl.org/int/gl/cor/2006-10-25}gl-cor:identifierCode"), parent=identRef, attributes=nonNumAttr,
                                    text=qbMemo)
            if qbName:
                instance.createFact(qname("{http://www.xbrl.org/int/gl/cor/2006-10-25}gl-cor:identifierDescription"), parent=identRef, attributes=nonNumAttr,
                                    text=qbName)
            #instance.createFact(qname("{http://www.xbrl.org/int/gl/cor/2006-10-25}gl-cor:identifierType"), parent=identRef, attributes=nonNumAttr,
            #                    text="V")

        if qbReport != "trialBalance":
            if qbTxnType: # not exactly same enumerations as expected by QB
                cleanedQbTxnType = qbTxnType.replace(" ","").lower()
                glDocType = qbTxnTypeToGL.get(cleanedQbTxnType) # try table lookup
                if glDocType is None: # not in table
                    if cleanedQbTxnType.endswith("check"): # didn't convert, probably should be a check
                        glDocType = "check"
                    # TBD add more QB transations here as they are discovered and not in table
                    else:
                        glDocType = qbTxnType # if all else fails pass through QB TxnType, it will fail GL validation and be noticed!
                instance.createFact(qname("{http://www.xbrl.org/int/gl/cor/2006-10-25}gl-cor:documentType"), parent=entryDetail, attributes=nonNumAttr,
                                    text=glDocType)

            '''This enumerated field is used to specifically state whether the entries have been
            posted to the originating system or not.'''
            instance.createFact(qname("{http://www.xbrl.org/int/gl/cor/2006-10-25}gl-cor:postingStatus"), parent=entryDetail, attributes=nonNumAttr,
                                text="posted")
            # A comment at the individual entry detail level.
            # instance.createFact(qname("{http://www.xbrl.org/int/gl/cor/2006-10-25}gl-cor:detailComment"), parent=entryDetail, attributes=nonNumAttr, text="Comment...")

        isFirst = False

    if saveInstance:
        qbRequestStatus[ticket] = _("Saving XBRL-GL instance")
        instance.saveInstance()
    qbRequestStatus[ticket] = _("Done")
    # TBD resolve errors
    instance.errors = []  # TBD fix this
    xbrlInstances[ticket] = instance.uuid
