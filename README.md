# 🧬 Genomic Co-Pilot

**AI-Powered Genomic Case Triage Dashboard** — built for the SOPHiA Genetics × ETH Zurich Future of Health Hackathon (May 8–10, 2026).

Helps genomic pathologists prioritize their caseload by ranking patient samples by clinical urgency using a **5-metric scoring system** with native **SOPHiA DDM™** CSV export support.

---

## 🎯 What It Does

A pathologist arrives Monday morning with dozens of pending analyses. Genomic Co-Pilot instantly ranks every case by urgency so she knows **where to start**.

---

## 🧠 How the Scoring System Works

### Variant-Level Scoring (5 Metrics)

Each variant in a patient's sample is scored independently across **5 clinical metrics**, each producing a score from **0 to 100**:

#### 1. Actionability (Weight: 30%)

> *"Is there a targeted therapy available for this gene?"*

| Condition | Score |
|-----------|-------|
| **Tier 1 gene** (EGFR, ALK, BRCA1, BRCA2, ROS1, BRAF, NTRK, RET…) | **90** |
| Tier 1 gene + loss-of-function consequence (frameshift, nonsense, splice) | **100** |
| **Tier 2 gene** (KRAS, PIK3CA, ESR1, FGFR2, MET, HER2, IDH1…) | **65** |
| Tier 2 gene + loss-of-function consequence | **75** |
| **Prognostic-only** gene (TP53, PTEN, RB1, APC, SMAD4, CDKN2A) | **30** |
| Unknown/benign gene | **10** |

The engine maps **21 actionable genes** to their FDA-approved targeted therapies (Osimertinib, Olaparib, Sotorasib, etc.) and **6 prognostic markers**.

#### 2. Disease Urgency (Weight: 30%)

> *"How pathogenic is this variant and how severe is its consequence?"*

Three sub-signals are summed:

| Sub-signal | Value | Points |
|------------|-------|--------|
| **ACMG Classification** | Pathogenic | +45 |
| | Likely Pathogenic | +30 |
| | VUS (Uncertain) | +10 |
| | Benign / Likely Benign | +0 |
| **SOPHiA ABCD Prediction** | A (High confidence pathogenic) | +35 |
| | B (Moderate confidence) | +22 |
| | C (Low confidence) | +8 |
| | D (Benign prediction) | +0 |
| **Consequence Severity** | Nonsense / Frameshift / Splice | +20 |
| | Missense | +8 |
| | Silent / Intronic | +0 |

A variant with ACMG: Pathogenic + ABCD: A + Frameshift → 45 + 35 + 20 = **100/100 (maximum urgency)**.

#### 3. QA Confidence (Weight: 10%)

> *"How reliable is this variant call?"*

Starts at a baseline of **50**, then adjusts based on sequencing quality:

| Factor | Condition | Adjustment |
|--------|-----------|------------|
| **Read Depth** | ≥ 200× | +25 |
| | ≥ 100× | +20 |
| | ≥ 50× | +10 |
| | < 20× | −15 |
| **VAF (Variant Allele Frequency)** | ≥ 30% | +20 |
| | ≥ 15% | +10 |
| | < 5% | −10 |
| **ABCD Predictor** | A | +10 |
| | B | +5 |

A high-depth (200×), high-VAF (30%+), ABCD:A variant → 50 + 25 + 20 + 10 = **105 → capped at 100**.

#### 4. gnomAD Rarity (Weight: 10%)

> *"Is this variant rare in the general population?"*

| Population Frequency | Score | Interpretation |
|---------------------|-------|----------------|
| Absent (not in gnomAD) | **95** | Very rare → likely pathogenic |
| N/A or empty | **80** | Assumed rare |
| < 0.001% (< 0.00001) | **90** | Ultra-rare |
| < 0.01% (< 0.0001) | **75** | Rare |
| < 0.1% (< 0.001) | **55** | Low frequency |
| < 1% (< 0.01) | **30** | Polymorphism |
| ≥ 1% | **10** | Common → likely benign |

#### 5. ClinVar Evidence (Weight: 20%)

> *"What does the clinical evidence say about this variant?"*

Two sub-signals are summed:

| Sub-signal | Value | Points |
|------------|-------|--------|
| **ClinVar Significance** | Pathogenic | +55 |
| | Likely Pathogenic | +40 |
| | VUS (Uncertain) | +15 |
| | Benign | +5 |
| | No data | +10 |
| **Review Status** | Expert panel reviewed | +35 |
| | Multiple submitters, no conflict | +25 |
| | Criteria provided, single submitter | +15 |
| | No assertion / empty | +5 |

ClinVar: Pathogenic + Expert panel → 55 + 35 = **90/100**.

---

### Variant Composite Score

