from unittest.mock import Mock, patch

from arelle.ModelInstanceObject import ModelContext
from arelle.ModelXbrl import ModelXbrl
from arelle.utils.Contexts import (
    partitionContexts,
    partitionModelXbrlContexts,
    getDuplicateContextPairs,
)

def test_notEqualDifferentHash():
    c1 = Mock(spec=ModelContext, contextDimAwareHash=1)
    c2 = Mock(spec=ModelContext, contextDimAwareHash=2)
    c1.isEqualTo.side_effect = lambda o, _: o is c1
    c2.isEqualTo.side_effect = lambda o, _: o is c2
    assert list(partitionContexts([c1, c2], True).values()) == [(c1,), (c2,)]

def test_notEqualSameHash():
    c1 = Mock(spec=ModelContext, contextDimAwareHash=1)
    c2 = Mock(spec=ModelContext, contextDimAwareHash=1)
    c1.isEqualTo.side_effect = lambda o, _: o is c1
    c2.isEqualTo.side_effect = lambda o, _: o is c2
    assert list(partitionContexts([c1, c2], True).values()) == [(c1,), (c2,)]

def test_equal():
    c1 = Mock(spec=ModelContext, contextDimAwareHash=1)
    c2 = Mock(spec=ModelContext, contextDimAwareHash=1)
    c1.isEqualTo.side_effect = lambda o, _: o is c1 or o is c2
    c2.isEqualTo.side_effect = lambda o, _: o is c1 or o is c2
    assert list(partitionContexts([c1, c2], True).values()) == [(c1, c2)]

def test_id():
    c1 = Mock(spec=ModelContext, contextDimAwareHash=1)
    c1.isEqualTo.side_effect = lambda o, _: o is c1
    assert list(partitionContexts([c1, c1], True).values()) == [(c1, c1)]


def test_nonDim_notEqualDifferentHash():
    c1 = Mock(spec=ModelContext, contextNonDimAwareHash=1)
    c2 = Mock(spec=ModelContext, contextNonDimAwareHash=2)
    c1.isEqualTo.side_effect = lambda o, _: o is c1
    c2.isEqualTo.side_effect = lambda o, _: o is c2
    assert list(partitionContexts([c1, c2], False).values()) == [(c1,), (c2,)]

def test_nonDim_notEqualSameHash():
    c1 = Mock(spec=ModelContext, contextNonDimAwareHash=1)
    c2 = Mock(spec=ModelContext, contextNonDimAwareHash=1)
    c1.isEqualTo.side_effect = lambda o, _: o is c1
    c2.isEqualTo.side_effect = lambda o, _: o is c2
    assert list(partitionContexts([c1, c2], False).values()) == [(c1,), (c2,)]

def test_nonDim_equal():
    c1 = Mock(spec=ModelContext, contextNonDimAwareHash=1)
    c2 = Mock(spec=ModelContext, contextNonDimAwareHash=1)
    c1.isEqualTo.side_effect = lambda o, _: o is c1 or o is c2
    c2.isEqualTo.side_effect = lambda o, _: o is c1 or o is c2
    assert list(partitionContexts([c1, c2], False).values()) == [(c1, c2)]

def test_nonDim_id():
    c1 = Mock(spec=ModelContext, contextNonDimAwareHash=1)
    c1.isEqualTo.side_effect = lambda o, _: o is c1
    assert list(partitionContexts([c1, c1], False).values()) == [(c1, c1)]


def test_detectAlternatingDuplicate():
    c1a = Mock(spec=ModelContext, contextDimAwareHash=1)
    c2 = Mock(spec=ModelContext, contextDimAwareHash=1)
    c1b = Mock(spec=ModelContext, contextDimAwareHash=1)
    c1a.isEqualTo.side_effect = lambda o, _: o is c1a or o is c1b
    c2.isEqualTo.side_effect = lambda o, _: o is c2
    c1b.isEqualTo.side_effect = lambda o, _: o is c1a or o is c1b
    modelXbrl = Mock(spec=ModelXbrl, contexts={1:c1a, 2:c2, 3:c1b}, hasXDT=True)
    partitions1 = list(partitionContexts([c1a, c2, c1b], True).values())
    assert partitions1 == [(c1a, c1b), (c2,)]
    partitions2 = list(partitionModelXbrlContexts(modelXbrl).values())
    assert partitions2 == partitions1
    duplicates = getDuplicateContextPairs(modelXbrl)
    assert duplicates == [(c1b, c1a)]
