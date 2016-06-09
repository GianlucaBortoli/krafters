import json
import sys
import subprocess
from time import sleep
from oauth2client.client import GoogleCredentials
from googleapiclient import discovery
from provisioner import GCP_PROJECT_ID, GCE_ZONE_ID


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


def delete_instance(gce, name):
    return gce.instances().delete(project=GCP_PROJECT_ID, zone=GCE_ZONE_ID, instance=name).execute()


def tear_down_gce_cluster(conf):
    credentials = GoogleCredentials.get_application_default()
    gce = discovery.build("compute", "v1", credentials=credentials)
    zone_operations = []
    for node in conf["nodes"]:
        print("Deleting node {}...".format(node["vmID"]))
        zone_operations.append(delete_instance(gce, node["vmID"]))
    for op in zone_operations:
        while True:
            result = gce.zoneOperations().get(project=GCP_PROJECT_ID, zone=GCE_ZONE_ID, operation=op["name"]).execute()
            if result["status"] == "DONE":
                # if "error" in result: raise Exception(result["error"])  # TODO handle error
                print("Deleted node {}".format(result["targetLink"].split("/")[-1]))
                break
            sleep(1)
    print("Cluster torn down correctly. Bye!")


def main():
    with open(sys.argv[1]) as configuration_f:
        conf = json.load(configuration_f)
    print("Tearing down a cluster of {} nodes on {}. Please wait...".format(str(len(conf["nodes"])), conf["mode"]))
    if conf["mode"] == "local":
        tear_down_local_cluster(conf)
    elif conf["mode"] == "gce":
        tear_down_gce_cluster(conf)

if __name__ == "__main__":
    main()
