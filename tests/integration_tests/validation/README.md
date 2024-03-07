# Running Conformance Suites

### Run conformance suites as a script:
Run the following to view conformance suite runner options:
```
python -m tests.integration_tests.validation.run_conformance_suites --help

  -h, --help            show this help message and exit
  --all                 Select all configured conformance suites
  --build-cache         Use CacheBuilder plugin to build cache from conformance
                        suite usage
  --download-cache      Download and apply pre-built cache package
  --download-overwrite  Download (and overwrite) selected conformance suite
                        files
  --download-missing    Download missing selected conformance suite files
  --list                List names of all configured conformance suites
  --log-to-file         Writes logs and results to .txt and .csv files
  --name NAME           Select only conformance suites with given names, comma
                        delimited
  --offline             Run without loading anything from the internet (local
                        files and cache only)
  --public              Select all public conformance suites
  --series              Run shards in series
  --shard SHARD         comma separated list of 0-indexed shards to run
  --test                Run selected conformance suite tests
```
One of the following options *must* be provided to select which suites to use:
* `--all`: select all configured conformance suites
* `--public`: select only those conformance suites available for public download
* `--name`: provide a comma-delimited list of conformance suite names (use `--list` to see names)

Example that runs the XBRL 2.1 conformance suite:
```
python -m tests.integration_tests.validation.run_conformance_suites --test --name xbrl_2_1
```

### Run conformance suites via pytest:
The same options for `run_conformance_suites` can be passed through `pytest`.

This example runs all publicly downloadable conformance suites through pytest:
```
pytest ./tests/integration_tests/validation/test_conformance_suites.py --public
```

### Download conformance suite files:
The files needed to run conformance suite tests can be downloaded by running with `--download-missing` or `--download-overwrite` options.
```
python -m tests.integration_tests.validation.run_conformance_suites --download-overwrite --test --name xbrl_2_1
```
Download options can be provided alongside `--test` to download before running tests, or alone to download without running tests.

This example attempts to download all configured conformance suites and will output messages for those without public downloads available:
```
python -m tests.integration_tests.validation.run_conformance_suites --download-missing --all
```