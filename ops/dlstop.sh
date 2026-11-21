#!/usr/bin/env bash
pkill -f "ops/fetch.py" 2>/dev/null; sleep 2; find ~/machina/input -name '*.part~' -delete 2>/dev/null; echo stopped
