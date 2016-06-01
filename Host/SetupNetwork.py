import json
import subprocess
import logging

import sys


def create_root_qdisc(interface):
    command = "sudo tc qdisc add dev "+interface+" root handle 1: htb"
    p = subprocess.Popen(command,
                         stdout=subprocess.PIPE,
                         stderr=subprocess.PIPE,
                         shell=True)
    out, err = p.communicate()
    if err:
        logging.error("[ERROR]: error creating root!\n\t" + err)
        return False
    else:
        return True


def clean_all_qdisc(interface):
    command = "sudo tc qdisc del dev "+interface+" root"
    p = subprocess.Popen(command,
                         stdout=subprocess.PIPE,
                         stderr=subprocess.PIPE,
                         shell=True)
    out, err = p.communicate()
    if err:
        logging.error("[ERROR]: error removing root!\n\t" + err)
        return False
    else:
        command = "sudo tc -s qdisc ls dev "+interface
        p = subprocess.Popen(command,
                             stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE,
                             shell=True)
        out, err = p.communicate()
        if err:
            logging.error("[ERROR]: error removing root!\n\t" + err)
            return False
        else:
            return True


def create_peer_qdisc(interface, peer):
    # TODO adjust bandwidth
    qid = "1:" + str(peer["id"])
    command = "sudo tc class add dev "+ interface +" parent 1: classid "+ qid +" htb rate 100Mbps"
    p = subprocess.Popen(command,
                         stdout=subprocess.PIPE,
                         stderr=subprocess.PIPE,
                         shell=True)
    out, err = p.communicate()
    if err:
        logging.error("[ERROR]: error creating class for peer " + peer + "!\n\t" + err)
        return False
    else:
        command = "sudo tc qdisc add dev "+interface+" parent "+ qid +" handle "+ str(peer["id"]) + ": htb"
        p = subprocess.Popen(command,
                             stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE,
                             shell=True)
        out, err = p.communicate()
        if err:
            logging.error("[ERROR]: error creating qdisc for peer " + str(peer) + "!\n\t" + err)
            return False
        else:
            # TODO add ip in match
            command = "sudo tc filter add dev "+ interface +" protocol ip u32 match ip dport "+str(peer["port"])+" 0xffff flowid"+ qid
            p = subprocess.Popen(command,
                                 stdout=subprocess.PIPE,
                                 stderr=subprocess.PIPE,
                                 shell=True)
            out, err = p.communicate()
            if err:
                logging.error("[ERROR]: error creating filter for peer " + str(peer) + "!\n\t" + err)
                return False
            else:
                command = "sudo tc filter add dev " + interface + " protocol ip u32 match ip sport " + str(peer["port"]) + " 0xffff flowid " + qid
                p = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
                out, err = p.communicate()
                if err:
                    logging.error("[ERROR]: error creating filter for peer " + str(peer) + "!\n\t" + err)
                    return False
                else:
                    return True


def init_qdisc(host, peers):
    interface = str(host["interface"])
    # Cleans qdisc configuration if present
    clean_all_qdisc(interface)
    # Creates the root qdisc
    if create_root_qdisc(interface):
        id = host["id"]
        for peer in peers:
            create_peer_qdisc(interface, peer)
    else:
        exit(1)


def main():
    logging.basicConfig(filename='debug.log', level=logging.DEBUG)
    try:
        # Loads configuration file
        with open(sys.argv[1]) as configuration_file:
            configuration = json.load(configuration_file)

        init_qdisc(configuration["host"],configuration["peers"])

    except:
        print "invalid file: " + sys.argv[1]


if __name__ == "__main__":
    main()
