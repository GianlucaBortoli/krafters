#!/usr/bin/python3.4

# Listen for test_executor
# argv[1] = IP address of the machine running this script (where the test daemon will be started)
# argv[2] = consensus algorithm
# argv[3] = the driver port for rethinkdb if needed

from xmlrpc.server import SimpleXMLRPCServer
import rethinkdb as r
import sys
import time
import logging

# NOTE DO NOT ADD EXTERNAL DEPENDENCIES: THIS SCRIPT HAS TO BE EXECUTED IN A STANDALONE WAY ON VM STARTUP

# some useful constants
TEST_DAEMON_PORT = 12346

# rethinkdb things
CONSENSUS_ALGORITHM_PORT = 12348
RETHINKDB_DB_NAME = 'test'
RETHINKDB_TABLE_NAME = 'test'
GCE_RETHINKDB_PORTS = {
    "driver_port": CONSENSUS_ALGORITHM_PORT,
    "cluster_port": CONSENSUS_ALGORITHM_PORT + 1,
    "http_port": CONSENSUS_ALGORITHM_PORT + 2
}


def rethinkdbSetup(host, port):
    try:
        connection = r.connect(host, port)
        logging.info("Connection with rethinkdb successful")
        # r.db_create(RETHINKDB_DB_NAME).run(connection)
        logging.info("Database {} created".format(RETHINKDB_DB_NAME))
        r.db(RETHINKDB_DB_NAME).table_create(RETHINKDB_TABLE_NAME).run(connection)
        logging.info('Db {} and table {} created successfully'.format(RETHINKDB_DB_NAME, RETHINKDB_TABLE_NAME))
    except:
        logging.error('Database {} already exists'.format(RETHINKDB_DB_NAME))
    finally:
        connection.close()


def rethinkdbAppendEntry(connection):
    value = {'key': 'value'}
    try:
        r.table(RETHINKDB_TABLE_NAME).insert(value, conflict='replace').run(connection)
        logging.info('key added')
    except:
        logging.error('{} not added'.format(value))


def psoAppendEntry():
    # TODO: implement me
    pass


def paxosAppendEntry():
    # TODO: implement me
    pass


# class used to implement different append requests for different algorithms
class TestManager:
    def __init__(self, algorithm, driver_port):
        self.algorithm = algorithm
        self.driver_port = driver_port
        self.connection = None

        if algorithm == "rethinkdb":
            rethinkdbSetup('localhost', driver_port)
            self.connection = r.connect('localhost', self.driver_port)

    # performs a single fundamental operation according to the selected algorithm
    def run_operation(self):
        if self.algorithm == "pso":
            psoAppendEntry()
        elif self.algorithm == "rethinkdb":
            rethinkdbAppendEntry(self.connection)
        elif self.algorithm == "paxos":
            paxosAppendEntry()
        else:
            logging.error('Algorithm {} not recognized'.format(self.algorithm))
            sys.exit()

    # wrapper used to execute multiple operations and register times
    def run(self, times):
        results = []

        for _ in range(0, times):
            t = time.perf_counter()
            self.run_operation()
            results.append(time.perf_counter() - t)

        # close rethinkdb connection
        #self.connection.close()
        return results


def main():
    logging.basicConfig(filename='test_daemon_debug.log', level=logging.DEBUG)
    server = SimpleXMLRPCServer((sys.argv[1], TEST_DAEMON_PORT), allow_none=True)

    # instantiate the test class
    if len(sys.argv) == 4:
        # I received also the 3rd argument (aka driver port) only if this is called
        # by rethinkdb
        test_manager = TestManager(sys.argv[2], sys.argv[3])
    else:
        # o.w. pso/paxos called it, so driver port is set but completely useless
        test_manager = TestManager(sys.argv[2], 0)

    # serve the run method
    server.register_function(test_manager.run, "run")
    # and serve forever
    server.serve_forever()


if __name__ == "__main__":
    main()
