## --------------------- Build Stage --------------------- 
FROM python:3.14.3 AS builder

WORKDIR /usr/src/app
RUN apt-get update

## Set environment variables to optimize Python
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

## Requirements are installed here to ensure they will be cached.
COPY requirements.txt .

RUN pip install --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt
## Optionally install gunicorn to run via wsgi server
# RUN pip install --no-cache-dir --upgrade gunicorn

## --------------------- Production Stage --------------------- 
FROM python:3.14.3 AS production

WORKDIR /usr/src/app
RUN apt-get update

## Set environment variables to optimize Python
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

## Copy python dependancies
COPY --from=builder /usr/local/lib/python3.14/site-packages/ /usr/local/lib/python3.14/site-packages/
COPY --from=builder /usr/local/bin/ /usr/local/bin/

## Copy application code
COPY arelleCmdLine.py .
COPY arelle ./arelle

## Copy and create docker scripts
COPY --chmod=755 docker/entrypoint.sh /entrypoint.sh
COPY --chmod=755 docker/start.sh /start.sh
COPY --chmod=755 docker/healthcheck.sh /healthcheck.sh

## Add user with home directory (Arelle caches to the user's home directory by default)
## Assign app ownership and switch to new user
RUN useradd -m arelle
RUN chown -R arelle:arelle /usr/src/app
USER arelle

ENTRYPOINT ["/entrypoint.sh"]
