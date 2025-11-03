from fastapi import FastAPI, UploadFile, File, Form, BackgroundTasks, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from pathlib import Path
import os
import uuid
import subprocess

app = FastAPI()

# base data dir – this matches the Render disk mount we talked about
DATA_DIR = Path("/app/app/data")
JOBS_DIR = DATA_DIR / "jobs"
JOBS_DIR.mkdir(parents=True, exist_ok=True)

# reference location (can be overridden in Render env vars)
REF_FASTA = os.environ.get("REF_FASTA", "/app/app/data/reference/genomic.fa")


# ----------------------------
# 1. try importing your real code
# ----------------------------
# We assume you created:
#   tfd_seq/trim.py       -> run_trim_galore(...)
#   tfd_seq/map.py        -> map_reads_and_sort(...)
#   tfd_seq/variants.py   -> analyze_bam_improved(...)
try:
    from tfd_seq.trim import run_trim_galore
except ImportError:
    run_trim_galore = None

try:
    from tfd_seq.map import map_reads_and_sort
except ImportError:
    map_reads_and_sort = None

try:
    from tfd_seq.variants import analyze_bam_improved
except ImportError:
    analyze_bam_improved = None


# ----------------------------
# HTML upload form
# ----------------------------
@app.get("/", response_class=HTMLResponse)
def index():
    return """
    <html>
      <body>
        <h2>WormSeq.io – upload paired-end FASTQ</h2>
        <form action="/upload" enctype="multipart/form-data" method="post">
          Sample name: <input type="text" name="sample" /><br><br>
          R1 FASTQ: <input type="file" name="r1" /><br><br>
          R2 FASTQ: <input type="file" name="r2" /><br><br>
          <input type="submit" value="Upload & Run" />
        </form>
        <p>After upload you'll get a job_id. Check it at /jobs/&lt;job_id&gt;</p>
      </body>
    </html>
    """


# ----------------------------
# upload endpoint
# ----------------------------
@app.post("/upload")
async def upload_and_run(
    background_tasks: BackgroundTasks,
    sample: str = Form(...),
    r1: UploadFile = File(...),
    r2: UploadFile = File(...),
):
    # make a job dir
    job_id = str(uuid.uuid4())
    job_dir = JOBS_DIR / job_id
    job_dir.mkdir(parents=True, exist_ok=True)

    # save the uploaded files
    r1_path = job_dir / r1.filename
    r2_path = job_dir / r2.filename

    with open(r1_path, "wb") as f:
        f.write(await r1.read())

    with open(r2_path, "wb") as f:
        f.write(await r2.read())

    # queue background work
    background_tasks.add_task(run_real_pipeline, job_id, job_dir, sample, r1_path, r2_path)

    return {"job_id": job_id, "status": "queued"}


# ----------------------------
# job status endpoint
# ----------------------------
@app.get("/jobs/{job_id}")
def job_status(job_id: str):
    job_dir = JOBS_DIR / job_id
    if not job_dir.exists():
        raise HTTPException(status_code=404, detail="job not found")

    done_file = job_dir / "done.txt"
    err_file = job_dir / "error.txt"
    log_file = job_dir / "pipeline.log"

    status = "running"
    if done_file.exists():
        status = "done"
    if err_file.exists():
        status = "error"

    log_text = ""
    if log_file.exists():
        log_text = log_file.read_text()[-4000:]  # last 4k chars

    return {
        "job_id": job_id,
        "status": status,
        "log": log_text,
    }


# ----------------------------
# health check
# ----------------------------
@app.get("/healthz")
def healthz():
    ref_exists = Path(REF_FASTA).exists()
    return {"ok": True, "ref_exists": ref_exists, "ref_path": REF_FASTA}


# ----------------------------
# the real pipeline
# ----------------------------
def run_real_pipeline(job_id: str, job_dir: Path, sample: str, r1_path: Path, r2_path: Path):
    """
    This is the part that replaces the dummy pipeline.
    It uses your actual functions, with your original signatures.
    """
    log_path = job_dir / "pipeline.log"

    def log(msg: str):
        with open(log_path, "a") as lf:
            lf.write(msg + "\n")

    try:
        log(f"[{job_id}] starting pipeline for sample={sample}")
        log(f"[{job_id}] REF_FASTA={REF_FASTA}")

        # sanity checks
        if run_trim_galore is None:
            raise RuntimeError("tfd_seq.trim.run_trim_galore not found")
        if map_reads_and_sort is None:
            raise RuntimeError("tfd_seq.map.map_reads_and_sort not found")
        if analyze_bam_improved is None:
            raise RuntimeError("tfd_seq.variants.analyze_bam_improved not found")
        if not Path(REF_FASTA).exists():
            raise RuntimeError(f"reference FASTA not found at {REF_FASTA}")

        # 1) trimming
        trimmed_dir = job_dir / "trimmed_reads"
        trimmed_dir.mkdir(exist_ok=True)
        log(f"[{job_id}] running Trim Galore...")
        # your original: run_trim_galore(fastq1, fastq2=None, output_dir="trimmed_reads")
        run_trim_galore(str(r1_path), str(r2_path), output_dir=str(trimmed_dir))
        log(f"[{job_id}] trimming done")

        # 2) locate trimmed outputs (they are usually *_val_1.fq and *_val_2.fq)
        trimmed_r1 = None
        trimmed_r2 = None
        for p in trimmed_dir.glob("*_val_1.fq"):
            trimmed_r1 = p
        for p in trimmed_dir.glob("*_val_2.fq"):
            trimmed_r2 = p
        if not trimmed_r1 or not trimmed_r2:
            raise RuntimeError("could not find trimmed FASTQ files after Trim Galore")

        log(f"[{job_id}] trimmed R1 = {trimmed_r1}")
        log(f"[{job_id}] trimmed R2 = {trimmed_r2}")

        # 3) mapping
        # your original function:
        # map_reads_and_sort(reference, read1, read2, output_prefix)
        output_prefix = str(job_dir / f"{sample}_aligned_reads")
        log(f"[{job_id}] mapping with BWA...")
        map_reads_and_sort(REF_FASTA, str(trimmed_r1), str(trimmed_r2), output_prefix)
        log(f"[{job_id}] mapping done")

        # map_reads_and_sort in your code produced:
        #   {output_prefix}.sam (removed)
        #   {output_prefix}_unsorted.bam (removed)
        #   {output_prefix}_sorted.bam  (final)
        sorted_bam = f"{output_prefix}_sorted.bam"
        if not Path(sorted_bam).exists():
            # your example had a slightly different name in the printout, so keep it flexible
            alt_sorted = f"{output_prefix}.bam"
            if Path(alt_sorted).exists():
                sorted_bam = alt_sorted
            else:
                raise RuntimeError("sorted BAM not found after mapping")

        # 4) variant calling
        # your original signature:
        # analyze_bam_improved(bam_file, ref_fasta, output_file, ...)
        variant_out = job_dir / f"{sample}_alternative_alleles.txt"
        log(f"[{job_id}] analyzing BAM for variants...")
        analyze_bam_improved(
            bam_file=sorted_bam,
            ref_fasta=REF_FASTA,
            output_file=str(variant_out),
            min_coverage=20,
            min_alt_reads=5,
            mapq_threshold=50,
        )
        log(f"[{job_id}] variant analysis done -> {variant_out}")

        # success
        (job_dir / "done.txt").write_text("ok")
        log(f"[{job_id}] pipeline completed successfully")

    except Exception as e:
        # write error marker
        (job_dir / "error.txt").write_text(str(e))
        log(f"[{job_id}] ERROR: {e}")
