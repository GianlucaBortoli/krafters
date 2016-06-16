#!/usr/bin/python

import matplotlib.pyplot as plt
import csv
import sys

# Format of the chart:
# x axis -> append number
# y axis -> time for that particular append
def generatePlot(result_csv):
    # list of lists. Every inner list contains the times
    # of each "run" command in the test file 
    test = []
    with open(result_csv, "rb") as f:
        rdr = csv.reader(f, delimiter=',', quotechar='|')
        for row in rdr:
            test.append(row)

    # set figure size
    plt.figure(figsize=(15,6))
    # draw plot
    for raw in test:
        xAxis = range(len(raw))
        yAxis = raw
        plt.plot(xAxis, yAxis) 
    # put axis labels
    plt.xlabel("num append")
    plt.ylabel("time (s)")
    plt.savefig(result_csv + ".png")
    plt.show()

if __name__ == '__main__':
    if len(sys.argv) == 2:
        generatePlot(sys.argv[1])
    else:
        print("Please provide *only* one csv file as argument")
