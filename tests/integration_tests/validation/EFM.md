# Updating EFM Conformance Suite

### Upload Conformance Suite
1. Download latest EFM conformance suite from the [SEC website](https://www.sec.gov/structureddata/osdinteractivedatatestsuite). Retain the filename (e.g. efm-74-250616.zip).
2. Upload the conformance suite package to the public S3 bucket at `/ci/conformance_suites`.

### Run Conformance Suite
In `efm_current.py`, update `CONFORMANCE_SUITE_ZIP_NAME` to the filename of the conformance suite package.
Run the following command to run the full conformance suite while generating a cache ZIP for each shard as well as a timing JSON file.
```shell
python tests/integration_tests/validation/run_conformance_suites.py --test --log-to-file --download-missing --name efm_current --shard=0-39 --build-cache 
```

### Build and Upload Cache
To ensure a complete cache package is generated, we need to merge the cache packages generated for each shard into a single package.
There are a number of ways to do this, below is one possible way:
```shell
mkdir merge
for x in *.zip ; do unzip -d merge -o -u $x ; done
cd merge
zip -r efm_current.zip .
```
Upload the final cache package (`efm_current.zip`) to the public S3 bucket at `/ci/caches/conformance_suites`.
This will add a new "version" of the existing `efm_current.zip` package in the bucket, which can be viewed by navigating into the file details in S3.
In `efm_current.py`, update `cache_version_id` with the latest `efm_current.zip` asset version ID.

#### Update Timing File
The previous run also generated `conf-efm_current-timing.json`. Rename this to `efm_current.json` and relocate to `tests/resources/conformance_suites_timing/efm_current.json`

#### Submit Pull Request
PR your changes to `efm_current.py` and `efm_current.json`.
