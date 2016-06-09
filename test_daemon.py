#!/usr/bin/python3.4

# Listen for test_executor
# argv[1] = IP address of the machine running this script (where the test daemon will be started)
# argv[2] = consensus algorithm

from xmlrpc.server import SimpleXMLRPCServer
import sys
import time

# NOTE DO NOT ADD EXTERNAL DEPENDENCIES: THIS SCRIPT HAS TO BE EXECUTED IN A STANDALONE WAY ON VM STARTUP

TEST_DAEMON_PORT = 12346


# class used to implement different append requests for different algorithms
class TestManager:
    # default algorithm is not defined
    algorithm = "undef"

    def __init__(self, algorithm):
        self.algorithm = algorithm

    # performs a single fundamental operation according to the selected algorithm
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
    server = SimpleXMLRPCServer((sys.argv[1], TEST_DAEMON_PORT))
    # instantiate the test class
    test_manager = TestManager(sys.argv[2])
    # serve the run method
    server.register_function(test_manager.run, "run")
    # and serve forever
    server.serve_forever()


if __name__ == "__main__":
    main()
