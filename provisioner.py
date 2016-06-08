import argparse
import json
import socket
from urllib.request import urlretrieve
import subprocess
import sys

MAX_CLUSTER_NODES = 9
CLUSTER_MODES = ["local", "gce"]
CONSENSUS_ALGORITHMS = ["raft", "paxos"]
RPC_SERVER_SCRIPT_URL = "https://raw.githubusercontent.com/GianlucaBortoli/krafters/master/network_manager.py"


def find_free_port():
    s = socket.socket()
    s.bind(('', 0))  # bind to a free random port
    return s.getsockname()[1]  # return the port number assigned


def get_node_config(cluster, node):
    return {"interface": node["interface"],
            "rpcPort": node["rpcPort"],
            "host": {
                "port": node["port"],
                "address": node["address"],
                "id": node["id"]},
            "peers": [{
                "address": peer["address"],
                "port": peer["port"],
                "id": peer["id"]} for peer in cluster if peer["id"] != node["id"]]}


def deploy_local_cluster(nodes_num, algorithm):
    cluster = []
    for i in range(1, nodes_num + 1):
        new_node = {
            "id": i,
            "address": "127.0.0.1",
            "port": find_free_port(),
            "rpcPort": find_free_port(),
            "interface": "lo"}
        print("Adding node to the configuration: {}".format(new_node))
        cluster.append(new_node)

    for node in cluster:
        node_file_path = "/tmp/provision_node_" + str(node["id"]) + "_config.json"
        with open(node_file_path, 'w') as out_f:
            json.dump(get_node_config(cluster, node), out_f, indent=4)
        command = [sys.executable, "network_manager.py", node_file_path]
        subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        print("Network manager started on node {}".format(node["id"]))

    print("Going to run algorithm {} on cluster...".format(algorithm))

    if algorithm == "paxos":
        pass
    elif algorithm == "raft":
        pass

    print("Provisioning completed: cluster is running and ready to execute test.")
    print("To perform a test run: run_test.py test_file_name")

    cluster_config_file = "masterConfig.json"  # this file will be used to tear down the cluster
    with open(cluster_config_file, 'w') as out_f:
        json.dump({
            "mode": "local",
            "algorithm": algorithm,
            "nodes": cluster
        }, out_f, indent=4)  # TODO: dump also in case of precedent error
    print("Cluster configuration saved in file {}.".format(cluster_config_file))
    print("To stop the cluster run: tear_down.py {}".format(cluster_config_file))


def deploy_gce_cluster(nodes, algorithm):
    # print("Fetching latest version of RPC server from {}...".format(RPC_SERVER_SCRIPT_URL))
    # script_path = "/tmp/rpc_server.py"
    # urlretrieve(RPC_SERVER_SCRIPT_URL, script_path) TODO uncomment when committing new network_manager.py
    # print("Script downloaded in {}. Fetching available ports on localhost...".format(script_path))
    pass


def main():
    parser = argparse.ArgumentParser(description="Run a consensus algorithm on a cluster of nodes.")
    parser.add_argument("-n", "--nodes", type=int, choices=range(1, MAX_CLUSTER_NODES + 1), dest="nodes", required=True,
                        help="cluster nodes number")
    parser.add_argument("-m", "--mode", type=str, choices=CLUSTER_MODES, dest="mode", required=True,
                        help="cluster node location")
    parser.add_argument("-a", "--algorithm", type=str, choices=CONSENSUS_ALGORITHMS, dest="algorithm", required=True,
                        help="consensus algorithm")
    args = parser.parse_args()
    print("Going to deploy a cluster of {} nodes. Please wait...".format(args.nodes))

    if args.mode == "local":
        deploy_local_cluster(args.nodes, args.algorithm)
    elif args.mode == "gce":
        deploy_gce_cluster(args.nodes, args.algorithm)


if __name__ == "__main__":
    main()
