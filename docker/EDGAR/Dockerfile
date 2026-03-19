FROM python:3.14.3

WORKDIR /usr/src/app

RUN apt update -y

ADD requirements.txt ./
ADD requirements-plugins.txt ./
RUN pip install --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt -r requirements-plugins.txt
## Optionally install gunicorn to run via wsgi server
# RUN pip install --no-cache-dir gunicorn

ADD arelleCmdLine.py /usr/src/app
ADD arelle /usr/src/app/arelle

## Clone EDGAR plugin
## Remove .git directory
## Move EDGAR plugin to Arelle plugin directory
RUN git clone --depth 1 https://github.com/Arelle/EDGAR.git \
    && rm -rf EDGAR/.git \
    && mv EDGAR arelle/plugin/

## Clone xule plugin
## Move xule validation contents (DQC.py & eforms.py) to Arelle validation directory
## Remove empty xule validation directory
## Move xule plugin directory contents to arelle plugin directory
## Remove remants of temporary xule directory
RUN git clone --depth 1 https://github.com/xbrlus/xule.git \
    && mv xule/plugin/validate/* arelle/plugin/validate/ \
    && rm -rf xule/plugin/validate \
    && mv xule/plugin/* arelle/plugin/ \
    && rm -rf xule

## Start webserver
CMD ["python", "arelleCmdLine.py", "--webserver=0.0.0.0:8080"]

## Optionally run with gunicorn with 2 workers, recycling workers after each request
## WARNING: Uncomment only one CMD at a time.
# CMD ["gunicorn", "arelle.CntlrCmdLine:wsgiApplication()", "--workers", "2", "--timeout", "180", "--max-requests", "1", "--bind", "0.0.0.0:8080"]

EXPOSE 8080

