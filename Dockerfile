FROM ubuntu:18.04
ADD . /opt/arelle
WORKDIR /opt/arelle
RUN apt update
RUN apt install -y python3-pip libxml2-dev libxslt1.dev
RUN pip3 install -r requirements.txt
EXPOSE 8099
CMD [ "python3", "./arelleCmdLine.py", "--webserver", "0.0.0.0:8099" ]