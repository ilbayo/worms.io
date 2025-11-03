# tfd_seq/config.py

from pathlib import Path

# default output dirs
BASE_DIR = Path(".").resolve()
TRIM_DIR = BASE_DIR / "trimmed_reads"
MAP_DIR = BASE_DIR / "mapped_reads"
VARIANT_DIR = BASE_DIR / "variants"

TRIM_DIR.mkdir(exist_ok=True, parents=True)
MAP_DIR.mkdir(exist_ok=True, parents=True)
VARIANT_DIR.mkdir(exist_ok=True, parents=True)
