#!/usr/bin/python3.4


import argparse
from functools import partial
from xmlrpc.client import ServerProxy as Server
import json
import random
import re
import csv

SYNTAX_ERROR = "Syntax Error"
ID_ERROR = "Id Error"
LOCAL_EXECUTION_ERROR = "Local Execution Error"
NETEM_ERROR = "Netem Error"


# Custom exception
class TestException(Exception):
    line = -1
    message = "undefined"
    type = "undefined"

    def __init__(self, type, message, line=-1):
        self.line = line
        self.message = message
        self.type = type

    def set_line(self, line):
        self.line = line

    def is_line_defined(self):
        return self.line > 0

    def __str__(self):
        return "[{}] At line {}: {}\n".format(self.type, self.line, self.message)

# Calls add lines to exception
def attach_line(fun, line):
    try:
        if fun:
            f = fun()
            return partial(attach_line, f, line)
    except TestException as e:
        if not e.is_line_defined():
            e.set_line(line)
            raise e
    except:
        pass


# class used to handle netem underlying network
class NetemMaster:
    nodes_rpc = {}

    def __init__(self, nodes):
        for n in nodes:
            self.nodes_rpc[str(n["id"])] = Server("http://{}:{}".format(n["address"], str(n["rpcPort"])))
        for n in nodes:
            self.nodes_rpc[str(n["id"])].clean_all_qdisc()
            self.nodes_rpc[str(n["id"])].create_root_qdisc()
        for n in nodes:
            if not self.nodes_rpc[str(n["id"])].init_qdisc():
                raise Exception("[{}] Error initializing qdiscs".format(NETEM_ERROR))

    # modify connection from source to target using netem_command
    def modify_connection(self, source, target, netem_command, bidirectional=False):

        if str(source) == str(target):
            return
        if bidirectional:
            print("[Netem] Modify connection from {} to {} both directions with command '{}'".format(str(source), str(
                    target), netem_command))
            if not self.nodes_rpc[str(source)].modify_outgoing_connection(str(target), netem_command) or not \
                    self.nodes_rpc[str(target)].modify_outgoing_connection(str(source), netem_command):
                raise TestException(NETEM_ERROR, "'{}' is not a valid netem command".format(netem_command))
        else:
            print("[Netem] Modify connection from {} to {} with command '{}'".format(str(source), str(
                    target), netem_command))
            if not self.nodes_rpc[str(source)].modify_outgoing_connection(str(target), netem_command):
                raise TestException(NETEM_ERROR, "'{}' is not a valid netem command".format(netem_command))

    # apply netem_command to multiple commands
    def modify_connections(self, sources, targets, netem_command, bidirectional=False):
        for source in sources:
            for target in targets:
                self.modify_connection(source, target, netem_command, bidirectional)


