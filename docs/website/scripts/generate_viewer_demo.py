"""
See COPYRIGHT.md for copyright information.

Generate the website iXBRL Viewer demo.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import urllib.request
from pathlib import Path

import regex


TAXONOMY_PACKAGE_FILENAME = "The_2023_Taxonomy_suite_v1.0.1.zip"
S3_PACKAGE_BUCKET = "https://arelle-public.s3.us-east-1.amazonaws.com/ci/taxonomy_packages/"
TAXONOMY_PACKAGE_URL = S3_PACKAGE_BUCKET + TAXONOMY_PACKAGE_FILENAME


VIEWER_DATA_PATTERN = regex.compile(
    r'<script[^>]*type=["\']application/x\.ixbrl-viewer\+json["\']'
    r"[^>]*>(.*?)</script>",
    regex.DOTALL,
)
VIEWER_SCRIPT_PATTERN = regex.compile(
    r'<script[^>]*src=["\']ixbrlviewer\.js["\'][^>]*></script>'
)


def _get_taxonomy_package(package_directory: Path) -> Path:
    destination = package_directory / TAXONOMY_PACKAGE_FILENAME
    if destination.is_file():
        return destination
    package_directory.mkdir(parents=True, exist_ok=True)
    try:
        urllib.request.urlretrieve(TAXONOMY_PACKAGE_URL, destination)
    except Exception:
        destination.unlink(missing_ok=True)
        raise
    return destination


def validate_viewer(viewer_path: Path) -> None:
    if not viewer_path.is_file():
        raise ValueError(f"Viewer is absent from {viewer_path}")
    viewer_html = viewer_path.read_text()
    if VIEWER_SCRIPT_PATTERN.search(viewer_html) is None:
        raise ValueError(f"Viewer script missing from {viewer_path}")
    viewer_data_match = VIEWER_DATA_PATTERN.search(viewer_html)
    if viewer_data_match is None:
        raise ValueError(f"Viewer data missing from {viewer_path}")
    try:
        json.loads(viewer_data_match.group(1))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Viewer data is invalid JSON: {viewer_path}") from exc


def generate_viewer(base_url: str) -> Path:
    site_root = Path(__file__).resolve().parents[1]
    repo_root = site_root.parent.parent
    filing_directory = site_root / "demo" / "filing"
    demo_ixbrl_report = filing_directory / "04958719_aa_2026-07-08.xhtml"
    package_directory = site_root / "demo" / "package"
    viewer_config_path = site_root / "demo" / "ixbrlviewer.config.json"
    publish_directory = site_root / "public" / "demo" / "ixbrl-viewer"
    viewer_path = publish_directory / "ixbrlviewer.html"
    if not demo_ixbrl_report.is_file():
        raise ValueError(f"Demo iXBRL report missing: {demo_ixbrl_report}")
    if not viewer_config_path.is_file():
        raise ValueError(f"Viewer config missing: {viewer_config_path}")

    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))
    from arelle.RuntimeOptions import RuntimeOptions
    from arelle.api.Session import Session

    taxonomy_package = _get_taxonomy_package(package_directory)
    shutil.rmtree(publish_directory, ignore_errors=True)
    publish_directory.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(viewer_config_path, publish_directory / viewer_config_path.name)

    options = RuntimeOptions(
        entrypointFile=str(demo_ixbrl_report),
        internetConnectivity="offline",
        logFile="logToStructuredMessage",
        logLevel="warning",
        packages=[str(taxonomy_package)],
        plugins="ixbrl-viewer",
        pluginOptions={
            "highlight_facts_on_startup": True,
            "saveViewerDest": str(publish_directory),
            "useStubViewer": True,
            "viewer_feature_home_link_url": base_url,
        },
    )
    with Session() as session:
        result = session.run(options)
        generation_log = json.loads(session.get_logs("json"))["log"]

    if not result or generation_log:
        raise RuntimeError(
            "Viewer generation failed"
            + (f":\n{json.dumps(generation_log, indent=1)}" if generation_log else "")
        )
    return viewer_path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="/")
    args = parser.parse_args()

    viewer_path = generate_viewer(args.base_url)
    validate_viewer(viewer_path)
    print(f"Viewer generated successfully: {viewer_path}")


if __name__ == "__main__":
    main()
