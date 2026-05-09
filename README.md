# 🧬 Genomic Co-Pilot

**AI-Powered Genomic Case Triage Dashboard** — built for the SOPHiA Genetics × ETH Zurich Future of Health Hackathon (May 8–10, 2026).

Helps genomic pathologists prioritize their caseload by ranking patient samples by clinical urgency using a **4-metric scoring system** with native **SOPHiA DDM™** CSV export support and optional **Claude AI** clinical summaries.

---

## 🎯 What It Does

A pathologist arrives Monday morning with dozens of pending analyses. Genomic Co-Pilot instantly ranks every case by urgency so she knows **where to start**.

Each variant is scored across **4 clinical metrics** derived directly from SOPHiA DDM™ data, then cases are ranked and color-coded by priority.

---

## 🧠 Scoring System — 4 Metrics

### Variant-Level Scoring

Each variant is independently scored across 4 metrics (0–100), weighted and combined into a single **composite score**.

#### 1. ABCD Prediction (Weight: 35%)

> *"What does SOPHiA DDM™'s own ABCD predictor say about this variant?"*

The ABCD predictor is SOPHiA DDM™'s proprietary classification system. It is the **primary** signal in our scoring because it already integrates SOPHiA's internal machine learning models.

| ABCD Class | Base Score | Interpretation |
|------------|-----------|----------------|
| **A** — High confidence pathogenic | **65** | Strong evidence of pathogenicity |
| **B** — Moderate confidence | **45** | Moderate pathogenic evidence |
| **C** — Low confidence | **20** | Limited evidence |
| **D** — Benign prediction | **5** | Likely benign |
| Unknown/empty | **10** | Insufficient data |

**Consequence severity bonus** (added on top):

| Consequence Type | Bonus |
|-----------------|-------|
| Nonsense / Frameshift / Stop gained / Splice | **+30** |
| Missense | **+12** |
| Inframe insertion/deletion | **+5** |

*Example: ABCD: A + Frameshift → 65 + 30 = **95/100***

#### 2. ClinVar Evidence (Weight: 25%)

> *"What does the global clinical evidence say about this variant?"*

Two sub-signals are summed:

| Sub-signal | Value | Points |
|------------|-------|--------|
| **ClinVar Significance** | Pathogenic | +55 |
| | Likely Pathogenic | +40 |
| | VUS (Uncertain Significance) | +15 |
| | Benign / Likely Benign | +5 |
| | No data | +10 |
| **Review Status** | Expert panel reviewed | +35 |
| | Multiple submitters, no conflict | +25 |
| | Criteria provided, single submitter | +15 |
| | No assertion / empty | +5 |

*Example: ClinVar Pathogenic + Expert panel → 55 + 35 = **90/100***

#### 3. Community Frequency (Weight: 20%)

> *"How common is this variant across all SOPHiA DDM™ labs worldwide?"*

This uses the **SOPHiA DDM™ Community Frequency** — the proportion of all samples across all SOPHiA DDM™ users worldwide that contain this variant. Unlike gnomAD (population frequency), this reflects **clinical lab frequency**, making it more relevant for identifying recurrent artifacts vs. real pathogenic variants.

| Community Frequency | Score | Interpretation |
|--------------------|-------|----------------|
| Absent (0 or N/A) | **95** | Never seen → very likely real & rare |
| < 0.1% | **90** | Ultra-rare across labs |
| < 0.5% | **75** | Rare |
| < 1% | **60** | Low frequency |
| < 5% | **40** | Moderate — could be polymorphism |
| < 10% | **25** | Common — likely benign or artifact |
| ≥ 10% | **10** | Very common → likely artifact |

*Example: Community frequency 0 → **95/100** (never seen in any SOPHiA DDM™ lab)*

#### 4. QA Confidence (Weight: 20%)

> *"How reliable is this variant call from a sequencing quality perspective?"*

