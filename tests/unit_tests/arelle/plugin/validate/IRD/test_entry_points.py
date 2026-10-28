from pathlib import Path
from types import ModuleType

import arelle.plugin.validate.IRD as ird_plugin
from arelle.plugin.validate.IRD.ValidationPluginExtension import ValidationPluginExtension
from arelle.plugin.validate.IRD.rules.ixbrl_technical import IRD_HREF_RE

_BASE = "http://xbrl.ird.gov.hk/taxonomy/2026-04-01/"


def _pluginData():
    pluginDir = Path(ird_plugin.__file__).parent
    return ValidationPluginExtension(
        name="Validate IRD",
        disclosureSystemConfigUrl=pluginDir / "resources" / "config.xml",
        validationTypes=["IRD"],
        validationRuleModules=[ModuleType("ird_rules")],
    ).newPluginData(None, None)  # type: ignore[arg-type]


def _https(href: str) -> str:
    return "https://" + href[len("http://"):]


def test_published_entry_points_are_http_only() -> None:
    data = _pluginData()
    href = f"{_BASE}ird_tc_entry_point_2026-04-01.xsd"
    assert href in data.validTcEntryPoints
    assert _https(href) not in data.validTcEntryPoints
    assert IRD_HREF_RE.match(href)
    assert IRD_HREF_RE.match(_https(href)) is None


def test_current_fs_entry_points_include_traditional_chinese() -> None:
    data = _pluginData()
    fs = f"{_BASE}ird_fs-zh-hk_entry_point_2026-04-01.xsd"
    fsPe = f"{_BASE}ird_fs_pe-zh-hk_entry_point_2026-04-01.xsd"
    assert fs in data.validFsEntryPoints
    assert fsPe in data.validFsPeEntryPoints
    assert _https(fs) not in data.validFsEntryPoints
    assert _https(fsPe) not in data.validFsPeEntryPoints
    assert IRD_HREF_RE.match(fs)
    assert IRD_HREF_RE.match(fsPe)
