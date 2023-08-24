FROM python:3.11.4

RUN mkdir /var/s3fs
WORKDIR /usr/src/app

RUN apt update -y \
    apt install -y ruby ruby-dev;

RUN apt-get install unixodbc-dev -y

RUN apt-get install -y s3fs

ADD requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
ADD arelleCmdLine.py /usr/src/app
ADD arelle /usr/src/app/arelle

RUN gem install bundler
RUN gem install shoryuken
RUN gem install aws-sdk-sqs

CMD ["python", "arelleCmdLine.py", "--webserver=0.0.0.0:8080"]
EXPOSE 8080
