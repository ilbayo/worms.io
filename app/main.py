# app/main.py
from fastapi import FastAPI, UploadFile, File, Form
from fastapi.responses import HTMLResponse
import io, base64
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
from app.mutation_load import load_variant_file, compute_mutation_load

app = FastAPI()

@app.get("/", response_class=HTMLResponse)
def index():
    return """
    <html><body style="font-family:sans-serif;margin:40px">
      <h2>Mutation-load viewer</h2>
      <form action="/analyze" method="post" enctype="multipart/form-data">
        <p>File 1 (required): <input type="file" name="file1" required></p>
        <p>File 2 (optional): <input type="file" name="file2"></p>
        <p>File 3 (optional): <input type="file" name="file3"></p>
        <p>File 4 (optional): <input type="file" name="file4"></p>
        <p>Chromosome: <input type="text" name="chrom" value="V"></p>
        <p>Start: <input type="number" name="start" value="5292480"></p>
        <p>End: <input type="number" name="end" value="5293019"></p>
        <p><button type="submit">Plot</button></p>
      </form>
    </body></html>
    """

@app.post("/analyze", response_class=HTMLResponse)
async def analyze(
    file1: UploadFile = File(...),
    file2: UploadFile = File(None),
    file3: UploadFile = File(None),
    file4: UploadFile = File(None),
    chrom: str = Form(...),
    start: int = Form(...),
    end: int = Form(...),
):
    files = [file1, file2, file3, file4]
    dfs = []
    for f in files:
        if f is not None:
            dfs.append(load_variant_file(io.BytesIO(await f.read())))

    fig, ax = plt.subplots(figsize=(8,4))
    for i, df in enumerate(dfs, start=1):
        xs, ys = compute_mutation_load(df, chrom, start, end, bin_size=30)
        ax.plot(xs, ys, label=f"sample{i}", lw=2)

    ax.set_title(f"Mutation load {chrom}:{start}-{end}")
    ax.set_xlabel("Genomic position")
    ax.set_ylabel("Weighted score")
    ax.legend()
    ax.grid(alpha=0.4)

    buf = io.BytesIO()
    plt.tight_layout()
    fig.savefig(buf, format="png")
    plt.close(fig)
    img_b64 = base64.b64encode(buf.getvalue()).decode()

    return f"""
    <html><body style="font-family:sans-serif;margin:40px">
      <h2>Mutation-load plot</h2>
      <img src="data:image/png;base64,{img_b64}" />
      <p><a href="/">Back</a></p>
    </body></html>
    """
