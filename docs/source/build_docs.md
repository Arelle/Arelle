# Building Documentation

```{eval-rst}
.. index:: Documentation
```

Arelle's documentation is built using Sphinx.
To build locally:

1. Install documentation dependencies from `requirements-docs.txt`. For example:
```
pip install -r requirements-docs.txt
```

2. Navigate to `/docs` directory.
```
cd docs
```

3. Build HTML
```
make html
```

4. Open `/docs/_build/html/index.html` in your browser.
