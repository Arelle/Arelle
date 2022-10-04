'''
china.py implements an OpenSql database extension for CAS (MOF) and SASAC extensions

See COPYRIGHT.md for copyright information.


to use from command line:
   --plugins xbrlDB/ext/china.py # note this plugin imports xbrlDB plugin

   if there are more than one plugin they are enclosed in quotes and separated by "|" (pipe) characters

'''
import os
from arelle.UrlUtil import ensureUrl
from arelle.Version import authorLabel, copyrightLabel

EXT_CHINA_TABLES = {
                "filing_china"
                }

def extChinaTableDdlFiles(xbrlOpenDb):
    return (EXT_CHINA_TABLES,
            [os.path.join("sql", "open", "ext", {"mssql": "china*MSSqlDB.sql",
                                                 "mysql": "china*MySqlDB.ddl",
                                                 "sqlite": "china*SQLiteDB.ddl",
                                                 "orcl": "china*OracleDB.sql",
                                                 "postgres": "china*PostgresDB.ddl"}[xbrlOpenDb.product])])

def extChinaMetadata(xbrlOpenDb, entrypoint, rssItem):
    md = xbrlOpenDb.metadata
    modelXbrl = xbrlOpenDb.modelXbrl
    # instance facts  containint metadata
    for factName, entityField in (("NameOfReportingEntityOrOtherMeansOfIdentification", "entityName"),
                                  ("ApprovingProvince", "entityProvince"),
                                  ("ApprovalDate", "entityApprovalDate"),
                                  ("ApprovalNo", "entityApprovalNumber"),
                                  ("Sponsor", "entitySponsor"),
                                  ("BusinessLicenseNumber", "entityLicenseNumber"),
                                  ("Industries", "entityIndustries"),
                                  ("TickerSymbol", "entityTickerSymbol")):
        try:
            concept = modelXbrl.nameConcepts[factName][0] # get qname irrespective of taxonomy year
            facts = modelXbrl.factsByQname[concept.qname]
            for fact in facts:
                if not fact.context.qnameDims: #default context
                    md[entityField] = fact.value.strip() # may have white space
                    break
        except IndexError:
            pass

def extChinaExistingFilingPk(xbrlOpenDb):
    md = xbrlOpenDb.metadata
    # consider a field which will allow retrieving a prior submitted filing
    return None


def extChinaFiling(xbrlOpenDb, now):
    md = xbrlOpenDb.metadata
    table = xbrlOpenDb.getTable('filing_china', None,
                          ('filing_pk',
                           'entity_name',
                           'entity_province',
                           'entity_approval_date',
                           'entity_approval_number',
                           'entity_sponsor',
                           'entity_license_number',
                           'entity_industries',
                           'entity_ticker_symbol'
                           ),
                          ('filing_pk',
                           ),
                          ((xbrlOpenDb.filingPk,
                            md["filingId"],
                            md.get("entityName"),
                            md.get("entityProvince"),
                            md.get("entityApprovalDate"),
                            md.get("entityApprovalNumber"),
                            md.get("entitySponsor"),
                            md.get("entityLicenseNumber"),
                            md.get("entityIndustries"),
                            md.get("entityTickerSymbol"),
                            ),),
                          checkIfExisting=True)

__pluginInfo__ = {
    'name': 'xbrlDB Extension for China CAS and SASAC',
    'version': '1.0',
    'description': "This plug-in implements additional database fields for China CAS and SASAC.  ",
    'license': 'Apache-2',
    'author': authorLabel,
    'copyright': copyrightLabel,
    'import': ('xbrlDB', ), # import dependent modules
    'xbrlDB.Open.Ext.TableDDLFiles': extChinaTableDdlFiles,
    'xbrlDB.Open.Ext.Metadata': extChinaMetadata,
    'xbrlDB.Open.Ext.ExistingFilingPk': extChinaExistingFilingPk,
    'xbrlDB.Open.Ext.ExtFiling': extChinaFiling,
}
