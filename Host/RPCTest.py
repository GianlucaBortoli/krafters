import xmlrpclib

#Example of rpc usage
s = xmlrpclib.ServerProxy('http://localhost:10001')
#s.init_qdisc()
print s.modify_connection("2", "delay 100ms")
