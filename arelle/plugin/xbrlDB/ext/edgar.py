'''
EDGAR.py implements an OpenSql database extension for SEC's EDGAR

See COPYRIGHT.md for copyright information.


to use from command line:
   --plugins xbrlDB/ext/EDGAR.py # note this plugin imports xbrlDB plugin

'''
import os, time
from arelle.ModelDocument import Type
from arelle.UrlUtil import authority
from arelle.Version import authorLabel, copyrightLabel

EXT_EDGAR_TABLES = {
                "filing_edgar", "report_edgar",
                "industry_edgar", "industry_edgar_level", "industry_edgar_structure",
                }

countryOfState = {
    "AL": "US","AK": "US","AZ": "US","AR": "US","CA": "US","CO": "US", "CT": "US","DE": "US",
    "FL": "US","GA": "US","HI": "US","ID": "US","IL": "US","IN": "US","IA": "US","KS": "US",
    "KY": "US","LA": "US","ME": "US","MD": "US","MA": "US","MI": "US","MN": "US","MS": "US",
    "MO": "US","MT": "US","NE": "US","NV": "US","NH": "US","NJ": "US","NM": "US","NY": "US",
    "NC": "US","ND": "US","OH": "US","OK": "US","OR": "US","PA": "US","RI": "US","SC": "US",
    "SD": "US","TN": "US","TX": "US","UT": "US","VT": "US","VA": "US","WA": "US","WV": "US",
    "WI": "US","WY": "US","DC": "US","PR": "US","VI": "US","AS": "US","GU": "US","MP": "US",
    "AB": "CA","BC": "CA","MB": "CA","NB": "CA","NL": "CA","NS": "CA","ON": "CA","PE": "CA",
    "QC": "CA","SK": "CA","NT": "CA","NU": "CA","YT": "CA"}


def extEdgarTableDdlFiles(xbrlOpenDb):
    return (EXT_EDGAR_TABLES,
            # may have glob wildcard characters
            [os.path.join("sql", "open", "ext", {"mssql": "edgarMSSqlDB.sql",
                                                 "mysql": "edgarMySqlDB.ddl",
                                                 "sqlite": "edgarSQLiteDB.ddl",
                                                 "orcl": "edgarOracleDB.sql",
                                                 "postgres": "edgarPostgresDB.ddl"}[xbrlOpenDb.product])])

def rssItemGet(rssItem, propertyName):
    if rssItem is not None:
        return getattr(rssItem, propertyName, None)
    return None

def extEdgarMetadata(xbrlOpenDb, entrypoint, rssItem):
    md = xbrlOpenDb.metadata
    # needed for core tables
    md["acceptedTimestamp"] = rssItemGet(rssItem, "acceptanceDatetime") or md.get("acceptance-datetime")
    # needed for ext tables
    md["fiscalYearEnd"] = rssItemGet(rssItem, "fiscalYearEnd") or md.get("fiscal-year-end")
    md["accessionNumber"] = rssItemGet(rssItem, "accessionNumber") or md.get("accession-number") or str(int(time.time()))
    md["filingDate"] = rssItemGet(rssItem, "filingDate") or md.get("filing-date")
    md["authorityHtml_Url"] = rssItemGet(rssItem, "htmlUrl") or md.get("primary-document-url")
    md["entryUrl"] = rssItemGet(rssItem, "url") or md.get("instance-url")
    md["companyName"] = rssItemGet(rssItem, "companyName") or md.get("conformed-name")
    md["zipUrl"] = rssItemGet(rssItem, "enclosureUrl")
    md["fiscalYearFocus"] = md.get("fiscal-year-focus")
    md["fiscalPeriodFocus"] = md.get("fiscal-period-focus")
    md["fiscalYearEnd"] = rssItemGet(rssItem, "fiscalYearEnd") or md.get("fiscal-year-end")
    md["fileNumber"] = rssItemGet(rssItem, "fileNumber") or md.get("file-number")  or str(int(time.time()))
    md["cik"] = rssItemGet(rssItem, "cikNumber") or md.get("cik")
    md["taxNumber"] = md.get("irs-number")
    md["SIC"] = rssItemGet(rssItem, "assignedSic") or md.get("assigned-sic") or -1
    md["filerCategory"] = md.get("filer-category")
    md["publicFloat"] = md.get("public-float")
    md["tradingSymbol"] = md.get("trading-symbol")
    md["stateOfIncorporation"] = md.get("state-of-incorporation")
    md["businessAddressPhone"] = md.get("business-address.phone")
    md["businessAddressStreet1"] = md.get("business-address.street1")
    md["businessAddressStreet2"] = md.get("business-address.street2")
    md["businessAddressCity"] = md.get("business-address.city")
    md["businessAddressState"] = md.get("business-address.state")
    md["businessAddressZip"] = md.get("business-address.zip")
    md["mailAddressStreet1"] = md.get("mail-address.street1")
    md["mailAddressStreet2"] = md.get("mail-address.street2")
    md["mailAddressCity"] = md.get("mail-address.city")
    md["mailAddressState"] = md.get("mail-address.state")
    md["mailAddressZip"] = md.get("mail-address.zip")
    md["formType"] = rssItemGet(rssItem, "formType") or md.get("document-type")
    md["reportId"] = "{}|{}|{}".format(md["cik"], md["formType"].replace("/A",""), md["fiscalYearFocus"], md["fiscalPeriodFocus"])

