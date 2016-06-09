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
RETHINKDB_PORT = 12347
DEVNULL = open(os.devnull, 'wb')


def configure_rethinkdb_master(cluster_port, driver_port, http_port):
    # the cluster_port is the one to be used for joining the master
    cmd = "rethinkdb --bind all --cluster-port {cp} --driver-port {dp} --http-port {hp} &".\
        format(cp=cluster_port, dp=driver_port, hp=http_port)
    p = sb.Popen(cmd, shell=True, stdout=DEVNULL)
    p.communicate()
    return "master on port {} up".format(cluster_port)


def configure_rethinkdb_follower(my_id, m_ip, m_cp, my_cp, my_dp, my_hp):
    cmd = ("rethinkdb --directory rethinkdb_data{id} " 
            "--join {ip}:{m_cp} --cluster-port {my_cp} "
            "--driver-port {my_dp} --http-port {my_hp} &").\
        format(id=my_id, ip=m_ip, m_cp=m_cp, my_cp=my_cp, my_dp=my_dp, my_hp=my_hp)
    p = sb.Popen(cmd, shell=True, stdout=DEVNULL)
    p.communicate()
    return "follower on port {} up".format(my_cp)


def stop_rethinkdb():
    cmd = "killall rethinkdb"
    sb.check_call(cmd, shell=True)
    return "rethinkdb stopped"


def foo():
    pass


def foo1():
    pass


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
        server.register_function(foo, "foo")
        server.register_function(foo1, "foo1")
        # finally serve them
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nProcess stopped by user...Bye!")
        sys.exit()
