import pandas as pd
import io

def load_variant_file(raw_bytes):
    # try utf-8, fallback to latin-1
    try:
        text = raw_bytes.decode("utf-8")
    except UnicodeDecodeError:
        text = raw_bytes.decode("latin-1")

    # auto-detect separator (tab or comma or spaces)
    df = pd.read_csv(
        io.StringIO(text),
        sep=None,            # let pandas sniff
        engine="python"      # needed for sep=None
    )

    # normalize columns
    lower = {c.lower(): c for c in df.columns}

    def pick(*cands):
        for c in cands:
            if c.lower() in lower:
                return lower[c.lower()]
        raise ValueError(f"Missing required column: one of {cands}")

    chrom_col = pick("Chromosome", "chrom", "chr", "#chrom")
    pos_col   = pick("Position", "pos", "start")
    af_col    = pick("AltAlleleFreq", "altallelefreq", "AF", "alt_freq", "allele_freq")

    df = df.rename(columns={
        chrom_col: "Chromosome",
        pos_col: "Position",
        af_col: "AltAlleleFreq",
    })

    return df
