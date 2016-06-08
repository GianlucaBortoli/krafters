import argparse
import json
import socket
from time import sleep
from urllib.request import urlretrieve
import subprocess
import sys
from contextlib import closing
from googleapiclient import discovery
from oauth2client.client import GoogleCredentials

MAX_CLUSTER_NODES = 9
CLUSTER_MODES = ["local", "gce"]
CONSENSUS_ALGORITHMS = ["pso", "rethinkdb"]
PYTHON2_ENV = None

# RPC_SERVER_SCRIPT_URL = "https://raw.githubusercontent.com/GianlucaBortoli/krafters/master/network_manager.py"

GCP_PROJECT_ID = "krafters-1334"
GCE_REGION_ID = "us-central1"
GCE_ZONE_ID = "us-central1-c"
GCE_INSTANCE_TYPE = "n1-standard-1"
GCE_OS_PROJECT = "ubuntu-os-cloud"
GCE_OS_FAMILY = "ubuntu-1204-lts"


def get_free_random_port():
    s = socket.socket()
    s.bind(("", 0))  # bind to a free random port
    return s.getsockname()[1]  # return the port number assigned


def is_socket_open(host, port):
    with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as sock:
        return sock.connect_ex((host, port)) == 0


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


def provide_local_cluster(nodes_num, algorithm):
    cluster = []
    for i in range(1, nodes_num + 1):
        new_node = {
            "id": i,
            "address": "127.0.0.1",
            "port": get_free_random_port(),
            "rpcPort": get_free_random_port(),
            "interface": "lo"}
        print("Adding node to the configuration: {}".format(new_node))
        cluster.append(new_node)
    # ✓ 1. spin machines [no need to run a configure daemon on localhost]

    print("Going to run algorithm {} on cluster...".format(algorithm))
    if algorithm == "pso":
        pass  # nothing to configure
    elif algorithm == "rethinkdb":
        #TODO: run local cluster
        pass  # TODO run service and configure master-slave
    # ✓ 2. run algorithm [no need to run a configure daemon on localhost]

    print("Running network manager on every node...")
    node_file_path = "/tmp/provision_node_{}_config.json"
    for node in cluster:
        with open(node_file_path.format(node["id"]), "w") as out_f:
            json.dump(get_node_config(cluster, node), out_f, indent=4)
        command = [sys.executable, "network_manager.py", node_file_path.format(node["id"])]  # TODO does the network manager really need to know all the cluster config?
        subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)  # process is run asynchronously
    for node in cluster:
        while not is_socket_open(node["address"], node["rpcPort"]):  # check that Popen actually started the script
            sleep(0.3)
        print("Network manager active on {}:{}".format(node["address"], str(node["rpcPort"])))
    # ✓ 3. run network managers

    endpoint_port = str(get_free_random_port())
    endpoint = cluster[0]["address"] + ":" + endpoint_port   # arbitrarily run the test daemon of the first node
    print("Running the test daemon on {}...".format(endpoint))
    command = [sys.executable, "test_daemon.py", node_file_path.format(cluster[0]["id"]), endpoint_port]  # TODO different params may be required
    subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)  # process is run asynchronously
    while not is_socket_open(cluster[0]["address"], int(endpoint_port)):  # check that Popen actually started the script
        sleep(0.3)
    print("Test daemon active on {}...".format(endpoint))
    # ✓ 4. run test daemon

    print("Provisioning completed: cluster is ready to execute test on {} at {}".format(algorithm, endpoint))
    cluster_config_file = "masterConfig.json"  # this file will be used to tear down the cluster
    with open(cluster_config_file, "w") as out_f:
        json.dump({
            "mode": "local",
            "algorithm": algorithm,
            "testEndpoint": endpoint,
            "nodes": cluster
        }, out_f, indent=4)
    print("Cluster configuration saved in file {}.\n".format(cluster_config_file))
    print("To perform a test run: run_test.py test_file_name {}".format(cluster_config_file))
    print("To stop the cluster run: tear_down.py {}".format(cluster_config_file))


