#!/usr/bin/env bash
# Create the Python venv used by the pipeline (inside Ubuntu WSL, on ext4).
set -e
mkdir -p ~/machina/work ~/machina/private
for t in aria2c 7z 7zz unzip unrar zstd qpdf mutool exiftool git gcc; do printf "%s=" "$t"; command -v "$t" >/dev/null && echo yes || echo no; done | tr "\n" " "; echo
if [ ! -x ~/machina/venv/bin/python ]; then python3 -m venv ~/machina/venv || { echo VENV_FAILED; exit 3; }; fi
~/machina/venv/bin/python -m pip install -q --upgrade pip 2>&1 | tail -1
~/machina/venv/bin/python -m pip install -q olefile pymupdf pikepdf pyahocorasick pillow numpy py7zr rarfile ezdxf openpyxl lxml xxhash chardet 2>&1 | tail -3
~/machina/venv/bin/python -c "import olefile, fitz, pikepdf, ahocorasick, PIL, numpy, py7zr, rarfile, ezdxf, openpyxl, lxml, xxhash; print('ALL IMPORTS OK')"
