from fastapi import FastAPI, UploadFile, File, Form
from fastapi.responses import HTMLResponse, Response
import pandas as pd
import io
import base64
import matplotlib
matplotlib.use("Agg")  # for headless render
import matplotlib.pyplot as plt

app = FastAPI()


@app.get("/", response_class=HTMLResponse)
def index():
    return """
    <html>
      <body>
        <h2>Mutation load viewer</h2>
        <form action="/analyze" method="post" enctype="multipart/form-data">
          Variant file 1: <input type="file" name="file1" required><br><br>
          Variant file 2: <input type="file" name="file2"><br><br>
          Variant file 3: <input type="file" name="file3"><br><br>
          Variant file 4: <input type="file" name="file4"><br><br>
          Chromosome: <input type="text" name="chrom" value="V"><br><br>
          Start: <input type="number" name="start" value="5292480"><br><br>
          End: <input type="number" name="end" value="5293019"><br><br>
          <button type="submit">Plot</button>
        </form>
      </body>
    </html>
    """


def load_variant_file(upload: UploadFile) -> pd.DataFrame:
    content = upload.file.read()
    df = pd.read_csv(io.BytesIO(content), sep="\t")
    return df


def sliding_window(df, chrom, start, end, bin_size=30):
    region = df[(df["Chromosome"] == chrom) & (df["Position"] >= start) & (df["Position"] <= end)]
    xs = []
    ys = []
    for s in range(start, end - bin_size + 2):
        e = s + bin_size - 1
        bin_events = region[(region["Position"] >= s) & (region["Position"] <= e)]
        # you filtered to AltAlleleFreq <= 0.35
        bin_events = bin_events[bin_events["AltAlleleFreq"] <= 0.35]
        count = len(bin_events)
        avg = bin_events["AltAlleleFreq"].mean() if count > 0 else 0
        xs.append(s)
        ys.append(count * avg)
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
            dfs.append(load_variant_file(f))

    # make plot
    fig, ax = plt.subplots(figsize=(8, 4))
    labels = ["sample1", "sample2", "sample3", "sample4"]
    for df, label in zip(dfs, labels):
        xs, ys = sliding_window(df, chrom, start, end, bin_size=30)
        ax.plot(xs, ys, label=label, linewidth=2)

    ax.set_title(f"Mutation load {chrom}:{start}-{end}")
    ax.set_xlabel("Genomic position (bin start)")
    ax.set_ylabel("Weighted score")
    ax.grid(True)
    ax.legend()

    # convert to base64 PNG
    buf = io.BytesIO()
    plt.tight_layout()
    fig.savefig(buf, format="png")
    plt.close(fig)
    img_b64 = base64.b64encode(buf.getvalue()).decode("utf-8")

    return f"""
    <html>
      <body>
        <h2>Mutation load {chrom}:{start}-{end}</h2>
        <img src="data:image/png;base64,{img_b64}" />
        <p><a href="/">Back</a></p>
      </body>
    </html>
    """
