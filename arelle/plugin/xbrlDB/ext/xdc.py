'''
EDGAR.py implements an OpenSql database extension for Seatig's XDC

See COPYRIGHT.md for copyright information.


to use from command line:
   --plugins xbrlDB/ext/XDC.py # note this plugin imports xbrlDB plugin

file name argument includes metadata:
  -f "[{\"file\":\"abc.xbrl\", ... and optional fields for extXdcMetadata ...}]"

note that reference parts are needed at least on first "loading" of the DTS

  -f '[{
        "submitterUserId": "herm0001",
        "submitterUserName": "Herm Fischer",
        "acceptanceTimestamp":"2017-11-25T10:00:00",
        "filingOwnerLEI": "1234567890",
        "sourcePortal": "cloud001",
        "filingId": "filing001",
        "filerId": "owner001",
        "reportId": "report001",
        "file":"/Users/hermf/Documents/mvsl/projects/China/Changhong/XDC Data Model/XDC_XBRL_v0.1.48/XDC_sampInst_v0.1.48_2003_FapiaoGeneralFixedAmount.xbrl",
        "supplementalUrls":["f1","f2"]
        },
        {"submitterUserId": "herm0001",
        "submitterUserName": "Herm Fischer",
        "acceptanceTimestamp":"2017-11-25T10:00:00",
        "filingOwnerLEI": "1234567890",
        "sourcePortal": "cloud001",
        "filingId": "filing001",
        "filerId": "owner001",
        "reportId": "report001",
        "file":
        "/Users/hermf/Documents/mvsl/projects/China/Changhong/XDC Data Model/XDC_XBRL_v0.1.48/XDC_sampInst_v0.1.48_2004_FapiaoGeneralWritten.xbrl",
        "supplementalUrls":["f3","f4"]}
        ]'
    -v '/Users/hermf/Documents/mvsl/projects/China/Changhong/XDC Data Model/XDC_XBRL_v0.1.48/XDC_elements_v0.1.48_2017-11-09_ref_externalDefinitionReference.xml'
    -v --plugin xbrlDB/ext/xdc --store-to-XBRL-DB "server.abc.com,8084,userid,password,databasename,90,pgOpenDB"

'''
import os
from arelle.UrlUtil import ensureUrl
from arelle.Version import authorLabel, copyrightLabel

EXT_XDC_TABLES = {
                "xdc_user",
                "submission_xdc",
                "filing_xdc"
                }

def extXdcTableDdlFiles(xbrlOpenDb):
    return (EXT_XDC_TABLES,
            # may have glob wildcard characters
            [os.path.join("sql", "open", "ext", {"mssql": "xdc*MSSqlDB.sql",
                                                "mysql": "xdc*MySqlDB.ddl",
                                                "sqlite": "xdc*SQLiteDB.ddl",
                                                "orcl": "xdc*OracleDB.sql",
                                                "postgres": "xdc*PostgresDB.ddl"}[xbrlOpenDb.product])])

def extXdcMetadata(xbrlOpenDb, entrypoint, rssItem):
    md = xbrlOpenDb.metadata
    # needed for core tables
    md["acceptedTimestamp"] = entrypoint.get("acceptanceTimestamp")
    # needed for ext tables
    md["submitterUserId"] = entrypoint.get("submitterUserId")
    md["submitterUserName"] = entrypoint.get("submitterUserName")
    md["sourcePortal"] = entrypoint.get("sourcePortal")
    md["filingId"] = entrypoint.get("filingId")
    md["filerId"] = entrypoint.get("filerId")
    md["reportId"] = entrypoint.get("reportId")
    md["supplementalUrls"] = entrypoint.get("supplementalUrls", ()) # default is empty list

