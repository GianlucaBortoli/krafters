import json
import subprocess
import logging
import sys
from xmlrpc.server import SimpleXMLRPCServer


class NetemManager:
    interface = ""
    host = {}
    peers = []

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
    create_peer_class_commands = ["sudo tc class add dev %INTERFACE% parent 1: classid 1:%SID% htb rate " + bandwidth,
                                  "sudo tc class add dev %INTERFACE% parent 1: classid 1:%DID% htb rate " + bandwidth]
    create_peer_qdisc_commands = ["sudo tc qdisc add dev %INTERFACE% parent 1:%SID% handle %SID%: netem delay 0ms",
                                  "sudo tc qdisc add dev %INTERFACE% parent 1:%DID% handle %DID%: netem delay 0ms"]
    create_peer_filter_commands = [
        "sudo tc filter add dev %INTERFACE% protocol ip u32 " +
        "match ip sport %PPORT% 0xffff " +
        "match ip src %PADDRESS%/32 " +
        "match ip dport %HPORT% 0xffff " +
        "match ip dst %HADDRESS%/32 " +
        "flowid 1:%SID% ",
        "sudo tc filter add dev %INTERFACE% protocol ip u32 " +
        "match ip dport %PPORT% 0xffff " +
        "match ip dst %PADDRESS%/32 " +
        "match ip sport %HPORT% 0xffff " +
        "match ip src %HADDRESS%/32 " +
        "flowid 1:%DID%"]
    modify_incoming_connections_commands = ["sudo tc qdisc change dev %INTERFACE% parent 1:%PID%1 netem %NETEM%"]
    modify_outgoing_connections_commands = ["sudo tc qdisc change dev %INTERFACE% parent 1:%PID%2 netem %NETEM%"]

    def __init__(self, interface, host, peers):
        logging.basicConfig(filename='debug.log', level=logging.DEBUG)
        self.interface = str(interface)
        self.host = host
        self.peers = peers

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
        err = self.run_commands(self.create_root_commands, {self.interface_token: self.interface})
        if err:
            logging.error("error creating root!\n\t" + err)
            return False
        else:
            return True

    def clean_all_qdisc(self):
        err = self.run_commands(self.delete_root_commands, {self.interface_token: self.interface})
        if err:
            logging.error("error removing root!\n\t" + err)
            return False
        else:
            return True

    def create_peer_qdisc(self, peer):
        id = str(self.host["id"])
        qid = str(peer["id"])
        source_id = id + qid + "1"
        destination_id = id + qid + "2"
        peer_port = str(peer["port"])
        peer_address = str(peer["address"])
        err = self.run_commands(self.create_peer_class_commands, {self.interface_token: self.interface,
                                                                  self.source_id_token: source_id,
                                                                  self.destination_id_token: destination_id})
        if err:
            logging.error("error creating class for peer " + str(peer) + "!\n\t" + err)
            return False
        else:
            err = self.run_commands(self.create_peer_qdisc_commands, {self.interface_token: self.interface,
                                                                      self.source_id_token: source_id,
                                                                      self.destination_id_token: destination_id})
            if err:
                logging.error("error creating qdisc for peer " + str(peer) + "!\n\t" + err)
                return False
            else:
                err = self.run_commands(self.create_peer_filter_commands, {self.interface_token: self.interface,
                                                                           self.source_id_token: source_id,
                                                                           self.destination_id_token: destination_id,
                                                                           self.peer_port_token: peer_port,
                                                                           self.peer_address_token: peer_address,
                                                                           self.host_port_token: str(self.host["port"]),
                                                                           self.host_address_token: str(
                                                                                   self.host["address"])})
                if err:
                    logging.error("error creating filter for peer " + str(peer) + "!\n\t" + err)
                    return False
                else:
                    return True

    def modify_incoming_connection(self, peer_id, netem_command):
        err = self.run_commands(self.modify_incoming_connections_commands, {self.interface_token: self.interface,
                                                                            self.peer_id_token: str(
                                                                                    self.host["id"]) + peer_id,
                                                                            self.netem_token: netem_command})
        if err:
            logging.error("error modifying incoming connection from peer " + peer_id + "!\n\t" + err)
            return False
        else:
            return True

    def modify_outgoing_connection(self, peer_id, netem_command):
        err = self.run_commands(self.modify_outgoing_connections_commands, {self.interface_token: self.interface,
                                                                            self.peer_id_token: str(
                                                                                    self.host["id"]) + peer_id,
                                                                            self.netem_token: netem_command})
        if err:
            logging.error("error modifying outgoing connection to peer " + peer_id + "!\n\t" + err)
            return False
        else:
            return True

    def modify_connection(self, peer_id, netem_command):
        return self.modify_incoming_connection(peer_id, netem_command) and self.modify_outgoing_connection(peer_id, netem_command)

    def init_qdisc(self):
        result = True
        for peer in self.peers:
            result = result and self.create_peer_qdisc(peer)
        return result


def run_rpc_server(configuration):
    netem_manager = NetemManager(configuration["interface"], configuration["host"], configuration["peers"])

    # usage examples
    # netem_manager.modify_incoming_connection("2", "loss 90%")
    # netem_manager.modify_outgoing_connection("3", "delay 400ms")
    # netem_manager.modify_connection("4", "loss 50% delay 200ms 100ms")

    print(configuration["rpcPort"])
    server = SimpleXMLRPCServer((str(configuration["host"]["address"]), configuration["rpcPort"]))
    server.register_instance(netem_manager)
    server.serve_forever()


def main():
    try:
        # Loads configuration file
        with open(sys.argv[1]) as configuration_file:
            configuration = json.load(configuration_file)
            run_rpc_server(configuration)
    except:
        print((sys.argv[1] + " is not a valid JSON file"))
        exit(1)


if __name__ == "__main__":
    main()