Each variant receives a **weighted composite score** combining all 5 metrics:

```
Composite = Actionability × 0.30
          + Disease Urgency × 0.30
          + ClinVar Evidence × 0.20
          + gnomAD Rarity × 0.10
          + QA Confidence × 0.10
```

The weights reflect clinical prioritization: **Actionability** and **Disease Urgency** drive 60% of the score because they directly impact patient management, while ClinVar provides 20% for evidence strength, and gnomAD + QA provide 20% for variant quality.

---

### Case-Level Ranking

Each patient case (which may contain 50–500+ variants) receives a **case score** computed as:

```
Case Score = Top Variant Score × 0.50
           + Average Variant Score × 0.30
           + Actionable Count Bonus × 0.20
```

Where:
- **Top Variant Score (50%)** — The highest composite score in the case. A single high-impact variant drives the case priority.
- **Average Variant Score (30%)** — Mean composite across all variants. Cases with many concerning variants rank higher.
- **Actionable Count Bonus (20%)** — 5 points per actionable variant (capped at 20). Rewards cases with multiple treatment options.

Cases are then classified into urgency tiers:

| Case Score | Tier | Color | Action |
|------------|------|-------|--------|
| **≥ 70** | 🔴 CRITICAL | Red | Immediate review required |
| **≥ 50** | 🟠 HIGH | Orange | Priority review |
| **≥ 30** | 🟡 MODERATE | Yellow | Standard review timeline |
| **< 30** | 🟢 LOW | Green | Routine processing |

---

## ⚡ How the AI Summary is Generated

Each ranked case card displays an **AI Summary** section. It can be generated in two modes:

### Mode 1: Rule-Based Fallback (Default — No API Key)

When no LLM API key is configured, the summary is generated deterministically from the scoring results:

1. **Variant counts**: "*263 variants — 0 pathogenic, 105 actionable.*"
2. **Top actionable genes**: Extracts all genes with Actionability ≥ 50, shows the top 4 unique genes.
3. **Therapy recommendations**: Lists the top 3 matched therapies from the gene→therapy database.
4. **Action label**: Maps the urgency tier to a clinical action ("Molecular tumor board discussion recommended" for high, "Standard workflow" for low).
5. **Estimated review time**: Calculated as `max(5, total_variants × 2)` minutes.

### Mode 2: LLM-Powered Summary (With API Key)

When a **Gemini**, **GPT-4o**, or **Claude** API key is set (via ⚙️ API Key button), the summary is generated by prompting the LLM with:

- Case score and urgency tier
- Variant counts (total, actionable, pathogenic)
- Average values of all 5 metrics
- Top 5 genes and matched therapies
- Detailed scores of the top 5 variants

The LLM outputs structured JSON with:
- `summary_bullets` — 4 clinical bullet points
- `recommended_action` — 1-line clinical action
- `estimated_review_time` — Review time estimate

The system prompt instructs the LLM to behave as an *"expert Genomic Pathologist AI Co-Pilot"* and reference specific gene and drug names.

### 📚 Literature Review (Per-Variant)

Clicking the 📚 button on any variant row triggers a **PubMed + LLM** pipeline:

1. **PubMed E-utilities Search** — Searches NCBI for `{gene} {HGVS} variant` (free, no API key needed)
2. **Abstract Fetching** — Retrieves titles, authors, journals, dates, and full abstracts of the top 5-8 papers
3. **LLM Summarization** — Sends the abstracts to Gemini/GPT/Claude with a clinical review prompt
4. **Output** — A modal with:
   - Evidence level badge (Strong / Moderate / Limited / Emerging)
   - Clinical literature review (2-3 paragraphs)
   - Key findings list
   - Clinical relevance statement
   - Clickable paper cards linking to PubMed

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

Click **Demo** → **Load Demo Data** to see pre-built oncology cases (NSCLC, Breast).

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
| `POST` | `/api/set_key` | Store LLM API key in session |
| `POST` | `/api/variant_papers` | PubMed search + LLM literature summary |

---

## 🛠️ Tech Stack

| Layer | Technology |
|-------|------------|
| Backend | Flask (Python) |
| Scoring | Rule-based 5-metric engine (21 actionable genes, 6 prognostic markers) |
| Literature | PubMed E-utilities (free NCBI API) |
| Data | SOPHiA DDM™ CSV exports + VQS API (DuckDB-as-a-service) |
| LLM (optional) | Gemini 2.5 Flash / GPT-4o / Claude |
| Frontend | Vanilla HTML/CSS/JS, Inter font, dark/light themes |

---

## ⚠️ Disclaimer

Hackathon prototype — not for clinical use. All scoring is rule-based and should be validated by qualified professionals.

---

Built with ❤️ at ETH Zurich for the **Future of Health Hackathon 2026**
