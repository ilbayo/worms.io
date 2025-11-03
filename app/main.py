from fastapi import FastAPI, UploadFile, File, Form, BackgroundTasks, HTTPException
from fastapi.responses import HTMLResponse
from pathlib import Path
from typing import Optional
import os
import uuid

app = FastAPI()

# base data dir – this matches the Render disk mount we talked about
DATA_DIR = Path("/app/app/data")
JOBS_DIR = DATA_DIR / "jobs"
JOBS_DIR.mkdir(parents=True, exist_ok=True)

# reference location (can be overridden in Render env vars)
REF_FASTA = os.environ.get("REF_FASTA", "/app/app/data/reference/genomic.fa")

# max upload guard (to avoid OOM on very large files in small Render plans)
MAX_UPLOAD_MB = 300  # adjust to your plan


# ----------------------------
# try importing your real code
# ----------------------------
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
# helper: save upload in chunks
# ----------------------------
async def save_upload(upload_file: UploadFile, dest: Path):
    size = 0
    with open(dest, "wb") as f:
        while True:
            chunk = await upload_file.read(1024 * 1024)  # 1 MB
            if not chunk:
                break
            size += len(chunk)
            if size > MAX_UPLOAD_MB * 1024 * 1024:
                dest.unlink(missing_ok=True)
                raise HTTPException(status_code=413, detail="File too large for this instance")
            f.write(chunk)


# ----------------------------
# HTML upload form (with progress bar)
# ----------------------------
@app.get("/", response_class=HTMLResponse)
def index():
    return """
    <html>
    <head>
      <title>WormSeq.io</title>
      <style>
        body { font-family: sans-serif; margin: 40px; }
        #progressContainer { width: 100%; background: #ddd; border-radius: 8px; margin-top: 10px; }
        #progressBar { width: 0%; height: 20px; background: #4CAF50; border-radius: 8px; text-align: center; color: white; transition: width .2s; }
      </style>
    </head>
    <body>
      <h2>WormSeq.io – Upload Paired-End FASTQ</h2>
      <form id="uploadForm">
        Sample name: <input type="text" name="sample" id="sample" /><br><br>
        R1 FASTQ: <input type="file" name="r1" id="r1" required /><br><br>
        R2 FASTQ: <input type="file" name="r2" id="r2" required /><br><br>
        <button type="submit">Upload & Run</button>
      </form>

      <div id="progressContainer">
        <div id="progressBar">0%</div>
      </div>

      <p id="status"></p>

      <script>
        const form = document.getElementById('uploadForm');
        const progressBar = document.getElementById('progressBar');
        const statusText = document.getElementById('status');

        form.addEventListener('submit', (event) => {
          event.preventDefault();
          const sample = document.getElementById('sample').value;
          const r1 = document.getElementById('r1').files[0];
          const r2 = document.getElementById('r2').files[0];
          if (!r1 || !r2) {
            alert("Please select both FASTQ files.");
            return;
          }

          const formData = new FormData();
          formData.append('sample', sample);
          formData.append('r1', r1);
          formData.append('r2', r2);

          const xhr = new XMLHttpRequest();
          xhr.open('POST', '/upload', true);

          xhr.upload.onprogress = (e) => {
            if (e.lengthComputable) {
              const percent = Math.round((e.loaded / e.total) * 100);
              progressBar.style.width = percent + '%';
              progressBar.textContent = percent + '%';
            }
          };

          xhr.onload = () => {
            if (xhr.status === 200) {
              const result = JSON.parse(xhr.responseText);
              progressBar.style.width = '100%';
              progressBar.textContent = 'Done!';
              statusText.innerHTML = `<b>Upload complete!</b><br>Job ID: ${result.job_id}<br>Status: ${result.status}<br>Check progress at: <a href="/jobs/${result.job_id}" target="_blank">/jobs/${result.job_id}</a>`;
            } else {
              statusText.textContent = 'Upload failed: ' + xhr.status + ' ' + xhr.responseText;
            }
          };

          xhr.onerror = () => {
            statusText.textContent = 'Error: could not upload file.';
          };

          xhr.send(formData);
        });
      </script>
    </body>
    </html>
    """


# ----------------------------
# upload endpoint
# ----------------------------
@app.post("/upload")
async def upload_and_run(
    background_tasks: BackgroundTasks,
    sample: Optional[str] = Form(None),
    r1: UploadFile = File(...),
    r2: UploadFile = File(...),
):
    # make a job dir
    job_id = str(uuid.uuid4())
    job_dir = JOBS_DIR / job_id
    job_dir.mkdir(parents=True, exist_ok=True)

    # save the uploaded files (chunked)
    r1_path = job_dir / r1.filename
    r2_path = job_dir / r2.filename
    await save_upload(r1, r1_path)
    await save_upload(r2, r2_path)

    if not sample:
        sample = f"sample_{job_id[:8]}"

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
        run_trim_galore(str(r1_path), str(r2_path), output_dir=str(trimmed_dir))
        log(f"[{job_id}] trimming done")

        # 2) locate trimmed outputs – allow .fq and .fq.gz
        trimmed_r1 = None
        trimmed_r2 = None
        candidates_r1 = list(trimmed_dir.glob("*_val_1.fq")) + list(trimmed_dir.glob("*_val_1.fq.gz"))
        candidates_r2 = list(trimmed_dir.glob("*_val_2.fq")) + list(trimmed_dir.glob("*_val_2.fq.gz"))
        if candidates_r1:
            trimmed_r1 = candidates_r1[0]
        if candidates_r2:
            trimmed_r2 = candidates_r2[0]
        if not trimmed_r1 or not trimmed_r2:
            raise RuntimeError("could not find trimmed FASTQ files after Trim Galore (looked for .fq and .fq.gz)")

        log(f"[{job_id}] trimmed R1 = {trimmed_r1}")
        log(f"[{job_id}] trimmed R2 = {trimmed_r2}")

        # 3) mapping
        output_prefix = str(job_dir / f"{sample}_aligned_reads")
        log(f"[{job_id}] mapping with BWA...")
        map_reads_and_sort(REF_FASTA, str(trimmed_r1), str(trimmed_r2), output_prefix)
        log(f"[{job_id}] mapping done")

        # figure out sorted BAM name
        sorted_bam = f"{output_prefix}_sorted.bam"
        if not Path(sorted_bam).exists():
            alt_sorted = f"{output_prefix}.bam"
            if Path(alt_sorted).exists():
                sorted_bam = alt_sorted
            else:
                raise RuntimeError("sorted BAM not found after mapping")

        # 4) variant calling
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
        (job_dir / "error.txt").write_text(str(e))
        log(f"[{job_id}] ERROR: {e}")
