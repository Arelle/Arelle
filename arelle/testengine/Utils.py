"""
See COPYRIGHT.md for copyright information.
"""
from __future__ import annotations

from pathlib import Path
from urllib.parse import unquote

CWD = Path.cwd()


def norm_path(path: Path) -> str:
    path = path.relative_to(CWD) if path.is_relative_to(CWD) else path
    path_str = str(path)
    if path_str.startswith("file:\\"):
        path_str = path_str[6:]
    return unquote(path_str)
