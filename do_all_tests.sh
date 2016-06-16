#!/bin/bash

for testfile in $( ls ./Tests/*.test ); do
    printf "[INFO] Starting test %s\n\n" "$testfile"
    ./test_executor.py masterConfig.json "$testfile"
    printf "\n[INFO]Done!\n\n"
done

for csv in $( ls ./Tests/*.csv ); do
    printf "[INFO] Generating chart from %s\n" "$csv"
    ./Tests/generate_plots.py "$csv"
done

printf "[INFO] Done!\n"