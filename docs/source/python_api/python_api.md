# Python API

The `arelle.api` module is the supported method for integrating Arelle into other Python applications.

:::{warning}
Arelle uses shared global state (PackageManager, PluginManager) which is NOT thread-safe.
Only ONE Session can run at a time across the entire process.

Safe usage:

- Use one Session at a time per process
- Use a process pool instead of thread pool for parallelism

Unsafe usage:

- Running multiple Sessions concurrently in any threads
- Threading.Thread with Session.run()
:::

## Session

The Arelle Python API provides `Session` to run Arelle and access output.
You can import it with:
:::{literalinclude} ../../../tests/integration_tests/scripts/tests/python_api_ixbrl-viewer.py
:start-after: "include import start"
:end-before: "include import end"
:::

From there you can configure the session, run Arelle, and retrieve the generated models and logs (see examples below).

## Logging

Arelle's logging system is accessible through the `Session` object. 
The following parameters can be provided when calling the `run()` method to control logging behavior:
- `logHandler`: Provide a custom logging handler to capture logs in a specific way (e.g., writing to a file, sending to an external logging service, etc.)
  - This parameter is higher priority than the `logFileName` keyword behavior, described below.
- `logFileName`: Specify a file path to write log messages to a file. Certain keywords trigger special behavior (note that `logHandler` takes precedence over these keywords):
  - `logToBuffer`: log messages will be stored in an internal buffer that can be accessed via the `get_logs()` method (see [`LogToBufferHandler`][log-to-buffer-handler]).
  - `logToPrint`: log messages will be printed to standard output (see [`LogToPrintHandler`][log-to-print-handler]).
  - `logToStdErr`: log messages will be printed to standard error (see [`LogToPrintHandler`][log-to-print-handler]).
  - `logToStructuredMessage`: log messages will be stored in an internal buffer as structured data (including log level, message, timestamp, etc.) that can be accessed via the `get_logs()` method (see [`StructuredMessageLogHandler`][structured-message-log-handler]).
- `logFilters`: A list of log filters to apply to the logs.

If `logHandler` and `logFileName` are omitted from the `run()` method call, Arelle will fall back to `RuntimeOptions.logFile` (same behavior as `logFileName`), before finally defaulting to `logToPrint`.

[log-to-buffer-handler]: project:/apidocs/arelle/arelle.logging.handlers.LogToBufferHandler.md
[log-to-print-handler]: project:/apidocs/arelle/arelle.logging.handlers.LogToPrintHandler.md
[structured-message-log-handler]: project:/apidocs/arelle/arelle.logging.handlers.StructuredMessageLogHandler.md

### Examples

#### Creating an iXBRL Viewer

:::{literalinclude} ../../../tests/integration_tests/scripts/tests/python_api_ixbrl-viewer.py
:start-after: "include start"
:end-before: "include end"
:::

#### Querying a Model

:::{literalinclude} ../../../tests/integration_tests/scripts/tests/python_api_query_model.py
:start-after: "include start"
:end-before: "include end"
:::

#### Using a Validation Plugin

:::{literalinclude} ../../../tests/integration_tests/scripts/tests/python_api_validate_esef.py
:start-after: "include start"
:end-before: "include end"
:::
