#!/usr/bin/env bash

export DEBIAN_FRONTEND=noninteractive
pwd
sudo add-apt-repository -y ppa:fkrull/deadsnakes
sudo apt-get update
sudo apt-get install -y python3.4
# fetch configure_daemon.py in background
curl https://raw.githubusercontent.com/GianlucaBortoli/krafters/master/configure_daemon.py > configure_daemon.py
sudo chmod 777 configure_daemon.py
# run configure_daemon.py in background
./configure_daemon.py &

# install rethinkdb
source /etc/lsb-release && echo "deb http://download.rethinkdb.com/apt $DISTRIB_CODENAME main" | \
    sudo tee /etc/apt/sources.list.d/rethinkdb.list
wget -qO- https://download.rethinkdb.com/apt/pubkey.gpg | sudo apt-key add -
sudo apt-get update && \
    sudo apt-get install -y rethinkdb
