#!/usr/bin/python3.4
import argparse

import matplotlib.pyplot as plt
import csv
import sys
import seaborn as sns

PLOT_TYPES = ["distribution", "mass", "raw"]


# Format of the chart:
# x axis -> append number
# y axis -> time for that particular append
def generateRawPlot(test):

    # set figure size
    plt.figure(figsize=(15, 6))
    handles = []
    # draw plot
    for raw in test:
        label = raw.pop(0)
        xAxis = range(len(raw))
        yAxis = [float(i) for i in raw]
        handle, = plt.plot(xAxis, yAxis, label=label)
        handles.append(handle)
    # put axis labels
    plt.xlabel("operations")
    plt.ylabel("time (s)")
    plt.legend(handles=handles)


def generateDistributionPlot(test):

    sns.set(color_codes=True)
    for row in test:
        label = row.pop(0)
        d = [float(i) for i in row]
        # Plot a filled kernel density estimate
        sns.distplot(d, hist=False, kde_kws={"shade": True}, label=label)
    plt.xlim([-0.01, 0.1])
    plt.xlabel("time (s)")
    plt.ylabel("operations")


def generateMassPlot(test):
    # set figure size
    plt.figure(figsize=(15, 6))
    handles = []
    # draw plot
    for raw in test:
        label = raw.pop(0)
        yAxis = [i / (len(raw)) for i in range(len(raw) + 1)]
        values = sorted([float(i) for i in raw])
        xAxis = [0] + values
        handle, = plt.plot(xAxis, yAxis, label=label)
        handles.append(handle)
    # put axis labels
    plt.xlabel("time (s)")
    plt.ylabel("probability of completion")
    plt.legend(handles=handles)


def main():
    argument_parser = argparse.ArgumentParser(description="Generates graph from test csv")
    argument_parser.add_argument("result_csv", type=str, nargs="*",
                                 help="path to test.csv file")
    argument_parser.add_argument("-t", "--type", type=str, choices=PLOT_TYPES, dest="type", default="raw",
                                 help="type of graph to print")
    argument_parser.add_argument("-o", "--output", type=str, dest="output_file_path",
                                 help="path of the output graph file")
    argument_parser.add_argument("-s", help="shows the results on a window", action="store_true")

    args = argument_parser.parse_args()

    data_series = []
    try:
        for result_csv in args.result_csv:
            with open(result_csv, "r") as f:
                rdr = csv.reader(f, delimiter=',', quotechar='|')
                for row in rdr:
                    data_series.append(row)
    except FileNotFoundError as e:
        print("File '{}' not found".format(args.result_csv))

    if not args.output_file_path:
        if len(args.result_csv) > 1:
            print("You must specify a output file name if you are printing a multiple file graph!")
            exit(1)
        output_file = args.result_csv[0]+".png"
    else:
        output_file = args.output_file_path

    if args.type == "raw":
        generateRawPlot(data_series)
    elif args.type == "distribution":
        generateDistributionPlot(data_series)
    else:
        generateMassPlot(data_series)

    plt.savefig(output_file)

    if args.s:
        plt.show()


if __name__ == '__main__':
    main()
