To run the scoring :
```bash
python3 compute_scores.py patient1.csv patient2.csv patient3.csv --output scores.csv
```
You can run up to 10 at the same time (but it is arbitrary)


# 🧬 GenomicOracle Co-Pilot

**AI-Powered Genomic Case Triage Dashboard** — built for the SOPHiA Genetics × ETH Zurich Future of Health Hackathon (May 8–10, 2026).

Helps genomic pathologists prioritize their caseload by ranking samples by clinical urgency using a **5-metric scoring system**.

---

## 🎯 What It Does

A pathologist arrives Monday morning with dozens of pending analyses. GenomicOracle Co-Pilot instantly ranks every case by urgency so she knows **where to start**.

Each variant is scored across **5 clinical metrics** (0–100):

| Metric | What It Measures |
|--------|------------------|
| **Actionability** | Is there a targeted therapy? (EGFR→Osimertinib, BRCA→Olaparib, etc.) |
| **Disease Urgency** | ACMG classification + ABCD predictor + consequence severity |
| **QA Confidence** | Read depth + allele frequency + predictor agreement |
| **gnomAD Rarity** | Population frequency (rarer = more likely pathogenic) |
| **ClinVar Evidence** | ClinVar significance + review status strength |

Cases are ranked **🔴 Critical → 🟠 High → 🟡 Moderate → 🟢 Low**.

---

## 🚀 Quick Start

```bash
# Clone
git clone https://github.com/YOUR_USERNAME/GenomicOracle.git
cd GenomicOracle

# Install
pip install -r requirements.txt

# Run
python app.py
```

Open **http://127.0.0.1:5001** in your browser.

---

## 📊 Data Sources (3 options)

### 🔌 VQS API (Live SOPHiA DDM™ integration)
1. Get a token from: https://iam-vandv.sophiagenetics.com/account/token
2. Get dataset keys from browser DevTools (Network tab)
3. Paste both into the dashboard → **Analyze**

### 📄 CSV Upload
Upload a CSV with columns: `Sample, Gene, HGVS, Consequence, ACMG, ABCD, ClinVar, gnomAD, ReadDepth, AF`

### 📋 Demo Mode
Click **Demo** → **Load Demo Data** to see 4 pre-built oncology cases.

---

## 🌓 Dark / Light Mode

Click the **☀️ Light / 🌙 Dark** button in the top-right corner.

---

## 📁 Project Structure

```
GenomicOracle/
├── app.py              # Flask routes (VQS API + CSV + demo)
├── ai_engine.py        # 5-metric scoring engine + CSV parser + LLM summaries
├── vqs_client.py       # SOPHiA VQS API client (auth + query)
├── requirements.txt    # Python dependencies
├── test_vqs_api.ps1    # PowerShell script to test VQS API
├── templates/
│   └── copilot.html    # Dashboard HTML
└── static/
    ├── style.css       # Dark/Light theme CSS
    └── app.js          # Frontend logic
```

---

## 🛠️ Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Flask (Python) |
| Scoring | Rule-based 5-metric engine |
| API | SOPHiA VQS (DuckDB-as-a-service) |
| LLM (optional) | Gemini / GPT-4o / Claude |
| Frontend | Vanilla HTML/CSS/JS, Inter font |

---

## ⚠️ Disclaimer

Hackathon prototype — not for clinical use. All scoring is rule-based and should be validated by qualified professionals.

---

Built with ❤️ at ETH Zurich for the **Future of Health Hackathon 2026**
