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
