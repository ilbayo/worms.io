# app/main.py
from fastapi import FastAPI, UploadFile, File, Form
from fastapi.responses import HTMLResponse
import pandas as pd
import io
import base64

import matplotlib
matplotlib.use("Agg")  # headless for Render
import matplotlib.pyplot as plt

app = FastAPI()


@app.get("/", response_class=HTMLResponse)
def index():
    return """
    <html>
      <head>
        <title>Mutation-load viewer</title>
      </head>
      <body style="font-family: sans-serif; margin: 40px;">
        <h2>Mutation-load viewer</h2>
        <p>Upload 1–4 variant tables (TSV) from your local pipeline.</p>
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
      </body>
    </html>
    """


def load_tsv(upload: UploadFile) -> pd.DataFrame:
    content = upload.file.read()
    return pd.read_csv(io.BytesIO(content), sep="\t")


def sliding_window(df: pd.DataFrame, chrom: str, start: int, end: int, bin_size: int = 30):
    region = df[
        (df["Chromosome"] == chrom)
        & (df["Position"] >= start)
        & (df["Position"] <= end)
    ]
    xs = []
    ys = []
    for s in range(start, end - bin_size + 2):
        e = s + bin_size - 1
        bin_ev = region[(region["Position"] >= s) & (region["Position"] <= e)]
        # mimic your notebook: filter by AltAlleleFreq <= 0.35
        bin_ev = bin_ev[bin_ev["AltAlleleFreq"] <= 0.35]
        cnt = len(bin_ev)
        avg = bin_ev["AltAlleleFreq"].mean() if cnt > 0 else 0
        xs.append(s)
        ys.append(cnt * avg)
    return xs, ys


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
    dfs = []
    for f in [file1, file2, file3, file4]:
        if f is not None:
            dfs.append(load_tsv(f))

    fig, ax = plt.subplots(figsize=(8, 4))
    labels = ["sample1", "sample2", "sample3", "sample4"]

    for df, label in zip(dfs, labels):
        xs, ys = sliding_window(df, chrom, start, end, bin_size=30)
        ax.plot(xs, ys, label=label, linewidth=2)

    ax.set_title(f"Mutation load {chrom}:{start}-{end}")
    ax.set_xlabel("Genomic position (bin start)")
    ax.set_ylabel("Weighted score")
    ax.grid(alpha=0.4)
    ax.legend()

    buf = io.BytesIO()
    plt.tight_layout()
    fig.savefig(buf, format="png")
    plt.close(fig)

    img_b64 = base64.b64encode(buf.getvalue()).decode("utf-8")

    return f"""
    <html>
      <body style="font-family: sans-serif; margin: 40px;">
        <h2>Mutation-load plot</h2>
        <img src="data:image/png;base64,{img_b64}" />
        <p><a href="/">Back</a></p>
      </body>
    </html>
    """
