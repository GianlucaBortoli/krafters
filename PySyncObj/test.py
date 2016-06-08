#!/usr/bin/env python

import os
import time
import random
from functools import partial
import itertools
from pysyncobj import SyncObj, SyncObjConf, replicated, FAIL_REASON

class TestObjAutoTick(SyncObj):

    def __init__(self, selfNodeAddr, otherNodeAddrs,
                 compactionTest = 0,
                 dumpFile = None,
                 compactionTest2 = False):

        cfg = SyncObjConf(autoTick=True, commandsQueueSize=10000, appendEntriesUseBatch=False)
        if compactionTest:
            cfg.logCompactionMinEntries = compactionTest
            cfg.logCompactionMinTime = 0.1
            cfg.appendEntriesUseBatch = True
            cfg.fullDumpFile = dumpFile
        if compactionTest2:
            cfg.logCompactionMinEntries = 99999
            cfg.logCompactionMinTime = 99999
            cfg.fullDumpFile = dumpFile
            cfg.sendBufferSize = 2 ** 21
            cfg.recvBufferSize = 2 ** 21
            cfg.appendEntriesBatchSize = 10
            cfg.maxCommandsPerTick = 5

        super(TestObjAutoTick, self).__init__(selfNodeAddr, otherNodeAddrs, cfg)
        self.__counter = 0
        self.__data = {}

    @replicated
    def addValue(self, value):
        self.__counter += value
        return self.__counter

    def getCounter(self):
        return self.__counter


class TestObj(SyncObj):

    def __init__(self, selfNodeAddr, otherNodeAddrs,
                 compactionTest = 0,
                 dumpFile = None,
                 compactionTest2 = False):

        cfg = SyncObjConf(autoTick=False, commandsQueueSize=10000, appendEntriesUseBatch=False)
        if compactionTest:
            cfg.logCompactionMinEntries = compactionTest
            cfg.logCompactionMinTime = 0.1
            cfg.appendEntriesUseBatch = True
            cfg.fullDumpFile = dumpFile
        if compactionTest2:
            cfg.logCompactionMinEntries = 99999
            cfg.logCompactionMinTime = 99999
            cfg.fullDumpFile = dumpFile
            cfg.sendBufferSize = 2 ** 21
            cfg.recvBufferSize = 2 ** 21
            cfg.appendEntriesBatchSize = 10
            cfg.maxCommandsPerTick = 5

        super(TestObj, self).__init__(selfNodeAddr, otherNodeAddrs, cfg)
        self.__counter = 0
        self.__data = {}

    @replicated
    def addValue(self, value):
        self.__counter += value
        return self.__counter

    @replicated
    def addKeyValue(self, key, value):
        self.__data[key] = value

    def getCounter(self):
        return self.__counter

    def getValue(self, key):
        return self.__data.get(key, None)

    def dumpKeys(self):
        print 'keys:', sorted(self.__data.keys())

def doTicks(objects, timeToTick, interval = 0.05):
    currTime = time.time()
    finishTime = currTime + timeToTick
    realInterval = float(interval) / float(len(objects))
    while currTime < finishTime:
        for o in objects:
            o._onTick(realInterval)
        currTime = time.time()

_g_nextAddress = 6000 + 60 * (int(time.time()) % 600)


def getNextAddr():
    global _g_nextAddress
    _g_nextAddress += 1
    return 'localhost:%d' % _g_nextAddress

start = 0
iters = 10000

def onAdd(res, err, cnt):
    if cnt % 1000 == 0:
        print 'onAdd %d:' % cnt, res, err

    if cnt == iters:
        print 'time: ', (time.time() - start)
        # print 'Counter value:', o1.getCounter(), o1._getLeader(), o1._getRaftLogSize(), o1._getLastCommitIndex()


