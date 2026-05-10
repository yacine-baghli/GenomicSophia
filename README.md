# KAIROS · Patient Scoring Dashboard

**AI-assisted genomic case triage** — built for the SOPHiA Genetics × ETH Zurich Future of Health Hackathon (May 8–10, 2026).

Helps genomic pathologists prioritize their caseload by automatically ranking patients by clinical urgency from SOPHiA DDM™ variant export CSVs.

---
<img width="1918" height="1091" alt="image" src="https://github.com/user-attachments/assets/ef0b6aad-7a7d-48d7-b18f-2e6cf8b7d4e4" />

## What It Does

A pathologist arrives Monday morning with a queue of pending analyses. KAIROS scores each patient across three objective dimensions and ranks them so she knows where to start — and lets her tune the ranking to match her clinical priorities.

| Score | What It Measures |
|---|---|
| **Disease Urgency** | SOPHiA DDM™ ABCD prediction: A=critical, B/C=elevated, D=benign — soft-clipped to 0–100 |
| **Rarity** | Community frequency inverted for A/B-class variants — rarer variants score higher |
| **QA Confidence** | Mean read depth normalized 0–100 — flags low-coverage samples |

The three scores combine into a weighted **Overall Priority** score. Weights are adjustable live in the dashboard.

---

## Quick Start

```bash
git clone https://github.com/yacine-baghli/GenomicSophia.git
cd GenomicSophia/interface
pip install -r requirements.txt
uvicorn main:app --reload
```

Open **http://localhost:8000** in your browser.

---

## Usage

### Demo patients
Click **Demo** in the sidebar to instantly load the three bundled example CSVs (`patient1.csv`, `patient2.csv`, `patient3.csv`) — no upload needed.

### Upload your own
Click **+ Upload**, drag and drop up to 10 SOPHiA DDM™ variant export CSVs, then click **Score Patients**. Uploading the same file again creates a versioned copy (`patient (v2).csv`) rather than overwriting.

### Adjust weights
Each score row in the breakdown panel has a 0–10 slider. Drag to shift emphasis — the overall score and sidebar ranking update live.

---

## Input Format

Standard SOPHiA DDM™ variant export CSV. Required columns:

| Column | Used For |
|---|---|
| `SOPHiA DDM™ prediction` (col 2) | Disease urgency — values A / B / C / D |
| `Read depth` | QA confidence normalization |
| `Community frequency` | Rarity score for A/B variants |

---

## Project Structure

```
interface/
├── main.py              # FastAPI backend — /api/score, /api/demo
├── compute_scores.py    # Scoring engine (disease urgency, rarity, QA)
├── static/
│   └── index.html       # KAIROS dashboard (single-file SPA)
├── patient1.csv         # Demo data — SOPHiA DDM™ export format
├── patient2.csv
├── patient3.csv
└── requirements.txt
```

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | FastAPI + Uvicorn |
| Scoring | `compute_scores.py` — pure pandas, no ML |
| Frontend | Vanilla HTML/CSS/JS — zero dependencies |
| Data | SOPHiA DDM™ variant export CSV |

---

## API

| Endpoint | Method | Description |
|---|---|---|
| `/api/score` | POST | Score uploaded CSV files (multipart/form-data, `files` field, max 10) |
| `/api/demo` | GET | Score the bundled demo patients |

Both return `{ "results": [ { "file", "Rows analyzed", "Disease urgency score", "Rarity score (A/B community freq)", "QA confidence score", "Overall patient score" }, ... ] }` sorted by overall score descending.

---

## Disclaimer

Hackathon prototype — not for clinical use. Scoring is rule-based and must be validated by qualified professionals before any clinical application.

---

Built at ETH Zurich for the **Future of Health Hackathon 2026** in collaboration with SOPHiA Genetics.
