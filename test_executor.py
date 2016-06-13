#!/usr/bin/python3.4

# argv[1] = masterConfig.json
# argv[2] = test file
# argv[3] (optional) = output file

import json
import logging
import random
import sys
from xmlrpc.client import ServerProxy as Server
import re
import csv


# class used to handle netem underlying network
class NetemMaster:
    nodes_rpc = {}

    def __init__(self, nodes):
        self.nodes_rpc = {str(n["id"]): Server("http://{}:{}".format(n["address"], str(n["rpcPort"]))) for n in nodes}

    # modify connection to source to target using netem_command
    def modify_connection(self, source, target, netem_command, bidirectional=False):
        if str(source) == str(target):
            return
        if bidirectional:
            print("modify connection from " + str(source) + " to " + str(
                    target) + " '" + netem_command + "' bidirectional")
            # self.nodes_rpc[source].modify_outgoing_connection(target, netem_command)
            # self.nodes_rpc[target].modify_outgoing_connection(source, netem_command)
        else:
            print("modify connection from " + str(source) + " to " + str(target) + " '" + netem_command + "'")
            # self.nodes_rpc[source].modify_outgoing_connection(target, netem_command)

    # apply netem_command to multiple commands
    def modify_connections(self, sources, targets, netem_command, bidirectional=False):
        for source in sources:
            for target in targets:
                self.modify_connection(source, target, netem_command, bidirectional)


