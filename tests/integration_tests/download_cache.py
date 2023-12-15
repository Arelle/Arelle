import argparse
import os
import subprocess
import urllib.request
import zipfile

PRIVATE_BUCKET = 'arelle'
PRIVATE_CACHE_PATTERN = 'caches/{}'
PUBLIC_BUCKET = 'arelle-public'
PUBLIC_CACHE_PATTERN = 'https://{}.s3.amazonaws.com/ci/caches/{}'
TEMP_ZIP_NAME = '_tempcache.zip'


def get_cache_directory() -> str:
    """
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


def download_and_apply_cache(name: str, private: bool, cache_directory: str) -> None:
    """
    :param name: Filename (including extension) of cache package to download
    :param private: True if the package is located in the private S3 bucket
    :param cache_directory: Directory to unpack cache package into
    """
    # Download ZIP from either public or private bucket.
    # Private bucket requires AWS CLI tool to be installed with credentials already configured
    if private:
        print(f'Downloading private package: {name}')
        if not os.getenv('AWS_ACCESS_KEY_ID'):
            raise ValueError('AWS_ACCESS_KEY_ID environment variable not set.')
        if not os.getenv('AWS_SECRET_ACCESS_KEY'):
            raise ValueError('AWS_SECRET_ACCESS_KEY environment variable not set.')
        if not os.getenv('AWS_DEFAULT_REGION'):
            raise ValueError('AWS_DEFAULT_REGION environment variable not set.')
        result = subprocess.run([
            'aws', 's3api', 'get-object',
            '--bucket', PRIVATE_BUCKET,
            '--key', PRIVATE_CACHE_PATTERN.format(name),
            TEMP_ZIP_NAME])
        if result.returncode != 0:
            raise Exception(f'Download failed with return code {result.returncode}')
    else:
        print(f'Downloading public package: {name}')
        urllib.request.urlretrieve(PUBLIC_CACHE_PATTERN.format(PUBLIC_BUCKET, name), TEMP_ZIP_NAME)
    # Unzip into cache directory
    with zipfile.ZipFile(TEMP_ZIP_NAME, 'r') as zip_ref:
        zip_ref.extractall(cache_directory)
    os.remove(TEMP_ZIP_NAME)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        prog='Download Cache',
        description='Downloads a cache package from either '
                    'the public or private Arelle S3 buckets '
                    'and applies it to the local cache.')
    parser.add_argument('--name', '-n', action='append', required=True,
                        help='Filename (including extension) of'
                             'cache package to download.')
    parser.add_argument('--private', action='store_true',
                        help='AWS CLI must be installed and '
                             'credentials must be configured '
                             'in environment prior to running.')
    parser.add_argument('--print', action='store_true',
                        help='Print cache directory tree structure.')

    args = parser.parse_args()
    cache_directory = get_cache_directory()
    for name in args.name:
        download_and_apply_cache(name, args.private, cache_directory)
    if args.print:
        for path in [
            os.path.join(dirpath, f)
            for (dirpath, dirnames, filenames) in os.walk(cache_directory)
            for f in filenames
        ]:
            print(path)

