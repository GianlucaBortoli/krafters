#!/usr/bin/python3.4

# Listen for test_executor
# port to listen to: 12346
# argv[1] = masterConfig.JSON

from xmlrpc.server import SimpleXMLRPCServer
import sys
import json

import time

# constants
RPC_LISTEN_PORT = 12346


# class used to implement different append requests for different algorithms
class TestManager:
    # default alforithm is not defined
    algorithm = "undef"

    def __init__(self, algorithm):
        self.algorithm = algorithm

    # performs a single foundamental operation according to the selected algorithm
    def run_operation(self):
        if self.algorithm == "pso":
            # TODO add specific operation here
            pass
        #TODO add here other algorithms implementations
        else:
            pass

    # wrapper used to execute multiple operations and register times
    def run(self, times):
        results = []
        for _ in range(0, times):
            t0 = time.clock()
            self.run_operation()
            results.append(time.clock() - t0)
        return results


def main():
    # Loads configuration file
    try:
        with open(sys.argv[1]) as configuration_file:
            configuration = json.load(configuration_file)

            # set up the rpc server
            server = SimpleXMLRPCServer(("127.0.0.1", RPC_LISTEN_PORT))
            # instantiate the test class
            test_manager = TestManager(configuration["algorithm"])
            # serve the run method
            server.register_function(test_manager.run, "run")
            # and serve forever
            server.serve_forever()
    except:
        print(" invalid masterConfiguration.json")
    #TODO add specific handlers for other exceptions


if __name__ == "__main__":
    main()
