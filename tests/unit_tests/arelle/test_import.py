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

# OIM Taxonomy uses typing features not available in Python 3.9 and earlier.
# Python 3.9 support will be dropped before this plugin is fully supported.
if sys.version_info < (3, 10):
    KNOWN_FAILURES |= frozenset([
        'arelle.plugin.OimTaxonomy.__init__',
        'arelle.plugin.OimTaxonomy.ModelValueMore',
        'arelle.plugin.OimTaxonomy.ValidateDTS',
        'arelle.plugin.OimTaxonomy.ViewXbrlTxmyObj',
        'arelle.plugin.OimTaxonomy.XbrlAbstract',
        'arelle.plugin.OimTaxonomy.XbrlConcept',
        'arelle.plugin.OimTaxonomy.XbrlConst',
        'arelle.plugin.OimTaxonomy.XbrlCube',
        'arelle.plugin.OimTaxonomy.XbrlDimension',
        'arelle.plugin.OimTaxonomy.XbrlDts',
        'arelle.plugin.OimTaxonomy.XbrlEntity',
        'arelle.plugin.OimTaxonomy.XbrlGroup',
        'arelle.plugin.OimTaxonomy.XbrlImportedTaxonomy',
        'arelle.plugin.OimTaxonomy.XbrlLabel',
        'arelle.plugin.OimTaxonomy.XbrlNetwork',
        'arelle.plugin.OimTaxonomy.XbrlProperty',
        'arelle.plugin.OimTaxonomy.XbrlReference',
        'arelle.plugin.OimTaxonomy.XbrlReport',
        'arelle.plugin.OimTaxonomy.XbrlTableTemplate',
        'arelle.plugin.OimTaxonomy.XbrlTaxonomy',
        'arelle.plugin.OimTaxonomy.XbrlTaxonomyObject',
        'arelle.plugin.OimTaxonomy.XbrlTransform',
        'arelle.plugin.OimTaxonomy.XbrlTypes',
        'arelle.plugin.OimTaxonomy.XbrlUnit',
    ])

# Don't test common third party plugins which may be copied into a developer's workspace.
IGNORE_MODULE_PREFIXES = (
    'arelle.plugin.EDGAR',
    'arelle.plugin.FERC',
    'arelle.plugin.iXBRLViewerPlugin',
    'arelle.plugin.semanticHash',
    'arelle.plugin.serializer',
    'arelle.plugin.SimpleXBRLModel',
    'arelle.plugin.validate.DQC',
    'arelle.plugin.validate.eforms',
    'arelle.plugin.validate.ESEF-DQC',
    'arelle.plugin.xendr',
    'arelle.plugin.Xince',
    'arelle.plugin.xodel',
    'arelle.plugin.xule',
    'arelle.resources',
)
MODULE_NAMES = [
    module_name
    for g in glob.glob('arelle/**/*.py', recursive=True)
    if not (module_name := g.replace('/', '.').replace('\\', '.').replace('.py', '')).startswith(IGNORE_MODULE_PREFIXES)
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
