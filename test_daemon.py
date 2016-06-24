#!/usr/bin/python3.4

# Daemon listening for test_executor commands
import logging
import timeit
from functools import partial
from socketserver import ThreadingMixIn
from xmlrpc.client import ServerProxy
from xmlrpc.server import SimpleXMLRPCServer
import rethinkdb as r
import requests
import sys
import time
# NOTE DO NOT ADD EXTERNAL DEPENDENCIES: THIS SCRIPT HAS TO BE EXECUTED IN A STANDALONE WAY ON VM STARTUP

TEST_DAEMON_PORT = 2082
DEFAULT_VALUE = "value"
RETHINKDB_DB_NAME = 'test'
RETHINKDB_TABLE_NAME = 'test'

CLUSTER_ACK = None
CLUSTER_APPEND_PORT = 12366
GAE_ENDPOINT = "http://krafters-1334.appspot.com/datastore"


class MultiThreadXMLRPCServer(ThreadingMixIn, SimpleXMLRPCServer):
    '''
    Mixes SimpleXMLRPCServer and ThreadingMixIn
    '''


# class Item(ndb.Model):
#     value = ndb.StringProperty(indexed=False)
#     date = ndb.DateTimeProperty(auto_now_add=True)


def rethinkdb_setup(connection):
    try:
        # r.db_create(RETHINKDB_DB_NAME).run(connection)
        logging.info("Database {} created".format(RETHINKDB_DB_NAME))
        r.db(RETHINKDB_DB_NAME).table_create(RETHINKDB_TABLE_NAME).run(connection)
        logging.info('Db {} and table {} created successfully'.format(RETHINKDB_DB_NAME, RETHINKDB_TABLE_NAME))
    except:
        logging.warning('Database {} already exists'.format(RETHINKDB_DB_NAME))


def rethinkdb_append_entry(connection):
    t = timeit.default_timer()
    value = {'key': DEFAULT_VALUE}
    try:
        r.table(RETHINKDB_TABLE_NAME).insert(value, conflict='replace').run(connection)
        logging.info('key added')
    except:
        logging.error('{} not added'.format(value))
    finally:
        return timeit.default_timer() - t


def datastore_append_entry():
    resp = requests.post(GAE_ENDPOINT, data={"val": DEFAULT_VALUE})
    return float(resp.text)


def cluster_append_entry(cluster_rpc_client):
    global CLUSTER_ACK
    res = cluster_rpc_client.append_entry(DEFAULT_VALUE)
    while CLUSTER_ACK is None:
        pass
    time = CLUSTER_ACK - res
    CLUSTER_ACK = None
    return time


def cluster_append_complete(new_current_value, time):
    global CLUSTER_ACK
    CLUSTER_ACK = time
    return None


# class used to implement different append requests for different algorithms
class TestManager:
    def __init__(self, algorithm_host, algorithm, algorithm_port):
        self.algorithm = algorithm
        self.algorithm_port = algorithm_port

        if algorithm == "rethinkdb":
            self.rdb_connection = r.connect('localhost', self.algorithm_port)
            logging.info("Connection with RethinkDB successful")
            rethinkdb_setup(self.rdb_connection)
            self.appendFunction = partial(rethinkdb_append_entry, self.rdb_connection)
        elif algorithm == "paxos" or algorithm == "pso":
            if algorithm_host == '\'\'' or algorithm_host == '':
                algorithm_host = '127.0.0.1'
            self.cluster_rpc_client = ServerProxy("http://{}:{}".format(algorithm_host, CLUSTER_APPEND_PORT),
                                                  allow_none=True)
            self.appendFunction = partial(cluster_append_entry, self.cluster_rpc_client)
        elif algorithm == "datastore":
            self.appendFunction = partial(datastore_append_entry)

    # wrapper used to execute multiple operations and register times
    def run(self, times):
        results = []
        while len(results) < times:
            try:
                results.append(self.appendFunction())
            except Exception as e:
                logging.error(e)
        return results


def run_test_server(server_port, algorithm, algorithm_port):
    logging.basicConfig(filename='test_daemon_debug.log', level=logging.DEBUG)
    server = MultiThreadXMLRPCServer((server_port, TEST_DAEMON_PORT), allow_none=True)
    test_manager = TestManager(server_port, algorithm, algorithm_port)
    server.register_function(test_manager.run, "run")
    server.register_function(cluster_append_complete, "cluster_append_complete")
    server.serve_forever()


if __name__ == "__main__":
    # argv[1] = IP address of the machine running this script (where the test daemon will be started)
    # argv[2] = consensus algorithm
    # argv[3] = the port of process running the algorithm when different from the default one
    run_test_server(sys.argv[1], sys.argv[2], sys.argv[3])
