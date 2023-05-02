import importlib

import pytest
from lxml import etree

from arelle import BetaFeatures


@pytest.fixture(autouse=True)
def reset():
    BetaFeatures._NEW_OBJECT_MODEL_STATUS_ACCESSED = False
    BetaFeatures._USE_NEW_OBJECT_MODEL = False
    yield
    BetaFeatures._NEW_OBJECT_MODEL_STATUS_ACCESSED = False
    BetaFeatures._USE_NEW_OBJECT_MODEL = False


def test_use_lxml_base_classes():
    import arelle.model

    importlib.reload(arelle.model)

    from arelle.model import CommentBase as InitCommentBase
    from arelle.model import ElementBase as InitElementBase
    from arelle.model import PIBase as InitPIBase

    from arelle.model.CommentBase import CommentBase
    from arelle.model.ElementBase import ElementBase
    from arelle.model.PIBase import PIBase

    element = InitElementBase()
    assert isinstance(element, etree.ElementBase)
    assert not isinstance(element, ElementBase)

    comment = InitCommentBase("comment")
    assert isinstance(comment, etree.CommentBase)
    assert not isinstance(comment, CommentBase)

    pi = InitPIBase("instruction")
    assert isinstance(pi, etree.PIBase)
    assert not isinstance(pi, PIBase)


def test_use_pure_python_base_classes():
    BetaFeatures.enableNewObjectModel()
    import arelle.model

    importlib.reload(arelle.model)

    from arelle.model import CommentBase as InitCommentBase
    from arelle.model import ElementBase as InitElementBase
    from arelle.model import PIBase as InitPIBase

    from arelle.model.CommentBase import CommentBase
    from arelle.model.ElementBase import ElementBase
    from arelle.model.PIBase import PIBase

    element = InitElementBase()
    assert not isinstance(element, etree.ElementBase)
    assert isinstance(element, ElementBase)

    comment = InitCommentBase("comment")
    assert not isinstance(comment, etree.CommentBase)
    assert isinstance(comment, CommentBase)

    pi = InitPIBase("instruction")
    assert not isinstance(pi, etree.PIBase)
    assert isinstance(pi, PIBase)


def test_enable_new_models_after_access_exception():
    import arelle.model

    importlib.reload(arelle.model)

    assert arelle.model.CommentBase is etree.CommentBase
    assert arelle.model.ElementBase is etree.ElementBase
    assert arelle.model.PIBase is etree.PIBase

    with pytest.raises(RuntimeError):
        BetaFeatures.enableNewObjectModel()
