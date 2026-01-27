from dataclasses import dataclass

@dataclass
class ConformanceSuiteIdOverride:
    pathSuffix: str
    readMeFirstUris: list[str]
    oldId: str
    newId: str

@dataclass
class ConformanceSuiteIdOverrides:
    pathContainsString: str
    overrides: tuple[ConformanceSuiteIdOverride, ...]

# Some conformance suites reuse variation IDs.
CONFORMANCE_SUITE_ID_OVERRIDES: tuple[ConformanceSuiteIdOverrides, ...] = (
    ConformanceSuiteIdOverrides(
        pathContainsString='conformance-suite-2025-sbr-domein-handelsregister',
        overrides=(
            ConformanceSuiteIdOverride(
                pathSuffix='conformance-suite-2025-sbr-domein-handelsregister/tests/G4-2-2_2/index.xml',
                readMeFirstUris=['TC4_invalid.xbri'],
                oldId='TC3_invalid',
                newId='TC4_invalid',
            ),
            ConformanceSuiteIdOverride(
                pathSuffix='conformance-suite-2025-sbr-domein-handelsregister/tests/G5-1-3_2/index.xml',
                readMeFirstUris=['TC2_valid.xbri'],
                oldId='TC1_valid',
                newId='TC2_valid',
            ),
        ),
    ),
)
