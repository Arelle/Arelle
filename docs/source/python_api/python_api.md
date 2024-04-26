# Python API (Beta)
:::{warning}
The Arelle Python Beta API (located in `arelle.api` module) is an in-progress API module.
A roadmap for this API is in development.

Users of this API should expect changes in future releases.
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
