#!/usr/bin/python2.7

import sys
import os.path
import argparse
import json

from twisted.internet import reactor

this_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append( os.path.dirname(this_dir) )

import config

from replicated_value    import BaseReplicatedValue
from messenger           import Messenger
from sync_strategy       import SimpleSynchronizationStrategyMixin
from resolution_strategy import ExponentialBackoffResolutionStrategyMixin
from master_strategy     import DedicatedMasterStrategyMixin


def main():
    with open(sys.argv[1]) as configuration_file:
        configuration = json.load(configuration_file)

    class ReplicatedValue(ExponentialBackoffResolutionStrategyMixin, SimpleSynchronizationStrategyMixin, BaseReplicatedValue):
        '''
        Mixes just the resolution and synchronization strategies into the base class
        '''

    id = configuration["host"]["id"]
    state_file = "./paxos_state_{}.json".format(id)
    peers = {peer["id"]: (peer["address"], peer["port"]) for peer in configuration["peers"]}
    peers[id] = (configuration["host"]["address"], configuration["host"]["port"])
    r = ReplicatedValue(id, peers.keys(), state_file)
    m = Messenger(id, peers, r)
    reactor.run()


if __name__ == "__main__":
    main()



