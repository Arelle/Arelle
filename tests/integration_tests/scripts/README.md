# Running integration test scripts

> Note: Conformance suites are run using a different entry point.
> See `tests/integration_tests/validation/README.md` for more information.

### Run scripts directly:
Run the following to view script runner options:
```
python -m tests.integration_tests.scripts.run_scripts --help

  -h, --help            show this help message and exit
  --all                 Select all configured integration tests.
  --arelle ARELLE       CLI command to run Arelle
  --download-cache      Whether or not to download and apply cache.
  --list                List names of all integration tests.
  --name NAME           Only run scripts whose name (stem) matches given name(s).
  --offline             Whether or not Arelle should run in offline mode.
  --working-directory WORKING_DIRECTORY
                        Directory to place temporary files and log output.
```
One of the following options *must* be provided to select which suites to use:
* `--all`: select all scripts
* `--name`: provide with script name, one or more times (use `--list` to see names)

Example that runs the Japan IXDS script:
```
python -m tests.integration_tests.scripts.run_scripts --name japan_ixds --arelle="python arelleCmdLine.py" 
```

### Run scripts via pytest:
The same options for `run_scripts` can be passed through `pytest`.

This example runs all scripts through pytest:
```
pytest ./tests/integration_tests/scripts/test_scripts.py --all --arelle="python arelleCmdLine.py"
```