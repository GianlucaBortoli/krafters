#!/usr/bin/python3.4
import random
import string

from time import sleep
from contextlib import closing
from oauth2client.client import GoogleCredentials
from googleapiclient import discovery
from googleapiclient import http
from test_daemon import TEST_DAEMON_PORT
from configure_daemon import CONFIGURE_DAEMON_PORT, NETWORK_MANAGER_PORT, \
    configure_rethinkdb_master, configure_rethinkdb_follower, run_test_daemon, run_paxos_node, LOCAL_NODE_CONF_FILE, \
    run_pso_node
from xmlrpc.client import ServerProxy as rpcClient
import argparse
import json
import socket
import subprocess
import sys

MAX_CLUSTER_NODES = 8  # default CPU-quota on GCE
CLUSTER_MODES = ["local", "gce"]
CONSENSUS_ALGORITHMS = ["pso", "paxos", "rethinkdb", "datastore"]

# TODO ENSURE YOU ARE SUDO BOTH HERE AND IN TEAR_DOWN
# TODO UPDATE USAGE OF TEST_EXECUTOR

GCP_PROJECT_ID = "krafters-1334"
GCS_BUCKET = "krafters"
GCE_REGION_ID = "us-central1"
GCE_ZONE_ID = "us-central1-c"
GCE_INSTANCE_TYPE = "n1-standard-1"
GCE_OS_PROJECT = "ubuntu-os-cloud"
GCE_OS_FAMILY = "ubuntu-1510"
GCE_FIREWALL_RULE_NAME = "allow-all-tcp-udp"

CONSENSUS_ALGORITHM_PORT = 12348
GCE_RETHINKDB_PORTS = {
    "driver_port": CONSENSUS_ALGORITHM_PORT,
    "cluster_port": CONSENSUS_ALGORITHM_PORT + 1,
    "http_port": CONSENSUS_ALGORITHM_PORT + 2
}

RANDOM_PORTS_POOL = set()


def provide_local_cluster(nodes_num, algorithm):
    cluster = []
    # 1. spin machines [no need to run a configure daemon on localhost]
    for i in range(1, nodes_num + 1):
        new_node = {
            "id": i,
            "address": "127.0.0.1",
            "port": get_free_random_port(),
            "rpcPort": get_free_random_port(),
            "interface": "lo"}
        print("Adding node to the configuration: {}".format(new_node))
        cluster.append(new_node)
    # ✓ 1. spin machines

    # 1.1 provide node-specific configuration files
    node_file_path = "/tmp/provision_node_{}_config.json"
    for node in cluster:
        with open(node_file_path.format(node["id"]), "w") as out_f:
            node_conf = get_node_config(cluster, node)
            # TODO check no secondary ports required for rdb
            # node_conf["portsToLock"] = node_conf["portsToLock"] + []
            json.dump(node_conf, out_f, indent=4)
    # ✓ 1.1 provide node-specific configuration files

    # 2. run algorithm [no need to run a configure daemon on localhost]
    test_daemon_endpoint = "127.0.0.1:" + str(TEST_DAEMON_PORT)
    print("Going to run algorithm {} on cluster...".format(algorithm))
    if algorithm == "pso":
        configure_pso_local(cluster, node_file_path, test_daemon_endpoint)
    elif algorithm == "paxos":
        configure_paxos_local(cluster, node_file_path, test_daemon_endpoint)
    elif algorithm == "rethinkdb":
        configure_rethinkdb_local(cluster)
    elif algorithm == "datastore":
        pass
    # ✓ 2. run algorithm

    # 3. run network managers
    print("Running network manager on every node...")
    for node in cluster:
        command = [sys.executable, "network_manager.py", node_file_path.format(node["id"])]
        subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)  # process is run asynchronously
    for node in cluster:
        while not is_socket_free(node["address"], node["rpcPort"]):  # check that Popen actually started the script
            sleep(0.3)
        print("Network manager active on {}:{}".format(node["address"], str(node["rpcPort"])))
    # ✓ 3. run network managers

    # 4. run test daemon
    print("Running the test daemon on {}...".format(test_daemon_endpoint))
    run_test_daemon(algorithm, cluster[0]['port'])
    print("Test daemon active on {}".format(test_daemon_endpoint))
    # ✓ 4. run test daemon

    print("Provisioning completed: cluster is ready to execute tests on {} at {}".format(algorithm, test_daemon_endpoint))
    cluster_config_file = "masterConfig.json"  # this file will be used to tear down the cluster
    with open(cluster_config_file, "w") as out_f:
        json.dump({
            "mode": "local",
            "algorithm": algorithm,
            "testDaemon": test_daemon_endpoint,
            "nodes": cluster
        }, out_f, indent=4)
    print("Cluster configuration saved in file {}.\n".format(cluster_config_file))
    print("To perform a test run: test_executor.py {} test_file_name".format(cluster_config_file))
    print("To stop the cluster run: tear_down.py {}".format(cluster_config_file))


