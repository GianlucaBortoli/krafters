#!/usr/bin/python3.4

import argparse
import json
import socket
from time import sleep
import subprocess
import sys
from contextlib import closing
from oauth2client.client import GoogleCredentials
from googleapiclient import discovery
from googleapiclient import http
from test_daemon import TEST_DAEMON_PORT
from configure_daemon import CONFIGURE_DAEMON_PORT, NETWORK_MANAGER_PORT
from xmlrpc.client import ServerProxy as rpcClient

MAX_CLUSTER_NODES = 8  # CPU-quota on GCE
CLUSTER_MODES = ["local", "gce"]
CONSENSUS_ALGORITHMS = ["pso", "rethinkdb"]
PYTHON2_ENV = None

# RPC_SERVER_SCRIPT_URL = "https://raw.githubusercontent.com/GianlucaBortoli/krafters/master/network_manager.py"

GCP_PROJECT_ID = "krafters-1334"
GS_BUCKET = "krafters"
GCE_REGION_ID = "us-central1"
GCE_ZONE_ID = "us-central1-c"
GCE_INSTANCE_TYPE = "n1-standard-1"
GCE_OS_PROJECT = "ubuntu-os-cloud"
GCE_OS_FAMILY = "ubuntu-1204-lts"
GCE_FIREWALL_RULE_NAME = "allow-all-tcp-udp"

CONSENSUS_ALGORITHM_PORT = 12348


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
        node_config_file = node_file_path.format(node["id"])
        with open(node_config_file, "w") as out_f:
            json.dump(get_node_config(cluster, node), out_f, indent=4)
        command = [sys.executable, "network_manager.py", node_config_file]
        subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)  # process is run asynchronously
    for node in cluster:
        while not is_socket_open(node["address"], node["rpcPort"]):  # check that Popen actually started the script
            sleep(0.3)
        print("Network manager active on {}:{}".format(node["address"], str(node["rpcPort"])))
    # ✓ 3. run network managers

    endpoint_port = str(TEST_DAEMON_PORT)
    endpoint = "127.0.0.1:" + endpoint_port  # run the test daemon on localhost
    print("Running the test daemon on {}...".format(endpoint))
    command = [sys.executable, "test_daemon.py", "127.0.0.1", algorithm]
    subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)  # process is run asynchronously
    while not is_socket_open("127.0.0.1", int(endpoint_port)):  # check that Popen actually started the script
        sleep(0.3)
    print("Test daemon active on {}".format(endpoint))
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
    print("To perform a test run: test_executor.py {} test_file_name".format(cluster_config_file))
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
        "tags": {
            "items": [
                "http-server",
                "https-server"
            ]
        },
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


def upload_object(gcs, file_path, file_name):
    body = {'name': file_name}
    with open(file_path, 'rb') as f:
        req = gcs.objects().insert(bucket=GS_BUCKET, body=body, predefinedAcl="publicRead",
                                   media_body=http.MediaIoBaseUpload(f, 'application/octet-stream'))
        resp = req.execute()
    return resp


