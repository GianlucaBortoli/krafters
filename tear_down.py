#!/usr/bin/python3.4

import json
import sys
import subprocess


def kill_process_by_port(port):
    command = ["fuser", "-k", str(port) + "/tcp", str(port) + "/udp"]
    return subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE).communicate()


def tear_down_local_cluster(conf):
    for node in conf["nodes"]:
        print("Shutting down process for node running at {}:{}".format(node["address"], node["port"]))
        kill_process_by_port(node["port"])
        print("Shutting down process for network manager running at {}:{}".format(node["address"], node["rpcPort"]))
        kill_process_by_port(node["rpcPort"])
    print("Shutting down process for test daemon running at {}".format(conf["testEndpoint"]))
    kill_process_by_port(conf["testEndpoint"].split(":")[1])
    print("Cluster torn down correctly. Bye!")


def tear_down_gce_cluster(conf):
    # TODO implement it
    pass


def main():
    with open(sys.argv[1]) as configuration_f:
        conf = json.load(configuration_f)
    print("Going to tear down a cluster of {} nodes on {}. Please wait...".format(conf["algorithm"], conf["mode"]))
    if conf["mode"] == "local":
        tear_down_local_cluster(conf)
    elif conf["mode"] == "gce":
        tear_down_gce_cluster(conf)

if __name__ == "__main__":
    main()
