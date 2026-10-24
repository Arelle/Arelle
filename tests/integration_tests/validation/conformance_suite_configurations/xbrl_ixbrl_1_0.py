import shutil
from pathlib import Path, PurePath

from tests.integration_tests.validation.conformance_suite_config import (
    AssetSource,
    ConformanceSuiteAssetConfig,
    ConformanceSuiteConfig,
)

CONFORMANCE_NS = "http://xbrl.org/2008/conformance"


def _preprocessing_func(config: ConformanceSuiteConfig) -> None:
    """Generate the test cases and index from the suite's ``.example`` sources.

    Follows the suite's ``make setup`` target (``bin/makeStaticFiles.sh``), using lxml
    to apply the suite's stylesheets so the build doesn't depend on bash, ``xsltproc``,
    or files outside the archive.

    The suite's stylesheets don't record expected results, so a result is added to each
    variation. FAIL tests are expected to be invalid, and PASS tests are expected to
    produce an instance equivalent to their ``.predictedOutput`` file.
    """
    # CI discovers suites without installing dependencies.
    from lxml import etree

    output_dir = config.entry_point_root
    suite_root = output_dir.parent
    bin_dir = suite_root / "bin"
    fragments_dir = suite_root / "resources" / "fragments"
    files_dir = output_dir / "files"
    files_dir.mkdir(parents=True, exist_ok=True)
    shutil.copytree(suite_root / "resources" / "schemas", output_dir / "schemas", dirs_exist_ok=True)

    extract_inputs = etree.XSLT(etree.parse(bin_dir / "extractTestInputs.xsl"))
    extract_outputs = etree.XSLT(etree.parse(bin_dir / "extractTestOutputs.xsl"))
    extract_metadata = etree.XSLT(etree.parse(bin_dir / "extractTestMetadata.xsl"))

    index = (fragments_dir / "index_top.xml").read_text(encoding="utf-8")
    index += ((fragments_dir / "index_testcases_top.xml").read_text(encoding="utf-8")
        .replace("ROOT", files_dir.name))
    index_testcase = (fragments_dir / "index_testcase.xml").read_text(encoding="utf-8")
    for example_path in sorted((suite_root / "testCases").glob("*.example")):
        name = example_path.stem
        example = etree.parse(example_path)
        (files_dir / f"{name}.html").write_bytes(str(extract_inputs(example)).encode("utf-8"))
        (files_dir / f"{name}.predictedOutput").write_bytes(str(extract_outputs(example)).encode("utf-8"))
        testcase = extract_metadata(
            example,
            baseFilename=etree.XSLT.strparam(name),
            schemaFilename=etree.XSLT.strparam(""),
        )
        variation = testcase.find(f"{{{CONFORMANCE_NS}}}variation")
        assert variation is not None, f"Generated test case has no variation: {name}"
        variation.set("id", "V-01")
        result = etree.SubElement(variation, f"{{{CONFORMANCE_NS}}}result")
        if name.startswith("FAIL-"):
            result.set("expected", "invalid")
        else:
            result.set("expected", "valid")
            etree.SubElement(result, f"{{{CONFORMANCE_NS}}}instance").text = f"{name}.predictedOutput"
        testcase.write(files_dir / f"{name}.xml", xml_declaration=True, encoding="UTF-8")
        index += index_testcase.replace("URI", f"{name}.xml")
    index += (fragments_dir / "index_bottom.xml").read_text(encoding="utf-8")
    (output_dir / "index.xml").write_text(index, encoding="utf-8")


ZIP_PATH = Path("inlinexbrl-conformancesuite-2010-04-20.zip")
EXTRACTED_PATH = Path(ZIP_PATH.stem)
config = ConformanceSuiteConfig(
    assets=[
        ConformanceSuiteAssetConfig.nested_conformance_suite(
            ZIP_PATH,
            EXTRACTED_PATH,
            entry_point_root=EXTRACTED_PATH / "output",
            entry_point=Path("index.xml"),
            public_download_url="https://www.xbrl.org/2010/inlinexbrl-conformancesuite-2010-04-20.zip",
            source=AssetSource.S3_PUBLIC,
        ),
    ],
    # The suite only checks extraction, but Arelle also validates the target document.
    expected_additional_testcase_errors={f"*files/{s}.xml:V-01": val for s, val in {
        # The extracted facts are invalid XBRL. Duration concepts are reported in instant
        # contexts, and some date facts contain markup.
        "PASS-element-ix-nonNumeric-escape-02": {
            "xbrl.4.7.2:contextPeriodType": 1,
            "xmlSchema:valueError": 1,
        },
        "PASS-element-ix-nonNumeric-escape-03": {
            "xbrl.4.7.2:contextPeriodType": 1,
            "xmlSchema:valueError": 1,
        },
        "PASS-element-ix-nonNumeric-escape-04": {
            "xbrl.4.7.2:contextPeriodType": 2,
            "xmlSchema:valueError": 1,
        },
        "PASS-element-ix-nonNumeric-escape-05": {
            "xbrl.4.7.2:contextPeriodType": 2,
        },
        "PASS-element-ix-nonNumeric-escape-06": {
            "xbrl.4.7.2:contextPeriodType": 2,
        },
        "PASS-element-ix-nonNumeric-escape-07": {
            "xbrl.4.7.2:contextPeriodType": 2,
        },
        # Facts use concepts that aren't defined in the referenced taxonomy.
        "PASS-element-link-footnote-complete": {
            "compareInstance:resultFactCounts": 1,
            "ix10.11.1.2:missingReferences": 1,
        },
        "PASS-elements-footnote-and-nonNumeric-unresolvable-uris-in-exclude": {
            "compareInstance:resultFactCounts": 1,
            "ix10.11.1.2:missingReferences": 1,
        },
        # The referenced linkbase_presentation.xml isn't included in the suite.
        "PASS-ix-references-04": {
            "IOerror": 1,
        },
        "PASS-ix-references-05": {
            "IOerror": 1,
        },
    }.items()},
    info_url="https://specifications.xbrl.org/work-product-index-inline-xbrl-inline-xbrl-1.0.html",
    name=PurePath(__file__).stem,
    plugins=frozenset({"inlineXbrlDocumentSet"}),
    preprocessing_func=_preprocessing_func,
    shards=4,
)
