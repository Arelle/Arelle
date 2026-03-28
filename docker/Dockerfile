## --------------------- Build Stage ---------------------
FROM python:3.14.3 AS builder

WORKDIR /usr/src/app

## Requirements are installed here to ensure they will be cached.
ARG INCLUDE_IXBRL_VIEWER=""
RUN if [ -n "$INCLUDE_IXBRL_VIEWER" ]; then \
        apt-get update \
        && apt-get install --upgrade -y --no-install-recommends \
        nodejs \
        npm; \
    fi

ARG EXTRA_PIP=""
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
COPY requirements.txt .
COPY requirements-plugins.txt .
RUN pip install --upgrade pip \
  && pip install --no-cache-dir -r requirements.txt ${EXTRA_PIP}

## Copy application code
COPY arelleCmdLine.py .
COPY arelle ./arelle

## Install plugin requirements when building with EDGAR or XULE plugins
ARG INCLUDE_EDGAR=""
ARG EDGAR_REF=""
ARG XULE_REF=""
ARG IXBRL_VIEWER_REF=""

## Clone EDGAR plugin if enabled and plugin doesn't already exist
## Uses EDGAR_REF to pin a specific tag/release if provided
RUN if ([ -n "$INCLUDE_EDGAR" ] || [ -n "$EDGAR_REF" ]) && [ ! -d arelle/plugin/EDGAR ]; then \
        git clone --depth 1 ${EDGAR_REF:+--branch "$EDGAR_REF"} https://github.com/Arelle/EDGAR.git \
        && rm -rf EDGAR/.git \
        && mv EDGAR arelle/plugin/; \
    fi

## Clone XULE plugin if enabled and plugin doesn't already exist
## Uses XULE_REF to pin a specific tag/release if provided
## Moves xule validation contents (DQC.py & eforms.py) to Arelle validation directory
## Moves xule plugin directory contents to arelle plugin directory
RUN if ([ -n "$INCLUDE_EDGAR" ] || [ -n "$XULE_REF" ]) && [ ! -d arelle/plugin/xule ]; then \
        git clone --depth 1 ${XULE_REF:+--branch "$XULE_REF"} https://github.com/xbrlus/xule.git \
        && mv xule/plugin/validate/* arelle/plugin/validate/ \
        && rm -rf xule/plugin/validate \
        && mv xule/plugin/* arelle/plugin/ \
        && rm -rf xule; \
    fi

## Clone ixbrl-viewer plugin if enabled and plugin doesn't already exist
## Uses IXBRL_VIEWER_REF to pin a specific tag/release if provided
RUN if ([ -n "$INCLUDE_IXBRL_VIEWER" ] || [ -n "$IXBRL_VIEWER_REF" ]) && [ ! -d arelle/plugin/iXBRLViewerPlugin ]; then \
        git clone --depth 1 ${IXBRL_VIEWER_REF:+--branch "$IXBRL_VIEWER_REF"} https://github.com/Arelle/ixbrl-viewer.git \
        && cd ixbrl-viewer \
        && npm ci \
        && make prod \
        && npm cache clean --force \
        && cd .. \
        && mv ixbrl-viewer/iXBRLViewerPlugin arelle/plugin/ \
        && rm -rf ixbrl-viewer; \
    fi

## ------------------- Production Stage -------------------
FROM python:3.14.3-slim AS production

## Prevent python from buffering stdout & stderr
ENV PYTHONUNBUFFERED=1

RUN apt-get update \
  && apt-get install --upgrade -y --no-install-recommends \
  curl \
  && apt-get purge -y --auto-remove \
  && rm -rf /var/lib/apt/lists/*

## Copy python dependencies and application code
COPY --from=builder /usr/src/app /usr/src/app
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

## Copy docker scripts
COPY --chmod=755 docker/scripts/entrypoint.sh /opt/entrypoint.sh
COPY --chmod=755 docker/scripts/start.sh /opt/start.sh
COPY --chmod=755 docker/scripts/healthcheck.sh /opt/healthcheck.sh

WORKDIR /usr/src/app

ENTRYPOINT ["/opt/entrypoint.sh"]
