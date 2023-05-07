from arelle.BetaFeatures import newObjectModelEnabled

# The if statement is negated here so that from mypy's perspective the types
# inherit from the lxml object model until the new models are ready to be used.
if not newObjectModelEnabled():
    from lxml.etree import CommentBase as CommentBase
    from lxml.etree import ElementBase as ElementBase
    from lxml.etree import PIBase as PIBase
else:
    from .CommentBase import CommentBase
    from .ElementBase import ElementBase  # type: ignore[assignment]
    from .PIBase import PIBase