def syncTwoObjects():

    random.seed(42)

    a = [getNextAddr(), getNextAddr(), getNextAddr(), getNextAddr()]

    o1 = TestObj(a[0], [a[1], a[2], a[3]])
    o2 = TestObj(a[1], [a[0], a[2], a[3]])
    o3 = TestObj(a[2], [a[0], a[1], a[3]])
    o4 = TestObj(a[3], [a[0], a[1], a[2]])

    objs = [o1, o2, o3, o4]

    doTicks(objs, 5)

    assert o1._getLeader() in a
    assert o1._getLeader() == o2._getLeader() and o2._getLeader() == o3._getLeader() and o3._getLeader() == o4._getLeader()

    start = time.time()
    iters = 10001
    for i in range(1, iters):
        o1.addValue(1, callback=partial(onAdd, cnt=i))

    doTicks(objs, 31)
    print 'ASSERT OK?', o1.getCounter()
    print (o1.getCounter() == iters)
    print 'time: ', (end-start)
    print 'Counter value:', o1.getCounter(), o1._getLeader(), o1._getRaftLogSize(), o1._getLastCommitIndex()


def syncTwoObjectsBackup():

    random.seed(42)

    a = [getNextAddr(), getNextAddr(), getNextAddr(), getNextAddr()]

    o1 = TestObj(a[0], [a[1], a[2], a[3]])
    o2 = TestObj(a[1], [a[0], a[2], a[3]])
    o3 = TestObj(a[2], [a[0], a[1], a[3]])
    o4 = TestObj(a[3], [a[0], a[1], a[2]])

    objs = [o1, o2, o3, o4]

    doTicks(objs, 3.5)

    assert o1._getLeader() in a
    assert o1._getLeader() == o2._getLeader() and o2._getLeader() == o3._getLeader() and o3._getLeader() == o4._getLeader()

    tot_sum = 0
    deltas = []
    for i in range(1, 20):
        start = time.clock()
        for _ in itertools.repeat(None, i):
            o1.addValue(200, callback=partial(onAdd, cnt=200))
        # o2.addValue(210, callback=partial(onAdd, cnt=210))
        # o3.addValue(220, callback=partial(onAdd, cnt=220))
        # o4.addValue(230, callback=partial(onAdd, cnt=230))

        # print("Start ticking")
        doTicks(objs, 0.5 * i)
        # print("Stop Ticking")
        assert o1.getCounter() == i * 200 + tot_sum
        print 'i: ', i, ' time: ', (end-start)
        deltas.append(end-start)
        tot_sum = o1.getCounter()

    print(deltas)

    random_deltas = []
    for i in range(1, 20):
        start = time.clock()
        for _ in itertools.repeat(None, i):
            random_obj = objs[random.randint(0, 3)]
            random_obj.addValue(200, callback=partial(onAdd, cnt=200))
        # o2.addValue(210, callback=partial(onAdd, cnt=210))
        # o3.addValue(220, callback=partial(onAdd, cnt=220))
        # o4.addValue(230, callback=partial(onAdd, cnt=230))

        # print("Start ticking")
        doTicks(objs, 0.5 * i)
        # print("Stop Ticking")
        assert o1.getCounter() == i * 200 + tot_sum
        print 'i: ', i, ' time: ', (end-start)
        random_deltas.append(end-start)
        tot_sum = o1.getCounter()

    print(random_deltas)
    for i in range(len(deltas)):
        print(random_deltas[i] - deltas[i])


    # doTicks(objs, 1)

    # while not (o1.getCounter() == o2.getCounter() and o2.getCounter() == o3.getCounter() and o3.getCounter() == o4.getCounter()):
    # while True:
    #     print("{} {} {} {}".format(o1.getCounter(), o2.getCounter(), o3.getCounter(), o4.getCounter()))
    #     # o1.addValue(200, callback=partial(onAdd))
    #     time.sleep(1)
    #     doTicks(objs, 0.005)

    # print("Stop Ticking")
    #
    # assert o1.getCounter() == 860
    # assert o2.getCounter() == 860
    # # global end
    #
    # print 'Counter value:', o1.getCounter(), o1._getLeader(), o1._getRaftLogSize(), o1._getLastCommitIndex()




