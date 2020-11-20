FROM ubuntu:18.04
ADD . /opt/arelle
WORKDIR /opt/arelle
RUN apt update;\
    apt install -y python3-pip libxml2-dev libxslt1.dev; \
    pip3 install -r requirements.txt; \
    pip3 install isodate; \
    apt install -y ruby ruby-dev;
RUN gem install bundler
RUN gem install shoryuken
RUN gem install aws-sdk-sqs
EXPOSE 8099
