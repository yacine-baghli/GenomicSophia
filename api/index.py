import sys
import tempfile
from pathlib import Path
from typing import List

import pandas as pd
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

# compute_scores.py lives at the repo root
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
from compute_scores import score_one_csv  # noqa: E402


def _clinvar_stars(status: str) -> int:
    s = (status or "").lower()
    if "expert" in s: return 4
    if "multiple" in s and "no_conflict" in s: return 3
    if "criteria_provided" in s: return 2
    if "no_assertion_criteria" in s: return 1
    return 0


def _clinvar_class(sig: str):
    s = (sig or "").lower().replace("_", " ").strip()
    if not s or s in ("nan", "not provided", "not classified"): return None
    if "likely pathogenic" in s: return "LP"
    if "pathogenic" in s: return "P"
    if "likely benign" in s: return "LB"
    if "benign" in s: return "B"
    return "VUS"


def extract_patient_data(path: Path) -> dict:
    empty = {
        "top_genes": [], "top_variants": [],
        "classification_counts": {"P": 0, "LP": 0, "VUS": 0, "LB": 0, "B": 0},
        "actionable_count": 0, "vaf_stats": {}, "low_coverage_genes": [],
    }
    try:
        df = pd.read_csv(path)
        if df.empty:
            return empty
    except Exception:
        return empty

    gene_col, pred_col = df.columns[0], df.columns[1]
    pred = df[pred_col].astype(str).str.strip().str.upper()

    def col(name): return name if name in df.columns else None
    conseq_col  = col("Coding consequence")
    protein_col = col("Protein")
    clinvar_col = col("clinvar_significance")
    clnstat_col = col("clinvar_review_status")
    vaf_col     = col("VAF(%)")
    depth_col   = col("Read depth")

    g_rows = df[[gene_col, pred_col]].copy()
    g_rows["_o"] = pred.map({"A": 0, "B": 1})
    g_rows = g_rows.dropna(subset=["_o"]).sort_values("_o")
    seen, top_genes = set(), []
    for _, row in g_rows.iterrows():
        g = str(row[gene_col]).strip()
        if g not in seen:
            seen.add(g)
            top_genes.append({"gene": g, "prediction": str(row[pred_col]).strip().upper()})
        if len(top_genes) >= 5:
            break

    ab_mask = pred.isin({"A", "B"})
    ab_df = df[ab_mask].copy()
    ab_df["_o"] = pred[ab_mask].map({"A": 0, "B": 1})
    ab_df = ab_df.sort_values("_o").head(10)

    top_variants = []
    for _, row in ab_df.iterrows():
        vaf_raw = pd.to_numeric(row.get(vaf_col) if vaf_col else None, errors="coerce")
        if pd.notna(vaf_raw):
            vaf_pct = round(float(vaf_raw) * 100, 1) if float(vaf_raw) <= 1.0 else round(float(vaf_raw), 1)
        else:
            vaf_pct = None
        clinvar_sig = str(row[clinvar_col]).replace("_", " ").strip() if clinvar_col else ""
        top_variants.append({
            "gene":          str(row[gene_col]).strip(),
            "prediction":    str(row[pred_col]).strip().upper(),
            "consequence":   str(row[conseq_col]).strip() if conseq_col else "",
            "protein":       str(row[protein_col]).strip() if protein_col else "",
            "clinvar":       clinvar_sig if clinvar_sig not in ("nan", "") else "—",
            "clinvar_stars": _clinvar_stars(str(row[clnstat_col]) if clnstat_col else ""),
            "vaf":           vaf_pct,
        })

    counts = {"P": 0, "LP": 0, "VUS": 0, "LB": 0, "B": 0}
    if clinvar_col:
        for sig in df[clinvar_col].astype(str):
            cls = _clinvar_class(sig)
            if cls:
                counts[cls] += 1

    actionable_count = int((pred == "A").sum())

    vaf_stats = {}
    if vaf_col:
        vaf_vals = pd.to_numeric(df[vaf_col], errors="coerce").dropna()
        if not vaf_vals.empty:
            mult = 100 if float(vaf_vals.max()) <= 1.0 else 1
            vaf_stats = {
                "mean": round(float(vaf_vals.mean()) * mult, 1),
                "min":  round(float(vaf_vals.min()) * mult, 1),
                "max":  round(float(vaf_vals.max()) * mult, 1),
            }

    low_cov = []
    if depth_col:
        depths = pd.to_numeric(df[depth_col], errors="coerce")
        gd = pd.DataFrame({"gene": df[gene_col], "depth": depths})
        gene_means = gd.groupby("gene")["depth"].mean()
        for g, d in gene_means[gene_means < 50].sort_values().items():
            low_cov.append({"gene": g, "depth": round(float(d), 0)})

    return {
        "top_genes":             top_genes,
        "top_variants":          top_variants,
        "classification_counts": counts,
        "actionable_count":      actionable_count,
        "vaf_stats":             vaf_stats,
        "low_coverage_genes":    low_cov,
    }


app = FastAPI(title="VQS Patient Scoring — KAIROS")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

DEMO_DIR = ROOT / "interface"
DEMO_FILES = ["patient1.csv", "patient2.csv", "patient3.csv"]


@app.get("/api/demo")
async def demo():
    results = []
    for name in DEMO_FILES:
        path = DEMO_DIR / name
        if not path.exists():
            continue
        try:
            scores = score_one_csv(path)
        except Exception as e:
            scores = {"file": name, "error": str(e), "Rows analyzed": 0,
                      "Disease urgency score": 0, "Rarity score (A/B community freq)": 0,
                      "QA confidence score": 0, "Overall patient score": 0}
        scores["file"] = name
        scores.update(extract_patient_data(path))
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
        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as tmp:
            tmp.write(content)
            tmp_path = Path(tmp.name)

        try:
            scores = score_one_csv(tmp_path)
            scores.update(extract_patient_data(tmp_path))
        except Exception as e:
            scores = {
                "file": upload.filename, "error": str(e), "Rows analyzed": 0,
                "Disease urgency score": 0, "Rarity score (A/B community freq)": 0,
                "QA confidence score": 0, "Overall patient score": 0,
                "top_genes": [], "top_variants": [],
                "classification_counts": {"P": 0, "LP": 0, "VUS": 0, "LB": 0, "B": 0},
                "actionable_count": 0, "vaf_stats": {}, "low_coverage_genes": [],
            }
        finally:
            tmp_path.unlink(missing_ok=True)

        scores["file"] = upload.filename
        results.append(scores)

    results.sort(key=lambda r: r.get("Overall patient score", 0), reverse=True)
    return {"results": results}


@app.get("/{full_path:path}")
async def serve_spa(full_path: str):
    return FileResponse(str(ROOT / "interface" / "static" / "index.html"))
