"""Parameters and helpers for test_xbrlDB"""
from __future__ import annotations
import gettext
import re
from arelle.Cntlr import Cntlr
from arelle.ModelXbrl import ModelXbrl
from arelle import FileSource
from arelle import PluginManager
from arelle.ModelFormulaObject import FormulaOptions
from arelle.CntlrCmdLine import filesourceEntrypointFiles
from arelle.plugin.inlineXbrlDocumentSet import commandLineFilingStart
from arelle import XPathContext
from arelle.FunctionXfi import concept_relationships
from arelle import XbrlConst
from arelle.plugin.xbrlDB.XbrlSemanticSqlDB import XbrlSqlDatabaseConnection
from arelle.plugin.xbrlDB.XbrlSemanticSqlDB import XBRLDBTABLES
from arelle.ModelDocument import Type, ModelDocument
from arelle.UrlUtil import ensureUrl


# xbrlDB supports multiple DB products, tests runs on sqlite by default
# but other connection parameters maybe added here
con_params =  [
    {
        'user': None,
        'password': None,
        'host': None,
        'port': None,
        'database': ':memory:',
        'timeout': None,
        'product': 'sqlite',
    },
    # {
    #     'user': <user name>,
    #     'password': <password>,
    #     'host': <host>,
    #     'port': <port default: 5432>,
    #     'database': <database name>,
    #     'timeout': None,
    #     'product': 'postgres',
    # },
    # {
    #     'user': <user name>,
    #     'password': <password>,
    #     'host': <host>,
    #     'port': <port default: 3306>,
    #     'database': <database name>,
    #     'timeout': None,
    #     'product': 'mysql',
    # },
    # {
    #     'user': <user name>,
    #     'password': <password>,
    #     'host': <host>,
    #     'port': <port default: 1521>,
    #     'database': <database name>,
    #     'timeout': None,
    #     'product': 'orcl',
    # },
    # {
    #     'user': <user name>,
    #     'password': <password>,
    #     'host': <host>,
    #     'port': <port default: 1433>,
    #     'database': <database name>,
    #     'timeout': None,
    #     'product': 'mssql',
    # },
]

ddlFiles = {
    "mssql": "xbrlSemanticMSSqlDB.sql",
    "mysql": "xbrlSemanticMySqlDB.ddl",
    "sqlite": "xbrlSemanticSQLiteDB.ddl",
    "orcl": "xbrlSemanticOracleDB.sql",
    "postgres": "xbrlSemanticPostgresDB.ddl"
}

# files used for testing insertXbrl
test_filings = [
    'https://www.sec.gov/Archives/edgar/data/789019/000156459021020891/0001564590-21-020891-xbrl.zip',
    # below file produces "duplicatedSchema warning"
    'https://filings.xbrl.org/95980079E2NBJT967T79/2021-12-31/ESEF/ES/0/95980079E2NBJT967T79-20211231-ES.zip'
]

## additional database objects created
productAdditionalTables = {'mysql': {'sequences'}}

# sequences used only in postgres, orcl, mssql
XBRLDBSEQUENCES = {'seq_entity', 'seq_filing', 'seq_object', 'seq_message', 'seq_relationship_set'}

productAdditionalSequences = {
    'postgres': {'seq_industry', 'seq_industry_level', 'seq_industry_structure'},
    'orcl': {'seq_industry'}
}

# triggers used only in orcl and mysql
XBRLDBTRIGGERS = {
    'orcl': {
        'resource_insert_trigger',
        'role_type_insert_trigger',
        'entity_identifier_insert_trigger',
        'filing_insert_trigger',
        'data_point_insert_trigger',
        'unit_insert_trigger',
        'data_type_insert_trigger',
        'period_insert_trigger',
        'message_insert_trigger',
        'rel_set_insert_trigger',
        'entity_insert_trigger',
        'relationship_insert_trigger',
        'report_insert_trigger',
        'aspect_value_sel_ins_trigger',
        'arcrole_type_insert_trigger',
        'aspect_insert_trigger',
        'document_insert_trigger'
    },
    'mysql': {
        'report_seq',
        'document_seq',
        'aspect_seq',
        'data_type_seq',
        'role_type_seq',
        'arcrole_type_seq',
        'resource_seq',
        'relationship_seq',
        'data_point_seq',
        'entity_identifier_seq',
        'period_seq',
        'unit_seq',
        'aspect_value_selection_set_seq'
    }
}

