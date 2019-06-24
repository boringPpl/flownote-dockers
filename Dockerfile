FROM jupyter/minimal-notebook
  
LABEL maintainer="Flow Note <flownote@hasbrain.com>"

USER root

# install dvc & flownote
RUN wget https://dvc.org/deb/dvc.list -O /etc/apt/sources.list.d/dvc.list && \
    apt-get update && \
    apt-get install -y --no-install-recommends dvc && \
    wget https://raw.githubusercontent.com/hasbrain/flownote-dockers/master/flownote.py -O /usr/local/bin/flownote && \
    chmod +x /usr/local/bin/flownote && \
    rm -rf /var/lib/apt/lists/*

RUN wget https://raw.githubusercontent.com/hasbrain/flownote-dockers/master/juopyter_notebook_config.py -O /etc/jupyter/jupyter_notebook_config.py

# Spark dependencies
ENV APACHE_SPARK_VERSION 2.4.3
ENV HADOOP_VERSION 2.7

RUN apt-get -y update && \
    apt-get install --no-install-recommends -y openjdk-8-jre-headless ca-certificates-java && \
    rm -rf /var/lib/apt/lists/*

RUN cd /tmp && \
    wget -q http://mirrors.ukfast.co.uk/sites/ftp.apache.org/spark/spark-${APACHE_SPARK_VERSION}/spark-${APACHE_SPARK_VERSION}-bin-hadoop${HADOOP_VERSION}.tgz && \
    echo "E8B7F9E1DEC868282CADCAD81599038A22F48FB597D44AF1B13FCC76B7DACD2A1CAF431F95E394E1227066087E3CE6C2137C4ABAF60C60076B78F959074FF2AD *spark-${APACHE_SPARK_VERSION}-bin-hadoop${HADOOP_VERSION}.tgz" | sha512sum -c - && \
    tar xzf spark-${APACHE_SPARK_VERSION}-bin-hadoop${HADOOP_VERSION}.tgz -C /usr/local --owner root --group root --no-same-owner && \
    rm spark-${APACHE_SPARK_VERSION}-bin-hadoop${HADOOP_VERSION}.tgz
RUN cd /usr/local && ln -s spark-${APACHE_SPARK_VERSION}-bin-hadoop${HADOOP_VERSION} spark

# Predefined user from jupyter docker-stacks
USER $NB_UID
