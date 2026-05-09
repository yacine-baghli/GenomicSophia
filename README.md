# 🧬 Genomic Co-Pilot

**AI-Powered Genomic Case Triage Dashboard** — built for the SOPHiA Genetics × ETH Zurich Future of Health Hackathon (May 8–10, 2026).

Helps genomic pathologists prioritize their caseload by ranking patient samples by clinical urgency using a **5-metric scoring system** with native **SOPHiA DDM™** CSV export support.

---

## 🎯 What It Does

A pathologist arrives Monday morning with dozens of pending analyses. Genomic Co-Pilot instantly ranks every case by urgency so she knows **where to start**.

Each variant is scored across **5 clinical metrics** (0–100):

| Metric | What It Measures |
|--------|------------------|
| **Actionability** | Is there a targeted therapy? (EGFR→Osimertinib, BRCA→Olaparib, etc.) |
| **Disease Urgency** | ACMG classification + ABCD predictor + consequence severity |
| **QA Confidence** | Read depth + allele frequency + predictor agreement |
| **gnomAD Rarity** | Population frequency (rarer = more likely pathogenic) |
| **ClinVar Evidence** | ClinVar significance + review status strength |

A **weighted composite score** (Act. 30% + Urg. 30% + ClinVar 20% + gnomAD 10% + QA 10%) ranks cases as:

**🔴 Critical (≥70)** → **🟠 High (≥50)** → **🟡 Moderate (≥30)** → **🟢 Low (<30)**

---

## 🚀 Quick Start

```bash
# Clone
git clone https://github.com/yacine-baghli/GenomicSophia.git
cd GenomicSophia

# Install
pip install -r requirements.txt

# Run
python app.py
```

Open **http://127.0.0.1:5001** in your browser. The dashboard auto-loads and ranks all CSV files from `/samples` on startup.

---

## 📊 Data Sources

### 📁 Local CSV Samples (Default)

Drop SOPHiA DDM™ export CSVs into the `samples/` folder — they're loaded automatically on startup.

- **3 sample patients included** (`patient1.csv`, `patient2.csv`, `patient3.csv`)
- Supports SOPHiA DDM™ export columns: `gene`, `SOPHiA DDM™ prediction`, `Coding consequence`, `clinvar_significance`, `gnomAD AF exomes`, `Read depth`, `VAF(%)`, `Protein`, `c.DNA`, etc.
- Also supports generic CSV with columns: `Sample`, `Gene`, `HGVS`, `ACMG`, `ABCD`, `ClinVar`, `gnomAD`, `ReadDepth`, `AF`

**From the dashboard you can:**
- **Add** more CSV files via upload → saved to `/samples`
- **Remove** files with the ✕ button on each chip
- **Re-rank** all cases together with one click

### 🔌 VQS API (Live SOPHiA DDM™ Platform)

1. Get a token from: `https://iam-vandv.sophiagenetics.com/account/token`
2. Get dataset keys from browser DevTools (Network tab)
3. Paste both into the VQS API tab → **Analyze**

### 📋 Demo Mode

Click **Demo** → **Load Demo Data** to see pre-built oncology cases (NSCLC, Breast, CRC).

---

## 🌓 Dark / Light Mode

Click the **☀️ Light / 🌙 Dark** button in the top-right corner.

---

## 📁 Project Structure

```
GenomicSophia/
├── app.py              # Flask routes & API endpoints
├── ai_engine.py        # 5-metric scoring engine + CSV parser + LLM summaries
├── vqs_client.py       # SOPHiA VQS API client (auth + query)
├── requirements.txt    # Python dependencies
├── test_vqs_api.ps1    # PowerShell script to test VQS API
├── samples/            # CSV data files (auto-loaded on startup)
│   ├── patient1.csv    # ESR1-Low-VAF-T (263 variants)
│   ├── patient2.csv    # ACCESS010-CP (319 variants)
│   └── patient3.csv    # DMD-dup (500 variants)
├── templates/
│   └── copilot.html    # Dashboard HTML
└── static/
    ├── style.css       # Dark/Light theme CSS
    └── app.js          # Frontend logic
```

---

## 🔬 API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/` | Dashboard |
| `GET` | `/api/samples` | List CSV files in `/samples` |
| `POST` | `/api/upload` | Upload & save CSVs to `/samples` |
| `POST` | `/api/remove_sample` | Remove a CSV from `/samples` |
| `POST` | `/api/rank` | Rank all cases from `/samples` |
| `POST` | `/api/analyze` | Analyze via VQS API |

---

## 🛠️ Tech Stack

| Layer | Technology |
|-------|------------|
| Backend | Flask (Python) |
| Scoring | Rule-based 5-metric engine (20+ actionable genes, ACMG/ABCD/ClinVar/gnomAD) |
| Data | SOPHiA DDM™ CSV exports + VQS API (DuckDB-as-a-service) |
| LLM (optional) | Gemini 2.5 Flash / GPT-4o / Claude |
| Frontend | Vanilla HTML/CSS/JS, Inter font, dark/light themes |

---

## ⚠️ Disclaimer

Hackathon prototype — not for clinical use. All scoring is rule-based and should be validated by qualified professionals.

---

Built with ❤️ at ETH Zurich for the **Future of Health Hackathon 2026**
