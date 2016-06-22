#!/usr/bin/python2.7
from functools import partial

import sys
import os.path
import json
import threading

from twisted.internet import reactor

this_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.dirname(this_dir))

from replicated_value import BaseReplicatedValue
from messenger import Messenger
from sync_strategy import SimpleSynchronizationStrategyMixin
from resolution_strategy import ExponentialBackoffResolutionStrategyMixin
from master_strategy import DedicatedMasterStrategyMixin
from SimpleXMLRPCServer import SimpleXMLRPCServer
import xmlrpclib


PAXOS_APPEND_PORT = 12366


def onUpdateFunction(test_daemon_client, new_current_value):
    print "CALLBACK: ", new_current_value
    test_daemon_client.paxos_append_complete(new_current_value)


def noop(new_current_value):
    print "CALLBACK: ", new_current_value


class TestDaemonListener:
    def __init__(self, messenger):
        self.messenger = messenger
        thread = threading.Thread(target=self.run, args=())
        thread.start()

    def run(self):
        server = SimpleXMLRPCServer(('127.0.0.1', PAXOS_APPEND_PORT), allow_none=True)
        server.register_function(self.messenger.paxos_append, "paxos_append")
        server.serve_forever()


def main():
    with open(sys.argv[1]) as configuration_file:
        configuration = json.load(configuration_file)

    if len(sys.argv) == 3:
        test_daemon_client = xmlrpclib.ServerProxy("http://{}".format(sys.argv[2]))
        callback = partial(onUpdateFunction, test_daemon_client)
    else:
        callback = partial(noop)

    class ReplicatedValue(ExponentialBackoffResolutionStrategyMixin, SimpleSynchronizationStrategyMixin,
                          BaseReplicatedValue):
        '''
        Mixes just the resolution and synchronization strategies into the base class
        '''

    id = configuration["host"]["id"]
    state_file = "./paxos_state_{}.json".format(id)
    peers = {peer["id"]: (peer["address"], peer["port"]) for peer in configuration["peers"]}
    peers[id] = (configuration["host"]["address"], configuration["host"]["port"])
    r = ReplicatedValue(id, peers.keys(), state_file, callback)
    m = Messenger(id, peers, r)
    if len(sys.argv) == 3:
        listener = TestDaemonListener(m)
    reactor.run()


if __name__ == "__main__":
    main()
