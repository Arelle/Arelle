"""
See COPYRIGHT.md for copyright information.
"""
from __future__ import annotations

import re
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from arelle.ValidateXbrl import ValidateXbrl
from arelle.typing import TypeGetText
from arelle.utils.PluginHooks import ValidationHook
from arelle.utils.validate.Decorator import validation
from arelle.utils.validate.Validation import Validation
from ..DisclosureSystems import (DISCLOSURE_SYSTEM_EDINET)
from ..PluginValidationDataExtension import PluginValidationDataExtension

_: TypeGetText

FILENAME_STEM_PATTERN = re.compile(r'[a-zA-Z0-9_-]*')


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=[DISCLOSURE_SYSTEM_EDINET],
)
def rule_EC0121E(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    EDINET.EC0121E: There is a directory or file that contains more than 31 characters
    or uses characters other than those allowed (alphanumeric characters, '-' and '_').
    """
    for path in (Path(file) for file in val.modelXbrl.fileSource.filesDir):
        if len(str(path.name)) > 31 or not FILENAME_STEM_PATTERN.match(path.stem):
            yield Validation.error(
                codes='EDINET.EC0121E',
                msg=_("There is a directory or file in %(directory)s that contains more than 31 characters "
                      "or uses characters other than those allowed (alphanumeric characters, '-' and '_'). "
                      "Directory or file name: %(basename)s "
                      "Please change the file name (or folder name) to within 31 characters and to usable "
                      "characters, and upload again."),
                directory=str(path.parent),
                basename=path.name,
                file=str(path)
            )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=[DISCLOSURE_SYSTEM_EDINET],
)
def rule_EC0129E(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    EDINET.EC0129E: Limit the number of subfolders to 3 or less from the XBRL directory.
    """
    startingDirectory = 'XBRL'
    for path in (Path(file) for file in val.modelXbrl.fileSource.filesDir):
        parents = [parent.name for parent in path.parents]
        if startingDirectory in parents:
            parents = parents[:parents.index(startingDirectory)]
        depth = len(parents)
        if depth > 3:
            yield Validation.error(
                codes='EDINET.EC0129E',
                msg=_("The subordinate directories of %(path)s go up to the %(depth)s level. "
                      "Please limit the number of subfolders to 3 or less and upload again."),
                path=str(path),
                depth=depth,
                file=str(path)
            )
