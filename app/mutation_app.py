# app/mutation_load.py
import pandas as pd

def load_variant_file(path_or_buffer):
    """Load a variant table from a TSV file or BytesIO object."""
    df = pd.read_csv(path_or_buffer, sep="\t")
    expected_cols = ["Chromosome", "Position", "AltAlleleFreq"]
    for c in expected_cols:
        if c not in df.columns:
            raise ValueError(f"Missing required column: {c}")
    return df


def compute_mutation_load(df, chrom, start, end, bin_size=30):
    """Compute sliding-window mutation load."""
    region = df[
        (df["Chromosome"] == chrom)
        & (df["Position"] >= start)
        & (df["Position"] <= end)
        & (df["AltAlleleFreq"] <= 0.35)
    ]
    xs, ys = [], []
    for s in range(start, end - bin_size + 2):
        e = s + bin_size - 1
        bin_ev = region[(region["Position"] >= s) & (region["Position"] <= e)]
        if len(bin_ev) >= 4:  # at least 4 events to count
            score = len(bin_ev) * bin_ev["AltAlleleFreq"].mean()
            xs.append(s)
            ys.append(score)
    return xs, ys

