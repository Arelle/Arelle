import os
import pytest
from arelle.Cntlr import Cntlr
from arelle import ModelXbrl
from arelle.plugin.xbrlDB.XbrlSemanticSqlDB import XbrlSqlDatabaseConnection as XbrlCon
from arelle.plugin.xbrlDB.XbrlSemanticSqlDB import XBRLDBTABLES
from arelle.plugin.xbrlDB.SqlDb import XPDBException
from xbrldb_test_helpers import ddlFiles
from xbrldb_test_helpers import con_params
from xbrldb_test_helpers import drop_existing_objects
from xbrldb_test_helpers import get_db_sequences
from xbrldb_test_helpers import get_db_triggers
from xbrldb_test_helpers import load_filing_wrapper
from xbrldb_test_helpers import select_docs_to_test_detection
from xbrldb_test_helpers import get_db_counts
from xbrldb_test_helpers import get_modelXbrl_counts
from xbrldb_test_helpers import XBRLDBSEQUENCES
from xbrldb_test_helpers import XBRLDBTRIGGERS
from xbrldb_test_helpers import test_filings

@pytest.mark.parametrize(
    'con_params', con_params
)
def test_disable_automatic_create(con_params: dict) -> None:
    cntlr = Cntlr()
    modelXbrl = ModelXbrl.create(cntlr.modelManager)
    con = XbrlCon(modelXbrl, **con_params)
    # make sure all tables are dropped
    drop_existing_objects(con, True)
    with pytest.raises(XPDBException) as ex:
        con.verifyTables()
    assert str(ex.value).endswith(ddlFiles[con.product])

    # clean up database
    drop_existing_objects(con, True)
    con.close()

@pytest.mark.parametrize(
    'con_params', con_params
)
def test_create(con_params: dict) -> None:
    cntlr = Cntlr()
    modelXbrl = ModelXbrl.create(cntlr.modelManager)
    con = XbrlCon(modelXbrl, **con_params)
    ddl_file = os.path.join(
        cntlr.pluginDir, 'xbrlDB', 'sql', 'semantic', ddlFiles[con.product])
    drop_existing_objects(con, True)
    con.create(ddl_file, False)

    # assert all db objects were created
    assert len(XBRLDBTABLES - con.tablesInDB()) == 0
    if con.product in ('postgres', 'orcl', 'mssql'):
        assert len(XBRLDBSEQUENCES - get_db_sequences(con)) == 0
    if con.product in XBRLDBTRIGGERS:
        assert len(XBRLDBTRIGGERS[con.product] - get_db_triggers(con)) == 0

    # clean up database
    drop_existing_objects(con, True)
    con.close()

@pytest.mark.parametrize(
    "con_params, entry_point", [(param, filing) for param in con_params for filing in test_filings]
)
def test_detect_preexisting_docs(con_params: dict, entry_point: str) -> None:
    """Test if existing documents are detected even if url has different protocol (http|https)"""
    modelXbrl = load_filing_wrapper(entry_point)
    con = XbrlCon(modelXbrl, **con_params)
    # clean up before inserting test data
    drop_existing_objects(con, True)
    # create schema
    ddl_file = os.path.join(
        modelXbrl.modelManager.cntlr.pluginDir, 'xbrlDB', 'sql', 'semantic', ddlFiles[con.product])
    con.create(ddl_file, False)
    # select and insert docs to test, these are documents
    # from the filings but inserted with url having
    # different protocol to test if they will be detected
    # as preexisting documents.
    tested_docs = select_docs_to_test_detection(modelXbrl, con)
    # necessary step before checking for preexisting documents
    con.identifyTaxonomyRelSetsOwner()
    # make sure preexisting docs ids is empty
    assert not getattr(con, 'existingDocumentIds', False)
    # identify preexisting documents
    con.identifyPreexistingDocuments()
    con.unlockAllTables()
    assert len({x for x in con.existingDocumentIds} - {x[0] for x in tested_docs}) == 0

    # clean up database
    drop_existing_objects(con, True)
    con.close()

@pytest.mark.parametrize(
    "con_params, entry_point", [(param, filing) for param in con_params for filing in test_filings]
)
def test_insert_xbrl(con_params: dict, entry_point: str) -> None:
    """loads filing and compare data inserted into db against filing data"""
    modelXbrl = load_filing_wrapper(entry_point)
    con = XbrlCon(modelXbrl, **con_params)
    drop_existing_objects(con, True)
    # create schema
    ddl_file = os.path.join(
        modelXbrl.modelManager.cntlr.pluginDir, 'xbrlDB', 'sql', 'semantic', ddlFiles[con.product])
    con.create(ddl_file, False)

    # insert filing
    con.insertXbrl(None, None)
    # compare object counts from modelXbrl and db
    mx_counts = get_modelXbrl_counts(modelXbrl, con)
    db_counts = get_db_counts(con)
    assert set(db_counts.keys()) == set(mx_counts.keys())
    for k, v in db_counts.items():
        assert v == mx_counts[k]
    # clean up database
    drop_existing_objects(con, True)
    con.close()
