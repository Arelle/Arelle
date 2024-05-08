from __future__ import annotations

import boto3
import os
import urllib.request
import zipfile
from pathlib import Path

from tests.integration_tests.download_cache import apply_cache
from tests.integration_tests.integration_test_util import get_s3_uri
from tests.integration_tests.validation.conformance_suite_config import ConformanceSuiteAssetConfig, AssetType, AssetSource


def _download_asset(asset: ConformanceSuiteAssetConfig, download_private: bool) -> bool:
    """
    Given an asset, determines the source to attempt download from,
    then performs the download.
    If the asset is configured with a private S3 source, will only attempt
    download if `download_private` is `True`, otherwise it will fall back
    to a public download URL, if configured.
    If not configured, no download will be performed and `False` returned.
    :return: True if download was successful.
    """
    if asset.source == AssetSource.LOCAL:
        print(f'Using local asset: {asset.full_local_path}')
        return True
    if asset.source == AssetSource.S3_PUBLIC:
        print(f'Using public S3 asset: {asset.full_local_path}')
        _download_public_s3_asset(asset)
        return True
    if asset.source == AssetSource.S3_PRIVATE and download_private:
        print(f'Using private S3 asset: {asset.full_local_path}')
        _download_private_s3_asset(asset)
        return True
    # Asset wasn't otherwise downloaded, fallback to public download URL, if configured.
    if asset.public_download_url:
        print(f'Using public asset: {asset.full_local_path}')
        _download_public_uri(asset.public_download_url, asset.full_local_path)
        return True
    return False


def _download_private_s3_asset(asset: ConformanceSuiteAssetConfig) -> None:
    """
    Downloads given asset from private S3 bucket.
    Will raise an error if the required AWS
    environment variables are not set.
    """
    key = asset.s3_key
    assert key is not None
    if asset.type == AssetType.CONFORMANCE_SUITE:
        key = f'conformance_suites/{key}'
    asset.full_local_path.parent.mkdir(parents=True, exist_ok=True)
    assert 'AWS_ACCESS_KEY_ID' in os.environ.keys(), 'Must have AWS_ACCESS_KEY_ID environment variable set.'
    assert 'AWS_SECRET_ACCESS_KEY' in os.environ.keys(), 'Must have AWS_SECRET_ACCESS_KEY environment variable set.'
    s3 = boto3.client('s3')
    if asset.s3_version_id:
        s3.download_file('arelle', Key=key, Filename=str(asset.full_local_path), ExtraArgs={'VersionId': asset.s3_version_id})
    else:
        s3.download_file('arelle', Key=key, Filename=str(asset.full_local_path))


def _download_public_s3_asset(asset: ConformanceSuiteAssetConfig) -> None:
    """
    Downloads given asset from public S3 bucket.
    """
    key = asset.s3_key
    assert key is not None
    if asset.type == AssetType.CONFORMANCE_SUITE:
        key = f'ci/conformance_suites/{key}'
    elif asset.type == AssetType.CACHE_PACKAGE:
        key = f'ci/caches/conformance_suites/{key}'
    elif asset.type == AssetType.TAXONOMY_PACKAGE:
        key = f'ci/taxonomy_packages/{key}'
    uri = get_s3_uri(key, version_id=asset.s3_version_id)
    _download_public_uri(uri, asset.full_local_path)


def _download_public_uri(uri: str, download_path: Path) -> None:
    """
    Downloads asset from given URI to given download path.
    """
    try:
        download_path.parent.mkdir(parents=True, exist_ok=True)
        urllib.request.urlretrieve(uri, download_path)
    except Exception as exc:
        raise Exception(f'Failed to download public URI "{uri}" to "{download_path}".') from exc


def _extract_asset(asset: ConformanceSuiteAssetConfig) -> None:
    """
    Performs the asset's configured extract sequence.
    An extract sequence is a list of from/to path pairs.
    For each element in the sequence, the zip at the `from` path
    is extracted to the `to` directory.
    """
    for extract_from, extract_to in asset.extract_sequence:
        extract_from = Path('tests/resources/conformance_suites') / extract_from
        extract_to = Path('tests/resources/conformance_suites') / extract_to
        with zipfile.ZipFile(extract_from, 'r') as zip_ref:
            os.makedirs(extract_to, exist_ok=True)
            zip_ref.extractall(extract_to)


def download_assets(
    assets: set[ConformanceSuiteAssetConfig],
    overwrite: bool,
    download_and_apply_cache: bool,
    download_private: bool,
) -> None:
    """
    Performs download for each of the given assets. Before each download, the asset's set of
    reserved paths is compared against the reserved paths of previous assets. If any conflicts
    are found (indicating two different assets may be overwriting each other), an `AssertionError`
    is raised.
    :param assets:
    :param overwrite: If assets that appear to be already downloaded should be skipped.
    :param download_and_apply_cache: If cache-type assets should be downloaded and applied or skipped.
    :param download_private: If download of private-source assets should be attempted.
    """
    reserved_paths: set[Path] = set()
    reserved_directories: set[Path] = set()
    for asset in assets:
        conflicting_paths = asset.get_conflicting_paths(reserved_paths)
        assert not conflicting_paths, \
            f'Assets have conflicting paths: {conflicting_paths}'
        conflicting_directories = asset.get_conflicting_directories(reserved_directories)
        assert not conflicting_directories, \
            f'Asset has reserved paths that conflict ' \
            f'with reserved directories: {conflicting_directories}'
        reserved_paths.update(asset.full_reserved_paths)
        reserved_directories.update(asset.full_reserved_directories)
        if os.path.exists(asset.full_local_path) and not overwrite:
            print(f'Using existing local asset: {asset.full_local_path}')
            continue  # File already exists at location, overwrite not specified
        if asset.type == AssetType.CACHE_PACKAGE and not download_and_apply_cache:
            continue  # Cache download not requested
        downloaded = _download_asset(asset, download_private)
        if downloaded:
            _extract_asset(asset)
        verify_asset(asset)
        if asset.type == AssetType.CACHE_PACKAGE:
            apply_cache(str(asset.full_local_path))
            print(f'Applied cache: {asset.full_local_path}')


def verify_asset(asset: ConformanceSuiteAssetConfig) -> None:
    """
    Verifies that an asset exists at it's expected location.
    For entry point assets, verifies that the entry point exists where it is expected.
    Raises an `AssertionError` on failure, otherwise logs a message.
    """
    assert asset.full_local_path.exists(), \
        f'Missing asset: {asset}'
    if asset.full_entry_point_root:
        if zipfile.is_zipfile(asset.full_entry_point_root):
            with zipfile.ZipFile(asset.full_entry_point_root, 'r') as zip_ref:
                assert asset.entry_point and asset.entry_point.as_posix() in zip_ref.namelist(), \
                    f'Asset entry point {asset.entry_point} does not exist in archive: {asset.full_entry_point_root}'
        else:
            assert asset.full_entry_point and asset.full_entry_point.exists(), \
                f'Asset entry point does not exist: {asset.full_entry_point}'
    print(f'Verified asset: {asset.full_local_path}')


def verify_assets(assets: set[ConformanceSuiteAssetConfig]) -> None:
    """
    Verifies each of the given assets exists locally.
    Raises an `AssertionError` on failure.
    Skips cache assets as they are deleted once applied.
    """
    for asset in assets:
        if asset.type == AssetType.CACHE_PACKAGE:
            continue  # Cache packages are deleted after being applied
        verify_asset(asset)
