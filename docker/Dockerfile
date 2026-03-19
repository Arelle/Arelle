FROM python:3.14.3

WORKDIR /usr/src/app

RUN apt-get update
RUN apt-get install unixodbc-dev -y

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY arelleCmdLine.py .
COPY arelle ./arelle

CMD ["python", "arelleCmdLine.py", "--webserver=0.0.0.0:8080"]
EXPOSE 8080
