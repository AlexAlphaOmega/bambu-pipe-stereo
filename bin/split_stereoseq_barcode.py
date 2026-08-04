#!/usr/bin/env python3
"""Split Flexiplex stereoseq output into read1 (CID+MID) + read2 (cDNA) for ST_BarcodeMap.

Flexiplex output (stdin): FASTQ with read name ``<CID>_<link1+MID>#<read_id>``.
Split the UMI field (25bp) into link1 (15bp) + MID (10bp), discard link1.
Output read1.fq (CID+MID sequence, all-I quality) + read2.fq (cDNA, passthrough).
"""
import sys
from pathlib import Path

LINK1_LEN = 15
MID_LEN = 10
CID_LEN = 25


def main():
    out1 = Path(sys.argv[1])  # read1.fq
    out2 = Path(sys.argv[2])  # read2.fq
    qual = "I" * (CID_LEN + MID_LEN)

    with open(out1, "w") as f1, open(out2, "w") as f2, open(sys.stdin.fileno(), "r") as fq:
        while True:
            name = fq.readline()
            if not name:
                break
            seq = fq.readline()
            sep = fq.readline()  # "+"
            qual_line = fq.readline()

            # name: "@CID_link1+MID#read_id"
            # strip "@" and everything after "#"
            assert name[0] == "@", f"Expected @, got {name[0]}"
            rest = name[1:].strip()
            cb_part = rest.split("#")[0]  # "CID_link1+MID"
            cb_parts = cb_part.split("_")
            cid = cb_parts[0]  # CID (25bp)
            umi = cb_parts[1]  # link1+MID (25bp)
            mid = umi[LINK1_LEN:]  # MID (10bp, after 15bp link1)

            # read1: CID+MID as sequence, all-I quality
            new_name = f"@{cid}_{mid}#{rest.split('#')[1] if '#' in rest else ''}\n"
            f1.write(new_name)
            f1.write(f"{cid}{mid}\n")
            f1.write("+\n")
            f1.write(f"{qual}\n")

            # read2: cDNA passthrough, rewrite name with CID_MID
            f2.write(new_name)
            f2.write(seq)
            f2.write(sep)
            f2.write(qual_line)


if __name__ == "__main__":
    main()