"""
See COPYRIGHT.md for copyright information.

iXBRL Technical rules — ``<link:schemaRef>`` entry point validation.

Rules implemented here:
  553-E-0498                 schemaRef href is not an IRD-shaped entry
                              point URL
  553-E-0470/0486/0500       schemaRef href is IRD-shaped, but the version
                              is not a current or past release
  553-E-0468                 schemaRef href is a recognised IRD taxonomy
                              version, but not the latest
  553-E-0535/0536/0544/0552  document contains more than one schemaRef
                              element

553-E-0467/0497/0534/0543 are not implemented. They are a
processor-dependent catch-all for schemaRef failures outside the
buckets above.

Each family of related codes shares a single root cause per the IRD's
own documentation, so a single rule function yields all codes in the
family together as a ``codes`` tuple.
"""
from __future__ import annotations

import re
from collections.abc import Iterable
from typing import Any, Literal

from arelle.ValidateXbrl import ValidateXbrl
from arelle.typing import TypeGetText
from arelle.utils.PluginHooks import ValidationHook
from arelle.utils.validate.Decorator import validation
from arelle.utils.validate.Validation import Validation
from ..DisclosureSystems import ALL_IRD_DISCLOSURE_SYSTEMS
from ..PluginValidationDataExtension import PluginValidationDataExtension

_: TypeGetText

# IRD entry-point URL from the iXBRL style guide. The directory date and
# the date repeated in the filename are the taxonomy version. ``http``
# and ``https`` are both accepted. Longer names (``fs_pe``) come before
# the prefixes they contain (``fs``).
IRD_HREF_RE = re.compile(
    r"^https?://xbrl\.ird\.gov\.hk/taxonomy/"
    r"(?P<date>\d{4}-\d{2}-\d{2})/"
    r"ird_(?:fs_pe(?:-zh-hk)?|fs(?:-zh-hk)?|tc(?:-zh-hk)?)_entry_point_"
    r"(?P<file_date>\d{4}-\d{2}-\d{2})\.xsd$"
)


def _irdVersionDate(href: str) -> str | None:
    """Return the version date when *href* is an IRD-shaped entry point.

    The directory date and the filename date must be the same date.
    """
    match = IRD_HREF_RE.match(href)
    if match is None or match.group("date") != match.group("file_date"):
        return None
    return match.group("date")


def _classifyHref(
    href: str, pluginData: PluginValidationDataExtension
) -> Literal["valid", "not_ird_shaped", "unrecognised_version", "old_version"]:
    """Classify a single schemaRef ``href`` for the 553-E rule family.

    Returns one of:
      "valid"                 — IRD-shaped, and the version is the latest
      "old_version"           — IRD-shaped, recognised past version (0468)
      "unrecognised_version"  — IRD-shaped, version is not a current or
                                past release (0470/0486/0500)
      "not_ird_shaped"        — href is not an IRD entry-point URL (0498)

    553-E-0467/0497/0534/0543 are not classified here. They are a
    processor-dependent catch-all for schemaRef failures outside these
    buckets.
    """
    version = _irdVersionDate(href)
    if version is None:
        return "not_ird_shaped"
    if version not in pluginData.releasedVersionDates:
        return "unrecognised_version"
    if version != pluginData.latestVersionDate:
        return "old_version"
    return "valid"


def _iterSchemaRefs(
    pluginData: PluginValidationDataExtension,
    modelXbrl: Any,
) -> Iterable[tuple[Any, str]]:
    """Yield ``(ref, href)`` for every ``link:schemaRef`` in the IXDS."""
    for refs in pluginData.getSchemaRefsByDocument(modelXbrl).values():
        for ref in refs:
            yield ref, (ref.get("{http://www.w3.org/1999/xlink}href", "") or "")


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=ALL_IRD_DISCLOSURE_SYSTEMS,
)
def rule_553_e_0468(
    pluginData: PluginValidationDataExtension,
    val: ValidateXbrl,
    *args: Any,
    **kwargs: Any,
) -> Iterable[Validation]:
    """553-E-0468: schemaRef does not reference the latest IRD TC
    taxonomy version.

    Fires when the href is shaped like a recognised IRD taxonomy entry
    point and its version date is a known released version, but
    not the current latest.
    """
    for ref, href in _iterSchemaRefs(pluginData, val.modelXbrl):
        if _classifyHref(href, pluginData) == "old_version":
            yield Validation.error(
                codes="IRD.553-E-0468",
                msg=_(
                    "schemaRef href '%(href)s' references a superseded "
                    "IRD taxonomy version; the latest version is "
                    "%(latestVersion)s."
                ),
                modelObject=ref,
                href=href,
                latestVersion=pluginData.latestVersionDate,
            )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=ALL_IRD_DISCLOSURE_SYSTEMS,
)
def rule_553_e_unrecognised_version(
    pluginData: PluginValidationDataExtension,
    val: ValidateXbrl,
    *args: Any,
    **kwargs: Any,
) -> Iterable[Validation]:
    """553-E-0470/0486/0500: IRD-shaped schemaRef, unrecognised version.
    """
    for ref, href in _iterSchemaRefs(pluginData, val.modelXbrl):
        if _classifyHref(href, pluginData) == "unrecognised_version":
            yield Validation.error(
                codes=("IRD.553-E-0470", "IRD.553-E-0486", "IRD.553-E-0500"),
                msg=_(
                    "schemaRef href '%(href)s' is an IRD-shaped entry "
                    "point, but '%(version)s' is not a current or past "
                    "IRD taxonomy version."
                ),
                modelObject=ref,
                href=href,
                version=_irdVersionDate(href),
            )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=ALL_IRD_DISCLOSURE_SYSTEMS,
)
def rule_553_e_0498(
    pluginData: PluginValidationDataExtension,
    val: ValidateXbrl,
    *args: Any,
    **kwargs: Any,
) -> Iterable[Validation]:
    """553-E-0498: schemaRef href is not an IRD-shaped entry point.
    """
    for ref, href in _iterSchemaRefs(pluginData, val.modelXbrl):
        if _classifyHref(href, pluginData) == "not_ird_shaped":
            yield Validation.error(
                codes="IRD.553-E-0498",
                msg=_(
                    "schemaRef href '%(href)s' is not an IRD-shaped "
                    "taxonomy entry point."
                ),
                modelObject=ref,
                href=href,
            )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=ALL_IRD_DISCLOSURE_SYSTEMS,
)
def rule_553_e_multiple_schema_refs(
    pluginData: PluginValidationDataExtension,
    val: ValidateXbrl,
    *args: Any,
    **kwargs: Any,
) -> Iterable[Validation]:
    """553-E-0535/0536/0544/0552: document contains more than one
    schemaRef element.
    """
    for uri, refs in pluginData.getSchemaRefsByDocument(val.modelXbrl).items():
        if len(refs) > 1:
            yield Validation.error(
                codes=(
                    "IRD.553-E-0535",
                    "IRD.553-E-0536",
                    "IRD.553-E-0544",
                    "IRD.553-E-0552",
                ),
                msg=_(
                    "Document '%(uri)s' contains %(count)s "
                    "link:schemaRef elements; exactly one taxonomy "
                    "entry point is permitted per data file."
                ),
                modelObject=refs,
                uri=uri,
                count=len(refs),
            )