def list_instances(compute):
    return compute.instances().list(project=GCP_PROJECT_ID, zone=GCE_ZONE_ID).execute().get("items", [])


def create_instance(gce, name, metadata, script):
    # fetch the latest image version
    image_response = gce.images().getFromFamily(project=GCE_OS_PROJECT, family=GCE_OS_FAMILY).execute()
    config = {
        "name": name,
        # "description": "description",
        "machineType": "zones/{}/machineTypes/{}".format(GCE_ZONE_ID, GCE_INSTANCE_TYPE),
        "disks": [{
            "boot": True,
            "autoDelete": True,
            "type": "PERSISTENT",
            "mode": "READ_WRITE",
            "deviceName": name + "-disk",
            "initializeParams": {
                "sourceImage": image_response["selfLink"],
                "diskType": "projects/{}/zones/{}/diskTypes/pd-standard".format(GCP_PROJECT_ID, GCE_ZONE_ID),
                "diskSizeGb": "10"
            }
        }],
        "networkInterfaces": [{
            "network": "global/networks/default",
            "projects/krafters-1334/regions/us-central1/subnetworks/default"
            "subnetwork": "projects/{}/regions/{}/subnetworks/default".format(GCP_PROJECT_ID, GCE_REGION_ID),
            "accessConfigs": [{"type": "ONE_TO_ONE_NAT", "name": "External NAT"}]
        }],
        "serviceAccounts": [{
            "email": "default",
            "scopes": [
                "https://www.googleapis.com/auth/devstorage.read_only",
                "https://www.googleapis.com/auth/logging.write",
                "https://www.googleapis.com/auth/monitoring.write",
                "https://www.googleapis.com/auth/servicecontrol",
                "https://www.googleapis.com/auth/service.management"
            ]
        }],
        "metadata": {
            "items": [{
                "key": "startup-script",
                "value": open(script, "r").read()  # this script will be executed automatically on every vm (re)start
            }]
        },
        "scheduling": {
            "preemptible": False,
            "onHostMaintenance": "MIGRATE",
            "automaticRestart": True
        }
    }
    # add custom metadata to the vm
    config["metadata"]["items"].extend({"key": key, "value": value} for key, value in metadata.items())
    return gce.instances().insert(project=GCP_PROJECT_ID, zone=GCE_ZONE_ID, body=config).execute()


