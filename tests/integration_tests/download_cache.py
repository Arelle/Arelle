from __future__ import annotations
import argparse
import os
import urllib.request
import zipfile


PUBLIC_CACHE_PATTERN = 'https://arelle-public.s3.amazonaws.com/ci/caches/{}'
TEMP_ZIP_NAME = '_tempcache.zip'


def download_and_apply_cache(name: str, cache_directory: str | None = None) -> None:
    """
    :param name: Filename (including extension) of cache package to download
    :param cache_directory: Directory to unpack cache package into
    """
    if cache_directory is None:
        cache_directory = get_cache_directory()
    # Download ZIP from public S3 bucket.
    urllib.request.urlretrieve(PUBLIC_CACHE_PATTERN.format(name), TEMP_ZIP_NAME)
    # Unzip into cache directory
    with zipfile.ZipFile(TEMP_ZIP_NAME, 'r') as zip_ref:
        zip_ref.extractall(cache_directory)
    os.remove(TEMP_ZIP_NAME)


def download_program() -> None:
    parser = argparse.ArgumentParser(
        prog='Download Cache',
        description='Downloads a cache package from the '
                    'public arelle S3 bucket and applies '
                    'it to the local environment cache.')
    parser.add_argument('--name', '-n', action='append', required=True,
                        help='Filename (including extension) of'
                             'cache package to download.')
    parser.add_argument('--print', action='store_true',
                        help='Print cache directory tree structure.')

    args = parser.parse_args()
    cache_directory = get_cache_directory()
    for name in args.name:
        download_and_apply_cache(name, cache_directory)
    if args.print:
        for path in [
            os.path.join(dirpath, f)
            for (dirpath, dirnames, filenames) in os.walk(cache_directory)
            for f in filenames
        ]:
            print(path)


def get_cache_directory() -> str:
    r"""
    Determines the default cache directory
    ubuntu: "$XDG_CONFIG_HOME/arelle/cache"
    macos: ~/Library/Caches/Arelle
    windows: "$env:LOCALAPPDATA\Arelle\cache"
    :return: Cache directory path
    """
    xdg_config_home = os.getenv('XDG_CONFIG_HOME')
    if xdg_config_home:
        return os.path.join(xdg_config_home, 'arelle', 'cache')
    local_app_data = os.getenv('LOCALAPPDATA')
    if local_app_data:
        return os.path.join(local_app_data, 'Arelle', 'cache')
    return os.path.join(os.path.expanduser('~'), 'Library', 'Caches', 'Arelle')


if __name__ == '__main__':
    download_program()
