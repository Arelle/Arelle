# Arelle Website

This directory is the Hugo project for arelle.org.
The production artifact is written to `public/`.

## Development

Install the website dependencies before building.

```sh
npm ci
hugo server
```

## Production

Build the minified production artifact with:

```sh
hugo --minify
```

## Generating the Viewer Demo

The website hosts a live iXBRL viewer demo.
Set up the repository environment and install the plugin dependencies.

```sh
python -m pip install -r ../../requirements.txt -r ../../requirements-plugins.txt
git clone --branch master --depth 1 https://github.com/Arelle/EDGAR.git ../../arelle/plugin/EDGAR
```

Skip the clone when `../../arelle/plugin/EDGAR` already exists.
From this directory, reproduce the local generation.

```sh
hugo --minify --baseURL /
python scripts/generate_viewer_demo.py
python -m http.server --directory public 8000
```

Open `http://localhost:8000/demo/ixbrl-viewer/ixbrlviewer.html`.

## Testing Links

After building the site, run [htmltest](https://github.com/wjdp/htmltest) from this
directory:

```sh
hugo --minify --baseURL /
python scripts/generate_viewer_demo.py
htmltest
```
