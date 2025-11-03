# tfd_seq/variants.py

import pysam
from collections import Counter
from pathlib import Path
from .config import VARIANT_DIR

def analyze_bam_improved(
    bam_file: str,
    ref_fasta: str,
    output_file: str | None = None,
    min_coverage: int = 20,
    min_alt_reads: int = 5,
    mapq_threshold: int = 50,
):
    """
    Identifies positions with alternative alleles in the genome from a BAM file.
    """
    bam = pysam.AlignmentFile(bam_file, "rb")
    ref = pysam.FastaFile(ref_fasta)

    output_path = Path(output_file) if output_file else VARIANT_DIR / (Path(bam_file).stem + "_variants.txt")

    with open(output_path, "w") as out:
        out.write("Chromosome\tPosition\tReadsPassingMAPQ\tAltReads\tAltAlleleFreq\tMultiallelic\n")

        for pileup_column in bam.pileup(stepper='all', truncate=True, min_base_quality=0):
            chrom = pileup_column.reference_name
            pos = pileup_column.reference_pos + 1

            base_calls = []
            for pileup_read in pileup_column.pileups:
                if pileup_read.is_del or pileup_read.is_refskip:
                    continue
                read = pileup_read.alignment
                if read.mapping_quality >= mapq_threshold:
                    base = read.query_sequence[pileup_read.query_position]
                    base_calls.append(base)

            total_reads = len(base_calls)
            if total_reads < min_coverage:
                continue

            base_counts = Counter(base_calls)
            reference_base = ref.fetch(chrom, pos - 1, pos).upper()
            alt_counts = {b: c for b, c in base_counts.items() if b != reference_base}

            alt_reads = sum(alt_counts.values())
            if alt_reads < min_alt_reads:
                continue

            alt_allele_freq = alt_reads / total_reads
            multiallelic = "Yes" if len(alt_counts) > 1 else "No"

            out.write(f"{chrom}\t{pos}\t{total_reads}\t{alt_reads}\t{alt_allele_freq:.4f}\t{multiallelic}\n")

    bam.close()
    ref.close()
    print(f"[tfd-seq] Variant analysis completed. Saved to {output_path}")
    return str(output_path)
