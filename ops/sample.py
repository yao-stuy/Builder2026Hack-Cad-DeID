#!/usr/bin/env python3
"""List downloaded input files of one type. Usage: sample.py EXT [N] [--biggest|--smallest]
EXT like .step or 'prt.*' (regex on the lower-cased file name end, anchored at the end)."""
import os, random, re, sys
ext = sys.argv[1].lower(); n = int(sys.argv[2]) if len(sys.argv) > 2 and sys.argv[2].isdigit() else 20
rx = re.compile((re.escape(ext) if ext.startswith('.') else ext) + r'$')
root = os.path.expanduser('~/machina/input'); hits = []
for d, _dirs, files in os.walk(root):
    for f in files:
        if rx.search(f.lower()) and not f.endswith('.part~'):
            p = os.path.join(d, f); hits.append((os.path.getsize(p), p))
if '--biggest' in sys.argv: hits.sort(reverse=True)
elif '--smallest' in sys.argv: hits.sort()
else: random.Random(3).shuffle(hits)
print(f'# {len(hits)} files match', file=sys.stderr)
for s, p in hits[:n]: print(f'{s}\t{p}')