def get_db_sequences(con:XbrlSqlDatabaseConnection) -> set:
    """Returns a set of sequences names existing in db"""
    return {x.lower() for x in con.sequencesInDB()}


def get_db_triggers(con:XbrlSqlDatabaseConnection) -> set:
    """Returns a set of triggers names existing in db"""
    return {x.lower() for x in con.triggersInDB()}

def drop_existing_objects(con: XbrlSqlDatabaseConnection, commit=False) -> None:
    """Safely drop only created objects"""

    drop_table_end = {
        'orcl': ' CASCADE CONSTRAINTS PURGE',
        'mssql': '',
        'sqlite': ''
    }
    db_tables = con.tablesInDB()
    xbrl_tables = XBRLDBTABLES.union(productAdditionalTables.get(con.product, set()))
    for table in xbrl_tables:
        if table in db_tables:
            con.execute(
                f'DROP TABLE {con.dbTableName(table)}{drop_table_end.get(con.product, " CASCADE")}',
                fetch=False, action=f'Dropping Table {table}'
            )
    assert (xbrl_tables - con.tablesInDB()) == xbrl_tables

    db_triggers = get_db_triggers(con)
    if db_triggers:
        xbrl_triggers = XBRLDBTRIGGERS.get(con.product, set())
        for trigger in xbrl_triggers:
            if trigger in db_triggers:
                con.execute(f'DROP TRIGGER {con.dbTableName(trigger)}', fetch=False, action=f'Dropping Trigger {trigger}')
        assert (xbrl_triggers - get_db_triggers(con)) == xbrl_triggers

    db_sequences = get_db_sequences(con)
    if db_sequences:
        xbrl_seq = XBRLDBSEQUENCES.union(productAdditionalSequences.get(con.product, set()))
        for seq in xbrl_seq:
            if seq in db_sequences:
                con.execute(f'DROP SEQUENCE {seq}', fetch=False, action=f'Dropping Sequence {seq}')
        assert (xbrl_seq - get_db_sequences(con)) == xbrl_seq

    if commit:
        con.commit()

def concept_relationships_wrapper(modelXbrl, *args):
    """Wrapper for xfi:concept-relationships implementation to extract relationships
    args: sourceConcept, linkRole, arcrole, axis, generations (optional), linkname (optional), arcname (optional)
    """
    xc = XPathContext.create(modelXbrl)
    result = concept_relationships(xc, None, args)
    return result

def load_filing_wrapper(f: str, validate=False) -> ModelXbrl:
    """Load and validate xbrl filing"""
    gettext.install('arelle')
    cntlr = Cntlr(logFileName='logToPrint')
    # cntlr.showStatus = lambda x,y=None: print(x)
    PluginManager.init(cntlr)
    fo = FormulaOptions()
    fo.formulaAction = 'none'
    cntlr.modelManager.formulaOptions = fo
    _transforms = PluginManager.addPluginModule("transforms/SEC")
    _inline_doc_set = PluginManager.addPluginModule("inlineXbrlDocumentSet")
    cntlr.modelManager.loadCustomTransforms()

    fs = FileSource.openFileSource(f, cntlr)
    entry_point_files = [{'file': f}]
    filesourceEntrypointFiles(fs, entry_point_files)
    commandLineFilingStart(cntlr, None, fs, entry_point_files)
    entry_point_file = entry_point_files[0].get('file') if isinstance(entry_point_files[0], dict) else entry_point_files[0]
    if fs.isArchive:
        fs.select(entry_point_file)
    else:
        fs = FileSource.openFileSource(entry_point_file, cntlr)

    modelXbrl = cntlr.modelManager.load(fs)
    if validate:
        cntlr.modelManager.validate()

    return modelXbrl