Starts at **50** baseline, then adjusts based on three quality signals:

| Factor | Condition | Adjustment |
|--------|-----------|------------|
| **Read Depth** | ≥ 200× | +25 |
| | ≥ 100× | +20 |
| | ≥ 50× | +10 |
| | < 20× | −15 |
| **VAF** (Variant Allele Frequency) | ≥ 30% | +20 |
| | ≥ 15% | +10 |
| | < 5% | −10 |
| **ABCD Predictor** (as QA proxy) | A | +10 |
| | B | +5 |

*Example: Read depth 200× + VAF 35% + ABCD:A → 50 + 25 + 20 + 10 = **105 → capped at 100***

---

### Variant Composite Score

Each variant receives a **weighted composite score**:

```
Composite = ABCD Score × 0.35
          + ClinVar Evidence × 0.25
          + Community Frequency × 0.20
          + QA Confidence × 0.20
```

**Why these weights?**
- **ABCD (35%)**: SOPHiA DDM™'s own ML-backed prediction is the strongest single signal for pathogenicity
- **ClinVar (25%)**: Provides independent clinical evidence with review status quality checks
- **Community Frequency (20%)**: SOPHiA DDM™ lab-wide frequency is more clinically relevant than population databases for filtering artifacts
- **QA Confidence (20%)**: Sequencing quality ensures we don't prioritize false positives

---

### Case-Level Ranking

Each patient case (50–500+ variants) receives a **case score**:

```
Case Score = Top Variant Score × 0.50
           + Average Variant Score × 0.30
           + High-ABCD Bonus × 0.20
```

| Component | Weight | Description |
|-----------|--------|-------------|
| **Top Variant** | 50% | Highest composite score — one critical variant drives the case |
| **Average Score** | 30% | Mean composite across all variants — cases with many concerning variants rank higher |
| **High-ABCD Bonus** | 20% | +5 per variant with ABCD score ≥ 65 (capped at +20). Rewards cases with multiple high-confidence variants |

Cases are classified into urgency tiers:

| Case Score | Tier | Color | Clinical Action |
|------------|------|-------|-----------------|
| **≥ 70** | 🔴 CRITICAL | Red | Immediate review required |
| **≥ 50** | 🟠 HIGH | Orange | Priority review |
| **≥ 30** | 🟡 MODERATE | Yellow | Standard review timeline |
| **< 30** | 🟢 LOW | Green | Routine processing |

---

## ⚡ AI Summary — Two Layers

Each ranked case displays a two-layer summary system:

### Layer 1: 🧠 AI Clinical Summary (LLM-Powered)

When a **Claude**, **Gemini**, or **OpenAI** API key is configured, the top 5 variants and case metrics are sent to the LLM, which generates a **2-3 sentence clinical narrative** — similar to what a genomic pathologist would dictate.

*Example output:*
> *"Two pathogenic PMS2 variants at high VAF (48-55%) indicate Lynch syndrome/MMR deficiency, alongside oncogenic TP53 and RB1 frameshifts suggesting an aggressive tumor with potential for immunotherapy response. The ESR1 hotspot mutation (p.Y537S) at low VAF indicates hormone therapy resistance emerging in this tumor."*

The LLM receives:
- Case score and urgency tier
- Variant counts (total, ClinVar-pathogenic)
- Average values of all 4 metrics
- Top genes and matched therapies
- Detailed data for the top 5 variants (gene, HGVS, consequence, ABCD, composite score, ClinVar, community frequency)

**How to activate:** Click **⚙️ API Key** → select **Claude** → paste your Anthropic API key → **💾 Save Key**. Then set the **LLM** dropdown to Claude and click **🔬 Rank All Cases**.

### Layer 2: ⚡ Deterministic Analysis (Always Available)

