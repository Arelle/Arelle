from __future__ import annotations


class CommentBase:
    def __init__(self, text: str) -> None:
        self._text = text
