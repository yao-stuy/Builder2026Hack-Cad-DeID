#!/usr/bin/env bash
# Quick status: download progress, memory, disk. Run inside Ubuntu WSL.
cd ~/machina || exit 1
n=$(find input -path input/.get-input -prune -o -type f -print 2>/dev/null | wc -l)
sz=$(du -sb input 2>/dev/null | cut -f1)
echo "input: files=$n bytes=$sz ($((sz/1000000000)) GB of 139.7)"
pgrep -fc "get-input.sh" | sed 's/^/get-input procs: /'
free -m | sed -n 2p
df -h / | tail -1
