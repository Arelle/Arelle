import logging
import os
import urllib.request
import zipfile
from tests.integration_tests.validation.conformance_suite_config import ConformanceSuiteConfig

logger = logging.getLogger("arelle")

DOWNLOADED_PATHS = set()


def _download_file(source: str, destination: str, overwrite: bool) -> None:
    if destination in DOWNLOADED_PATHS:
        return
    if not overwrite and os.path.exists(destination):
        return
    logger.info(f"Downloading public conformance suite file.\n\tFrom: {source}\n\tTo: {destination}")
    urllib.request.urlretrieve(source, destination)
    DOWNLOADED_PATHS.add(destination)


def download_conformance_suite(config: ConformanceSuiteConfig, overwrite: bool = False) -> None:
    destination_path = config.prefixed_local_filepath
    zip_directory = os.path.dirname(destination_path)
    os.makedirs(zip_directory, exist_ok=True)
    if config.public_download_url:
        _download_file(config.public_download_url, destination_path, overwrite)
    elif not os.path.exists(destination_path):
        membership_messages = [f"[{config.name}] No public download available."]
        if config.membership_url:
            membership_messages.append(f"\tMembership required (Join here: {config.membership_url}).")
        membership_messages.append(f"\tMore info: {config.info_url}")
        logger.warning("\n".join(membership_messages))
    if config.additional_downloads:
        for source, destination in config.additional_downloads.items():
            _download_file(source, destination, overwrite)


def extract_conformance_suite(config: ConformanceSuiteConfig) -> None:
    destination_path = config.prefixed_local_filepath
    extract_path = config.prefixed_extract_filepath
    if extract_path:
        assert os.path.exists(destination_path), 'Can not extract conformance suite file: ZIP file does not exist.'
        if not os.path.exists(extract_path):
            logger.info(f"[{config.name}] Extracting conformance suite file.\n\tFrom: {destination_path}\n\tTo: {extract_path}")
            with zipfile.ZipFile(destination_path, 'r') as zip_ref:
                zip_ref.extractall(extract_path)