class CommandUnwrapper:
    nodes_number = -1
    executor = {}
    local_execution = False

    def __init__(self, nodes_number, executor, local_execution=False):
        self.nodes_number = nodes_number
        self.executor = executor
        self.local_execution = local_execution

    def run_command(self, n_op):
        # no bound in operation number
        return partial(self.executor.run_command, n_op)

    # checks if ids are valid
    def modify_link_from_to(self, sources, targets, netem_command, bidirectional):
        sources, targets = self.resolve_ids(sources, targets)
        # if it's a local execution checks if the parameters are compatible
        if self.local_execution and (
                        len(sources) < self.nodes_number - 1 or (bidirectional and targets < self.nodes_number - 1)):
            # if not raises an exception
            raise TestException(LOCAL_EXECUTION_ERROR, "impossible to specify single sources in local commands")
        return partial(self.executor.modify_link_from_to, sources, targets, netem_command, bidirectional)

    # generates random id for links
    def modify_random_link(self, connection_number, netem_command, bidirectional):
        selected = set()
        n_selected = 0
        sources = set()
        targets = set()
        while n_selected < connection_number:
            source = random.randrange(0, self.nodes_number) + 1
            target = source
            while target == source:
                target = random.randrange(0, self.nodes_number) + 1
            if not str(source) + "-" + str(target) in selected:
                sources.add(source)
                targets.add(target)
                if bidirectional:
                    selected.add(str(target) + "-" + str(source))
                selected.add(str(source) + "-" + str(target))
                n_selected += 1
        return self.modify_link_from_to(list(sources), list(targets), netem_command, bidirectional)

    # resets every connection, related to reset command
    def reset(self):
        return partial(self.modify_link_from_to(["all"], ["all"], "delay 0ms", False))

    # resolve "all" and "rand" using given random_values
    def resolve(self, ids, random_values):
        result = set()
        for value in ids:
            if value.isdigit():
                integer = int(value)
                if integer > self.nodes_number:
                    raise TestException(ID_ERROR, "Id {} out of range ".format(str(value)))
                result.add(integer)
            elif value == "rand":
                result.add(random_values.pop(0))
            elif value == "all":
                for i in range(1, self.nodes_number + 1):
                    result.add(i)
            else:
                raise TestException(ID_ERROR, "Id {} is not valid".format(str(value)))
        return result

    def resolve_ids(self, sources, targets):
        referred_ids = set()
        random_values_count = 0
        random_values = []

        # checks which id has been used
        for value in sources + targets:
            if value.isdigit():
                integer = int(value)
                referred_ids.add(integer)
            if value == "rand":
                random_values_count += 1

        if len(referred_ids) + random_values_count > self.nodes_number:
            raise TestException(ID_ERROR, "'Rand' keyword has been used too many times!")

        # generates random numbers to resolve "rand"
        while random_values_count > 0:
            ran = random.randrange(self.nodes_number) + 1
            if ran not in referred_ids:
                referred_ids.add(ran)
                random_values.append(ran)
                random_values_count -= 1

        # replaces "rand" and "all" in sources
        r_sources = self.resolve(sources, random_values)

        # replaces "rand" and "all" in targets
        r_targets = self.resolve(targets, random_values)

        return r_sources, r_targets


class Executor:
    test_daemon = {}
    csv_writer = {}
    netem_master = {}

    def __init__(self, test_daemon, netem_master, csv_file_path):
        self.test_daemon = test_daemon
        self.csv_writer = csv.writer(open(csv_file_path, 'w', newline=''))
        self.netem_master = netem_master

    # calls run function on test_daemon and saves results to csv
    def run_command(self, n_op):
        print("[Run] Running {} operations".format(str(n_op)))
        self.csv_writer.writerow(self.test_daemon.run(n_op))
        print("[Run] Done")

    # calls netem master to change connection rules
    def modify_link_from_to(self, sources, targets, netem_command, bidirectional):
        self.netem_master.modify_connections(sources, targets, netem_command, bidirectional)