def provide_gce_cluster(nodes_num, algorithm):
    credentials = GoogleCredentials.get_application_default()
    gce = discovery.build("compute", "v1", credentials=credentials)
    zone_operations = []
    instance_name = "vm-node-{}"
    for i in range(1, nodes_num + 1):
        metadata = {"myfookey": "myfoovalue"}  # TODO put cluster info instead
        zone_operations.append(create_instance(gce, instance_name.format(i), metadata, "gce-startup-script.sh"))
        # vm creation is run asynchronously: check that the operation is completed
    for zone_op in zone_operations:
        print("Waiting for operation to finish...")
        while True:
            result = gce.zoneOperations().get(project=GCP_PROJECT_ID, zone=GCE_ZONE_ID, operation=zone_op).execute()
            if result["status"] == "DONE":
                break
                # if "error" in result: raise Exception(result["error"])  # TODO handle error
            sleep(1)
    print(list_instances(gce))

    return

    cluster = []
    for i in range(1, nodes_num + 1):
        new_node = {
            "id": i,
            "address": "127.0.0.1",
            "port": get_free_random_port(),
            "rpcPort": get_free_random_port(),
            "interface": "lo"}
        print("Adding node to the configuration: {}".format(new_node))
        cluster.append(new_node)
    # ✓ 1. spin machines [no need to run a configure daemon on localhost]

    print("Going to run algorithm {} on cluster...".format(algorithm))
    if algorithm == "pso":
        pass  # nothing to configure
    elif algorithm == "rethinkdb":
        #TODO: here call methods on configure_daemon.py
        pass  # TODO run service and configure master-slave
    # ✓ 2. run algorithm [no need to run a configure daemon on localhost]

    print("Running network manager on every node...")
    node_file_path = "/tmp/provision_node_{}_config.json"
    for node in cluster:
        with open(node_file_path.format(node["id"]), "w") as out_f:
            json.dump(get_node_config(cluster, node), out_f, indent=4)
        command = [sys.executable, "network_manager.py", node_file_path.format(node["id"])]  # TODO does the network manager really need to know all the cluster config?
        subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)  # process is run asynchronously
    for node in cluster:
        while not is_socket_open(node["address"], node["rpcPort"]):  # check that Popen actually started the script
            sleep(0.3)
        print("Network manager active on {}:{}".format(node["address"], str(node["rpcPort"])))
    # ✓ 3. run network managers

    endpoint_port = str(get_free_random_port())
    endpoint = cluster[0]["address"] + ":" + endpoint_port   # arbitrarily run the test daemon of the first node
    print("Running the test daemon on {}...".format(endpoint))
    command = [sys.executable, "test_daemon.py", node_file_path.format(cluster[0]["id"]), endpoint_port]  # TODO different params may be required
    subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)  # process is run asynchronously
    while not is_socket_open(cluster[0]["address"], int(endpoint_port)):  # check that Popen actually started the script
        sleep(0.3)
    print("Test daemon active on {}...".format(endpoint))
    # ✓ 4. run test daemon

    print("Provisioning completed: cluster is ready to execute test on {} at {}".format(algorithm, endpoint))
    cluster_config_file = "masterConfig.json"  # this file will be used to tear down the cluster
    with open(cluster_config_file, "w") as out_f:
        json.dump({
            "mode": "local",
            "algorithm": algorithm,
            "testEndpoint": endpoint,
            "nodes": cluster
        }, out_f, indent=4)
    print("Cluster configuration saved in file {}.\n".format(cluster_config_file))
    print("To perform a test run: run_test.py test_file_name {}".format(cluster_config_file))
    print("To stop the cluster run: tear_down.py {}".format(cluster_config_file))


    # print("Fetching latest version of RPC server from {}...".format(RPC_SERVER_SCRIPT_URL))
    # script_path = "/tmp/rpc_server.py"
    # urlretrieve(RPC_SERVER_SCRIPT_URL, script_path) TODO uncomment when committing new network_manager.py
    # print("Script downloaded in {}. Fetching available ports on localhost...".format(script_path))
    pass


def main():
    parser = argparse.ArgumentParser(description="Run a consensus algorithm on a cluster of nodes.")
    parser.add_argument("-n", "--nodes", type=int, choices=range(1, MAX_CLUSTER_NODES + 1), dest="nodes", default=3,
                        help="cluster nodes number")
    parser.add_argument("-m", "--mode", type=str, choices=CLUSTER_MODES, dest="mode", default="local",
                        help="cluster node location")
    parser.add_argument("-a", "--algorithm", type=str, choices=CONSENSUS_ALGORITHMS, dest="algorithm", default="pso",
                        help="consensus algorithm")
    parser.add_argument("-p", "--python", type=str, dest="python", default="/usr/bin/python2.7", help="python2 bin")

    args = parser.parse_args()
    print("Going to deploy a cluster of {} nodes on {}. Please wait...".format(args.nodes, args.mode))
    global PYTHON2_ENV
    PYTHON2_ENV = args.python

    # Provisioning steps:
    # 1. spin machines (possibly running a configure daemon on each of them)
    # 2. run algorithm (possibly by using each configure daemon)
    # 3. run network managers
    # 4. run test daemon

    if args.mode == "local":
        provide_local_cluster(args.nodes, args.algorithm)
    elif args.mode == "gce":
        provide_gce_cluster(args.nodes, args.algorithm)


if __name__ == "__main__":
    main()