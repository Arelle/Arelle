## --------------------- Build Stage ---------------------
ARG PYTHON_VERSION="3.14.7"
FROM python:${PYTHON_VERSION} AS builder

WORKDIR /usr/src/app

## jq reads the plugin versions from plugin-versions.json
RUN apt-get update \
  && apt-get install -y --no-install-recommends jq \
  && rm -rf /var/lib/apt/lists/*

## Requirements are installed here to ensure they will be cached.
ARG EXTRA_PIP=""
## Plugin requirements includes PythonMonkey which requires npm to install node modules.
RUN case "$EXTRA_PIP" in \
      *requirements-plugins.txt*) \
        apt-get update \
        && apt-get install -y --no-install-recommends npm \
        && rm -rf /var/lib/apt/lists/* ;; \
    esac
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
COPY requirements.txt .
COPY requirements-plugins.txt .
RUN pip install --upgrade pip \
  && pip install --no-cache-dir -r requirements.txt ${EXTRA_PIP}

## Copy application code
COPY arelleCmdLine.py .
COPY arelle ./arelle

## Generate version file if version is provided
ARG ARELLE_VERSION=""
COPY requirements-versioning.txt .
COPY pyproject.toml .
RUN if [ -n "$ARELLE_VERSION" ]; then \
      pip install --no-cache-dir -r requirements-versioning.txt \
      && SETUPTOOLS_SCM_PRETEND_VERSION="$ARELLE_VERSION" \
         python -m setuptools_scm --force-write-version-files; \
    fi

## Install plugin requirements when building with EDGAR or XULE plugins
ARG INCLUDE_EDGAR=""
ARG EDGAR_REF=""
ARG XULE_REF=""

## Plugin release tags used when EDGAR_REF / XULE_REF are blank
COPY plugin-versions.json .

## Clone EDGAR plugin if enabled and plugin doesn't already exist
## Uses EDGAR_REF (branch, tag or SHA) if provided, otherwise the tag in plugin-versions.json
RUN if ([ -n "$INCLUDE_EDGAR" ] || [ -n "$EDGAR_REF" ]) && [ ! -d arelle/plugin/EDGAR ]; then \
        git init -q EDGAR \
        && git -C EDGAR fetch -q --depth 1 https://github.com/Arelle/EDGAR.git "${EDGAR_REF:-$(jq -r .EDGAR_VERSION plugin-versions.json)}" \
        && git -C EDGAR checkout -q FETCH_HEAD \
        && rm -rf EDGAR/.git \
        && mv EDGAR arelle/plugin/; \
    fi

## Clone XULE plugin if enabled and plugin doesn't already exist
## Uses XULE_REF (branch, tag or SHA) if provided, otherwise the tag in plugin-versions.json
## Moves XULE validation contents (DQC.py & eforms.py) to Arelle validation directory
## Moves XULE plugin directory contents to arelle plugin directory
RUN if ([ -n "$INCLUDE_EDGAR" ] || [ -n "$XULE_REF" ]) && [ ! -d arelle/plugin/xule ]; then \
        git init -q xule \
        && git -C xule fetch -q --depth 1 https://github.com/xbrlus/xule.git "${XULE_REF:-$(jq -r .XULE_VERSION plugin-versions.json)}" \
        && git -C xule checkout -q FETCH_HEAD \
        && rm -rf xule/.git \
        && mv xule/plugin/validate/* arelle/plugin/validate/ \
        && rm -rf xule/plugin/validate \
        && mv xule/plugin/* arelle/plugin/ \
        && rm -rf xule; \
    fi

## ------------------- Production Stage -------------------
FROM python:${PYTHON_VERSION}-slim AS production

## Prevent python from buffering stdout & stderr
ENV PYTHONUNBUFFERED=1

RUN apt-get update \
  && apt-get install --upgrade -y --no-install-recommends \
  curl \
  && apt-get purge -y --auto-remove \
  && rm -rf /var/lib/apt/lists/*

## Copy python dependencies and application code
COPY --from=builder /usr/src/app/arelle /usr/src/app/arelle
COPY --from=builder /usr/src/app/arelleCmdLine.py /usr/src/app/arelleCmdLine.py
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

## Copy docker scripts
COPY --chmod=755 docker/scripts/entrypoint.sh /opt/entrypoint.sh
COPY --chmod=755 docker/scripts/start.sh /opt/start.sh
COPY --chmod=755 docker/scripts/healthcheck.sh /opt/healthcheck.sh

WORKDIR /usr/src/app

ENTRYPOINT ["/opt/entrypoint.sh"]
