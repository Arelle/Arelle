## --------------------- Build Stage ---------------------
FROM python:3.14.3 AS builder

WORKDIR /usr/src/app

## Requirements are installed here to ensure they will be cached.
ARG EXTRA_PIP=""
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
COPY requirements.txt .
COPY requirements-plugins.txt .
RUN pip install --upgrade pip \
  && pip install --no-cache-dir \
  -r requirements.txt \
  -r requirements-plugins.txt \
  ${EXTRA_PIP}

## Copy application code
COPY arelleCmdLine.py .
COPY arelle ./arelle

## Install plugin requirements when building with EDGAR or XULE plugins
ARG INCLUDE_EDGAR=""
ARG EDGAR_REF=""
ARG XULE_REF=""

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
COPY --chmod=755 docker/scripts/entrypoint.sh /entrypoint.sh
COPY --chmod=755 docker/scripts/start.sh /start.sh
COPY --chmod=755 docker/scripts/healthcheck.sh /healthcheck.sh

WORKDIR /usr/src/app

## Add user with home directory (Arelle caches to the user's home directory by default)
## Assign app ownership and switch to new user
RUN useradd -m arelle \
  && chown -R arelle:arelle /usr/src/app
USER arelle

ENTRYPOINT ["/entrypoint.sh"]
