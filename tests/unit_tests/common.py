"""Shared constants for arelle unit tests."""

# Third-party packages commonly copied into a developer's workspace,
# expressed as forward-slash path prefixes relative to the project root.
THIRD_PARTY_PATH_PREFIXES: tuple[str, ...] = (
    'arelle/plugin/EDGAR',
    'arelle/plugin/FERC',
    'arelle/plugin/iXBRLViewerPlugin',
    'arelle/plugin/semanticHash',
    'arelle/plugin/serializer',
    'arelle/plugin/SimpleXBRLModel',
    'arelle/plugin/xbrlus',
    'arelle/plugin/xendr',
    'arelle/plugin/Xince',
    'arelle/plugin/xodel',
    'arelle/plugin/xule',
    'arelle/plugin/validate/DQC',
    'arelle/plugin/validate/eforms',
    'arelle/plugin/validate/ESEF-DQC',
    'arelle/resources',
)
