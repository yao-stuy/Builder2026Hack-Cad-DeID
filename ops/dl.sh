#!/usr/bin/env bash
# Run one downloader shard (resumable). Usage: dl.sh PRIMARY(s3|mirror) SHARD(k/n) THREADS
cp -n /mnt/c/Users/jcyao/cad-deid/starter/manifest.tsv ~/machina/manifest.tsv 2>/dev/null
export FETCH_PRIMARY="${1:-s3}" FETCH_SHARD="${2:-0/1}"
exec python3 -u /mnt/c/Users/jcyao/cad-deid/ops/fetch.py ~/machina/manifest.tsv ~/machina/input "${3:-96}"