def provide_gce_cluster(nodes_num, algorithm):
    credentials = GoogleCredentials.get_application_default()
    gce = discovery.build("compute", "v1", credentials=credentials)
    config_dir = "config/"
    config_file_template = "provision_node_{}_config.json"
    zone_operations = []
    vm_ids = []
    for i in range(1, nodes_num + 1):
        vm_ids.append("vm-node-{}".format(i))
        metadata = {"bucket": GS_BUCKET, "clusterConfig": config_dir + config_file_template.format(vm_ids[-1])}
        print("Starting a new virtual machine with name {}".format(vm_ids[-1]))
        zone_operations.append(create_instance(gce, vm_ids[-1], metadata, "gce-startup-script.sh"))
        # vm creation is run asynchronously: check that the operation is really completed

    cluster = []
    for (i, zone) in [(i, zone_op["name"]) for (i, zone_op) in enumerate(zone_operations)]:
        print("Checking if virtual machine {} is ready...".format(vm_ids[i]))
        while True:
            result = gce.zoneOperations().get(project=GCP_PROJECT_ID, zone=GCE_ZONE_ID, operation=zone).execute()
            if result["status"] == "DONE":
                print("Virtual machine {} is ready.".format(vm_ids[i]))
                # if "error" in result: raise Exception(result["error"])  # TODO handle error
                result = gce.instances().get(project=GCP_PROJECT_ID, zone=GCE_ZONE_ID, instance=vm_ids[i]).execute()
                new_node = {
                    "id": i + 1,
                    "address": result["networkInterfaces"][0]["accessConfigs"][0]["natIP"],  # ephemeral external IP
                    "port": CONSENSUS_ALGORITHM_PORT,
                    "rpcPort": NETWORK_MANAGER_PORT,
                    "interface": result["networkInterfaces"][0]["name"],  # network interface name is usually nic0
                    "vmID": vm_ids[i]
                }
                print("Adding node to the configuration: {}".format(new_node))
                cluster.append(new_node)
                break
            sleep(1)
    # ✓ 1. spin machines [configure daemons will be run by the startup script on every node]

    try:
        gce.firewalls().get(project=GCP_PROJECT_ID, firewall=GCE_FIREWALL_RULE_NAME).execute()
        print("Firewall rule to allow traffic already exists.")
    except:  # rule does not exist: create it
        print("Creating firewall rule to allow traffic...")
        firewall_rule = {
            "description": "Allow traffic on every TCP/UDP port",
            "allowed": [{"IPProtocol": "tcp", "ports": ["1-65535"]},
                        {"IPProtocol": "udp", "ports": ["1-65535"]},
                        {"IPProtocol": "icmp"}],
            "name": GCE_FIREWALL_RULE_NAME,
        }
        gce.firewalls().insert(project=GCP_PROJECT_ID, body=firewall_rule).execute()
        print("Firewall rule to allow traffic created.")
    # ✓ 1.1 allow network traffic on VMs

    print("Going to run algorithm {} on cluster...".format(algorithm))
    sleep(55)  # give time to VMs to complete their startup scripts
    if algorithm == "pso":
        pass  # nothing to configure
    elif algorithm == "rethinkdb":
        #TODO: here call methods on configure_daemon.py
        pass  # TODO run service and configure master-slave
    # ✓ 2. run algorithm [via configure daemons]

    print("Running network manager on every node...")
    gcs = discovery.build('storage', 'v1', credentials=credentials)
    configure_daemons = []
    for node in cluster:
        node_config_file = "/tmp/" + config_file_template.format(node["vmID"])
        with open(node_config_file, "w") as out_f:
            json.dump(get_node_config(cluster, node), out_f, indent=4)
        upload_object(gcs, node_config_file, config_dir + config_file_template.format(node["vmID"]))
        configure_daemons.append(rpcClient('http://{}:{}'.format(node["address"], CONFIGURE_DAEMON_PORT)))
        retries = 0
        while True:
            try:
                configure_daemons[-1].run_network_manager()
                # this rpc will download the node-specific configuration file from gs and run the network manager
                # each node can discover its configuration file by querying its own metadata
                break
            except Exception as e:
                print(e)
                retries += 1
                if retries < 10:
                    print("An error occurred while starting the network manager. Retrying ({}/{})...".format(retries, 10))
                else:
                    print("An error occurred while starting the network manager. Unable to complete provisioning")
                    exit(2)  # TODO handle
        print("Network manager active on {}:{}".format(node["address"], str(node["rpcPort"])))
    # ✓ 3. run network managers

    endpoint = cluster[0]["address"] + ":" + str(TEST_DAEMON_PORT)  # arbitrarily run the test daemon on first node
    print("Running the test daemon on {}...".format(endpoint))
    retries = 0
    while True:
        try:
            configure_daemons[0].run_test_daemon(algorithm)
            break
        except Exception as e:
            print(e)
            retries += 1
            if retries < 10:
                print("An error occurred while starting the test daemon. Retrying ({}/{})...".format(retries, 10))
            else:
                print("An error occurred while starting the test daemon. Unable to complete provisioning")
                exit(2)  # TODO handle
    print("Test daemon active on {}".format(endpoint))
    # ✓ 4. run test daemon

    print("Provisioning completed: cluster is ready to execute test on {} at {}".format(algorithm, endpoint))
    cluster_config_file = "masterConfig.json"  # this file will be used to tear down the cluster
    with open(cluster_config_file, "w") as out_f:
        json.dump({
            "mode": "gce",
            "algorithm": algorithm,
            "testDaemon": endpoint,
            "nodes": cluster
        }, out_f, indent=4)
    print("Cluster configuration saved in file {}.\n".format(cluster_config_file))
    print("To perform a test run: test_executor.py {} test_file_name".format(cluster_config_file))
    print("To stop the cluster run: tear_down.py {}".format(cluster_config_file))


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
