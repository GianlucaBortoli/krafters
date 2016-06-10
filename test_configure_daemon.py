#!/usr/bin/python3.4

# Built only to test configure_daemon functionalities on localhost

import xmlrpc.client
import json
from provisioner import get_free_random_port

# some useful constants
CONFIG_FILE = './masterConfig.json'
RPC_PORT = 12345
GCE_PORTS = {
    "cluster_port": 12347,
    "driver_port": 12348,
    "http_port": 12349
}


def createServer(ip, port):
    return xmlrpc.client.ServerProxy('http://{}:{}'.format(ip, port))


def configure_rethinkdb(cluster, mode):
    # Configures every node of the cluster.
    master_cluster_port = get_free_random_port() # this is the one for joining
    if mode == "local":
        # local -> get driver_port from file (provisioner) and use random
        #          ports for all the others
        print("Local mode")
        for node in cluster:
            s = createServer(node['address'], RPC_PORT)
            if node['id'] == 1:
                print("m{}: ".format(node['id']), node)
                # the first node is always the master
                print(s.configure_rethinkdb_master(master_cluster_port,
                    node['port'],
                    get_free_random_port()))
            else:
                print("f{}: ".format(node['id']), node)
                # all the others are followers
                print(s.configure_rethinkdb_follower(node['id'],
                    cluster[0]['address'],
                    master_cluster_port,
                    get_free_random_port(),
                    node['port'],
                    get_free_random_port()))
    elif mode == "gce":
        # gce -> use GCE_PORTS since we are in different nodes and
        #        we don't have problems with ports
        print("GCE mode")
        for node in cluster:
            s = createServer(node['address'], RPC_PORT)
            if node['id'] == 1:
                print(s.configure_rethinkdb_master(GCE_PORTS['cluster_port'],
                    GCE_PORTS['driver_port'],
                    GCE_PORTS['http_port']))
            else:
                print(s.configure_rethinkdb_follower(node['id'],
                    cluster[0]['address'],
                    GCE_PORTS['cluster_port'],
                    GCE_PORTS['cluster_port'],
                    GCE_PORTS['driver_port'],
                    GCE_PORTS['http_port']))
    else:
        print("Mode {} not recognized".format(mode))
        return

    return "Configuration done"


if __name__ == '__main__':
    with open(CONFIG_FILE, 'r') as conf:
        cluster = json.load(conf)

    s = createServer('localhost', RPC_PORT)
    print(configure_rethinkdb(cluster['nodes'], 'local'))
    #print(s.stop_rethinkdb())