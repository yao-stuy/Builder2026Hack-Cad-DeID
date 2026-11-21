#!/usr/bin/env bash
# Run a bash script from the project root: ops/run.sh ops/tmp/x.sh args
cd /mnt/c/Users/jcyao/cad-deid && s="$1" && shift && exec bash "$s" "$@"
