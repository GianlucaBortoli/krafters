#!/usr/bin/python3.4

# Daemon listening for test_executor commands

from functools import partial
from xmlrpc.server import SimpleXMLRPCServer
import rethinkdb as r
import sys
import time
import logging
# NOTE DO NOT ADD EXTERNAL DEPENDENCIES: THIS SCRIPT HAS TO BE EXECUTED IN A STANDALONE WAY ON VM STARTUP

TEST_DAEMON_PORT = 12346
RETHINKDB_DB_NAME = 'test'
RETHINKDB_TABLE_NAME = 'test'


def rethinkdbSetup(connection):
    try:
        # r.db_create(RETHINKDB_DB_NAME).run(connection)
        logging.info("Database {} created".format(RETHINKDB_DB_NAME))
        r.db(RETHINKDB_DB_NAME).table_create(RETHINKDB_TABLE_NAME).run(connection)
        logging.info('Db {} and table {} created successfully'.format(RETHINKDB_DB_NAME, RETHINKDB_TABLE_NAME))
    except:
        logging.warning('Database {} already exists'.format(RETHINKDB_DB_NAME))


def rethinkdbAppendEntry(connection):
    value = {'key': 'value'}
    try:
        r.table(RETHINKDB_TABLE_NAME).insert(value, conflict='replace').run(connection)
        logging.info('key added')
    except:
        logging.error('{} not added'.format(value))


# class used to implement different append requests for different algorithms
class TestManager:
    def __init__(self, algorithm, algorithm_port):
        self.algorithm = algorithm
        self.algorithm_port = algorithm_port

        if algorithm == "rethinkdb":
            self.rdb_connection = r.connect('localhost', self.algorithm_port)
            logging.info("Connection with RethinkDB successful")
            rethinkdbSetup(self.rdb_connection)
            self.appendFunction = partial(rethinkdbAppendEntry, self.rdb_connection)

    # wrapper used to execute multiple operations and register times
    def run(self, times):
        results = []
        for _ in range(0, times):
            t = time.perf_counter()
            self.appendFunction()
            results.append(time.perf_counter() - t)
        return results


def run_test_server(server_port, algorithm, algorithm_port):
    logging.basicConfig(filename='test_daemon_debug.log', level=logging.DEBUG)
    server = SimpleXMLRPCServer((server_port, TEST_DAEMON_PORT), allow_none=True)
    test_manager = TestManager(algorithm, algorithm_port)
    server.register_function(test_manager.run, "run")
    server.serve_forever()


if __name__ == "__main__":
    # argv[1] = IP address of the machine running this script (where the test daemon will be started)
    # argv[2] = consensus algorithm
    # argv[3] = the port of process running the algorithm when different from the default one
    run_test_server(sys.argv[1], sys.argv[2], sys.argv[3])
