import sys
import tempfile
from pathlib import Path
from typing import List

import pandas as pd
import requests
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

sys.path.insert(0, str(Path(__file__).parent))
from ai_engine import parse_csv_to_cases, score_case  # noqa: E402


def score_csv_sophia(path: Path) -> dict:
    """Score a CSV using GenomicSophia's 4-metric engine."""
    try:
        with open(path, 'r', encoding='utf-8') as f:
            text = f.read()
    except UnicodeDecodeError:
        with open(path, 'r', encoding='latin-1') as f:
            text = f.read()
    cases = parse_csv_to_cases(text)
    # Merge all cases into one for per-file scoring
    all_variants = []
    for variants in cases.values():
        all_variants.extend(variants)
    scored = score_case(all_variants, case_id=path.name)
    return {
        "file": path.name,
        "Rows analyzed": scored["total_variants"],
        # 4 GenomicSophia metrics
        "abcd_score": scored["avg_abcd"],
        "clinvar_score": scored["avg_clinvar"],
        "community_score": scored["avg_community"],
        "qa_score": scored["avg_qa"],
        "case_score": scored["case_score"],
        "urgency": scored["urgency"],
        "urgency_label": scored["urgency_label"],
        "pathogenic_count": scored["pathogenic_count"],
        "top_therapies": scored["top_therapies"],
        "scored_variants": scored["scored_variants"],
    }


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
    conseq_col    = col("Coding consequence")
    protein_col   = col("Protein")
    clinvar_col   = col("clinvar_significance")
    clnstat_col   = col("clinvar_review_status")
    vaf_col       = col("VAF(%)")
    depth_col     = col("Read depth")

    # ── Top genes (A then B, deduplicated, max 5) ──────────────
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

    # ── Top variants (A/B only, max 10) ───────────────────────
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

    # ── ClinVar classification counts (all variants) ───────────
    counts = {"P": 0, "LP": 0, "VUS": 0, "LB": 0, "B": 0}
    if clinvar_col:
        for sig in df[clinvar_col].astype(str):
            cls = _clinvar_class(sig)
            if cls:
                counts[cls] += 1

    # ── Actionable count (prediction A) ───────────────────────
    actionable_count = int((pred == "A").sum())

    # ── VAF stats ─────────────────────────────────────────────
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

    # ── Low coverage genes (mean depth < 50×) ─────────────────
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


import glob
import json
import os
import requests as http_requests

app = FastAPI(title="KAIROS · AI-Powered Genomic Case Triage")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# In-memory API key store (per-process)
_llm_config = {"provider": "none", "api_key": ""}


@app.get("/api/demo")
async def demo():
    """Auto-discover all CSVs in the samples folder."""
    results = []
    base = Path(__file__).parent
    csv_files = sorted((base / "samples").glob("*.csv"))
    for path in csv_files:
        name = path.name
        try:
            scores = score_csv_sophia(path)
        except Exception as e:
            scores = {"file": name, "error": str(e), "Rows analyzed": 0,
                      "abcd_score": 0, "clinvar_score": 0,
                      "community_score": 0, "qa_score": 0, "case_score": 0}
        scores["file"] = name
        scores.update(extract_patient_data(path))
        results.append(scores)
    results.sort(key=lambda r: r.get("case_score", 0), reverse=True)
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
            scores = score_csv_sophia(tmp_path)
            scores.update(extract_patient_data(tmp_path))
        except Exception as e:
            scores = {
                "file": upload.filename, "error": str(e), "Rows analyzed": 0,
                "abcd_score": 0, "clinvar_score": 0,
                "community_score": 0, "qa_score": 0, "case_score": 0,
                "top_genes": [], "top_variants": [],
                "classification_counts": {"P": 0, "LP": 0, "VUS": 0, "LB": 0, "B": 0},
                "actionable_count": 0, "vaf_stats": {}, "low_coverage_genes": [],
            }
        finally:
            tmp_path.unlink(missing_ok=True)
        scores["file"] = upload.filename
        results.append(scores)
    results.sort(key=lambda r: r.get("case_score", 0), reverse=True)
    return {"results": results}


# ─── LLM API Key ──────────────────────────────────────────────────────────────

@app.post("/api/set_key")
async def set_key(body: dict):
    _llm_config["provider"] = body.get("provider", "anthropic")
    _llm_config["api_key"] = body.get("api_key", "")
    return {"success": True, "provider": _llm_config["provider"]}


@app.get("/api/get_key_status")
async def get_key_status():
    return {"provider": _llm_config["provider"],
            "has_key": bool(_llm_config["api_key"])}


# ─── LLM Summary (variant_analysis_ai.py prompt) ──────────────────────────────

