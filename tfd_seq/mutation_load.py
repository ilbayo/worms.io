# tfd_seq/mutation_load.py

import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path

def mutation_load_sliding_window(
    variant_file: str,
    chrom: str,
    start: int,
    end: int,
    bin_size: int = 30,
    max_alt_freq: float = 0.35,
    out_png: str | None = None,
):
    df = pd.read_csv(variant_file, sep="\t")
    region = df[(df["Chromosome"] == chrom) & (df["Position"] >= start) & (df["Position"] <= end)]

    bins = []
    scores = []

    for s in range(start, end - bin_size + 2):
        e = s + bin_size - 1
        subset = region[(region["Position"] >= s) & (region["Position"] <= e)]
        subset = subset[subset["AltAlleleFreq"] <= max_alt_freq]
        if len(subset) > 0:
            score = len(subset) * subset["AltAlleleFreq"].mean()
        else:
            score = 0
        bins.append(s)
        scores.append(score)

    plt.figure(figsize=(10,4))
    plt.plot(bins, scores)
    plt.title(f"Mutation load {chrom}:{start}-{end}")
    plt.xlabel("Genomic position")
    plt.ylabel("Weighted score")
    plt.tight_layout()

    if out_png:
        plt.savefig(out_png, dpi=150)
        print(f"[tfd-seq] Saved plot to {out_png}")
    else:
        plt.show()
