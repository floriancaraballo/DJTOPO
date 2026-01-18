#!/bin/sh

# Instalar dependencias para compilar Opus
apk add --no-cache alpine-sdk libsndfile-dev

# Descargar y compilar libopus
cd /tmp
wget https://downloads.xiph.org/releases/opus/opus-1.4.tar.gz
tar -xzf opus-1.4.tar.gz
cd opus-1.4
./configure --disable-shared --enable-static --prefix=/usr
make
make install

# Ejecutar el bot
python bot.py