def syncThreeObjectsLeaderFail():

    random.seed(12)

    a = [getNextAddr(), getNextAddr(), getNextAddr()]

    o1 = TestObj(a[0], [a[1], a[2]])
    o2 = TestObj(a[1], [a[2], a[0]])
    o3 = TestObj(a[2], [a[0], a[1]])
    objs = [o1, o2, o3]

    doTicks(objs, 3.5)

    assert o1._getLeader() in a
    assert o1._getLeader() == o2._getLeader()
    assert o1._getLeader() == o3._getLeader()

    o1.addValue(150)
    o2.addValue(200)

    doTicks(objs, 0.5)

    assert o3.getCounter() == 350

    prevLeader = o1._getLeader()

    newObjs = [o for o in objs if o._getSelfNodeAddr() != prevLeader]

    assert len(newObjs) == 2

    doTicks(newObjs, 3.5)
    assert newObjs[0]._getLeader() != prevLeader
    assert newObjs[0]._getLeader() in a
    assert newObjs[0]._getLeader() == newObjs[1]._getLeader()

    newObjs[1].addValue(50)

    doTicks(newObjs, 0.5)

    assert newObjs[0].getCounter() == 400

    doTicks(objs, 3.5)
    for o in objs:
        assert o.getCounter() == 400

def manyActionsLogCompaction():

    random.seed(42)

    a = [getNextAddr(), getNextAddr(), getNextAddr()]

    o1 = TestObj(a[0], [a[1], a[2]], compactionTest=100)
    o2 = TestObj(a[1], [a[2], a[0]], compactionTest=100)
    o3 = TestObj(a[2], [a[0], a[1]], compactionTest=100)
    objs = [o1, o2, o3]

    doTicks(objs, 3.5)

    assert o1._getLeader() in a
    assert o1._getLeader() == o2._getLeader()
    assert o1._getLeader() == o3._getLeader()

    for i in xrange(0, 500):
        o1.addValue(1)
        o2.addValue(1)

    doTicks(objs, 1.5)

    assert o1.getCounter() == 1000
    assert o2.getCounter() == 1000
    assert o3.getCounter() == 1000

    assert o1._getRaftLogSize() <= 100
    assert o2._getRaftLogSize() <= 100
    assert o3._getRaftLogSize() <= 100

    newObjs = [o1, o2]
    doTicks(newObjs, 3.5)

    for i in xrange(0, 500):
        o1.addValue(1)
        o2.addValue(1)

    doTicks(newObjs, 4.0)

    assert o1.getCounter() == 2000
    assert o2.getCounter() == 2000
    assert o3.getCounter() != 2000

    doTicks(objs, 3.5)

    assert o3.getCounter() == 2000

    assert o1._getRaftLogSize() <= 100
    assert o2._getRaftLogSize() <= 100
    assert o3._getRaftLogSize() <= 100

def onAddValue(res, err, info):
    assert res == 3
    assert err == FAIL_REASON.SUCCESS
    info['callback'] = True

def checkCallbacksSimple():

    random.seed(42)

    a = [getNextAddr(), getNextAddr(), getNextAddr()]

    o1 = TestObj(a[0], [a[1], a[2]])
    o2 = TestObj(a[1], [a[2], a[0]])
    o3 = TestObj(a[2], [a[0], a[1]])
    objs = [o1, o2, o3]

    doTicks(objs, 3.5)

    assert o1._getLeader() in a
    assert o1._getLeader() == o2._getLeader()
    assert o1._getLeader() == o3._getLeader()


    callbackInfo = {
        'callback': False
    }
    o1.addValue(3, callback=partial(onAddValue, info=callbackInfo))

    doTicks(objs, 0.5)

    assert o2.getCounter() == 3
    assert callbackInfo['callback'] == True

def removeFiles(files):
    for f in (files):
        try:
            os.remove(f)
        except:
            pass

