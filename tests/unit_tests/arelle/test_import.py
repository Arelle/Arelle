import glob
import subprocess
import sys

import pytest

KNOWN_FAILURES = frozenset([
    'arelle.CntlrProfiler',
    'arelle.FunctionXfi',
    'arelle.PrototypeDtsObject',
    'arelle.ViewCsvRelationshipSet',
    'arelle.archive.LoadSavePreLbCsv',
    'arelle.archive.SaveTableToExelle',
    'arelle.archive.TR3toTR4',
    'arelle.archive.plugin.loadFromOIM-2018',
    'arelle.archive.plugin.sphinx.SphinxEvaluator',
    'arelle.archive.plugin.validate.XFsyntax.xf',
    'arelle.formula.FormulaEvaluator',
])
# Don't test common third party plugins which may be copied into a developer's workspace.
COMMON_THIRD_PARTY_PLUGINS = (
    'arelle/plugin/EDGAR',
    'arelle/plugin/FERC',
    'arelle/plugin/iXBRLViewerPlugin',
    'arelle/plugin/semanticHash.py',
    'arelle/plugin/serializer',
    'arelle/plugin/SimpleXBRLModel',
    'arelle/plugin/validate/DQC.py',
    'arelle/plugin/validate/eforms.py',
    'arelle/plugin/validate/ESEF-DQC.py',
    'arelle/plugin/xendr',
    'arelle/plugin/Xince.py',
    'arelle/plugin/xodel',
    'arelle/plugin/xule',
)
MODULE_NAMES = [
    g.replace('/', '.').replace('\\', '.').replace('.py', '')
    for g in glob.glob('arelle/**/*.py', recursive=True)
    if not g.startswith(COMMON_THIRD_PARTY_PLUGINS)
]
TEST_PARAMS = [
    pytest.param(
        module_name,
        id=module_name,
        marks=[pytest.mark.xfail()] if module_name in KNOWN_FAILURES else []
    ) for module_name in MODULE_NAMES
]


@pytest.mark.slow
@pytest.mark.parametrize('module_name', TEST_PARAMS)
def test(module_name):
    subprocess.run([sys.executable, '-c', f'import {module_name}'], check=True)
