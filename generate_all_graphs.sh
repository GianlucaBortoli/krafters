#!/bin/bash

DIR=final_tests

for csv in $( ls $DIR/*.csv ); do
    printf "\n[INFO]Generating graph for file %s\n..." "$csv"
    ./generate_plots.py -o "$csv.raw.png" "$csv"
    ./generate_plots.py -t mass -o "$csv.mass.png" "$csv"
    ./generate_plots.py -t distribution -o "$csv.dist.png" "$csv"
    printf "\n[INFO]Done!\n"
done