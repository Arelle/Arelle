"""
See COPYRIGHT.md for copyright information.
"""

from __future__ import annotations

import io
import json
import os
from dataclasses import dataclass, field
from typing import Optional


RESOURCE_DIR = os.path.join(os.path.dirname(__file__), "resources")
ERROR_TAXONOMY_FILES = ("oime.json", "oimce.json", "oimte.json")
LABEL_TYPE = "xbrl:label"
DOCUMENTATION_TYPE = "xbrl:documentation"
MESSAGE_TYPE_SUFFIX = ":errorMessage"
SEVERITY_PROPERTY = "xbrl:severity"
REMOVED_PROPERTY = "oimte:removedError"
OBJECT_TYPE_NETWORK = "ErrorsByObjectType"
BASE_OBJECT_TYPE_NETWORK = "ErrorsByBaseObjectType"


@dataclass(slots=True)
class ErrorDefinition:
    code: str
    taxonomy: str
    severity: Optional[str] = None
    label: Optional[str] = None
    documentation: Optional[str] = None
    message_template: Optional[str] = None
    removed: bool = False
    properties: dict[str, object] = field(default_factory=dict)


class ErrorCatalog:
    def __init__(self, resourceDir: Optional[str] = None) -> None:
        self.resourceDir = resourceDir or RESOURCE_DIR
        self.definitions: dict[str, ErrorDefinition] = {}
        self._networkGroups: dict[str, dict[str, tuple[str, ...]]] = {}
        self._errorFamilies: dict[str, list[tuple[str, str]]] = {}
        self._load()

    def _load(self) -> None:
        for fileName in ERROR_TAXONOMY_FILES:
            filePath = os.path.join(self.resourceDir, fileName)
            if not os.path.exists(filePath):
                continue
            with io.open(filePath, mode="rt", encoding="utf-8") as fh:
                taxonomy = json.load(fh)
            self._ingest_taxonomy(fileName, taxonomy)

    def _ingest_taxonomy(self, taxonomyName: str, taxonomy: dict[str, object]) -> None:
        xbrlModel = taxonomy.get("xbrlModel", {}) if isinstance(taxonomy, dict) else {}
        members = xbrlModel.get("members", ()) if isinstance(xbrlModel, dict) else ()
        labels = xbrlModel.get("labels", ()) if isinstance(xbrlModel, dict) else ()
        networks = xbrlModel.get("networks", ()) if isinstance(xbrlModel, dict) else ()

        for member in members:
            if not isinstance(member, dict):
                continue
            code = member.get("name")
            if not isinstance(code, str):
                continue
            errorDef = self.definitions.setdefault(code, ErrorDefinition(code=code, taxonomy=taxonomyName))
            properties = member.get("properties", ())
            if isinstance(properties, list):
                for prop in properties:
                    if not isinstance(prop, dict):
                        continue
                    propName = prop.get("property")
                    propValue = prop.get("value")
                    if not isinstance(propName, str):
                        continue
                    errorDef.properties[propName] = propValue
                    if propName == SEVERITY_PROPERTY and isinstance(propValue, str):
                        errorDef.severity = propValue
                    elif propName == REMOVED_PROPERTY:
                        errorDef.removed = bool(propValue)

        for label in labels:
            if not isinstance(label, dict):
                continue
            code = label.get("relatedName")
            labelType = label.get("labelType")
            language = label.get("language")
            value = label.get("value")
            if not (isinstance(code, str) and isinstance(labelType, str) and isinstance(value, str)):
                continue
            if language != "en":
                continue
            errorDef = self.definitions.setdefault(code, ErrorDefinition(code=code, taxonomy=taxonomyName))
            if labelType == LABEL_TYPE:
                errorDef.label = value
            elif labelType == DOCUMENTATION_TYPE:
                errorDef.documentation = value
            elif labelType.endswith(MESSAGE_TYPE_SUFFIX):
                errorDef.message_template = value

        for network in networks:
            if not isinstance(network, dict):
                continue
            self._ingest_network(network)

    def _ingest_network(self, network: dict[str, object]) -> None:
        name = network.get("name")
        if not isinstance(name, str):
            return
        networkKey = self._network_key(name)
        if networkKey not in (OBJECT_TYPE_NETWORK, BASE_OBJECT_TYPE_NETWORK):
            return
        roots = network.get("roots", ())
        relationships = network.get("relationships", ())
        groups: dict[str, list[tuple[float, str]]] = {}
        if isinstance(roots, list):
            for root in roots:
                if isinstance(root, str):
                    groups.setdefault(root, [])
        if isinstance(relationships, list):
            for rel in relationships:
                if not isinstance(rel, dict):
                    continue
                source = rel.get("source")
                target = rel.get("target")
                if not (isinstance(source, str) and isinstance(target, str)):
                    continue
                order = rel.get("order", 0)
                try:
                    sortOrder = float(order)
                except (TypeError, ValueError):
                    sortOrder = 0.0
                groups.setdefault(source, []).append((sortOrder, target))
                self._errorFamilies.setdefault(target, []).append((networkKey, source))
        self._networkGroups[networkKey] = {
            root: tuple(target for _, target in sorted(targets, key=lambda item: item[0]))
            for root, targets in groups.items()
        }

    @staticmethod
    def _network_key(networkName: str) -> str:
        if ":" in networkName:
            return networkName.partition(":")[2]
        return networkName

    def has(self, code: str) -> bool:
        return code in self.definitions

    def get(self, code: str) -> Optional[ErrorDefinition]:
        return self.definitions.get(code)

    def label(self, code: str) -> Optional[str]:
        errorDef = self.get(code)
        return errorDef.label if errorDef else None

    def severity(self, code: str) -> Optional[str]:
        errorDef = self.get(code)
        return errorDef.severity if errorDef else None

    def documentation(self, code: str) -> Optional[str]:
        errorDef = self.get(code)
        return errorDef.documentation if errorDef else None

    def message_template(self, code: str) -> Optional[str]:
        errorDef = self.get(code)
        return errorDef.message_template if errorDef else None

    def is_removed(self, code: str) -> bool:
        errorDef = self.get(code)
        return bool(errorDef and errorDef.removed)

    def object_families(self, baseObjects: bool = False) -> dict[str, tuple[str, ...]]:
        networkKey = BASE_OBJECT_TYPE_NETWORK if baseObjects else OBJECT_TYPE_NETWORK
        return dict(self._networkGroups.get(networkKey, {}))

    def family_names(self, baseObjects: bool = False) -> tuple[str, ...]:
        return tuple(self.object_families(baseObjects=baseObjects).keys())

    def errors_for_family(self, familyName: str, baseObjects: bool = False) -> tuple[str, ...]:
        networkKey = BASE_OBJECT_TYPE_NETWORK if baseObjects else OBJECT_TYPE_NETWORK
        return self._networkGroups.get(networkKey, {}).get(familyName, ())

    def families_for_error(self, code: str, baseObjects: Optional[bool] = None) -> tuple[tuple[str, str], ...]:
        families = self._errorFamilies.get(code, ())
        if baseObjects is None:
            return tuple(families)
        networkKey = BASE_OBJECT_TYPE_NETWORK if baseObjects else OBJECT_TYPE_NETWORK
        return tuple((familyNetwork, familyName) for familyNetwork, familyName in families if familyNetwork == networkKey)

    def family_report_lines(self, baseObjects: bool = False) -> tuple[str, ...]:
        families = self.object_families(baseObjects=baseObjects)
        reportLines: list[str] = []
        for familyName, errorCodes in families.items():
            if errorCodes:
                labels = ", ".join(self.label(code) or code for code in errorCodes[:3])
                if len(errorCodes) > 3:
                    labels += ", ..."
                reportLines.append(f"{familyName}: {len(errorCodes)} errors [{labels}]")
            else:
                reportLines.append(f"{familyName}: 0 errors")
        return tuple(reportLines)

    def family_report(self, baseObjects: bool = False) -> str:
        title = "Errors By Base Object Type" if baseObjects else "Errors By Object Type"
        lines = [title, *self.family_report_lines(baseObjects=baseObjects)]
        return "\n".join(lines)


_errorCatalog: Optional[ErrorCatalog] = None


def get_error_catalog() -> ErrorCatalog:
    global _errorCatalog
    if _errorCatalog is None:
        _errorCatalog = ErrorCatalog()
    return _errorCatalog


def emit_error(compMdl, code: str, message: str, **kwargs):
    catalog = get_error_catalog()
    if not catalog.has(code):
        unknownCodes = getattr(compMdl, "_unknownErrorCodes", None)
        if unknownCodes is None:
            unknownCodes = set()
            setattr(compMdl, "_unknownErrorCodes", unknownCodes)
        unknownCodes.add(code)
    elif catalog.is_removed(code):
        removedCodes = getattr(compMdl, "_removedErrorCodes", None)
        if removedCodes is None:
            removedCodes = set()
            setattr(compMdl, "_removedErrorCodes", removedCodes)
        removedCodes.add(code)
    compMdl.error(code, message, **kwargs)
