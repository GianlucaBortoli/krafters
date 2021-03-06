#!/usr/bin/python3.4

# Use xmlrpc server in order to listen for provisioner requests to configure algorithms for cloud tests.
# This daemon is supposed to run on every node of the cluster.
# All the required tools are supposed to be already installed on the machine running this daemon.

from contextlib import closing
from time import sleep
from xmlrpc.server import SimpleXMLRPCServer
import subprocess
import socket
import os
# NOTE DO NOT ADD EXTERNAL DEPENDENCIES: THIS SCRIPT HAS TO BE EXECUTED IN A STANDALONE WAY ON VM STARTUP

# TODO ENSURE PAXOS IS INSTALLED

CONFIGURE_DAEMON_PORT = 12345
TEST_DAEMON_PORT = 2082
NETWORK_MANAGER_PORT = 12347

DEVNULL = open(os.devnull, 'wb')
LOCAL_NODE_CONF_FILE = "node_conf.json"


def run_test_daemon(algorithm, algorithm_port):
    file_path = os.path.dirname(os.path.abspath(__file__)).replace(" ", "\ ")
    cmd = "python3.4 {}/test_daemon.py '' {} {} &".format(file_path, algorithm, algorithm_port)
    subprocess.Popen(cmd, shell=True, stdout=DEVNULL).communicate()  # process is run in background
    wait_for_ports([TEST_DAEMON_PORT], 0.5)
    print("Test daemon process started")


def run_network_manager():
    # ensure this function is called only when the node can access its configuration file
    command = ["sudo", "./network_manager.py", LOCAL_NODE_CONF_FILE]
    subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)  # process is run asynchronously
    wait_for_ports([NETWORK_MANAGER_PORT], 0.3)
    print("Network manager started")


def download_node_config():
    # this rpc will download the node-specific configuration file from gs and run the network manager
    # each node can discover its configuration file by querying its own metadata
    command = ["curl", "http://metadata.google.internal/computeMetadata/v1/instance/attributes/clusterConfig", "-H",
               "Metadata-Flavor: Google"]
    out, _ = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE).communicate()
    gcs_node_conf_file = out.decode("utf-8")
    print("GCS file: {}".format(gcs_node_conf_file))
    command = ["curl", "http://metadata.google.internal/computeMetadata/v1/instance/attributes/bucket", "-H",
               "Metadata-Flavor: Google"]
    out, _ = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE).communicate()
    bucket = out.decode("utf-8")
    print("GCS bucket: {}".format(bucket))
    command = ["sudo", "gsutil", "cp", "gs://{}/{}".format(bucket, gcs_node_conf_file), LOCAL_NODE_CONF_FILE]
    subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE).communicate()
    return "GCS file download completed {}".format(gcs_node_conf_file)


# PSO functions

def run_pso_node(port, node_config_file, test_daemon=None):
    if test_daemon:
        cmd = "./pysyncobj/custom_server.py {} {} &".format(node_config_file, test_daemon)
    else:
        cmd = "./pysyncobj/custom_server.py {} &".format(node_config_file)
    subprocess.Popen(cmd, shell=True, stdout=DEVNULL).communicate()
    wait_for_ports([port], 0.3, tcp=False)
    return "PSO node started"


# Paxos functions

def run_paxos_node(port, node_config_file, test_daemon=None):
    if test_daemon:
        cmd = "./paxos/custom_server.py {} {} &".format(node_config_file, test_daemon)
    else:
        cmd = "./paxos/custom_server.py {} &".format(node_config_file)
    subprocess.Popen(cmd, shell=True, stdout=DEVNULL).communicate()
    wait_for_ports([port], 0.3, tcp=False)
    return "Paxos node started"


# RethinkDB functions

def configure_rethinkdb_master(cluster_port, driver_port, http_port, canonical_address):
    # the cluster_port is the one to be used for joining the master
    cmd = "rethinkdb --cache-size 0 --bind all --cluster-port {cp} --driver-port {dp} --http-port {hp} --canonical-address {ca} &". \
        format(cp=cluster_port, dp=driver_port, hp=http_port, ca=canonical_address)
    subprocess.Popen(cmd, shell=True, stdout=DEVNULL).communicate()
    wait_for_ports([cluster_port, driver_port, http_port], 0.5)
    return "RethinkDB master ready on port {}".format(cluster_port)


def configure_rethinkdb_follower(my_id, m_ip, m_cp, my_cp, my_dp, my_hp):
    cmd = ("rethinkdb --cache-size 0 --bind all --directory rethinkdb_data{id} "
           "--join {ip}:{m_cp} --cluster-port {my_cp} "
           "--driver-port {my_dp} --http-port {my_hp} &"). \
        format(id=my_id, ip=m_ip, m_cp=m_cp, my_cp=my_cp, my_dp=my_dp, my_hp=my_hp)
    subprocess.Popen(cmd, shell=True, stdout=DEVNULL).communicate()
    wait_for_ports([my_cp, my_dp, my_hp], 0.5)
    return "RethinkDB follower ready on port {}".format(my_cp)


def stop_rethinkdb():
    subprocess.check_call("killall rethinkdb", shell=True)
    return "RethinkDB processes stopped"


# socket utility

def is_socket_free(host, port, tcp=True):
    protocol = socket.SOCK_STREAM if tcp else socket.SOCK_DGRAM
    with closing(socket.socket(socket.AF_INET, protocol)) as sock:
        return sock.connect_ex((host, port)) == 0  # function returns 0 if port is open (no process is using the port)


def wait_for_ports(ports_to_check, timeout, tcp=True):
    for port in ports_to_check:
        print("Waiting for port {}...".format(port))
        while not is_socket_free("127.0.0.1", port, tcp):
            sleep(timeout)


# main

def main():
    try:
        server = SimpleXMLRPCServer(("", CONFIGURE_DAEMON_PORT), allow_none=True)
        print("Configure daemon listening on port {}...".format(CONFIGURE_DAEMON_PORT))
        # register all exposed functions
        server.register_function(run_test_daemon, "run_test_daemon")
        server.register_function(run_network_manager, "run_network_manager")
        server.register_function(download_node_config, "download_node_config")
        server.register_function(run_pso_node, "run_pso_node")
        server.register_function(run_paxos_node, "run_paxos_node")
        server.register_function(configure_rethinkdb_master, "configure_rethinkdb_master")
        server.register_function(configure_rethinkdb_follower, "configure_rethinkdb_follower")
        server.register_function(stop_rethinkdb, "stop_rethinkdb")
        # finally serve them
        server.serve_forever()
    except KeyboardInterrupt as e:
        print(e)
        print("\nProcess stopped by user. Bye!")


if __name__ == '__main__':
    main()
