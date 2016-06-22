#!/usr/bin/python2.7

# Daemon listening for test_executor commands
from Queue import Queue
from SimpleXMLRPCServer import SimpleXMLRPCServer

import xmlrpclib

from functools import partial
import sys
import threading
import time
import logging

# NOTE DO NOT ADD EXTERNAL DEPENDENCIES: THIS SCRIPT HAS TO BE EXECUTED IN A STANDALONE WAY ON VM STARTUP

TEST_DAEMON_PORT = 2082
DEFAULT_VALUE = "value"
DEFAULT_PAXOS_VALUE = 1

PAXOS_CLUSTER_ACK = None

PAXOS_APPEND_PORT = 12366

from SocketServer import ThreadingMixIn
from SimpleXMLRPCServer import SimpleXMLRPCServer

class MyXMLRPCServer(ThreadingMixIn, SimpleXMLRPCServer):
    '''
    Mixes SimpleXMLRPCServer and ThreadingMixIn
    '''


# class used to implement different append requests for different algorithms
class TestManager:
    def __init__(self, algorithm_host, algorithm, algorithm_port):
        self.algorithm = algorithm
        self.algorithm_port = algorithm_port

        if algorithm == "pso":
            pass  # TODO
        elif algorithm == "paxos":
            self.paxos_rpc_client = xmlrpclib.ServerProxy("http://{}:{}".format(algorithm_host, PAXOS_APPEND_PORT))
            # self.paxos_node = ReactorPaxosNode(algorithm_host, algorithm_port)

    # wrapper used to execute multiple operations and register times
    def run(self, times):
        results = []
        for _ in range(0, times):
            t = time.clock()  # TODO CHECK IF CONSISTENT WITH TIME.PERF()
            if self.algorithm == "pso":
                pass  # TODO IMPLEMENT ME
            elif self.algorithm == "paxos":
                global PAXOS_CLUSTER_ACK
                self.paxos_rpc_client.paxos_append(666)
                while PAXOS_CLUSTER_ACK is None:
                    pass
                PAXOS_CLUSTER_ACK = None
            results.append(time.clock() - t)  # TODO CHECK IF CONSISTENT WITH TIME.PERF()
        return results


def paxos_append_complete(new_current_value):
    global PAXOS_CLUSTER_ACK
    PAXOS_CLUSTER_ACK = new_current_value
    print "RCV: ", new_current_value
    return None


def run_test_server(server_port, algorithm, algorithm_port):
    if server_port == '\'\'' or server_port == '':
        server_port = '127.0.0.1'
    logging.basicConfig(filename='test_daemon_debug.log', level=logging.DEBUG)
    # server = SimpleXMLRPCServer((server_port, TEST_DAEMON_PORT), allow_none=True)
    server = MyXMLRPCServer((server_port, TEST_DAEMON_PORT), allow_none=True)
    test_manager = TestManager(server_port, algorithm, algorithm_port)
    server.register_function(test_manager.run, "run")
    server.register_function(paxos_append_complete, "paxos_append_complete")
    server.serve_forever()


if __name__ == "__main__":
    # argv[1] = IP address of the machine running this script (where the test daemon will be started)
    # argv[2] = consensus algorithm
    # argv[3] = the port of process running the algorithm when different from the default one
    run_test_server(sys.argv[1], sys.argv[2], sys.argv[3])
