from xmlrpc.server import SimpleXMLRPCServer
import sys
import json


def main():
    # TODO run daemon waiting for tester calls

    # Foo binding of useless server (required to test the provisioner). Must be deleted.
    try:
        # Loads configuration file
        with open(sys.argv[1]) as configuration_file:
            configuration = json.load(configuration_file)
            server = SimpleXMLRPCServer((str(configuration["host"]["address"]), int(sys.argv[2])))
            server.serve_forever()
    except Exception as e:
        print((sys.argv[1] + " is not a valid JSON file"))
        print(e)
        exit(2)

if __name__ == "__main__":
    main()
