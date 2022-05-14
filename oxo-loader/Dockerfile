FROM python:3.9.3-slim

# RUN apk add --no-cache bash mariadb-dev build-base
#RUN apk --update add mysql mysql-client

COPY oxo-loader/requirements.txt /requirements.txt
RUN pip3 install -r /requirements.txt

COPY oxo-loader /opt/oxo-loader
RUN chmod +x /opt/oxo-loader/load_all.sh

CMD bash