def checkDumpToFile():
    removeFiles(['dump1.bin', 'dump2.bin'])

    random.seed(42)

    a = [getNextAddr(), getNextAddr()]

    o1 = TestObj(a[0], [a[1]], compactionTest=True, dumpFile = 'dump1.bin')
    o2 = TestObj(a[1], [a[0]], compactionTest=True, dumpFile = 'dump2.bin')
    objs = [o1, o2]
    doTicks(objs, 3.5)

    assert o1._getLeader() in a
    assert o1._getLeader() == o2._getLeader()

    o1.addValue(150)
    o2.addValue(200)

    doTicks(objs, 1.0)

    assert o1.getCounter() == 350
    assert o2.getCounter() == 350

    del o1
    del o2

    a = [getNextAddr(), getNextAddr()]
    o1 = TestObj(a[0], [a[1]], compactionTest=1, dumpFile = 'dump1.bin')
    o2 = TestObj(a[1], [a[0]], compactionTest=1, dumpFile = 'dump2.bin')
    objs = [o1, o2]
    doTicks(objs, 3.5)

    assert o1._getLeader() in a
    assert o1._getLeader() == o2._getLeader()

    assert o1.getCounter() == 350
    assert o2.getCounter() == 350

    removeFiles(['dump1.bin', 'dump2.bin'])


def getRandStr():
    return '%0100000x' % random.randrange(16 ** 100000)


def checkBigStorage():
    removeFiles(['dump1.bin', 'dump2.bin'])

    random.seed(42)

    a = [getNextAddr(), getNextAddr()]

    o1 = TestObj(a[0], [a[1]], compactionTest2=True, dumpFile = 'dump1.bin')
    o2 = TestObj(a[1], [a[0]], compactionTest2=True, dumpFile = 'dump2.bin')
    objs = [o1, o2]
    doTicks(objs, 3.5)

    assert o1._getLeader() in a
    assert o1._getLeader() == o2._getLeader()

    # Store ~50Mb data.
    testRandStr = getRandStr()
    for i in xrange(0, 500):
        o1.addKeyValue(i, getRandStr())
    o1.addKeyValue('test', testRandStr)

    # Wait for replication.
    doTicks(objs, 15.0, 0.05)

    assert o1.getValue('test') == testRandStr

    o1._forceLogCompaction()
    o2._forceLogCompaction()

    # Wait for disk dump
    doTicks(objs, 5.0, 0.05)


    a = [getNextAddr(), getNextAddr()]
    o1 = TestObj(a[0], [a[1]], compactionTest=1, dumpFile = 'dump1.bin')
    o2 = TestObj(a[1], [a[0]], compactionTest=1, dumpFile = 'dump2.bin')
    objs = [o1, o2]
    doTicks(objs, 3.5)

    assert o1._getLeader() in a
    assert o1._getLeader() == o2._getLeader()

    assert o1.getValue('test') == testRandStr
    assert o2.getValue('test') == testRandStr

    removeFiles(['dump1.bin', 'dump2.bin'])


def magic():
    random.seed(42)
    a = [getNextAddr(), getNextAddr(), getNextAddr(), getNextAddr()]
    o1 = TestObjAutoTick(a[0], [a[1], a[2], a[3]])
    o2 = TestObjAutoTick(a[1], [a[0], a[2], a[3]])
    o3 = TestObjAutoTick(a[2], [a[0], a[1], a[3]])
    o4 = TestObjAutoTick(a[3], [a[0], a[1], a[2]])

    objs = [o1, o2, o3, o4]

    # while o1._getLeader() not in a:
    #     pass
    # assert o1._getLeader() == o2._getLeader() and o2._getLeader() == o3._getLeader() and o3._getLeader() == o4._getLeader()

    global start
    start = time.time()
    for i in range(1, iters + 1):
        o1.addValue(1, callback=partial(onAdd, cnt=i))
    time.sleep(60)

def runTests():
    magic()
    # syncTwoObjects()
    # syncThreeObjectsLeaderFail()
    # manyActionsLogCompaction()
    # checkCallbacksSimple()
    # checkDumpToFile()
    # checkBigStorage()
    print '[SUCCESS]'

if __name__ == '__main__':
    runTests()
