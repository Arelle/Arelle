FROM python:3.14.3

WORKDIR /usr/src/app

RUN apt-get update

COPY requirements.txt .
COPY requirements-plugins.txt .
RUN pip install --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt -r requirements-plugins.txt
## Optionally install gunicorn to run via wsgi server
# RUN pip install --no-cache-dir gunicorn

COPY arelleCmdLine.py .
COPY arelle ./arelle

## Check if EDGAR plugin already exists
## If not:
##      Clone EDGAR plugin using EDGAR_REF to pin a specific tag/release
##      Remove .git directory
##      Move EDGAR plugin to Arelle plugin directory
ARG EDGAR_REF=""
RUN if [ ! -d arelle/plugin/EDGAR ]; then \
        git clone --depth 1 ${EDGAR_REF:+--branch "$EDGAR_REF"} https://github.com/Arelle/EDGAR.git \
        && rm -rf EDGAR/.git \
        && mv EDGAR arelle/plugin/; \
    fi

## Check if XULE plugin already exists
## If not:
##      Clone xule plugin using XULE_REF to pin a specific tag/release
##      Move xule validation contents (DQC.py & eforms.py) to Arelle validation directory
##      Remove empty xule validation directory
##      Move xule plugin directory contents to arelle plugin directory
##      Remove remnants of temporary xule directory
ARG XULE_REF=""
RUN if [ ! -d arelle/plugin/xule ]; then \
        git clone --depth 1 ${XULE_REF:+--branch "$XULE_REF"} https://github.com/xbrlus/xule.git \
        && mv xule/plugin/validate/* arelle/plugin/validate/ \
        && rm -rf xule/plugin/validate \
        && mv xule/plugin/* arelle/plugin/ \
        && rm -rf xule; \
    fi

## Start webserver
CMD ["python", "arelleCmdLine.py", "--webserver=0.0.0.0:8080"]

## Optionally run with gunicorn with 2 workers, recycling workers after each request
## WARNING: Uncomment only one CMD at a time.
# CMD ["gunicorn", "arelle.CntlrCmdLine:wsgiApplication()", "--workers", "2", "--timeout", "180", "--max-requests", "1", "--bind", "0.0.0.0:8080"]

EXPOSE 8080

