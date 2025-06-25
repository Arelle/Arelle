# Building Documentation

:::{index} Building Documentation
:::

Arelle's documentation is built using Sphinx and published to [Read the Docs][read-the-docs-project].

[read-the-docs-project]: https://arelle.readthedocs.io/

## Build Locally

1. Install documentation dependencies.

   ```shell
   pip install -r requirements-docs.txt
   ```

2. Navigate to the `docs` directory.

   ```shell
   cd docs
   ```

3. Build HTML documentation
   * Linux or macOS

     ```shell
     # build
     make html
     # or auto rebuild on file changes (useful when working on documentation)
     make livehtml
     ```

   * Windows

     ```powershell
     # build
     .\make.bat html
     # or auto rebuild on file changes (useful when working on documentation)
     .\make.bat livehtml
     ```

4. Open documentation:
    * file `docs/_build/html/index.html` if using `make html`
    * <http://127.0.0.1:8000/> if using `make livehtml`