def extEdgarInitializeBatch(self, rssObject):
    results = self.execute("SELECT fe.accession_number, s.accepted_timestamp "
                           "FROM report r, filing_edgar fe, submission s "
                           "WHERE r.filing_fk = fe.filing_pk AND r.submission_fk = s.submission_pk")
    existingFilings = dict((accessionNumber, timestamp)
                           for accessionNumber, timestamp in results) # timestamp is a string
    for rssItem in rssObject.rssItems:
        if (rssItem.accessionNumber in existingFilings and
            rssItem.acceptanceDatetime == existingFilings[rssItem.accessionNumber]):
            rssItem.skipRssItem = True

def extEdgarExistingFilingPk(xbrlOpenDb):
    accessionNumber = xbrlOpenDb.metadata.get("accessionNumber")
    if accessionNumber:
        results = xbrlOpenDb.execute("SELECT filing_pk FROM filing_edgar WHERE accession_number = '{}'".format(accessionNumber))
        for filingPk, in results:
            return filingPk
    return None

def extEdgarFiling(xbrlOpenDb, now):
    md = xbrlOpenDb.metadata
    table = xbrlOpenDb.getTable('filing_edgar', 'filing_pk',
                          ('filing_pk',
                           'accession_number',
                           'filing_date',
                           'authority_html_url',
                           'entry_url',
                           'entity_name',
                           'zip_url',
                           'fiscal_year',
                           'fiscal_period',
                           'restatement_index',
                           'period_index',
                           'fiscal_year_end',
                           'file_number',
                           'cik',
                           'tax_number',
                           'standard_industry_code',
                           'filer_category',
                           'public_float',
                           'trading_symbol',
                           'legal_state',
                           'phone',
                           'phys_addr1', 'phys_addr2', 'phys_city', 'phys_state', 'phys_zip', 'phys_country',
                           'mail_addr1', 'mail_addr2', 'mail_city', 'mail_state', 'mail_zip', 'mail_country'
                          ),
                          ('filing_pk',),
                          ((xbrlOpenDb.filingPk,
                            md["accessionNumber"],  # NOT NULL
                            md["filingDate"] or now,  # NOT NULL
                            md["authorityHtml_Url"],
                            md["entryUrl"],
                            md["companyName"],
                            md["zipUrl"], # enclsure zip URL if any
                            md["fiscalYearFocus"],
                            md["fiscalPeriodFocus"],
                            None, #'restatement_index',
                            None, #'period_index',
                            md["fiscalYearEnd"],
                            md["fileNumber"],
                            md["cik"],
                            md["taxNumber"],
                            md["SIC"],
                            md["filerCategory"],
                            md["publicFloat"],
                            md["tradingSymbol"],
                            md["stateOfIncorporation"],
                            md["businessAddressPhone"],
                            md["businessAddressStreet1"],
                            md["businessAddressStreet2"],
                            md["businessAddressCity"],
                            md["businessAddressState"],
                            md["businessAddressZip"],
                            countryOfState.get(md["businessAddressState"]),
                            md["mailAddressStreet1"],
                            md["mailAddressStreet2"],
                            md["mailAddressCity"],
                            md["mailAddressState"],
                            md["mailAddressZip"],
                            countryOfState.get(md["mailAddressState"])
                            ),),
                          checkIfExisting=True)

