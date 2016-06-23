#!/usr/bin/env bash

export DEBIAN_FRONTEND=noninteractive
# add repos & keys
source /etc/lsb-release && echo "deb http://download.rethinkdb.com/apt $DISTRIB_CODENAME main" | \
    sudo tee /etc/apt/sources.list.d/rethinkdb.list
wget -qO- https://download.rethinkdb.com/apt/pubkey.gpg | sudo apt-key add -
sudo apt-get update

# install python3.4 and git
sudo apt-get install -y \
    git \
    gcc
# fetch network_manager.py
curl https://raw.githubusercontent.com/GianlucaBortoli/krafters/master/network_manager.py > network_manager.py
sudo chmod 777 network_manager.py
# fetch test_daemon.py
curl https://raw.githubusercontent.com/GianlucaBortoli/krafters/master/test_daemon.py > test_daemon.py
#sudo gsutil cp gs://krafters/test_daemon.py test_daemon.py
sudo chmod 777 test_daemon.py
# fetch configure_daemon.py
curl https://raw.githubusercontent.com/GianlucaBortoli/krafters/master/configure_daemon.py > configure_daemon.py
sudo chmod 777 configure_daemon.py
# run configure_daemon.py in background
./configure_daemon.py &

# install rethinkdb
sudo apt-get install -y rethinkdb
sudo wget https://bootstrap.pypa.io/get-pip.py
sudo python3.4 get-pip.py
sudo python2.7 get-pip.py
sudo -H pip3.4 install rethinkdb

# notify provisioner script is executed
instance=$(sudo curl http://metadata.google.internal/computeMetadata/v1/instance/attributes/myid -H "Metadata-Flavor: Google")
bucket=$(sudo curl http://metadata.google.internal/computeMetadata/v1/instance/attributes/bucket -H "Metadata-Flavor: Google")
sudo echo > $instance

# clone our repo & copy paxos/PSO
git clone https://github.com/GianlucaBortoli/krafters.git
mv ./krafters/paxos .
mv ./krafters/pysyncobj .
rm -rf ./krafters

# install paxos/PSO dependencies
sudo -H pip2.7 install \
    essential-paxos \
    paxos
sudo apt-get install -y python-twisted
sudo -H pip2.7 install pysyncobj

# notify we're done
gsutil cp $instance gs://$bucket/$instance