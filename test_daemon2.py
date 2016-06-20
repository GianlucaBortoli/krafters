#!/usr/bin/python2.7

# Daemon listening for test_executor commands
from Queue import Queue
from SimpleXMLRPCServer import SimpleXMLRPCServer

from functools import partial
import sys
import threading
import time
import logging

from twisted.internet import reactor, defer, protocol
# TODO: ENSURE TWISTED IS INSTALLED
# NOTE DO NOT ADD EXTERNAL DEPENDENCIES: THIS SCRIPT HAS TO BE EXECUTED IN A STANDALONE WAY ON VM STARTUP

TEST_DAEMON_PORT = 12346
DEFAULT_VALUE = "value"


class ClientProtocol(protocol.DatagramProtocol):
    def __init__(self, node_ip, node_port, new_value):
        self.addr = (node_ip, node_port)
        self.new_value = new_value

    def startProtocol(self):
        self.transport.write('propose {0}'.format(self.new_value), self.addr)


class ReactorPaxosNode:
    def __init__(self, ip, port):
        self.spin = True
        self.ip = ip
        self.port = port
        self.queue = Queue()
        thread = threading.Thread(target=self.run, args=())
        thread.start()

    def run(self):
        def append_from_queue():
            while self.spin:
                if not self.queue.empty():
                    reactor.listenUDP(0, ClientProtocol(self.ip, self.port, self.queue.get()))
            reactor.stop()

        reactor.callWhenRunning(append_from_queue)
        reactor.run(installSignalHandlers=False)

    def stop(self):
        self.spin = False

    def add_item(self, item):
        self.queue.put(item)


# class used to implement different append requests for different algorithms
class TestManager:
    def __init__(self, server_port, algorithm, algorithm_port):
        self.algorithm = algorithm
        self.algorithm_port = algorithm_port

        if algorithm == "pso":
            pass  # TODO
        elif algorithm == "paxos":
            self.paxos_node = ReactorPaxosNode(server_port, TEST_DAEMON_PORT)

    # wrapper used to execute multiple operations and register times
    def run(self, times):
        results = []
        for _ in range(0, times):
            t = time.clock()  # TODO CHECK IF CONSISTENT WITH TIME.PERF()
            if self.algorithm == "pso":
                pass  # TODO IMPLEMENT ME
            elif self.algorithm == "paxos":
                self.paxos_node.add_item(DEFAULT_VALUE)  # TODO CONFIGURE PAXOS SERVER TO SEND REPLY
            results.append(time.clock() - t)  # TODO CHECK IF CONSISTENT WITH TIME.PERF()
        return results


def run_test_server(server_port, algorithm, algorithm_port):
    logging.basicConfig(filename='test_daemon_debug.log', level=logging.DEBUG)
    server = SimpleXMLRPCServer((server_port, TEST_DAEMON_PORT), allow_none=True)
    test_manager = TestManager(server_port, algorithm, algorithm_port)
    server.register_function(test_manager.run, "run")
    server.serve_forever()


if __name__ == "__main__":
    # argv[1] = IP address of the machine running this script (where the test daemon will be started)
    # argv[2] = consensus algorithm
    # argv[3] = the port of process running the algorithm when different from the default one
    run_test_server(sys.argv[1], sys.argv[2], sys.argv[3])