def provide_gce_cluster(nodes_num, algorithm):
    # 1. spin machines [configure daemons will be run by the startup script on every node]
    credentials = GoogleCredentials.get_application_default()
    gce = discovery.build("compute", "v1", credentials=credentials)
    config_dir = "config/"
    config_file_template = "provision_node_{}_config.json"
    zone_operations, vm_ids, cluster = [], [], []
    for i in range(1, nodes_num + 1):
        vm_ids.append("vm-node-{}-{}".format(i, get_random_string(6)))
        metadata = {"bucket": GCS_BUCKET,
                    "clusterConfig": config_dir + config_file_template.format(vm_ids[-1]),
                    "myid": vm_ids[-1]}
        print("Starting a new virtual machine with name {}".format(vm_ids[-1]))
        zone_operations.append(create_instance(gce, vm_ids[-1], metadata, "gce-startup-script.sh"))
        # vm creation is run asynchronously: check that the operation is really completed

    for (i, zone) in [(i, zone_op["name"]) for (i, zone_op) in enumerate(zone_operations)]:
        print("Checking if virtual machine {} is ready...".format(vm_ids[i]))
        while True:
            result = gce.zoneOperations().get(project=GCP_PROJECT_ID, zone=GCE_ZONE_ID, operation=zone).execute()
            if result["status"] == "DONE":
                print("Virtual machine {} is ready.".format(vm_ids[i]))
                result = gce.instances().get(project=GCP_PROJECT_ID, zone=GCE_ZONE_ID, instance=vm_ids[i]).execute()
                new_node = {
                    "id": i + 1,
                    "address": result["networkInterfaces"][0]["accessConfigs"][0]["natIP"],  # ephemeral external IP
                    "port": CONSENSUS_ALGORITHM_PORT,
                    "rpcPort": NETWORK_MANAGER_PORT,
                    "interface": "eth0",
                    "vmID": vm_ids[i]
                }
                print("Adding node to the configuration: {}".format(new_node))
                cluster.append(new_node)
                break
            sleep(2)
    # ✓ 1. spin machines

    # 1.1 allow network traffic on VMs if needed
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
        print("Firewall rule to allow traffic created: {}.".format(firewall_rule))
    # ✓ 1.1 allow network traffic on VMs

    # 1.2 wait for startup scripts
    print("Waiting for startup scripts to be completed on VMs...")
    gcs = discovery.build('storage', 'v1', credentials=credentials)
    for vm_id_file in vm_ids:
        while not gcs_file_exists(gcs, vm_id_file):  # acknowledge file created by startup script at the end
            sleep(2)
        gcs.objects().delete(bucket=GCS_BUCKET, object=vm_id_file).execute()  # clean up

    # ✓ 1.2 wait for startup scripts

    configure_daemons = [rpcClient('http://{}:{}'.format(node["address"], CONFIGURE_DAEMON_PORT)) for node in cluster]
    # 1.3 provide node-specific configuration files [via configure daemons]
    for node in cluster:
        node_config_file = "/tmp/" + config_file_template.format(node["vmID"])
        with open(node_config_file, "w") as out_f:
            if algorithm == "rethinkdb":
                node_conf = get_node_config(cluster, node, additional_ports=[GCE_RETHINKDB_PORTS["cluster_port"]])
            else:
                node_conf = get_node_config(cluster, node)
            json.dump(node_conf, out_f, indent=4)
        upload_object(gcs, node_config_file, config_dir + config_file_template.format(node["vmID"]))  # send file to VM
    for configure_daemon in configure_daemons:
        configure_daemon.download_node_config()
    # ✓ 1.3 provide node-specific configuration files

    # 2. run algorithm [via configure daemons]
    test_daemon_endpoint = cluster[0]["address"] + ":" + str(TEST_DAEMON_PORT)  # arbitrarily run the test daemon on first node
    print("Going to run algorithm {} on cluster...".format(algorithm))
    if algorithm == "pso":
        configure_pso_gce(cluster, configure_daemons, test_daemon_endpoint)
    elif algorithm == "paxos":
        configure_paxos_gce(cluster, configure_daemons, test_daemon_endpoint)
    elif algorithm == "rethinkdb":
        configure_rethinkdb_gce(cluster, configure_daemons)
    elif algorithm == "datastore":
        pass
    # ✓ 2. run algorithm [via configure daemons]

    # 3. run network managers [via configure daemons]
    print("Running network manager on every node...")
    for node in cluster:
        node_config_file = "/tmp/" + config_file_template.format(node["vmID"])
        with open(node_config_file, "w") as out_f:
            json.dump(get_node_config(cluster, node), out_f, indent=4)
        upload_object(gcs, node_config_file, config_dir + config_file_template.format(node["vmID"]))  # send file to VM
        configure_daemons[node["id"] - 1].run_network_manager()
        # this rpc will download the node-specific configuration file from gs and run the network manager
        # each node can discover its configuration file by querying its own metadata
        print("Network manager active on {}:{}".format(node["address"], str(node["rpcPort"])))
    # ✓ 3. run network managers

    # 4. run test daemon [via configure daemon]
    print("Running the test daemon on {}...".format(test_daemon_endpoint))
    configure_daemons[0].run_test_daemon(algorithm, cluster[0]["port"])
    print("Test daemon active on {}".format(test_daemon_endpoint))
    # ✓ 4. run test daemon

    print("Provisioning completed: cluster is ready to execute tests on {} at {}".format(algorithm, test_daemon_endpoint))
    cluster_config_file = "masterConfig.json"  # this file will be used to tear down the cluster
    with open(cluster_config_file, "w") as out_f:
        json.dump({
            "mode": "gce",
            "algorithm": algorithm,
            "testDaemon": test_daemon_endpoint,
            "nodes": cluster
        }, out_f, indent=4)
    print("Cluster configuration saved in file {}.\n".format(cluster_config_file))
    print("To perform a test run: test_executor.py {} test_file_name".format(cluster_config_file))
    print("To stop the cluster run: tear_down.py {}".format(cluster_config_file))


