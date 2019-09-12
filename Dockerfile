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

RUN wget https://raw.githubusercontent.com/hasbrain/flownote-dockers/master/jupyter_notebook_config.py -O /etc/jupyter/jupyter_notebook_config.py

# Predefined user from jupyter docker-stacks
USER $NB_UID