def extEdgarExistingReportPk(xbrlOpenDb):
    md = xbrlOpenDb.metadata
    # find if this exact report is being replaced
    #if md["reportId"]:
    #    results = xbrlOpenDb.execute("SELECT report_pk FROM report WHERE report_id = '{}'".format(md["reportId"]))
    #    for reportPk, in results:
    #        return reportPk
    return None

def extEdgarReport(xbrlOpenDb, now):
    md = xbrlOpenDb.metadata
    table = xbrlOpenDb.getTable('report_edgar', None,
                          ('report_pk',
                           'form_type'
                           ),
                          ('report_pk',),
                          ((xbrlOpenDb.reportPk,
                            md["formType"]
                            ),),
                          checkIfExisting=True)
    if md.get("reportId"):
        xbrlOpenDb.updateTable("report",
                               ("report_id", "is_most_current"),
                               ((md.get("reportId"), False),)
                               )
    xbrlOpenDb.updateTable("report",
                           ("report_pk", "is_most_current"),
                           ((xbrlOpenDb.reportPk, True),)
                           )

def extEdgarReportUpdate(xbrlOpenDb):
    agencySchemaDocId = stdSchemaDocId = None
    for mdlDoc in xbrlOpenDb.modelXbrl.urlDocs.values():
        if mdlDoc in xbrlOpenDb.documentIds:
            for refDoc, ref in mdlDoc.referencesDocument.items():
                if refDoc.inDTS and ref.referenceTypes & {"href", "import", "include"} \
                   and refDoc in xbrlOpenDb.documentIds:
                    if refDoc.type == Type.SCHEMA:
                        nsAuthority = authority(refDoc.targetNamespace, includeScheme=False)
                        nsPath = refDoc.targetNamespace.split('/')
                        if len(nsPath) > 2:
                            if ((nsAuthority in ("fasb.org", "xbrl.us") and nsPath[-2] == "us-gaap") or
                                (nsAuthority == "xbrl.ifrs.org" and nsPath[-1] in ("ifrs", "ifrs-full", "ifrs-smes"))):
                                stdSchemaDocId = xbrlOpenDb.documentIds[refDoc]
                            elif (nsAuthority == "xbrl.sec.gov" and nsPath[-2] == "rr"):
                                agencySchemaDocId = xbrlOpenDb.documentIds[refDoc]
        if agencySchemaDocId or stdSchemaDocId:
            xbrlOpenDb.updateTable("report_edgar",
                                   ("report_pk", "agency_schema_doc_fk", "standard_schema_doc_fk"),
                                   ((xbrlOpenDb.reportPk, agencySchemaDocId, stdSchemaDocId),)
                                   )

__pluginInfo__ = {
    'name': 'xbrlDB Extension for SEC EDGAR',
    'version': '1.0',
    'description': "This plug-in implements additional database fields for U.S. SEC EDGAR.  ",
    'license': 'Apache-2',
    'author': authorLabel,
    'copyright': copyrightLabel,
    'import': ('xbrlDB', ), # import dependent modules
    # classes of mount points (required)
    'xbrlDB.Open.Ext.TableDDLFiles': extEdgarTableDdlFiles,
    'xbrlDB.Open.Ext.Metadata': extEdgarMetadata,
    'xbrlDB.Open.Ext.InitializeBatch': extEdgarInitializeBatch,
    'xbrlDB.Open.Ext.ExistingFilingPk': extEdgarExistingFilingPk,
    'xbrlDB.Open.Ext.ExtFiling': extEdgarFiling,
    'xbrlDB.Open.Ext.ExtReport': extEdgarReport,
    'xbrlDB.Open.Ext.ExistingReportPk': extEdgarExistingReportPk,
    'xbrlDB.Open.Ext.ExtReportUpdate': extEdgarReportUpdate,
}
