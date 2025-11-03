from fastapi import FastAPI, UploadFile, File, Form, BackgroundTasks
from fastapi.responses import HTMLResponse, JSONResponse
from pathlib import Path
import uuid
import os

app = FastAPI()

DATA_DIR = Path("/app/app/data")
DATA_DIR.mkdir(parents=True, exist_ok=True)

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
      </body>
    </html>
    """

@app.post("/upload")
async def upload(
    sample: str = Form(...),
    r1: UploadFile = File(...),
    r2: UploadFile = File(...),
    background_tasks: BackgroundTasks = None
):
    job_id = str(uuid.uuid4())
    job_dir = DATA_DIR / "jobs" / job_id
    job_dir.mkdir(parents=True, exist_ok=True)

    r1_path = job_dir / r1.filename
    r2_path = job_dir / r2.filename

    with open(r1_path, "wb") as f:
        f.write(await r1.read())
    with open(r2_path, "wb") as f:
        f.write(await r2.read())

    # later we call your tfd_seq functions here
    if background_tasks:
        background_tasks.add_task(dummy_pipeline, job_dir, sample, r1_path, r2_path)

    return {"job_id": job_id, "status": "queued"}

def dummy_pipeline(job_dir: Path, sample: str, r1_path: Path, r2_path: Path):
    # placeholder for:
    # 1) run_trim_galore(...)
    # 2) map_reads_and_sort(...)
    # 3) analyze_bam_improved(...)
    (job_dir / "done.txt").write_text("pipeline would run here")

@app.get("/healthz")
def healthz():
    ref_path = Path(os.environ.get("REF_FASTA", "/app/app/data/reference/genomic.fa"))
    return {"ok": True, "ref_exists": ref_path.exists()}