A rule-based summary generated from the scoring results — no API key required:
1. **Variant counts**: *"319 variants — 5 ClinVar-pathogenic."*
2. **High-confidence genes**: Top ABCD:A/B genes
3. **Therapy recommendations**: Matched from the 21-gene actionable database
4. **Action label**: Based on urgency tier

---

## 📚 Literature Search (Per-Variant)

Clicking the **📚** button on any variant row opens a modal that:
1. Searches **PubMed E-utilities** for `{gene} {HGVS} variant` (free NCBI API, no key needed)
2. Shows **clickable paper cards** with title, authors, journal, date
3. Links to the full PubMed page for that variant

No LLM is involved — this provides direct access to primary literature.

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

### Optional: Enable Claude AI Summaries

```bash
# Set Anthropic API key as env variable (alternative to UI)
set ANTHROPIC_API_KEY=sk-ant-...
python app.py
```

Or use the **⚙️ API Key** button in the dashboard header.

---

## 📊 Data Sources

### 📁 Local CSV Samples (Default)

Drop SOPHiA DDM™ export CSVs into the `samples/` folder — they're loaded automatically.

- **3 sample patients included** (`patient1.csv`, `patient2.csv`, `patient3.csv`)
- Reads SOPHiA DDM™ columns: `gene`, `SOPHiA DDM™ prediction` (ABCD), `Coding consequence`, `clinvar_significance`, `clinvar_review_status`, `Community frequency`, `Read depth`, `VAF(%)`, `Protein`, `c.DNA`
- Also supports generic CSV: `Sample`, `Gene`, `HGVS`, `ABCD`, `ClinVar`, `ReadDepth`, `AF`

**From the dashboard you can:**
- **Add** more CSVs via upload → saved to `/samples`
- **Remove** files with the ✕ button
- **Re-rank** all cases together

### 🔌 VQS API (Live SOPHiA DDM™ Platform)

1. Get credentials from: `https://iam-vandv.sophiagenetics.com/account/token`
2. Get dataset keys from browser DevTools (Network tab)
3. Paste into the VQS API tab → **Analyze**

### 📋 Demo Mode

Pre-built oncology case for quick demonstration.

---

## 📁 Project Structure

```
GenomicSophia/
├── app.py              # Flask routes & API endpoints
├── ai_engine.py        # 4-metric scoring engine + CSV parser + LLM summaries
├── vqs_client.py       # SOPHiA VQS API client
├── requirements.txt    # Python dependencies
├── samples/            # CSV data (auto-loaded on startup)
│   ├── patient1.csv    # ESR1-Low-VAF-T (263 variants)
│   ├── patient2.csv    # COQ8A-SKIV2L (500 variants)
│   └── patient3.csv    # ACCESS010-CP (319 variants)
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
| `POST` | `/api/upload` | Upload & persist CSVs to `/samples` |
| `POST` | `/api/remove_sample` | Remove a CSV from `/samples` |
| `POST` | `/api/rank` | Score & rank all cases (+ optional LLM summary) |
| `POST` | `/api/analyze` | Analyze via VQS API |
| `POST` | `/api/set_key` | Store LLM API key in session |
| `POST` | `/api/variant_papers` | PubMed paper search for a gene/variant |

---

## 🛠️ Tech Stack

| Layer | Technology |
|-------|------------|
| Backend | Flask (Python) |
| Scoring | 4-metric engine: ABCD (35%) + ClinVar (25%) + Community Freq. (20%) + QA (20%) |
| LLM | Claude Sonnet 4 / Gemini 2.5 Flash / GPT-4o (optional) |
| Literature | PubMed E-utilities (free NCBI API) |
| Data | SOPHiA DDM™ CSV exports + VQS API |
| Frontend | Vanilla HTML/CSS/JS, Inter font, dark/light themes |

---

## ⚠️ Disclaimer

Hackathon prototype — not for clinical use. All scoring is rule-based and should be validated by qualified professionals.

---

Built with ❤️ at ETH Zurich for the **Future of Health Hackathon 2026**
