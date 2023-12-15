# Running integration test scripts

> Note: Conformance suites are run using a different entry point.
> See `tests/integration_tests/validation/README.md` for more information.

### Run scripts directly:
Run the following to view script runner options:
```
python -m tests.integration_tests.scripts.run_conformance_suites --help

  -h, --help            show this help message and exit
  --all                 Select all scripts
  --list                List names of all scripts
  --name NAME           Select only scripts with given names, comma
                        delimited
```
One of the following options *must* be provided to select which suites to use:
* `--all`: select all scripts
* `--name`: provide a comma-delimited list of script names (use `--list` to see names)

Example that runs the Japan IXDS script:
```
python -m tests.integration_tests.scripts.run_scripts --name japan_ixds
```

### Run scripts via pytest:
The same options for `run_scripts` can be passed through `pytest`.

This example runs all scripts through pytest:
```
pytest ./tests/integration_tests/scripts/test_scripts.py --all
```