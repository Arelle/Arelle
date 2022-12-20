import glob
import os.path
import subprocess
import sys

import pytest

KNOWN_FAILURES = frozenset([
    'CntlrProfiler.py',
    'FormulaEvaluator.py',
    'FunctionXfi.py',
    'PrototypeDtsObject.py',
    'ViewWinRenderedGrid.py',
])
FILE_NAMES = list(map(os.path.basename, glob.glob('arelle/*.py')))
TEST_PARAMS = [
    pytest.param(
        file_name.replace('.py', ''),
        id=file_name,
        marks=[pytest.mark.xfail()] if file_name in KNOWN_FAILURES else []
    ) for file_name in FILE_NAMES
]


@pytest.mark.parametrize('module_name', TEST_PARAMS)
def test(module_name):
    assert module_name.isidentifier()
    subprocess.run([sys.executable, '-c', f'import arelle.{module_name}'], check=True)
