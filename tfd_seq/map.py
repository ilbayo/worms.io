# tfd_seq/map.py

import subprocess
import pysam
import os
from pathlib import Path
from .config import MAP_DIR

def map_reads_and_sort(reference: str, read1: str, read2: str, output_prefix: str, output_dir: str | Path = MAP_DIR):
    """
    Maps paired-end reads to a reference genome using BWA,
    converts to sorted BAM, and indexes.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    sam_file = output_dir / f"{output_prefix}.sam"
    unsorted_bam = output_dir / f"{output_prefix}_unsorted.bam"
    sorted_bam = output_dir / f"{output_prefix}_sorted.bam"

    reference = Path(reference)

    try:
        # index reference if needed
        if not reference.with_suffix(".fa.fai").exists() and not (str(reference) + ".fai"):
            print("[tfd-seq] Indexing reference with samtools faidx ...")
            pysam.faidx(str(reference))

        print("[tfd-seq] Mapping with BWA MEM ...")
        with open(sam_file, "w") as sam_out:
            bwa_cmd = [
                "bwa", "mem",
                str(reference), read1, read2
            ]
            result = subprocess.run(bwa_cmd, stdout=sam_out, stderr=subprocess.PIPE, text=True)
            if result.returncode != 0:
                print("[tfd-seq] Error during BWA mapping:")
                print(result.stderr)
                return None

        print("[tfd-seq] Converting SAM to BAM ...")
        subprocess.run(["samtools", "view", "-b", "-o", str(unsorted_bam), str(sam_file)], check=True)

        print("[tfd-seq] Sorting BAM ...")
        subprocess.run(["samtools", "sort", "-o", str(sorted_bam), str(unsorted_bam)], check=True)

        print("[tfd-seq] Indexing sorted BAM ...")
        subprocess.run(["samtools", "index", str(sorted_bam)], check=True)

        # cleanup
        os.remove(sam_file)
        os.remove(unsorted_bam)

        print(f"[tfd-seq] Done. Sorted BAM: {sorted_bam}")
        return str(sorted_bam)

    except Exception as e:
        print(f"[tfd-seq] Unexpected error: {e}")
        return None
