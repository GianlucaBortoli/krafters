#!/bin/bash

DIR=final_tests/global_rethinkdb

for testfile in $( ls $DIR/*.test ); do
    printf "[INFO] Starting test %s\n\n" "$testfile"
    ./test_executor.py masterConfig.json "$testfile"
    printf "\n[INFO]Done!\n\n"
done

printf "[INFO] Done!\n"