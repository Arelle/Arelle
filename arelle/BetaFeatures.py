from __future__ import annotations

BETA_OBJECT_MODEL_FEATURE = "betaObjectModel"
# Add camelCaseOptionName
BETA_FEATURES_AND_DESCRIPTIONS: dict[str, str] = {
    BETA_OBJECT_MODEL_FEATURE: "Replace lxml based object model with a pure Python class hierarchy.",
}


_NEW_OBJECT_MODEL_STATUS_ACCESSED = False
_USE_NEW_OBJECT_MODEL = False


def enableNewObjectModel() -> None:
    global _USE_NEW_OBJECT_MODEL
    if _USE_NEW_OBJECT_MODEL:
        return
    if _NEW_OBJECT_MODEL_STATUS_ACCESSED:
        raise RuntimeError("Can't change object model transition setting after classes have already been defined.")
    _USE_NEW_OBJECT_MODEL = True


def newObjectModelEnabled() -> bool:
    global _NEW_OBJECT_MODEL_STATUS_ACCESSED
    _NEW_OBJECT_MODEL_STATUS_ACCESSED = True
    return _USE_NEW_OBJECT_MODEL