@app.post("/api/llm_summary")
async def llm_summary(body: dict):
    """Generate importance score + 2-sentence summary using the variant_analysis_ai prompt."""
    provider = _llm_config.get("provider", "none")
    api_key = _llm_config.get("api_key", "")
    if not api_key or provider == "none":
        return {"success": False, "error": "No API key configured."}

    top_variants = body.get("top_variants", [])
    total = body.get("total_variants", 0)
    top_count = len(top_variants)
    variant_lines = []
    for v in top_variants[:10]:
        variant_lines.append(
            f"Gene: {v.get('gene','')} | Prediction: {v.get('prediction','')} "
            f"| ClinVar: {v.get('clinvar','')} | Consequence: {v.get('consequence','')} "
            f"| Protein: {v.get('protein','')} | VAF: {v.get('vaf','')}"
        )
    variants_str = "\n".join(variant_lines)

    prompt = f"""Analyze these genetic variants from a patient sample. The file contains {total} total variants.

Top {top_count} prioritized variants:
{variants_str}

Please provide:
1. An importance score (0-100) where 100 means these variants represent a critical clinical case requiring urgent action
2. A brief summary (2 sentences) of the most relevant/important variants and what they indicate

Respond with a JSON object containing:
{{
  "importance_score": <number 0-100>,
  "summary": "<brief summary of key findings>"
}}

Scoring guidelines:
0-20: Benign or likely benign variants with no known clinical significance.
21-40: Variants of uncertain significance with weak disease association.
41-60: Potentially clinically relevant variants, moderate evidence.
61-80: Pathogenic or likely pathogenic with strong disease association.
81-100: Critical clinically actionable findings requiring urgent attention.

Use the FULL range of scores. Scores like 67, 82, 91 are preferred.

Consider: pathogenicity, actionability, gene involvement, prediction confidence, VAF values.
"""
    try:
        raw = _call_llm(provider, api_key, prompt)
        # Parse JSON from response
        js = raw[raw.find("{"):raw.rfind("}") + 1]
        result = json.loads(js)
        return {"success": True,
                "importance_score": round(float(result.get("importance_score", 50)), 1),
                "summary": result.get("summary", "Analysis complete.")}
    except Exception as e:
        return {"success": False, "error": str(e)}


def _call_llm(provider, key, prompt):
    if provider == "anthropic":
        import anthropic
        c = anthropic.Anthropic(api_key=key)
        r = c.messages.create(model="claude-opus-4-1-20250805", max_tokens=500,
                              messages=[{"role": "user", "content": prompt}])
        return r.content[0].text
    elif provider == "gemini":
        from google import genai
        from google.genai import types
        c = genai.Client(api_key=key)
        r = c.models.generate_content(model="gemini-2.5-flash", contents=prompt,
            config=types.GenerateContentConfig(system_instruction="You are an expert genomic pathologist. Respond with JSON only."))
        return r.text
    elif provider == "openai":
        import openai
        c = openai.OpenAI(api_key=key)
        r = c.chat.completions.create(model="gpt-4o", messages=[
            {"role": "system", "content": "You are an expert genomic pathologist. Respond with JSON only."},
            {"role": "user", "content": prompt}])
        return r.choices[0].message.content
    raise ValueError(f"Unknown provider: {provider}")


# ─── PubMed Papers ─────────────────────────────────────────────────────────────

@app.get("/api/papers/{gene}")
async def papers(gene: str, hgvs: str = ""):
    terms = [gene]
    if hgvs:
        terms.append(hgvs)
    terms.append("variant")
    query = " ".join(terms)
    try:
        sr = requests.get("https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi",
            params={"db": "pubmed", "term": query, "retmax": 6, "sort": "date", "retmode": "json"}, timeout=10)
        ids = sr.json().get("esearchresult", {}).get("idlist", [])
        if not ids:
            sr = requests.get("https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi",
                params={"db": "pubmed", "term": f"{gene} pathogenic therapy", "retmax": 6, "sort": "date", "retmode": "json"}, timeout=10)
            ids = sr.json().get("esearchresult", {}).get("idlist", [])
        if not ids:
            return {"papers": []}
        fr = requests.get("https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi",
            params={"db": "pubmed", "id": ",".join(ids), "retmode": "json"}, timeout=10)
        result = fr.json().get("result", {})
        papers = []
        for pid in ids:
            p = result.get(pid, {})
            if not p or "title" not in p:
                continue
            auths = ", ".join([a.get("name", "") for a in p.get("authors", [])[:3]])
            if len(p.get("authors", [])) > 3:
                auths += " et al."
            papers.append({"pmid": pid, "title": p["title"], "authors": auths,
                           "journal": p.get("fulljournalname", p.get("source", "")),
                           "date": p.get("pubdate", ""),
                           "url": f"https://pubmed.ncbi.nlm.nih.gov/{pid}/"})
        return {"papers": papers}
    except Exception as e:
        return {"papers": [], "error": str(e)}


app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
async def root():
    return FileResponse("static/index.html")
