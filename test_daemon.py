#!/usr/bin/python3.4

# Daemon listening for test_executor commands

from functools import partial
from socketserver import ThreadingMixIn
from xmlrpc.client import ServerProxy
from xmlrpc.server import SimpleXMLRPCServer
import rethinkdb as r
import sys
import time
import logging
# NOTE DO NOT ADD EXTERNAL DEPENDENCIES: THIS SCRIPT HAS TO BE EXECUTED IN A STANDALONE WAY ON VM STARTUP

TEST_DAEMON_PORT = 2082
DEFAULT_VALUE = "value"
RETHINKDB_DB_NAME = 'test'
RETHINKDB_TABLE_NAME = 'test'

PAXOS_CLUSTER_ACK = None
PAXOS_APPEND_PORT = 12366


class MultiThreadXMLRPCServer(ThreadingMixIn, SimpleXMLRPCServer):
    '''
    Mixes SimpleXMLRPCServer and ThreadingMixIn
    '''


def rethinkdbSetup(connection):
    try:
        # r.db_create(RETHINKDB_DB_NAME).run(connection)
        logging.info("Database {} created".format(RETHINKDB_DB_NAME))
        r.db(RETHINKDB_DB_NAME).table_create(RETHINKDB_TABLE_NAME).run(connection)
        logging.info('Db {} and table {} created successfully'.format(RETHINKDB_DB_NAME, RETHINKDB_TABLE_NAME))
    except:
        logging.warning('Database {} already exists'.format(RETHINKDB_DB_NAME))


def rethinkdbAppendEntry(connection):
    t = time.perf_counter()
    value = {'key': DEFAULT_VALUE}
    try:
        r.table(RETHINKDB_TABLE_NAME).insert(value, conflict='replace').run(connection)
        logging.info('key added')
    except:
        logging.error('{} not added'.format(value))
    finally:
        return time.perf_counter() - t


def paxosAppendEntry(paxos_rpc_client):
    global PAXOS_CLUSTER_ACK
    res = paxos_rpc_client.paxos_append(DEFAULT_VALUE)
    while PAXOS_CLUSTER_ACK is None:
        pass
    time = PAXOS_CLUSTER_ACK - res
    PAXOS_CLUSTER_ACK = None
    return time


def paxos_append_complete(new_current_value, time):
    global PAXOS_CLUSTER_ACK
    PAXOS_CLUSTER_ACK = time
    return None


# class used to implement different append requests for different algorithms
class TestManager:
    def __init__(self, algorithm_host, algorithm, algorithm_port):
        self.algorithm = algorithm
        self.algorithm_port = algorithm_port

        if algorithm == "rethinkdb":
            self.rdb_connection = r.connect('localhost', self.algorithm_port)
            logging.info("Connection with RethinkDB successful")
            rethinkdbSetup(self.rdb_connection)
            self.appendFunction = partial(rethinkdbAppendEntry, self.rdb_connection)
        elif algorithm == "paxos":
            self.paxos_rpc_client = ServerProxy("http://{}:{}".format(algorithm_host, PAXOS_APPEND_PORT))
            self.appendFunction = partial(paxosAppendEntry, self.paxos_rpc_client)

    # wrapper used to execute multiple operations and register times
    def run(self, times):
        results = []
        for _ in range(0, times):
            results.append(self.appendFunction())
        return results


def run_test_server(server_port, algorithm, algorithm_port):
    if server_port == '\'\'' or server_port == '':
        server_port = '127.0.0.1'
    logging.basicConfig(filename='test_daemon_debug.log', level=logging.DEBUG)
    # server = SimpleXMLRPCServer((server_port, TEST_DAEMON_PORT), allow_none=True)
    server = MultiThreadXMLRPCServer((server_port, TEST_DAEMON_PORT), allow_none=True)
    test_manager = TestManager(server_port, algorithm, algorithm_port)
    server.register_function(test_manager.run, "run")
    server.register_function(paxos_append_complete, "paxos_append_complete")
    server.serve_forever()


if __name__ == "__main__":
    # argv[1] = IP address of the machine running this script (where the test daemon will be started)
    # argv[2] = consensus algorithm
    # argv[3] = the port of process running the algorithm when different from the default one
    run_test_server(sys.argv[1], sys.argv[2], sys.argv[3])
