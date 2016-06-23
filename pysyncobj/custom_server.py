#!/usr/bin/python2.7

import json
import time
import random
import threading
import timeit
from functools import partial
import sys
from pysyncobj import SyncObj, SyncObjConf, replicated, FAIL_REASON
from SimpleXMLRPCServer import SimpleXMLRPCServer
import xmlrpclib


PSO_APPEND_PORT = 12366

def onUpdateFunction(test_daemon_client, res, err):
    print "CALLBACK: ", res, err
    t = timeit.default_timer()
    test_daemon_client.cluster_append_complete(res, t)  # TODO CHECK RES


def noop(res, err):
    print "CALLBACK: ", res, err


class TestDaemonListener:
    def __init__(self, callback, pso_node):
        self.callback = callback
        self.pso_node = pso_node
        thread = threading.Thread(target=self.run, args=())
        thread.start()

    def run(self):
        server = SimpleXMLRPCServer(('127.0.0.1', PSO_APPEND_PORT), allow_none=True)
        server.register_function(self.pso_append, "append_entry")
        server.serve_forever()

    def pso_append(self, value):
        t = timeit.default_timer()
        self.pso_node.setValue(value, callback=self.callback)
        return t



class TestObjAutoTick(SyncObj):
    def __init__(self, selfNodeAddr, otherNodeAddrs, compactionTest = 0, dumpFile = None, compactionTest2 = False):
        cfg = SyncObjConf(autoTick=True, commandsQueueSize=10000, appendEntriesUseBatch=False)
        if compactionTest:
            cfg.logCompactionMinEntries = compactionTest
            cfg.logCompactionMinTime = 0.1
            cfg.appendEntriesUseBatch = True
            cfg.fullDumpFile = dumpFile
        if compactionTest2:
            cfg.logCompactionMinEntries = 99999
            cfg.logCompactionMinTime = 99999
            cfg.fullDumpFile = dumpFile
            cfg.sendBufferSize = 2 ** 21
            cfg.recvBufferSize = 2 ** 21
            cfg.appendEntriesBatchSize = 10
            cfg.maxCommandsPerTick = 5

        super(TestObjAutoTick, self).__init__(selfNodeAddr, otherNodeAddrs, cfg)
        self.__item = 0
        self.__data = {}

    @replicated
    def setValue(self, value):
        self.__item = value
        return self.__item

    def getCounter(self):
        return self.__counter


def main():
    with open(sys.argv[1]) as configuration_file:
        configuration = json.load(configuration_file)

    if len(sys.argv) == 3:
        test_daemon_client = xmlrpclib.ServerProxy("http://{}".format(sys.argv[2]))
        callback = partial(onUpdateFunction, test_daemon_client)
    else:
        callback = partial(noop)

    node = configuration["host"]["address"] + ":" + str(configuration["host"]["port"])
    print node
    peers = [peer["address"] + ":" + str(peer["port"]) for peer in configuration["peers"]]
    print peers
    pso_node = TestObjAutoTick(node, peers)
    if len(sys.argv) == 3:
        listener = TestDaemonListener(callback, pso_node)

    while True:
        pass


if __name__ == "__main__":
    main()
