# Building Documentation

```{eval-rst}
.. index:: Documentation
```

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

3. Build HTML documentation.

   ```shell
   make html
   ```

4. Open `docs/_build/html/index.html` in your browser.
