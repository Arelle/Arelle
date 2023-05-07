from __future__ import annotations


class PIBase:
    def __init__(self, target: str, text: str | None = None) -> None:
        self._target = target
        self._text = text if text is not None else ""
