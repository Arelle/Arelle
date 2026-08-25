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
