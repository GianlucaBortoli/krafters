#!/usr/bin/env bash

export DEBIAN_FRONTEND=noninteractive

# run configure_daemon.py in background
curl https://raw.githubusercontent.com/GianlucaBortoli/krafters/master/configure_daemon.py > configure_daemon.py
chmod +x configure_daemon.py
./configure_daemon.py &

# install rethinkdb
source /etc/lsb-release && echo "deb http://download.rethinkdb.com/apt $DISTRIB_CODENAME main" | \
    sudo tee /etc/apt/sources.list.d/rethinkdb.list
wget -qO- https://download.rethinkdb.com/apt/pubkey.gpg | sudo apt-key add -
sudo apt-get update && \
    sudo apt-get install -y rethinkdb
