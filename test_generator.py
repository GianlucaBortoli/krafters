#!/usr/bin/python3.4


class Node:
    id = ""

    def __init__(self, id):
        self.id = str(id)

    @staticmethod
    def random():
        return "rand"

    def __str__(self):
        return self.id


class NodeGroup:
    nodes = []

    def __init__(self, nodes=[]):
        if nodes:
            self.nodes = nodes

    @staticmethod
    def all():
        return "all"

    def add(self, node):
        self.nodes.append(node)

    def __str__(self):
        result = ""
        for node in self.nodes:
            result += str(node) + " "
        if len(result) > 0:
            result = result[:-1]
        return result


class Test:
    test_lines = []

    def __init__(self):
        self.test_lines = list()

    def run(self, n_op):
        self.test_lines.append("run {}".format(n_op))

    def reset(self):
        self.test_lines.append("reset")

    def from_to_command(self, sources, targets, bidirectional, netem_command):
        if bidirectional:
            return "from {} to {} bidirectional set {}".format(str(sources), str(targets), netem_command)
        else:
            return "from {} to {} set {}".format(str(sources), str(targets), netem_command)

    def set_delay(self, delay, sources=NodeGroup.all(), targets=NodeGroup.all(), bidirectional=False):
        self.test_lines.append(self.from_to_command(sources, targets, bidirectional, "delay {}ms".format(str(delay))))

    def set_loss(self, loss, sources=NodeGroup.all(), targets=NodeGroup.all(), bidirectional=False):
        self.test_lines.append(self.from_to_command(sources, targets, bidirectional, "loss {}%".format(str(loss))))

    # other functions here!

    def partition(self, group1, group2):
        self.set_loss(100, group1, group2, True)

    def repeat(self, test, times):
        self.test_lines.append("do")
        lines = test.get_lines()
        for line in lines:
            self.test_lines.append("\t{}".format(str(line)))
        self.test_lines.append("{} times".format(str(times)))

    def repeat_all(self, times):
        test_lines = ["do"]
        for line in self.test_lines:
            test_lines.append("\t{}".format(line))
        test_lines.append("{} times".format(str(times)))
        self.test_lines = test_lines

    def get_lines(self):
        return self.test_lines

    def print_to_file(self,  path):
        file = open(path, "wb")
        for line in self.test_lines:
            file.write(bytes("{}\n".format(str(line)),"UTF-8"))


def main():
    # example program
    partition1 = NodeGroup([Node(1), Node.random()])

    partition2 = NodeGroup()
    partition2.add(Node(2))
    partition2.add(Node.random())

    partition_test = Test()
    partition_test.partition(partition1, partition2)
    partition_test.run(100)

    complete_test = Test()
    complete_test.repeat(partition_test, 5)
    complete_test.reset()
    complete_test.set_delay(100)
    complete_test.run(100)
    complete_test.set_loss(40, Node.random(), NodeGroup.all())
    complete_test.run(100)
    complete_test.repeat_all(3)

    complete_test.print_to_file("test.test")



if __name__ == "__main__":
    main()



