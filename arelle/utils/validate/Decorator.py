"""
See COPYRIGHT.md for copyright information.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Iterable, Optional

from typing_extensions import TypeAlias

from arelle.utils.PluginHooks import ValidationHook
from arelle.utils.validate.Validation import Validation

ValidationFunction: TypeAlias = Callable[..., Optional[Iterable[Validation]]]


_VALIDATION_RULE_ATTRIBUTES_KEY = "_ARELLE_VALIDATION_ATTRIBUTES"


def validation(
    hook: ValidationHook,
    disclosureSystems: str | list[str] | None = None,
    excludeDisclosureSystems: str | list[str] | None = None,
) -> Callable[[ValidationFunction], ValidationFunction]:
    """
    Decorator for registering plugin validations. At most one of disclosureSystems and
    excludeDisclosureSystems parameters may be provided. If neither is provided the rule
    applies to all disclosure systems.

    All validation plugin functions should begin with the prefix "rule". For instance `def rule05(...):`.
    There is a test that checks all validation plugin functions (in the Arelle repo) beginning with the
    "rule" prefix to verify that the decorator has been applied.

    :param hook: The plugin validation hook the function should run with.
    :param disclosureSystems: The disclosure systems the validation should run with.
    :param excludeDisclosureSystems: The disclosure systems to exclude from running the rule with.
    :return: the registered validation function.
    """
    parsedIncluded = _wrapStrWithList(disclosureSystems)
    parsedExcluded = _wrapStrWithList(excludeDisclosureSystems) or []
    attributes = ValidationAttributes(hook, parsedIncluded, parsedExcluded)

    def decorator(f: ValidationFunction) -> ValidationFunction:
        if not callable(f):
            raise ValueError("@validation decorator must be used only to decorate functions.")

        _setValidationAttributes(f, attributes)
        return f

    return decorator


def _wrapStrWithList(items: list[str] | str | None) -> list[str] | None:
    return [items] if isinstance(items, str) else items


@dataclass(frozen=True)
class ValidationAttributes:
    hook: ValidationHook
    disclosureSystems: list[str] | None
    excludeDisclosureSystems: list[str]

    def __post_init__(self) -> None:
        if self.disclosureSystems is not None:
            if len(self.disclosureSystems) == 0:
                raise ValueError("disclosureSystems is an empty list. You can provide a list of disclosure systems, use None to match all, or use None and excludeDisclosureSystems to select disclosure systems.")
            if len(self.excludeDisclosureSystems) > 0:
                raise ValueError("disclosureSystems or excludeDisclosureSystems may be used, but not both.")


def getValidationAttributes(func: Callable[..., Any]) -> ValidationAttributes | None:
    return getattr(func, _VALIDATION_RULE_ATTRIBUTES_KEY, None)


def _setValidationAttributes(func: Callable[..., Any], attributes: ValidationAttributes) -> None:
    setattr(func, _VALIDATION_RULE_ATTRIBUTES_KEY, attributes)