# socket utility

def get_free_random_port():
    while True:
        s = socket.socket()
        s.bind(("", 0))  # bind to a free random port
        port = s.getsockname()[1]
        if port not in RANDOM_PORTS_POOL:
            RANDOM_PORTS_POOL.add(port)
            return port


def is_socket_free(host, port, tcp=True):
    protocol = socket.SOCK_STREAM if tcp else socket.SOCK_DGRAM
    with closing(socket.socket(socket.AF_INET, protocol)) as sock:
        return sock.connect_ex((host, port)) == 0  # function returns 0 if port is open (no process is using the port)


# provisioner utility

def get_node_config(cluster, node, additional_ports=None):
    if additional_ports is None:
        additional_ports = []
    return {"interface": node["interface"],
            "rpcPort": node["rpcPort"],
            "host": {
                "port": node["port"],
                "address": node["address"],
                "id": node["id"]},
            "peers": [{
                "address": peer["address"],
                "port": peer["port"],
                "id": peer["id"],
                "portsToLock": [peer["port"]] + additional_ports} for peer in cluster if peer["id"] != node["id"]]}


def get_random_string(length):
    return ''.join(random.choice(string.ascii_lowercase) for _ in range(length))


# GCP utility

def list_instances(compute):
    return compute.instances().list(project=GCP_PROJECT_ID, zone=GCE_ZONE_ID).execute().get("items", [])


def gcs_file_exists(gcs, file_name):
    try:
        gcs.objects().get(bucket=GCS_BUCKET, object=file_name).execute()
        return True
    except:
        return False


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
                "https://www.googleapis.com/auth/devstorage.read_write",  # allow Google Cloud Storage read/write
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
        return gcs.objects().insert(bucket=GCS_BUCKET, body=body, predefinedAcl="publicRead",
                                    media_body=http.MediaIoBaseUpload(f, 'application/octet-stream')).execute()


# algorithm utility

def configure_pso_local(cluster, node_file_path, test_daemon):
    # the first PSO node must be configured to send callbacks to test daemon
    print("Running PSO node at {}:{}...".format(cluster[0]["address"], cluster[0]["port"]))
    print(run_pso_node(cluster[0]["port"], node_file_path.format(cluster[0]["id"]), test_daemon))
    # the others don't have to send callbacks
    for node in cluster[1:]:
        print("Running PSO node at {}:{}...".format(node["address"], node["port"]))
        print(run_pso_node(node["port"], node_file_path.format(node["id"])))


def configure_pso_gce(cluster, configure_daemons, test_daemon):
    # the first PSO node must be configured to send callbacks to test daemon
    print("Running PSO node at {}:{}...".format(cluster[0]["address"], cluster[0]["port"]))
    print(configure_daemons[0].run_pso_node(cluster[0]["port"], LOCAL_NODE_CONF_FILE, test_daemon))
    # the others don't have to send callbacks
    for (i, node) in enumerate(cluster[1:], start=1):
        print("Running PSO node at {}:{}...".format(node["address"], node["port"]))
        print(configure_daemons[i].run_pso_node(node["port"], LOCAL_NODE_CONF_FILE))


