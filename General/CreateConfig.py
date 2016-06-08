import json
import sys


def create_configuration_files(peers, path):
    for peer in peers:
        data = {"interface": peer["interface"],
                "rpcPort": peer["rpcPort"],
                "host": {
                    "port": peer["port"],
                    "address": peer["address"],
                    "id": peer["id"]
                },
                "peers": []}
        for other_peer in peers:
            if other_peer["id"] != peer["id"]:
                data["peers"].append({
                    "address": other_peer["address"],
                    "port": other_peer["port"],
                    "id": other_peer["id"]
                })

        with open(path+"config" + str(peer["id"]) + ".json", 'w') as outfile:
            json.dump(data, outfile)


def main():
    try:
        # Loads configuration file
        with open(sys.argv[1]) as configuration_file:
            peers = json.load(configuration_file)
    except:
        print(sys.argv[1] + " is not a valid JSON file")
        exit(1)

    path = ""
    create_configuration_files(peers,path)


if __name__ == "__main__":
    main()
