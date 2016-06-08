#!/usr/bin/python3.4

# Built only to test configure_daemon functionalities on localhost

import xmlrpc.client

RPC_PORT = 12345 

cluster = [
    {
        "id": 1,
        "ip": "localhost"
    },
    {
        "id": 2,
        "ip": "localhost"
    },
    {
        "id": 3,
        "ip": "localhost"
    }
]


def createServer(ip, port):
    return xmlrpc.client.ServerProxy('http://{}:{}'.format(ip, port))


def configure_rethinkdb(cluster):
    # Configures every node of the cluster.
    # Works both for local and distributed mode
    for node in cluster:
        s = createServer(node['ip'], RPC_PORT)
        if node['id'] == 1:
            # the first node is always the master
            print(s.configure_rethinkdb_master())
        else:
            # all the others are followers
            # NOTE: the offset is set to id-1 since ids are 1..N
            print(s.configure_rethinkdb_follower(cluster[0]['ip'], 
                node['id'], 
                node['id'] - 1))
    return "Configuration done"


if __name__ == '__main__':
    s = createServer('localhost', RPC_PORT)
    print(configure_rethinkdb(cluster))
    #print(s.stop_rethinkdb())