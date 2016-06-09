#!/usr/bin/env bash

# install rethinkdb
export DEBIAN_FRONTEND=noninteractive
source /etc/lsb-release && echo "deb http://download.rethinkdb.com/apt $DISTRIB_CODENAME main" | \
    sudo tee /etc/apt/sources.list.d/rethinkdb.list
wget -qO- https://download.rethinkdb.com/apt/pubkey.gpg | sudo apt-key add -
sudo apt-get update && \
    sudo apt-get install -y rethinkdb

# run configure_daemon.py in background
./configure_daemon.py &
