#!/usr/bin/python3.4

# Use server xmlrpc in order to listen for provisioner - configuring the algorithms for
# clout tests. This is supposed to run in each node of the cluster. It supposes that all
# the tools are already installed on the machine.
#
# Methods to provide to the provisioner:
# rethinkdb:    configure_rethinkdb_master, configure_rethinkdb_follower
# paxos:        configure_paxos
# pso:          < nothing to do here >

import subprocess as sb
import os
import sys
from xmlrpc.server import SimpleXMLRPCServer

# some useful constants
RPC_LISTEN_PORT = 12345
RETHINKDB_START_PORT = 12350
DEVNULL = open(os.devnull, 'wb')


def configure_rethinkdb_master():
    cmd = "rethinkdb --bind all --cluster-port {port} &".\
        format(port=RETHINKDB_START_PORT)
    p = sb.Popen(cmd, shell=True, stdout=DEVNULL)
    p.communicate()
    return "master on port {} up".format(RETHINKDB_START_PORT)


def configure_rethinkdb_follower(master_ip, node_id, offset):
    cmd = "rethinkdb --port-offset {off} --directory rethinkdb_data{id} --join {ip}:{port} &".\
        format(off=offset, id=node_id, ip=master_ip, port=RETHINKDB_START_PORT)
    p = sb.Popen(cmd, shell=True, stdout=DEVNULL)
    p.communicate()
    return "follower on port {} up".format(RETHINKDB_START_PORT + offset)


def stop_rethinkdb():
    cmd = "killall rethinkdb"
    sb.check_call(cmd, shell=True)
    return "rethinkdb stopped"


def configure_paxos():
    pass


if __name__ == '__main__':
    try:
        server = SimpleXMLRPCServer(("localhost", RPC_LISTEN_PORT))
        print("Configure daemon listening on port {}...".format(RPC_LISTEN_PORT))
        # register all exposed functions
        server.register_function(configure_rethinkdb_master, "configure_rethinkdb_master")
        server.register_function(configure_rethinkdb_follower, "configure_rethinkdb_follower")
        server.register_function(configure_paxos, "configure_paxos")
        server.register_function(stop_rethinkdb, "stop_rethinkdb")
        # finally serve them
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nProcess stopped by user...Bye!")
        sys.exit()