class Parser:
    # pattern matching for commands
    modify_link_pattern = re.compile(
            " *from +(all +|(([0-9]+|rand) +)+)to +(all +|(([0-9]+|rand) +)+)(bidirectional +)?set +[a-z]+.*")
    modify_random_link_pattern = re.compile(" *on +[0-9]+ +connections? +(bidirectional +)?set +[a-z]+.*")
    reset_pattern = re.compile(" *reset *")
    run_pattern = re.compile(" *run +[0-9]+ *")
    do_pattern = re.compile(" *do *")
    times_pattern = re.compile(" *[0-9]+ +times? *")

    command_checker = {}

    def __init__(self, command_checker):
        self.command_checker = command_checker

    # returns first number of a line, used for n times command
    def get_times(self, test_line):
        tokens = test_line.split()
        times = int(tokens[0])
        return times

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

    # parses test file
    def parse(self, test_file):
        do_open = -1
        pointers = []
        index = 0
        commands_list = []
        while index < len(test_file):

            test_line = test_file[index]
            test_line = test_line.rstrip()

            unknown_command = False

            function = None
            arguments = []
            try:
                if not test_line:
                    pass
                elif self.modify_link_pattern.match(test_line):
                    params = self.get_params(test_line, "link")
                    function = self.command_checker.modify_link_from_to
                    arguments = [params["ids"]["sources"], params["ids"]["targets"], params["netem_command"],
                                 params["bidirectional"]]
                elif self.modify_random_link_pattern.match(test_line):
                    params = self.get_params(test_line, "rlink")
                    function = self.command_checker.modify_random_link
                    arguments = [params["connection_number"], params["netem_command"], params["bidirectional"]]
                elif self.reset_pattern.match(test_line):
                    function = partial(self.command_checker.reset)
                elif self.run_pattern.match(test_line):
                    params = self.get_params(test_line, "run")
                    function = self.command_checker.run_command
                    arguments = [int(params["nop"])]
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
                    unknown_command = True
            except Exception as e:
                raise TestException(SYNTAX_ERROR, "Syntax error in command '{}'".format(str(test_line)), index + 1)

            if unknown_command:
                raise TestException(SYNTAX_ERROR, "Command '{}' is unknown".format(str(test_line)), index + 1)

            if function:
                commands_list.append(partial(attach_line, partial(function, *arguments), index + 1))
            index += 1

        return commands_list


def main():
    argument_parser = argparse.ArgumentParser(description="Run a test file on the distributed system")
    argument_parser.add_argument("config_file_path", type=str,
                                 help="path to masterConfiguration file generated by provisioner.py")
    argument_parser.add_argument("test_file_path", type=str,
                                 help="test file to execute")
    argument_parser.add_argument("-o", "--output", type=str, dest="output_file_path",
                                 help="path of the output file")
    argument_parser.add_argument("-l", help="executes test in local mode", action="store_true")

    args = argument_parser.parse_args()

    # Loads configuration file
    try:
        with open(args.config_file_path) as configuration_file:
            conf = json.load(configuration_file)
    except FileNotFoundError:
        print("'{}' does not exist".format(args.config_file_path))
        exit(2)

    # Loads test file
    try:
        with open(args.test_file_path) as f:
            test_file_lines = f.readlines()
    except FileNotFoundError:
        print("'{}' does not exist".format(args.test_file_path))
        exit(2)

    # Connects to network managers
    try:
        netem_master = NetemMaster(conf["nodes"])
    except Exception as e:
        print("[Connection error] Error connecting to nodes network manager: {}".format(e))
        exit(1)

    # Connects to to test daemon
    try:
        if not conf["testDaemon"]:
            print("[Configuration Error] test daemon address has not been specified in '{}' ".format(
                args.config_file_path))
            exit(2)
        test_daemon = Server("http://" + conf["testDaemon"])
    except Exception as e:
        print("[Connection error] Error connecting to test daemon: on address {}".format(conf["testDaemon"]))
        exit(1)

    # Sets output file path
    output_file_path = args.test_file_path + ".csv"
    if args.output_file_path:
        output_file_path = args.output_file_path

    # Initialize Executor, Checker and Parser
    if not conf["nodes"]:
        print("[Configuration Error] nodes have not been specified correctly on '{}' configuration file".format(
            args.config_file_path))
        exit(2)
    executor = Executor(test_daemon, netem_master, output_file_path)
    command_checker = CommandUnwrapper(len(conf["nodes"]), executor, args.l)
    test_parser = Parser(command_checker)

    # Runs test file
    try:
        command_list = test_parser.parse(test_file_lines)
        while command_list:
            command = command_list.pop(0)()
            if command:
                command_list.append(command)
    except Exception as e:
        print(e)
        exit(1)

    command_checker.reset()
    print("\nRun completed successfully, results have been saved to {} !\n".format(output_file_path))


if __name__ == "__main__":
    main()