def extXdcExistingFilingPk(xbrlOpenDb):
    md = xbrlOpenDb.metadata
    if md["filingId"]:
        results = xbrlOpenDb.execute("SELECT f.filing_pk FROM filing f, filing_xdc fx "
                                     "WHERE f.filing_pk = fx.filing_pk AND fx.filing_id = '{}' AND f.filer_id = '{}'"
                                     .format(md["filingId"], md["filerId"]))
        for filingPk, in results:
            return filingPk
    return None


def extXdcSubmission(xbrlOpenDb, now):
    md = xbrlOpenDb.metadata
    table = xbrlOpenDb.getTable('xdc_user', 'user_pk',
                          ('user_id',
                           'name'
                           ),
                          ('user_id',),
                          ((md["submitterUserId"],
                            md["submitterUserName"]
                            ),),
                          checkIfExisting=True)
    for userId, _userNumber in table:
        xbrlOpenDb.userId = userId
        break

    table = xbrlOpenDb.getTable('submission_xdc', None,
                          ('submission_pk',
                           'submitter_fk',
                           'source_portal'
                           ),
                          ('submission_pk',),
                          ((xbrlOpenDb.submissionId,
                            xbrlOpenDb.userId,
                            md["sourcePortal"]
                            ),)
                          )

def extXdcFiling(xbrlOpenDb, now):
    md = xbrlOpenDb.metadata
    table = xbrlOpenDb.getTable('filing_xdc', None,
                          ('filing_pk',
                           'filing_id'
                           ),
                          ('filing_pk',
                           ),
                          ((xbrlOpenDb.filingPk,
                            md["filingId"]
                            ),),
                          checkIfExisting=True)

    # add supplemental document references
    supplementalDocumentsTable = xbrlOpenDb.getTable(
                         'document', 'document_pk',
                          ('url', 'type'),
                          ('url',),
                          set((ensureUrl(docUrl),
                               "attachment")
                              for docUrl in md["supplementalUrls"]),
                          checkIfExisting=True)

    table = xbrlOpenDb.getTable('referenced_documents',
                          None, # no id column in this table
                          ('object_fk','document_fk'),
                          ('object_fk','document_fk'),
                          tuple((xbrlOpenDb.filingPk, supplementalDocumentId)
                                for supplementalDocumentId, _url in supplementalDocumentsTable),
                          checkIfExisting=True)

def extXdcExistingReportPk(xbrlOpenDb):
    md = xbrlOpenDb.metadata
    # find if this exact report is being replaced
    #if md["reportId"]:
    #    results = xbrlOpenDb.execute("SELECT report_pk FROM report WHERE report_id = '{}'".format(md["reportId"]))
    #    for reportPk, in results:
    #        return reportPk
    return None

def extXdcReport(xbrlOpenDb, now):
    md = xbrlOpenDb.metadata
    if md.get("reportId"):
        xbrlOpenDb.updateTable("report",
                               ("report_id", "is_most_current"),
                               ((md.get("reportId"), False),)
                               )
    xbrlOpenDb.updateTable("report",
                           ("report_pk", "is_most_current"),
                           ((xbrlOpenDb.reportPk, True),)
                           )

__pluginInfo__ = {
    'name': 'xbrlDB Extension for Seatig XDC',
    'version': '1.0',
    'description': "This plug-in implements additional database fields for Changhong XDC.  ",
    'license': 'Apache-2',
    'author': authorLabel,
    'copyright': copyrightLabel,
    'import': ('xbrlDB', ), # import dependent modules
    'xbrlDB.Open.Ext.TableDDLFiles': extXdcTableDdlFiles,
    'xbrlDB.Open.Ext.Metadata': extXdcMetadata,
    'xbrlDB.Open.Ext.ExistingFilingPk': extXdcExistingFilingPk,
    'xbrlDB.Open.Ext.ExtSubmission': extXdcSubmission,
    'xbrlDB.Open.Ext.ExtFiling': extXdcFiling,
    'xbrlDB.Open.Ext.ExistingReportPk': extXdcExistingReportPk,
    'xbrlDB.Open.Ext.ExtReport': extXdcReport,
}
