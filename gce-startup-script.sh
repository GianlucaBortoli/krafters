#!/usr/bin/env bash

export DEBIAN_FRONTEND=noninteractive
pwd
# install python3.4
sudo add-apt-repository -y ppa:fkrull/deadsnakes
sudo apt-get update
sudo apt-get install -y python3.4
# fetch network_manager.py
curl https://raw.githubusercontent.com/GianlucaBortoli/krafters/master/network_manager.py > network_manager.py
sudo chmod 777 network_manager.py
# fetch test_daemon.py
curl https://raw.githubusercontent.com/GianlucaBortoli/krafters/master/test_daemon.py > test_daemon.py
sudo chmod 777 test_daemon.py
curl https://raw.githubusercontent.com/GianlucaBortoli/krafters/master/test_daemon2.py > test_daemon2.py
sudo chmod 777 test_daemon2.py
# fetch configure_daemon.py
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

sudo wget https://bootstrap.pypa.io/get-pip.py
sudo python3.4 get-pip.py
sudo -H pip install rethinkdb

# notify provisioner script is executed
instance=$(sudo curl http://metadata.google.internal/computeMetadata/v1/instance/attributes/myid -H "Metadata-Flavor: Google")
bucket=$(sudo curl http://metadata.google.internal/computeMetadata/v1/instance/attributes/bucket -H "Metadata-Flavor: Google")
sudo echo > $instance
gsutil cp $instance gs://$bucket/$instance
