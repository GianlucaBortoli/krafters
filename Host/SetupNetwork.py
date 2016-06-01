import json
import subprocess
import logging

import sys

interface_token = "%INTERFACE%"
source_id_token = "%SID%"
destination_id_token = "%DID%"
peer_port_token = "%PPORT%"
peer_address_token = "%PADDRESS%"
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
    "sudo tc filter add dev %INTERFACE% protocol ip u32 match ip sport %PPORT% 0xffff match ip src %PADDRESS%/32 flowid %SID% ",
    "sudo tc filter add dev %INTERFACE% protocol ip u32 match ip dport %PPORT% 0xffff match ip dst %PADDRESS%/32 flowid %DID%"]
modify_incoming_connections_commands = ["sudo tc qdisc change dev %INTERFACE% parent 1:%PID%1 netem %NETEM%"]
modify_outgoing_connections_commands = ["sudo tc qdisc change dev %INTERFACE% parent 1:%PID%2 netem %NETEM%"]


def run(command):
    logging.info(command)
    p = subprocess.Popen(command,
                         stdout=subprocess.PIPE,
                         stderr=subprocess.PIPE,
                         shell=True)
    out, err = p.communicate()
    return err


def run_commands(commands, substitution_map={}):
    error = ""
    for command in commands:
        for token,value in substitution_map.iteritems():
            command = command.replace(token, value)
        e = run(command)
        if e:
            error += e + "\n"
    return error


def create_root_qdisc(interface):
    err = run_commands(create_root_commands, {interface_token: interface})
    if err:
        logging.error("error creating root!\n\t" + err)
        return False
    else:
        return True


def clean_all_qdisc(interface):
    err = run_commands(delete_root_commands, {interface_token: interface})
    if err:
        logging.error("error removing root!\n\t" + err)
        return False
    else:
        return True


def create_peer_qdisc(interface, peer):
    qid = str(peer["id"])
    source_id = qid + "1"
    destination_id = qid + "2"
    peer_port = str(peer["port"])
    peer_address = str(peer["address"])
    err = run_commands(create_peer_class_commands, {interface_token: interface,
                                                    source_id_token: source_id,
                                                    destination_id_token: destination_id})
    if err:
        logging.error("error creating class for peer " + str(peer) + "!\n\t" + err)
        return False
    else:
        err = run_commands(create_peer_qdisc_commands, {interface_token: interface,
                                                        source_id_token: source_id,
                                                        destination_id_token: destination_id})
        if err:
            logging.error("error creating qdisc for peer " + str(peer) + "!\n\t" + err)
            return False
        else:
            err = run_commands(create_peer_filter_commands, {interface_token: interface,
                                                             source_id_token: source_id,
                                                             destination_id_token: destination_id,
                                                             peer_port_token: peer_port,
                                                             peer_address_token: peer_address})
            if err:
                logging.error("error creating filter for peer " + str(peer) + "!\n\t" + err)
                return False
            else:
                return True


def modify_incoming_connection(interface,peer_id, netem):
    err = run_commands(modify_incoming_connections_commands, {interface_token: interface,
                                                              peer_id_token: peer_id,
                                                              netem_token: netem})
    if err:
        logging.error("error modifying incoming connection from peer " + peer_id + "!\n\t" + err)
        return False
    else:
        return True

def modify_outgoing_connection(interface,peer_id, netem):
    err = run_commands(modify_outgoing_connections_commands, {interface_token: interface,
                                                              peer_id_token: peer_id,
                                                              netem_token: netem})
    if err:
        logging.error("error modifying outgoing connection to peer " + peer_id + "!\n\t" + err)
        return False
    else:
        return True

def modify_connection(interface,peer_id, netem):
    return modify_incoming_connection(interface,peer_id,netem) and modify_outgoing_connection(interface,peer_id,netem)

def init_qdisc(host, peers):
    interface = str(host["interface"])
    # Cleans qdisc configuration if present
    clean_all_qdisc(interface)
    # Creates the root qdisc
    if create_root_qdisc(interface):
        id = host["id"]
        for peer in peers:
            create_peer_qdisc(interface, peer)
        modify_incoming_connection("lo", "2", "loss 90%")
    else:
        exit(1)


def main():
    logging.basicConfig(filename='debug.log', level=logging.DEBUG)

    try:
        # Loads configuration file
        with open(sys.argv[1]) as configuration_file:
            configuration = json.load(configuration_file)

        init_qdisc(configuration["host"], configuration["peers"])
    except:
        print "file "+sys.argv[1]+" does not exist"


if __name__ == "__main__":
    main()