def select_docs_to_test_detection(modelXbrl: ModelXbrl, con: XbrlSqlDatabaseConnection) -> list[tuple[ModelDocument, str]]:
    """Selects model documents from modelXbrl, converts
        url protocol from http to https and vice versa
        and insert these document with modified protocol
        into db to test if these documents will be detected
        as existing regardless of url protocol
    """
    tested_docs = []
    for doc_url, model_doc in modelXbrl.urlDocs.items():
        if (con.isSemanticDocument(model_doc)
            and not doc_url.lower().endswith('ixds')
            and doc_url.lower().startswith('http')):
            # short_url = re.sub('^https?://', '', doc_url)
            converted_url = doc_url
            if doc_url.lower().startswith('http:'):
                converted_url = re.sub('^http', 'https', doc_url)
            if doc_url.lower().startswith('https:'):
                converted_url = re.sub('^https', 'http', doc_url)
            tested_docs.append((model_doc, converted_url))
            if len(tested_docs) == 3:
                break
    # makes sure urls are different
    assert all([mdl_doc.uri != url for mdl_doc, url in tested_docs])
    assert len(con.execute(f'SELECT document_id FROM {con.dbTableName("document")}')) == 0
    inserted_docs = con.getTable(
        'document', 'document_id',
        ('document_url', 'document_type', 'namespace'),
        ('document_url',),
        set((ensureUrl(conv_url),
            Type.typeName[mdl_doc.type],
            mdl_doc.targetNamespace)
            for mdl_doc, conv_url in tested_docs)
    )
    con.commit()
    assert len(tested_docs) == len(con.execute(f'SELECT document_id FROM {con.dbTableName("document")}'))
    return tested_docs

def get_modelXbrl_counts(modelXbrl: ModelXbrl, con: XbrlSqlDatabaseConnection) -> dict[str, int]:
    """Gets count of objects in filing (facts, concepts, ....)"""
    result = {}
    result['count_docs'] = len(
        {x for x in modelXbrl.urlDocs.values() if con.isSemanticDocument(x)})
    result['count_concepts'] = len(
        {x for x in modelXbrl.qnameConcepts.values() if con.isSemanticDocument(x.modelDocument)})
    result['count_facts'] = len(modelXbrl.facts)
    result['count_contexts'] = len(modelXbrl.contexts)
    result['count_mx_concepts_without_dims'] = len(
        [x for x,y in modelXbrl.contexts.items() if not y.hasSegment and not y.hasScenario])
    arcs = {x for x in modelXbrl.arcroleTypes}
    lrs = {x for x in modelXbrl.roleTypes}
    result['count_role_types'] = len(lrs)
    result['count_arcrole_types'] = len(arcs)

    all_arcs = {
        x[0] for x in modelXbrl.baseSets.keys() if not x[0].startswith('XBRL-')} # includes built in
    all_lrs = {
        x[1] for x in modelXbrl.baseSets.keys() if x[1] is not None} # includes default
    #  Get relationships
    mdl_rels = []
    for arc in all_arcs:
        for lr in all_lrs:
            for rel in concept_relationships_wrapper(
                modelXbrl, XbrlConst.qnXfiRoot, lr, arc, 'descendant'):
                mdl_rels.append(rel)

    count_rel_sets = 0
    for arcrole, ELR, linkqname, arcqname in modelXbrl.baseSets.keys():
        if ELR and linkqname and arcqname and not arcrole.startswith("XBRL-"):
            count_rel_sets +=1
    result['count_rel_sets'] = count_rel_sets
    result['count_mdl_rels'] = len(mdl_rels)
    return result

def get_db_counts(con: XbrlSqlDatabaseConnection) -> dict[str, int]:
    """Gets count of objects in db (facts, concepts, ....)"""
    result = {}
    result['count_docs'] = con.execute(
        f'SELECT count(*) FROM {con.dbTableName("document")}')[0][0]
    result['count_concepts'] = con.execute(
        f'SELECT count(*) FROM {con.dbTableName("aspect")}')[0][0]
    result['count_facts'] = con.execute(
        f'SELECT count(*) FROM {con.dbTableName("data_point")}' )[0][0]
    result['count_contexts'] = con.execute(
        f'SELECT count(distinct context_xml_id) FROM {con.dbTableName("data_point")}')[0][0]
    result['count_mx_concepts_without_dims'] = con.execute(
        f'SELECT count(distinct context_xml_id) FROM {con.dbTableName("data_point")} WHERE aspect_value_selection_id is null'
    )[0][0]
    result['count_role_types'] = con.execute(
        f'SELECT count(*) from {con.dbTableName("role_type")}')[0][0]
    result['count_arcrole_types'] = con.execute(
        f'SELECT count(*) from {con.dbTableName("arcrole_type")}')[0][0]
    result['count_rel_sets'] = con.execute(
        f'SELECT count(*) from {con.dbTableName("relationship_set")}')[0][0]
    result['count_mdl_rels'] = con.execute(
        f'SELECT count(*) from {con.dbTableName("relationship")}')[0][0]
    return result
