#!/usr/bin/env python3
"""Bin ST_BarcodeMap output + rewrite read name to bambu-pipe format.

Input: ST_BarcodeMap mapped_r2.fq.gz. Read name format:
    <id>|||CB:Z:x_y|||UR:Z:MID

Output (stdout): FASTQ with read name:
    <bin{bs}_{x//bs}_{y//bs}>_<MID>#<id>

For multiple binsizes (comma-separated, e.g. "50" or "20,50,100"),
the primary output (stdout) uses the target binsize (default 50).
"""
import sys
import gzip
from pathlib import Path

LINK1_LEN = 15


def parse_stereoseq_name(name):
    """Parse ST_BarcodeMap read name -> (id, x, y, mid)."""
    rest = name.strip()
    # Split on |||
    parts = rest.split("|||")
    read_id = parts[0]  # everything before |||
    cb = None
    ur = None
    for p in parts[1:]:
        if p.startswith("CB:Z:"):
            cb = p[5:]  # x_y
        elif p.startswith("UR:Z:"):
            ur = p[5:]  # MID
    if cb is None or ur is None:
        return None, None, None, None
    x_str, y_str = cb.split("_")
    return read_id, int(x_str), int(y_str), ur


def main():
    fastq_gz = sys.argv[1]  # mapped_r2.fq.gz
    target_bs = int(sys.argv[2]) if len(sys.argv) > 2 else 50  # target binsize (default 50)

    with gzip.open(fastq_gz, "rt") as fq:
        while True:
            name = fq.readline()
            if not name:
                break
            seq = fq.readline()
            sep = fq.readline()
            qual = fq.readline()

            # Parse ST_BarcodeMap read name
            read_id, x, y, mid = parse_stereoseq_name(name)
            if read_id is None:
                continue  # skip reads without CB/UR

            # Bin to target binsize
            bx = x // target_bs
            by = y // target_bs
            cb = f"bin{target_bs}_{bx}_{by}"

            # Rewrite to bambu-pipe format: <barcode>_<umi>#<read_id>
            new_name = f"@{cb}_{mid}#{read_id}\n"
            sys.stdout.write(new_name)
            sys.stdout.write(seq)
            sys.stdout.write(sep)
            sys.stdout.write(qual)


if __name__ == "__main__":
    main()