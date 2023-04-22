FROM ubuntu:20.04

RUN apt-get update && apt-get install -y software-properties-common gcc

RUN apt-get update && apt-get install -y python3.6 python3-distutils python3-pip python3-apt

RUN mkdir /var/s3fs
ADD . /opt/arelle
WORKDIR /opt/arelle
RUN apt update;\
    apt install -y python3.6 libxml2-dev libxslt1.dev; \
    pip3 install -r requirements.txt; \
    pip3 install isodate; \
    pip3 install --upgrade lxml; \
    apt install -y ruby ruby-dev;
RUN apt-get install -y s3fs
RUN gem install bundler
RUN gem install shoryuken
RUN gem install aws-sdk-sqs
EXPOSE 8099
