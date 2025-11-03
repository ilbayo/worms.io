# tfd_seq/trim.py

import subprocess
from pathlib import Path

def run_trim_galore(fastq1: str, fastq2: str | None = None, output_dir: str = "trimmed_reads"):
    """
    Run Trim Galore on single-end or paired-end FASTQ files.
    """
    outdir = Path(output_dir)
    outdir.mkdir(parents=True, exist_ok=True)

    if fastq2:
        cmd = [
            "trim_galore",
            "--paired",
            "--output_dir", str(outdir),
            fastq1, fastq2,
        ]
    else:
        cmd = [
            "trim_galore",
            "--output_dir", str(outdir),
            fastq1,
        ]

    print("[tfd-seq] running:", " ".join(cmd))
    subprocess.run(cmd, check=True)
    print(f"[tfd-seq] trimming done, files in: {outdir}")
    return str(outdir)
