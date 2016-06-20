#!/usr/bin/python

import matplotlib.pyplot as plt
import csv
import sys
import seaborn as sns

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

def generateDistributionPlot(result_csv):
    test = []
    with open(result_csv, "r") as f:
        rdr = csv.reader(f, delimiter=',', quotechar='|')
        for row in rdr:
            test.append(row)

    sns.set(style="white", palette="muted", color_codes=True)
    i = 0
    for row in test:
        i += 1
        d = [float(i) for i in row]
        # Plot a filled kernel density estimate
        sns.distplot(d, hist=False, kde_kws={"shade": True}, label=str(i))
    plt.xlim([-0.01,0.1])
    plt.savefig(result_csv + ".png")

def generateMassPlot(result_csv):
    #to implement
    pass

if __name__ == '__main__':
    if len(sys.argv) == 2:
        generateDistributionPlot(sys.argv[1])
    else:
        print("Please provide *only* one csv file as argument")
