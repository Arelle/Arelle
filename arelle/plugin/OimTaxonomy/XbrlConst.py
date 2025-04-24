"""
See COPYRIGHT.md for copyright information.
"""
import regex as re
from arelle.ModelValue import qname

# MERGE TO arelle.XbrlConst when promoting plugin to infrastructure

oimTaxonomyDocTypePattern = re.compile(r"\s*\{.*\"documentType\"\s*:\s*\"https://xbrl.org/PWD/[0-9]{4}-[0-9]{2}-[0-9]{2}/oim\"", flags=re.DOTALL)
oimTaxonomyDocTypes = (
        "https://xbrl.org/PWD/2025-01-31/oim",
    )

xbrl = "https://xbrl.org/2025"

qnStdLabel = qname("{https://xbrl.org/2025}xbrli:label")
