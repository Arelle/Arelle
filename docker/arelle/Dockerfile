## --------------------- Build Stage ---------------------
FROM python:3.14.3 AS builder

WORKDIR /usr/src/app

## Requirements are installed here to ensure they will be cached.
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
COPY requirements.txt .

RUN pip install --upgrade pip \
  && pip install --no-cache-dir -r requirements.txt
## Optionally install gunicorn to run via wsgi server
# RUN pip install --no-cache-dir --upgrade gunicorn

## ------------------- Production Stage -------------------
FROM python:3.14.3-slim AS production

## Prevent python from buffering stdout & stderr
ENV PYTHONUNBUFFERED=1

RUN apt-get update \
  && apt-get install --upgrade -y --no-install-recommends \
  curl \
  && apt-get purge -y --auto-remove \
  && rm -rf /var/lib/apt/lists/*

## Copy python dependencies
COPY --from=builder /usr/local/lib/python3.14/site-packages/ /usr/local/lib/python3.14/site-packages/
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

## Copy docker scripts
COPY --chmod=755 docker/scripts/entrypoint.sh /entrypoint.sh
COPY --chmod=755 docker/scripts/start.sh /start.sh
COPY --chmod=755 docker/scripts/healthcheck.sh /healthcheck.sh

## Copy application code
WORKDIR /usr/src/app
COPY arelleCmdLine.py .
COPY arelle ./arelle

## Add user with home directory (Arelle caches to the user's home directory by default)
## Assign app ownership and switch to new user
RUN useradd -m arelle \
  && chown -R arelle:arelle /usr/src/app
USER arelle

ENTRYPOINT ["/entrypoint.sh"]
