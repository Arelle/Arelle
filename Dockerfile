FROM python:3.12.2

WORKDIR /usr/src/app

RUN apt update -y
RUN apt-get install unixodbc-dev -y

ADD requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
ADD arelleCmdLine.py /usr/src/app
ADD arelle /usr/src/app/arelle

CMD ["python", "arelleCmdLine.py", "--webserver=0.0.0.0:8080"]
EXPOSE 8080
