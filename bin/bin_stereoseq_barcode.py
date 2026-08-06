#!/usr/bin/env python3
"""Bin ST_BarcodeMap output + rewrite read name to bambu-pipe format.

Input: ST_BarcodeMap mapped_r2.fq.gz. Read name format:
    @CID_MID#read_id|||CB:Z:x_y|||UR:Z:MID
(the first part is the read1 name from the split script; the actual read_id
is everything after the last '#').

Output (stdout): FASTQ with read name:
    @bin{bs}_{x//bs}_{y//bs}_{MID}#read_id
"""
import sys
import gzip


def parse_stereoseq_name(name):
    """Parse ST_BarcodeMap read name -> (read_id, x, y, mid)."""
    rest = name.strip()
    parts = rest.split("|||")
    first = parts[0]  # "@CID_MID#read_id"
    read_id = first.split("#")[-1]  # strip the @CID_MID# prefix
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
    target_bs = int(sys.argv[2]) if len(sys.argv) > 2 else 50

    with gzip.open(fastq_gz, "rt") as fq:
        while True:
            name = fq.readline()
            if not name:
                break
            seq = fq.readline()
            sep = fq.readline()
            qual = fq.readline()

            read_id, x, y, mid = parse_stereoseq_name(name)
            if read_id is None:
                continue

            bx = x // target_bs
            by = y // target_bs
            # barcode without underscores so bambu's <barcode>_<umi># parse is unambiguous
            cb = f"bin{target_bs}x{bx}y{by}"

            new_name = f"@{cb}_{mid}#{read_id}\n"
            sys.stdout.write(new_name)
            sys.stdout.write(seq)
            sys.stdout.write(sep)
            sys.stdout.write(qual)


if __name__ == "__main__":
    main()