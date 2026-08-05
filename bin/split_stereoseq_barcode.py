#!/usr/bin/env python3
"""Split Flexiplex stereoseq output into read1 (CID+MID) + read2 (cDNA) for ST_BarcodeMap.

Flexiplex demux output (stdin): FASTQ with read name ``@<CID>_<MID>#<read_id>``
(optionally with CB/UB tags appended). The UMI in the name is the 10bp MID.
Output read1.fq (CID+MID sequence, all-I quality) + read2.fq (cDNA).
"""
import sys
from pathlib import Path

CID_LEN = 25
MID_LEN = 10


def main():
    out1 = Path(sys.argv[1])  # read1.fq
    out2 = Path(sys.argv[2])  # read2.fq
    qual = "I" * (CID_LEN + MID_LEN)

    with open(out1, "w") as f1, open(out2, "w") as f2:
        name = sys.stdin.readline()
        while name:
            seq = sys.stdin.readline()
            sep = sys.stdin.readline()
            qual_line = sys.stdin.readline()

            # name: "@CID_MID#read_id" (possibly + \tCB:Z:...\tUB:Z:... tags)
            assert name[0] == "@", f"Expected @, got {name[0]}"
            rest = name[1:].strip()
            cb_part = rest.split("#")[0]  # "CID_MID"
            cb_parts = cb_part.split("_")
            cid = cb_parts[0]  # CID (25bp)
            mid = cb_parts[1][-MID_LEN:]  # MID (10bp, last 10 of the UMI field)
            read_id = rest.split("#")[1] if "#" in rest else ""
            read_id = read_id.split("\t")[0]  # strip trailing tags

            # clean 4-line FASTQ: @name / seq / + / qual  (no tags in name)
            new_name = f"@{cid}_{mid}#{read_id}\n"
            f1.write(new_name)
            f1.write(f"{cid}{mid}\n+\n{qual}\n")
            f2.write(new_name)
            f2.write(seq)
            f2.write("+\n")
            f2.write(qual_line)

            name = sys.stdin.readline()


if __name__ == "__main__":
    main()