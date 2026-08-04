#!/usr/bin/env python3
"""Extract stereoseq spatial coordinates from ST_BarcodeMap output.

Reads the mapped_r2 FASTQ (ST_BarcodeMap output), parses CB:Z:x_y,
bins to target binsize, writes unique bin entries.

If no FASTQ is provided (e.g. at PREPARE_INPUT_STANDARD stage), generates
a placeholder. The actual coords are extracted later from the BAM.

Usage:
    extract_stereoseq_coords.py <binsize> [mapped_r2.fq.gz] [output.txt]
"""
import sys
import gzip
from pathlib import Path

BS = int(sys.argv[1]) if len(sys.argv) > 1 else 50
fq_path = sys.argv[2] if len(sys.argv) > 2 else None
out_path = sys.argv[3] if len(sys.argv) > 3 else "stereoseq_coordinates.txt"

seen_bins = set()

if fq_path and Path(fq_path).exists():
    # Parse ST_BarcodeMap output: <id>|||CB:Z:x_y|||UR:Z:MID
    opener = gzip.open(fq_path, "rt") if fq_path.endswith(".gz") else open(fq_path)
    with opener as f:
        for line in f:
            if line.startswith("@"):
                rest = line.strip()
                for part in rest.split("|||"):
                    if part.startswith("CB:Z:"):
                        cb = part[5:]  # x_y
                        xs, ys = cb.split("_")
                        bx = int(xs) // BS
                        by = int(ys) // BS
                        seen_bins.add((bx, by))
                        break
    # If no data, fall through to placeholder
else:
    # No FASTQ provided (called from PREPARE_INPUT_STANDARD before
    # preprocessing). Write a placeholder; the actual coords will be
    # extracted from the BAM later.
    pass

with open(out_path, "w") as out:
    out.write("barcode\tx_coordinate\ty_coordinate\n")
    for bx, by in sorted(seen_bins):
        out.write(f"bin{BS}_{bx}_{by}\t{bx}\t{by}\n")