class TestParser:
    # pattern matching for commands
    modify_link_pattern = re.compile(
            " *from +(all +|(([0-9]+|rand) +)+)to +(all +|(([0-9]+|rand) +)+)(bidirectional +)?set +[a-z]+.*")
    modify_random_link_pattern = re.compile(" *on +[0-9]+ +connections? +(bidirectional +)?set +[a-z]+.*")
    reset_pattern = re.compile(" *reset *")
    run_pattern = re.compile(" *run +[0-9]+ *")
    do_pattern = re.compile(" *do *")
    times_pattern = re.compile(" *[0-9]+ +times? *")

    netem_master = {}
    test_daemon = {}
    nodes_number = 0
    csv_writer = {}

    def __init__(self, netem_master, nodes_number, test_daemon):
        self.netem_master = netem_master
        self.nodes_number = nodes_number
        self.test_daemon = test_daemon

    # returns first number of a line, used for n times command
    def get_times(self, test_line):
        tokens = test_line.split()
        times = int(tokens[0])
        return times

    # sets output file path
    def set_output_path(self, output_path):
        self.csv_writer = csv.writer(open(output_path, 'w', newline=''))

    # calls run function on test_daemon and saves results to csv
    def run_command(self, n_op):
        self.csv_writer.writerow(self.test_daemon.run(n_op))

    # calls netem master to change connection rules
    def modify_link_from_to(self, sources, targets, netem_command, bidirectional):
        self.netem_master.modify_connections(sources, targets, netem_command, bidirectional)

    # generates random id and change rules
    def modify_random_link(self, connection_number, netem_command, bidirectional):
        selected = set()
        n_selected = 0
        while n_selected < connection_number:
            source = random.randrange(0, self.nodes_number)
            target = source
            while target == source:
                target = random.randrange(0, self.nodes_number)
            if not str(source) + "-" + str(target) in selected:
                self.netem_master.modify_connection(source, target, netem_command, bidirectional)
                if bidirectional:
                    selected.add(str(target) + "-" + str(source))
                selected.add(str(source) + "-" + str(target))
                n_selected += 1

    # resets every connection, related to reset command
    def reset(self):
        for i in range(0, self.nodes_number):
            for j in range(i, self.nodes_number):
                self.netem_master.modify_connection(i, j, "", True)

    # resolve "rand" and "all" keywords in commands
    def resolve_ids(self, ids):
        referred_ids = set()
        random_values_count = 0
        random_values = []
        for key, values in ids.items():
            for value in values:
                if value.isdigit():
                    referred_ids.add(int(value))
                if value == "rand":
                    random_values_count += 1
        while random_values_count > 0:
            ran = random.randrange(self.nodes_number)
            if ran not in referred_ids:
                referred_ids.add(ran)
                random_values.append(ran)
                random_values_count -= 1
        for key, values in ids.items():
            values_to_remove = []
            offset = 0
            for i in range(0, len(values)):
                if values[i] == "rand":
                    values_to_remove.append(i)
                    ids[key].append(random_values[random_values_count])
                    random_values_count += 1
                elif values[i] == "all":
                    del values[i]
                    for j in range(0, self.nodes_number):
                        ids[key].append(str(j))
                elif not values[i].isdigit():
                    print("unknown id '" + values[i] + "' : it will be removed")
                    values_to_remove.append(i)
            for value_to_remove in values_to_remove:
                del values[value_to_remove - offset]
                offset += 1

    # function used to extract parameters from commands
    def get_params(self, test_line, operation_name):
        params = {"ids": {}}
        if operation_name == "run":
            tokens = test_line.split()
            params["nop"] = tokens[1]
        elif operation_name == "link":
            netem_command = test_line.split("set")[1]
            first_part = test_line.split("set")[0]
            if " bidirectional " in first_part:
                first_part = first_part.replace(" bidirectional", "")
                params["bidirectional"] = True
            else:
                params["bidirectional"] = False
            source_tokens = first_part.split("to")[0].replace("from", "").split()
            destination_tokens = first_part.split("to")[1].split()
            params["netem_command"] = netem_command
            params["ids"]["sources"] = source_tokens
            params["ids"]["targets"] = destination_tokens
            self.resolve_ids(params["ids"])
        elif operation_name == "rlink":
            netem_command = test_line.split("set")[1]
            first_part = test_line.split("set")[0]
            if " bidirectional " in first_part:
                first_part = first_part.replace(" bidirectional", "")
                params["bidirectional"] = True
            else:
                params["bidirectional"] = False
            connection_number = int(first_part.replace("on", "").split()[0])
            params["netem_command"] = netem_command
            params["connection_number"] = connection_number
        return params

    # runs test file's command one after the other
    def run_test(self, test_file):
        do_open = -1
        pointers = []
        index = 0
        while index < len(test_file):
            try:
                test_line = test_file[index]
                test_line = test_line.rstrip()

                if not test_line:
                    pass
                elif self.modify_link_pattern.match(test_line):
                    params = self.get_params(test_line, "link")
                    self.modify_link_from_to(params["ids"]["sources"], params["ids"]["targets"],
                                             params["netem_command"],
                                             params["bidirectional"])
                elif self.modify_random_link_pattern.match(test_line):
                    params = self.get_params(test_line, "rlink")
                    self.modify_random_link(params["connection_number"], params["netem_command"],
                                            params["bidirectional"])
                elif self.reset_pattern.match(test_line):
                    self.reset()
                elif self.run_pattern.match(test_line):
                    params = self.get_params(test_line, "run")
                    try:
                        self.run_command(int(params["nop"]))
                    except:
                        print("Unable to connect to test_daemon")
                        break
                elif self.do_pattern.match(test_line):
                    do_open += 1
                    if len(pointers) < do_open + 1:
                        pointers.append({"start": index, "repetition": 1})
                    else:
                        pointers[do_open]["start"] = index
                        pointers[do_open]["repetition"] = 1
                elif self.times_pattern.match(test_line):
                    if pointers[do_open]["repetition"] < self.get_times(test_line):
                        index = pointers[do_open]["start"]
                        pointers[do_open]["repetition"] += 1
                    else:
                        do_open -= 1
                else:
                    print("Command \n\t>'" + str(test_line) + "'\n at line " + str(index + 1) + " unknown")
                    break
                index += 1
            except:
                print(
                    "Command \n\t>'" + str(test_line) + "'\n at line " + str(index + 1) + " is not well formed!")
                break


def main():
    logging.basicConfig(filename='debug.log', level=logging.DEBUG)
    try:
        # Loads configuration file
        with open(sys.argv[1]) as configuration_file:
            conf = json.load(configuration_file)

            server = Server("http://" + conf["testDaemon"])
            test_parser = TestParser(NetemMaster(conf["nodes"]), len(conf["nodes"]), server)

            try:
                # loads test file
                with open(sys.argv[2]) as f:
                    test_file = f.readlines()
                output_file_path = sys.argv[2] + ".csv"
                # if 3rd argument is specified, it is used as output file path
                if sys.argv[3]:
                    output_file_path = sys.argv[3]

                # sets output csv file path
                test_parser.set_output_path(output_file_path)
                # runs test specified
                test_parser.run_test(test_file)
            except "FileNotFoundError":
                print(sys.argv[1] + " is not a valid test file")
                exit(1)
    except "FileNotFoundError":
        print(sys.argv[1] + " is not a valid JSON file")
        exit(1)
    except:
        pass


if __name__ == "__main__":
    main()