def configure_paxos_local(cluster, node_file_path, test_daemon):
    # the first Paxos node must be configured to send callbacks to test daemon
    print("Running Paxos node at {}:{}...".format(cluster[0]["address"], cluster[0]["port"]))
    print(run_paxos_node(cluster[0]["port"], node_file_path.format(cluster[0]["id"]), test_daemon))
    # the others don't have to send callbacks
    for node in cluster[1:]:
        print("Running Paxos node at {}:{}...".format(node["address"], node["port"]))
        print(run_paxos_node(node["port"], node_file_path.format(node["id"])))


def configure_paxos_gce(cluster, configure_daemons, test_daemon):
    # the first Paxos node must be configured to send callbacks to test daemon
    print("Running Paxos node at {}:{}...".format(cluster[0]["address"], cluster[0]["port"]))
    print(configure_daemons[0].run_paxos_node(cluster[0]["port"], LOCAL_NODE_CONF_FILE, test_daemon))
    # the others don't have to send callbacks
    for (i, node) in enumerate(cluster[1:], start=1):
        print("Running Paxos node at {}:{}...".format(node["address"], node["port"]))
        print(configure_daemons[i].run_paxos_node(node["port"], LOCAL_NODE_CONF_FILE))


def configure_rethinkdb_local(cluster):
    # RethinkDB requires multiple nodes to join the master
    master_cluster_port = get_free_random_port()  # master port is used for joining
    # RethinkDB requires every node to provide a set of ports
    # One port is used to interact with the node running the algorithm (driver_port), the others are framework's ones
    # On localhost framework ports are generated randomly
    print("Running RethinkDB master node {}: ".format(cluster[0]['id']), cluster[0])
    print(configure_rethinkdb_master(master_cluster_port, cluster[0]['port'], get_free_random_port(), 'localhost'))
    for node in cluster[1:]:
        print("Running RethinkDB follower node {}: ".format(node['id']), node)
        print(configure_rethinkdb_follower(node['id'], cluster[0]['address'], master_cluster_port,
                                           get_free_random_port(), node['port'], get_free_random_port()))


def configure_rethinkdb_gce(cluster, configure_daemons):
    # RethinkDB requires multiple nodes to join the master
    # RethinkDB requires every node to provide a set of ports
    # One port is used to interact with the node running the algorithm (driver_port), the others are framework's ones
    # On GCE we can always use the same set of ports, because they will be surely available (VM just spun up)
    print("Trying to contact remote master configure daemon...")
    # configure_daemon = rpcClient('http://{}:{}'.format(cluster[0]['address'], CONFIGURE_DAEMON_PORT))
    print(configure_daemons[0].configure_rethinkdb_master(GCE_RETHINKDB_PORTS['cluster_port'],
                                                          GCE_RETHINKDB_PORTS['driver_port'],
                                                          GCE_RETHINKDB_PORTS['http_port'], cluster[0]['address']))
    print("Trying to contact remote followers configure daemons...")
    for (i, node) in enumerate(cluster[1:]):
        print(configure_daemons[i + 1].configure_rethinkdb_follower(node['id'], cluster[0]['address'],
                                                                    GCE_RETHINKDB_PORTS['cluster_port'],
                                                                    GCE_RETHINKDB_PORTS['cluster_port'],
                                                                    GCE_RETHINKDB_PORTS['driver_port'],
                                                                    GCE_RETHINKDB_PORTS['http_port']))


# main

def main():
    parser = argparse.ArgumentParser(description="Run a consensus algorithm on a cluster of nodes.")
    parser.add_argument("-n", "--nodes", type=int, choices=range(1, MAX_CLUSTER_NODES + 1), dest="nodes", default=3,
                        help="cluster nodes number")
    parser.add_argument("-m", "--mode", type=str, choices=CLUSTER_MODES, dest="mode", default="local",
                        help="cluster node location")
    parser.add_argument("-a", "--algorithm", type=str, choices=CONSENSUS_ALGORITHMS, dest="algorithm",
                        default="datastore", help="consensus algorithm")
    args = parser.parse_args()
    print("Going to deploy a cluster of {} nodes on {}. Please wait...".format(args.nodes, args.mode))

    # try:
    #     p = subprocess.Popen("sudo echo", stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
    #     out, err = p.communicate()
    #     if err:
    #         raise Exception()
    # except:
    #     print("You must execute this program as sudoer!")
    #     exit(1)

    # Provisioning steps:
    # 1. spin machines (possibly running a configure daemon on each of them)
    # 2. run algorithm (possibly by using each configure daemon)
    # 3. run network managers
    # 4. run test daemon

    try:
        if args.mode == "local":
            provide_local_cluster(args.nodes, args.algorithm)
        elif args.mode == "gce":
            provide_gce_cluster(args.nodes, args.algorithm)
    except Exception as e:
        print("An error occurred while setting up the cluster: {}".format(e))
        print("The environment can be in an inconsistent state (VMs may be on, files may require deletion, etc).")
        print("Cluster configuration file may not be available for tear_down.py. Please, check components manually.")


if __name__ == "__main__":
    main()
