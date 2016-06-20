#!/usr/bin/python2.7

# This module provides a very simple client interface for suggesting new
# replicated values to one of the servers. No reply is received so an eye must
# be kept on the server output to see if the new suggestion is received. Also,
# when master leases are in use, requests must be sent to the current master
# server. All non-master servers will ignore the requests since they do not have
# the ability to propose new values in the multi-paxos chain.

import sys
import threading
from time import sleep

from twisted.internet import reactor, defer, protocol

import config


class ClientProtocol(protocol.DatagramProtocol):
    def __init__(self, node_ip, node_port, new_value):
        self.addr      = (node_ip, node_port)
        self.new_value = new_value

    def startProtocol(self):
        self.transport.write('propose {0}'.format(self.new_value), self.addr)


class ReactorThread:
    def __init__(self, ip, port):
        self.spin = True
        self.ip = ip
        self.port = port
        self.queue = []
        thread = threading.Thread(target=self.run, args=())
        thread.start()

    def run(self):
        def append_from_queue():
            while self.spin:
                if len(self.queue) > 0:
                    reactor.listenUDP(0, ClientProtocol(self.ip, self.port, self.queue.pop()))
            reactor.stop()

        reactor.callWhenRunning(append_from_queue)
        reactor.run(installSignalHandlers=False)

    def stop(self):
        self.spin = False

    def add_item(self, item):
        self.queue.append(item)


def main():
    # '127.0.0.1', 1234
    reactor = ReactorThread(sys.argv[1], int(sys.argv[2]))
    reactor.add_item('111')
    sleep(3)
    reactor.add_item('222')
    sleep(3)
    reactor.add_item('444')
    reactor.stop()


if __name__ == "__main__":
    main()
