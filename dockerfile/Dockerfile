FROM python:3.8.5-alpine

MAINTAINER hexanyn, hexanyn@gmail.com

RUN apk add gcc musl-dev

RUN pip3 install requests slackclient pygments spotipy

ENTRYPOINT sh /data/start.sh
