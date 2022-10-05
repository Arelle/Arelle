from arelle import ModelManager
from arelle.CntlrCmdLine import CntlrCmdLine
from arelle.FileSource import openFileSource


def test_independent_model_manager():
    """Test creating a new ModelManager and associating it with a Cntlr.

    XULE does this.
    """
    cntlr = CntlrCmdLine(uiLang='en')
    file_source = openFileSource('arelle/config/empty-instance.xml', cntlr)
    modelManager = ModelManager.initialize(cntlr)
    modelXbrl = modelManager.load(file_source)
    assert modelXbrl
