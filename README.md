# KAIROS · Patient Scoring Dashboard

**AI-assisted genomic case triage** — built for the SOPHiA Genetics × ETH Zurich Future of Health Hackathon (May 8–10, 2026).

[🌐 Live Website](https://genomicsophia-interface.vercel.app/) *(Update this link with your actual Vercel URL if different)*

Helps genomic pathologists prioritize their caseload by automatically ranking patients by clinical urgency from SOPHiA DDM™ variant export CSVs. It features a transparent, 4-metric scoring system, real-time literature retrieval, and an advanced AI clinical summarization engine powered by Claude.

https://genomic-sophia.vercel.app 

---
<img width="1919" height="1089" alt="image" src="https://github.com/user-attachments/assets/1753f5bc-df78-4803-9ff4-70a003ff1997" />

## What It Does

A pathologist arrives Monday morning with a queue of pending analyses. KAIROS evaluates each patient across four objective dimensions and ranks them so they know exactly where to start — and lets them tune the ranking to match their clinical priorities.

| Score | What It Measures |
|---|---|
| **Urgency (ABCD)** | SOPHiA DDM™ ABCD prediction: A=critical, B/C=elevated, D=benign — soft-clipped to 0–100 |
| **ClinVar Score** | Weighted based on ClinVar significance (Pathogenic, Likely Pathogenic, VUS, etc.) and review status (stars) |
| **Rarity (Community)** | Community frequency inverted for A/B-class variants — rarer variants score higher |
| **QA Confidence** | Mean read depth normalized 0–100 — flags low-coverage samples |

These four scores combine into a weighted **Overall Priority** score. Weights are adjustable live in the dashboard.

---

## 🌟 Key Features & How to Use Them

### 1. Dynamic Patient Scoring & Ranking
- **How to use**: Simply upload patient CSVs or click **Demo**. The dashboard automatically ranks patients. Use the **sliders** in the "Score Breakdown" panel to shift the emphasis of the 4 key metrics. The overall score and sidebar ranking will update instantly.

### 2. AI Clinical Summary (Claude API Integration)
KAIROS integrates directly with Anthropic's Claude LLM to provide a high-level clinical summary and an independent "AI Score" for the patient's top variants.
- **How to use**: 
  1. Click the **⚙️ API Key** button in the top right.
  2. Select `Anthropic` and paste your API key.
  3. Select a patient and click **✨ Generate AI Summary**.
- **How it works**: The backend sends the top 10 prioritized variants (based on pathogenicity and A/B prediction) to the Anthropic Claude API model, asking for a 0-100 severity score and a 2-sentence clinical summarization of the key actionable findings.

### 3. Real-Time PubMed Literature Retrieval
- **How to use**: In the "Top Variants" table, click the **📚** button next to any variant.
- **How it works**: KAIROS queries the NCBI E-utilities API live, searching PubMed for the specific Gene and HGVS mutation. A modal will pop up with the most recent relevant academic papers, complete with authors, journals, and direct links to PubMed.

### 4. Interactive Gene Databases
- **How to use**: Click on any highlighted Gene name (e.g., in the Shared Genes panel or Top Variants table).
- **How it works**: Fetches live data from external genomic databases (MyGene.info and CIViC) to provide a quick summary of the gene's function and known clinical significance.

### 5. Batch Demo Loading
- **How to use**: Click the **Demo** button in the left sidebar.
- **How it works**: The backend automatically traverses the local `samples/` directory, processes all bundled patient CSVs simultaneously, and loads them into the UI without requiring manual file uploads.

---

## Quick Start (Local Development)

```bash
git clone https://github.com/yacine-baghli/GenomicSophia.git
cd GenomicSophia
pip install -r requirements.txt
python -m uvicorn interface.main:app --port 8000 --reload
```

Open **http://localhost:8000** in your browser.

*(Note: Vercel deployments are natively supported. Vercel automatically routes to `api/index.py` which wraps the FastAPI application.)*

---

## Input Format

Standard SOPHiA DDM™ variant export CSV. Required columns:

| Column | Used For |
|---|---|
| `SOPHiA DDM™ prediction` (col 2) | Disease urgency — values A / B / C / D |
| `clinvar_significance` / `review_status` | Pathogenicity classification and ClinVar scoring |
| `Read depth` | QA confidence normalization |
| `Community frequency` | Rarity score for A/B variants |

---

## Project Structure

```text
.
├── api/
│   └── index.py         # Vercel Serverless entrypoint
├── interface/
│   ├── main.py          # FastAPI backend — /api/score, /api/demo, /api/llm_summary
│   ├── ai_engine.py     # Core 4-metric scoring engine
│   ├── static/
│   │   └── index.html   # KAIROS dashboard (single-file SPA)
│   └── samples/         # Bundled Demo CSVs
├── vercel.json          # Vercel deployment configuration
└── requirements.txt     # Global dependencies (FastAPI, Pandas, Anthropic, Requests)
```

---

## Tech Stack

| Layer | Technology |
|---|---|
| **Backend** | FastAPI + Uvicorn |
| **Scoring** | `ai_engine.py` — Pure Pandas, heuristic-based |
| **AI Engine** | Anthropic Claude API (JSON structured outputs) |
| **Integrations**| NCBI E-utilities (PubMed), MyGene, CIViC |
| **Frontend** | Vanilla HTML/CSS/JS — Zero build-step |
| **Deployment**| Vercel Serverless Functions |

---

## Disclaimer

Hackathon prototype — not for clinical use. Scoring is rule-based and must be validated by qualified professionals before any clinical application.

---

Built at ETH Zurich for the **Future of Health Hackathon 2026** in collaboration with SOPHiA Genetics.
