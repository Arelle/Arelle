from pathlib import Path, PurePath

from tests.integration_tests.validation.conformance_suite_config import (
    ConformanceSuiteAssetConfig,
    ConformanceSuiteConfig, AssetSource,
)

config = ConformanceSuiteConfig(
    assets=[
        ConformanceSuiteAssetConfig.conformance_suite(
            Path("xbrl-xsdtests_v2026-08-07-1508.zip"),
            entry_point=Path("index.xml"),
            public_download_url="https://github.com/Arelle/xbrl-xsdtests/releases/download/v2026.08.07-1508/xbrl-xsdtests_v2026-08-07-1508.zip",
            source=AssetSource.S3_PUBLIC,
        ),
    ],
    expected_additional_testcase_errors={f"*{s}": val for s, val in {
        # Generated conformance suite doesn't report number of expected occurences,
        # so Arelle (with match-all) considers additional occurences as a failure.
        # The intent of the source testcase is that there are 2 invalid values,
        # and Arelle correctly fires 2 errors, so this "failure" is accepted.
        "accepted/anyURI/anyURI-21837395-testcase.xml:Microsoft_anyURI_b005_1355_anyURI_b005_1355.i": {
            "xmlSchema:valueError": 1,
        },
    }.items()},
    expected_failure_ids=frozenset(f"{s}" for s in [
        # F.1.1: Block Escape (https://www.w3.org/TR/xmlschema-2/#cces)
        # e.g. <xsd:pattern value="\p{IsXYZ}+"/> where XYZ denotes a Unicode block
        "accepted/string/string-11411fc5-testcase.xml:Microsoft_reL25_reL25.v",
        "accepted/string/string-134052df-testcase.xml:Microsoft_reL69_reL69.v",
        "accepted/string/string-17d9c5eb-testcase.xml:Microsoft_reL41_reL41.v",
        "accepted/string/string-1dfaac9f-testcase.xml:Microsoft_reL73_reL73.v",
        "accepted/string/string-207a812e-testcase.xml:Microsoft_reL81_reL81.v",
        "accepted/string/string-22007c63-testcase.xml:Microsoft_reL45_reL45.v",
        "accepted/string/string-28fd27e0-testcase.xml:Microsoft_reL35_reL35.v",
        "accepted/string/string-369ad5f6-testcase.xml:Microsoft_reL87_reL87.v",
        "accepted/string/string-3742cbae-testcase.xml:Microsoft_reL59_reL59.v",
        "accepted/string/string-3db3c89d-testcase.xml:Microsoft_reL33_reL33.v",
        "accepted/string/string-3ddb9ae5-testcase.xml:Microsoft_reL53_reL53.v",
        "accepted/string/string-40dbca64-testcase.xml:Microsoft_reL47_reL47.v",
        "accepted/string/string-42bf2f9b-testcase.xml:Microsoft_reL49_reL49.v",
        "accepted/string/string-45291263-testcase.xml:Microsoft_reL17_reL17.v",
        "accepted/string/string-5a9b923c-testcase.xml:Microsoft_reF40_reF40.v",
        "accepted/string/string-61eda1df-testcase.xml:Microsoft_reL1_reL1.v",
        "accepted/string/string-632f43d7-testcase.xml:Microsoft_reL61_reL61.v",
        "accepted/string/string-73f8adbb-testcase.xml:Microsoft_reL19_reL19.v",
        "accepted/string/string-7b4ca6d1-testcase.xml:Microsoft_reL51_reL51.v",
        "accepted/string/string-7b66b4db-testcase.xml:Microsoft_reL5_reL5.v",
        "accepted/string/string-8281a928-testcase.xml:Microsoft_reL85_reL85.v",
        "accepted/string/string-860d632b-testcase.xml:Microsoft_reL43_reL43.v",
        "accepted/string/string-8e04f44d-testcase.xml:Microsoft_reL63_reL63.v",
        "accepted/string/string-8f44c91a-testcase.xml:Microsoft_reL39_reL39.v",
        "accepted/string/string-912d85dc-testcase.xml:Microsoft_reL83_reL83.v",
        "accepted/string/string-97cce6e9-testcase.xml:Microsoft_reL31_reL31.v",
        "accepted/string/string-9c219ae9-testcase.xml:Microsoft_reL37_reL37.v",
        "accepted/string/string-a8c7235b-testcase.xml:Microsoft_reL11_reL11.v",
        "accepted/string/string-b4fb4f33-testcase.xml:Microsoft_reL55_reL55.v",
        "accepted/string/string-b6fcc6ec-testcase.xml:Microsoft_reL3_reL3.v",
        "accepted/string/string-b9d0fab7-testcase.xml:Microsoft_reL27_reL27.v",
        "accepted/string/string-bc4eeb52-testcase.xml:Microsoft_reL57_reL57.v",
        "accepted/string/string-befc0049-testcase.xml:Microsoft_reL67_reL67.v",
        "accepted/string/string-c14f46ef-testcase.xml:Microsoft_reL71_reL71.v",
        "accepted/string/string-dd2478c5-testcase.xml:Microsoft_reL79_reL79.v",
        "accepted/string/string-fd308f5a-testcase.xml:Microsoft_reL65_reL65.v",

        # F.1.1: Multi-Character Escape (https://www.w3.org/TR/xmlschema-2/#cces)
        # \C -> [^\c]
        "accepted/string/string-20c71448-testcase.xml:Microsoft_reG19_reG19.v",
        "accepted/string/string-2fbc056a-testcase.xml:Microsoft_reR20_reR20.v",
        "accepted/string/string-2fbc056a-testcase.xml:Microsoft_reR22_reR22.v",
        "accepted/string/string-a9c1ee56-testcase.xml:Microsoft_reR24_reR24.v",
        # \D -> [^\d]
        "accepted/string/string-2940bcdf-testcase.xml:Microsoft_reT17_reT17.i",
        "accepted/string/string-2940bcdf-testcase.xml:Microsoft_reT51_reT51.v",
        "accepted/string/string-2940bcdf-testcase.xml:Microsoft_reT63_reT63.i",
        # \I -> [^\i]
        "accepted/string/string-85b1401f-testcase.xml:Microsoft_reQ18_reQ18.v",
        "accepted/string/string-85b1401f-testcase.xml:Microsoft_reQ20_reQ20.v",
        "accepted/string/string-922585a4-testcase.xml:Microsoft_reQ22_reQ22.v",
        "accepted/string/string-9bbd2066-testcase.xml:Microsoft_reQ12_reQ12.v",
        # \W -> [^\w]
        "accepted/string/string-6e830617-testcase.xml:Microsoft_reV30_reV30.i",
        "accepted/string/string-6e830617-testcase.xml:Microsoft_reV32_reV32.i",
        "accepted/string/string-6e830617-testcase.xml:Microsoft_reV34_reV34.i",
        "accepted/string/string-6e830617-testcase.xml:Microsoft_reV36_reV36.i",
        "accepted/string/string-6e830617-testcase.xml:Microsoft_reV38_reV38.i",
        "accepted/string/string-6e830617-testcase.xml:Microsoft_reV40_reV40.i",
        "accepted/string/string-6e830617-testcase.xml:Microsoft_reV42_reV42.i",
        # \d -> \p{Nd}
        "accepted/string/string-cd992c8a-testcase.xml:Microsoft_reS38_reS38.v",
        "accepted/string/string-cd992c8a-testcase.xml:Microsoft_reS42_reS42.i",
        # \w -> [#x0000-#x10FFFF]-[\p{P}\p{Z}\p{C}]
        "accepted/string/string-338dd95a-testcase.xml:Microsoft_reU6_reU6.i",
        "accepted/string/string-918b9db5-testcase.xml:Microsoft_reZ002_reZ002.i",

        # Other
        # <xsd:pattern value="[\i\c]+:[\i\c]+"/> <elem>a:b</elem>
        "accepted/QName/QName-6d013dc0-testcase.xml:Microsoft_reDC5_reDC5.v",
        # <xsd:pattern value="a\r\nb"/> <elem>a&#xD;&#xA;b</elem>
        "accepted/string/string-01dd9f2a-testcase.xml:Microsoft_reI65_reI65.v",
        # <xsd:pattern value="\n\ra\n\rb"/> <elem>&#xA;&#xD;a&#xA;&#xD;b</elem>
        "accepted/string/string-1296eec6-testcase.xml:Microsoft_reI67_reI67.v",
        # <xsd:pattern value="a|b|a|c|b|d|a"/> <elem>aa</elem>
        "accepted/string/string-6ae04587-testcase.xml:Microsoft_reA32_reA32.i",
        # <xsd:pattern value="a|b"/> <elem>aa</elem>
        "accepted/string/string-7edddfb3-testcase.xml:Microsoft_reA18_reA18.i",
        # <xsd:pattern value="a|b"/> <elem>ab</elem>
        "accepted/string/string-7edddfb3-testcase.xml:Microsoft_reA20_reA20.i",
        # <xsd:pattern value="\r\ra\r\rb\r\r"/> <elem>&#xD;&#xD;a&#xD;&#xD;b&#xD;&#xD;</elem>
        "accepted/string/string-9f2bbc66-testcase.xml:Microsoft_reI55_reI55.v",

        # The accuracy of "queried" testcases may be disputed.
        # https://www.w3.org/Bugs/Public/show_bug.cgi?id=4113
        "queried/string/string-0b492168-testcase.xml:Microsoft_reJ77_reJ77.i",
        "queried/string/string-10f33baf-testcase.xml:Microsoft_reJ13_reJ13.i",
        "queried/string/string-2940bcdf-testcase.xml:Microsoft_reT63_reT63.i",
        "queried/string/string-3c6f9caa-testcase.xml:Microsoft_reJ23_reJ23.i",
        "queried/string/string-3e52cc84-testcase.xml:Microsoft_reJ19_reJ19.i",
        "queried/string/string-4a16381f-testcase.xml:Microsoft_reJ75_reJ75.i",
        "queried/string/string-68380144-testcase.xml:Microsoft_reJ61_reJ61.i",
        "queried/string/string-6fd0c269-testcase.xml:Microsoft_reJ33_reJ33.i",
        "queried/string/string-875ce552-testcase.xml:Microsoft_reJ11_reJ11.i",
        "queried/string/string-9efdf92b-testcase.xml:Microsoft_reJ21_reJ21.i",
        "queried/string/string-bf19c0df-testcase.xml:Microsoft_reJ35_reJ35.i",
        "queried/string/string-c4be5c9a-testcase.xml:Microsoft_reJ25_reJ25.i",
        "queried/string/string-cd992c8a-testcase.xml:Microsoft_reS42_reS42.i",
        "queried/string/string-cf5b0c73-testcase.xml:Microsoft_reJ69_reJ69.i",
        "queried/string/string-e11efe7e-testcase.xml:Microsoft_reJ31_reJ31.i",
        "queried/string/string-f357e125-testcase.xml:Microsoft_reJ29_reJ29.i",
    ]),
    info_url="https://github.com/Arelle/xbrl-xsdtests",
    name=PurePath(__file__).stem,
    test_case_result_options="match-all",
    shards=3,  # Fits on single macos GHA runner's 3 cores
)
