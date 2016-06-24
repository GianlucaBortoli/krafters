#!/usr/bin/python3.4

import json
import subprocess
import logging
import sys
from xmlrpc.server import SimpleXMLRPCServer


# NOTE DO NOT ADD EXTERNAL DEPENDENCIES: THIS SCRIPT HAS TO BE EXECUTED IN A STANDALONE WAY ON VM STARTUP


class NetemManager:
    interface = ""
    host = {}
    peers = []
    mode = ""

    interface_token = "%INTERFACE%"
    source_id_token = "%SID%"
    destination_id_token = "%DID%"
    peer_port_token = "%PPORT%"
    peer_address_token = "%PADDRESS%"
    host_port_token = "%HPORT%"
    host_address_token = "%HADDRESS%"
    peer_id_token = "%PID%"
    netem_token = "%NETEM%"

    bandwidth = "100Mbps"

    create_root_commands = ["sudo tc qdisc add dev %INTERFACE% root handle 1: htb"]
    delete_root_commands = ["sudo tc qdisc del dev %INTERFACE% root",
                            "sudo tc -s qdisc ls dev %INTERFACE%"]
    create_peer_class_commands = ["sudo tc class add dev %INTERFACE% parent 1: classid 1:%DID% htb rate " + bandwidth]
    create_peer_qdisc_commands = ["sudo tc qdisc add dev %INTERFACE% parent 1:%DID% handle %DID%: netem delay 0ms"]
    create_peer_filter_commands_local = [
        "sudo tc filter add dev %INTERFACE% protocol ip u32 " +
        "match ip dport %PPORT% 0xffff " +
        "flowid 1:%DID%"]
    create_peer_filter_commands_gce = [
        "sudo tc filter add dev %INTERFACE% protocol ip u32 " +
        "match ip dst %PADDRESS%/32 " +
        "flowid 1:%DID%"]
    modify_outgoing_connections_commands = ["sudo tc qdisc change dev %INTERFACE% parent 1:%PID%2 netem %NETEM%"]

    def __init__(self, interface, host, peers, mode):
        logging.basicConfig(filename=('debug' + str(host["id"])) + '.log', level=logging.DEBUG)
        self.interface = str(interface)
        self.host = host
        self.peers = peers
        self.mode = mode

    def run(self, command):
        logging.info(command)
        p = subprocess.Popen(command,
                             stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE,
                             shell=True)
        out, err = p.communicate()
        return err

    def run_commands(self, commands, substitution_map={}):
        error = ""
        for command in commands:
            for token, value in substitution_map.items():
                command = command.replace(token, value)
            e = self.run(command)
            if e:
                error += e + "\n"
        return error

    def create_root_qdisc(self):
        print("Creating root")
        try:
            err = self.run_commands(self.create_root_commands, {self.interface_token: self.interface})
            if err:
                logging.error("error creating root!\n\t" + err)
                return False
            else:
                return True
        except:
            return False

    def clean_all_qdisc(self):
        print("Cleaning all qdiscs")
        try:
            err = self.run_commands(self.delete_root_commands, {self.interface_token: self.interface})
            if err:
                logging.error("error removing root!\n\t" + err)
                return False
            else:
                return True
        except:
            return False

    def create_peer_qdisc(self, peer):
        try:
            id = str(self.host["id"])
            qid = str(peer["id"])
            destination_id = id + qid + "2"

            err = self.run_commands(self.create_peer_class_commands, {self.interface_token: self.interface,
                                                                      self.destination_id_token: destination_id})
            if err:
                logging.error("error creating class for peer " + str(peer) + "!\n\t" + err)
                return False
            else:
                err = self.run_commands(self.create_peer_qdisc_commands, {self.interface_token: self.interface,
                                                                          self.destination_id_token: destination_id})
                if err:
                    logging.error("error creating qdisc for peer " + str(peer) + "!\n\t" + err)
                    return False
                else:
                    if self.mode == "local":
                        for peer_port in peer["portToLock"]:
                            err = self.run_commands(self.create_peer_filter_commands_local,
                                                    {self.interface_token: self.interface,
                                                     self.destination_id_token: destination_id,
                                                     self.peer_port_token: str(peer_port)})
                            if err:
                                logging.error("error creating filter for peer " + str(peer) + "!\n\t" + err)
                                return False
                        return True
                    else:
                        for peer_address in peer["addressesToLock"]:
                            err = self.run_commands(self.create_peer_filter_commands_gce,
                                                    {self.interface_token: self.interface,
                                                     self.destination_id_token: destination_id,
                                                     self.peer_address_token: str(peer_address)})
                            if err:
                                logging.error("error creating filter for peer " + str(peer) + "!\n\t" + err)
                                return False
                        return True

        except:
            return False

    def modify_outgoing_connection(self, peer_id, netem_command):
        print("Command '" + netem_command + "' to outgoing connection received")
        try:
            err = self.run_commands(self.modify_outgoing_connections_commands, {self.interface_token: self.interface,
                                                                                self.peer_id_token: str(
                                                                                        self.host["id"]) + peer_id,
                                                                                self.netem_token: netem_command})
            if err:
                logging.error("error modifying outgoing connection to peer " + peer_id + "!\n\t" + err)
                return False
            else:
                return True
        except:
            return False

    def init_qdisc(self):
        print("Initializing peer qdiscs")
        result = True
        for peer in self.peers:
            result = result and self.create_peer_qdisc(peer)
        return result


def run_rpc_server(configuration):
    netem_manager = NetemManager(configuration["interface"], configuration["host"], configuration["peers"], configuration["mode"])

    server = SimpleXMLRPCServer(("", configuration["rpcPort"]))
    server.register_instance(netem_manager)
    server.serve_forever()


def main():
    try:
        # Loads configuration file
        with open(sys.argv[1]) as configuration_file:
            configuration = json.load(configuration_file)
            run_rpc_server(configuration)
    except Exception as e:
        print((sys.argv[1] + " is not a valid JSON file"))
        print(e)
        exit(2)


if __name__ == "__main__":
    main()
