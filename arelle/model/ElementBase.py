from __future__ import annotations


class ElementBase:
    def __init__(self, *children: ElementBase, attrib: dict[str, str] | None = None, nsmap: dict[str, str] | None = None, **extra: str) -> None:
        self._children = children
        self._attrib = attrib if attrib is not None else {}
        self._nsmap = nsmap if nsmap is not None else {}
