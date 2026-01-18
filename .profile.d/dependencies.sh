#!/bin/bash
# Instalar libopus y libsndfile en Railway
curl -sL https://github.com/soulteary/apt-source-ops/raw/main/public/install-apt-source.sh | bash
apt-get update
apt-get install -y libopus0 libsndfile1
export LD_LIBRARY_PATH="/usr/lib/x86_64-linux-gnu:$LD_LIBRARY_PATH"