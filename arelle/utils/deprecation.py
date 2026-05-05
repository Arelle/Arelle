"""
See COPYRIGHT.md for copyright information.
"""

from __future__ import annotations

import warnings
from collections.abc import Callable
from typing import Any

_DEFAULT_REMOVAL_VERSION = "3.0"


class ModuleDeprecations:
    """Registry of deprecated module-level attributes.

    Pairs with a module's `__getattr__` to emit a :class:`DeprecationWarning`
    when a removed attribute is accessed, while still returning its value for
    backward compatibility.

    Example usage in a module:

        _DEPRECATIONS = ModuleDeprecations(__name__)
        _DEPRECATIONS.add("old_const", new_const, "use new_const instead")

        def __getattr__(name: str) -> Any:
            return _DEPRECATIONS.resolve(name)
    """

    def __init__(self, module_name: str) -> None:
        """Create a deprecation registry for the given *module_name*."""
        self._module_name = module_name
        self._deprecated: dict[str, tuple[Any, str]] = {}
        self._lazy_keys: set[str] = set()

    def add(
        self,
        name: str,
        value: Any,
        guidance: str,
        removal_version: str = _DEFAULT_REMOVAL_VERSION,
    ) -> None:
        """Register a deprecated attribute that returns *value* on access."""
        if name in self._deprecated:
            raise ValueError(f"Deprecated attr '{name}' already registered in {self._module_name}")
        self._deprecated[name] = (value, self._message(name, guidance, removal_version))

    def add_all(
        self,
        items: dict[str, Any],
        guidance: str,
        removal_version: str = _DEFAULT_REMOVAL_VERSION,
    ) -> None:
        """Register multiple deprecated attributes sharing the same *guidance*."""
        for name, value in items.items():
            self.add(name, value, guidance, removal_version)

    def add_lazy(
        self,
        name: str,
        factory: Callable[[], Any],
        guidance: str,
        removal_version: str = _DEFAULT_REMOVAL_VERSION,
    ) -> None:
        """Register a deprecated attribute whose value is produced by *factory* on access."""
        if name in self._deprecated:
            raise ValueError(f"Deprecated attr '{name}' already registered in {self._module_name}")
        self._deprecated[name] = (factory, self._message(name, guidance, removal_version))
        self._lazy_keys.add(name)

    def add_lazy_all(
        self,
        items: dict[str, Callable[[], Any]],
        guidance: str,
        removal_version: str = _DEFAULT_REMOVAL_VERSION,
    ) -> None:
        """Register multiple lazy deprecated attributes sharing the same *guidance*."""
        for name, factory in items.items():
            self.add_lazy(name, factory, guidance, removal_version)

    def _message(self, name: str, guidance: str, removal_version: str) -> str:
        return f"{self._module_name}.{name} is deprecated. Will be removed in {removal_version}. {guidance}."

    def resolve(self, name: str) -> Any:
        """Look up *name*, emit a :class:`DeprecationWarning`, and return its value.

        Raises :class:`AttributeError` if *name* is not registered.
        Intended to be called from a module-level `__getattr__`.
        """
        if name not in self._deprecated:
            raise AttributeError(name)
        value, message = self._deprecated[name]
        warnings.warn(message, DeprecationWarning, stacklevel=3)
        return value() if name in self._lazy_keys else value
