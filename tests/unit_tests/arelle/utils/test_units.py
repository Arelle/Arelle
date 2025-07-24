from unittest.mock import Mock, patch

from arelle.ModelInstanceObject import ModelUnit
from arelle.ModelXbrl import ModelXbrl
from arelle.utils.Units import (
    partitionUnits,
    partitionModelXbrlUnits,
    getDuplicateUnitGroups,
)

def test_notEqualDifferentHash():
    u1 = Mock(spec=ModelUnit, hash=1)
    u2 = Mock(spec=ModelUnit, hash=2)
    u1.isEqualTo.side_effect = lambda o: o is u1
    u2.isEqualTo.side_effect = lambda o: o is u2
    assert list(partitionUnits([u1, u2]).values()) == [(u1,), (u2,)]

def test_notEqualSameHash():
    u1 = Mock(spec=ModelUnit, hash=1)
    u2 = Mock(spec=ModelUnit, hash=1)
    u1.isEqualTo.side_effect = lambda o: o is u1
    u2.isEqualTo.side_effect = lambda o: o is u2
    assert list(partitionUnits([u1, u2]).values()) == [(u1,), (u2,)]

def test_equal():
    u1 = Mock(spec=ModelUnit, hash=1)
    u2 = Mock(spec=ModelUnit, hash=1)
    u1.isEqualTo.side_effect = lambda o: o is u1 or o is u2
    u2.isEqualTo.side_effect = lambda o: o is u1 or o is u2
    assert list(partitionUnits([u1, u2]).values()) == [(u1, u2)]

def test_id():
    u1 = Mock(spec=ModelUnit, hash=1)
    u1.isEqualTo.side_effect = lambda o: o is u1
    assert list(partitionUnits([u1, u1]).values()) == [(u1, u1)]


def test_detectAlternatingDuplicate():
    u1a = Mock(spec=ModelUnit, hash=1)
    u2 = Mock(spec=ModelUnit, hash=1)
    u1b = Mock(spec=ModelUnit, hash=1)
    u1a.isEqualTo.side_effect = lambda o: o is u1a or o is u1b
    u2.isEqualTo.side_effect = lambda o: o is u2
    u1b.isEqualTo.side_effect = lambda o: o is u1a or o is u1b
    modelXbrl = Mock(spec=ModelXbrl, units={1:u1a, 2:u2, 3:u1b})
    partitions1 = list(partitionUnits([u1a, u2, u1b]).values())
    assert partitions1 == [(u1a, u1b), (u2,)]
    partitions2 = list(partitionModelXbrlUnits(modelXbrl).values())
    assert partitions2 == partitions1
    duplicates = getDuplicateUnitGroups(modelXbrl)
    assert duplicates == [(u1a, u1b)]
