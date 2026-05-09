import sys
import tempfile
from pathlib import Path
from typing import List

import pandas as pd
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

# Import score_one_csv from sibling compute_scores.py
sys.path.insert(0, str(Path(__file__).parent.parent))
from compute_scores import score_one_csv  # noqa: E402


def extract_top_genes(path: Path) -> list:
    try:
        df = pd.read_csv(path)
        gene_col, pred_col = df.columns[0], df.columns[1]
        order = {"A": 0, "B": 1}
        rows = df[[gene_col, pred_col]].copy()
        rows["_ord"] = rows[pred_col].astype(str).str.strip().str.upper().map(order)
        rows = rows.dropna(subset=["_ord"]).sort_values("_ord")
        seen, result = set(), []
        for _, row in rows.iterrows():
            g = str(row[gene_col]).strip()
            if g not in seen:
                seen.add(g)
                result.append({"gene": g, "prediction": str(row[pred_col]).strip().upper()})
            if len(result) >= 5:
                break
        return result
    except Exception:
        return []

app = FastAPI(title="VQS Patient Scoring — compute_scores.py")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


DEMO_FILES = ["patient1.csv", "patient2.csv", "patient3.csv"]

@app.get("/api/demo")
async def demo():
    results = []
    base = Path(__file__).parent
    for name in DEMO_FILES:
        path = base / name
        if not path.exists():
            continue
        try:
            scores = score_one_csv(path)
        except Exception as e:
            scores = {"file": name, "error": str(e), "Rows analyzed": 0,
                      "Disease urgency score": 0, "Rarity score (A/B community freq)": 0,
                      "QA confidence score": 0, "Overall patient score": 0}
        scores["file"] = name
        scores["top_genes"] = extract_top_genes(path)
        results.append(scores)
    results.sort(key=lambda r: r.get("Overall patient score", 0), reverse=True)
    return {"results": results}


@app.post("/api/score")
async def score(files: List[UploadFile] = File(...)):
    if len(files) > 10:
        raise HTTPException(400, "Maximum 10 CSV files per request")

    results = []
    for upload in files:
        if not upload.filename.lower().endswith((".csv", ".tsv")):
            raise HTTPException(400, f"{upload.filename} is not a CSV/TSV file")

        content = await upload.read()

        # Write to a temp file so score_one_csv (which uses pd.read_csv(Path)) can read it
        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as tmp:
            tmp.write(content)
            tmp_path = Path(tmp.name)

        try:
            scores = score_one_csv(tmp_path)
            scores["top_genes"] = extract_top_genes(tmp_path)
        except Exception as e:
            scores = {
                "file": upload.filename,
                "error": str(e),
                "Rows analyzed": 0,
                "Disease urgency score": 0,
                "Rarity score (A/B community freq)": 0,
                "QA confidence score": 0,
                "Overall patient score": 0,
                "top_genes": [],
            }
        finally:
            tmp_path.unlink(missing_ok=True)

        scores["file"] = upload.filename
        results.append(scores)

    # Sort by overall score descending
    results.sort(key=lambda r: r.get("Overall patient score", 0), reverse=True)
    return {"results": results}


app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
async def root():
    return FileResponse("static/index.html")
