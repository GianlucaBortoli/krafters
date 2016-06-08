# Use server xmlrpc in order to listen for provisioner - configuring the algorithms for
# clout tests
#
# one runs for each node of the cluster
#
# Methods to provide to the provisioner:
# rethinkdb:    configure_rethinkdb_master & configure_rethinkdb_follower
# paxos:        configure_paxos
# pso:          < nothing to do here >