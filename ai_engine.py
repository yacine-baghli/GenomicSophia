"""
AI Engine — Scores and ranks genomic cases by 4 clinical metrics.
Metrics: ABCD Prediction, ClinVar Evidence, Community Frequency, QA Confidence.
"""

import json
import os
import csv
from io import StringIO

# ─── Known Gene/Variant Databases ──────────────────────────────────────────

ACTIONABLE_GENES = {
    "EGFR":  {"tier": 1, "therapies": ["Osimertinib", "Erlotinib", "Gefitinib"]},
    "ALK":   {"tier": 1, "therapies": ["Alectinib", "Lorlatinib", "Crizotinib"]},
    "ROS1":  {"tier": 1, "therapies": ["Crizotinib", "Entrectinib"]},
    "BRAF":  {"tier": 1, "therapies": ["Dabrafenib+Trametinib", "Vemurafenib"]},
    "KRAS":  {"tier": 2, "therapies": ["Sotorasib (G12C)", "Adagrasib (G12C)"]},
    "NTRK1": {"tier": 1, "therapies": ["Larotrectinib", "Entrectinib"]},
    "NTRK2": {"tier": 1, "therapies": ["Larotrectinib", "Entrectinib"]},
    "NTRK3": {"tier": 1, "therapies": ["Larotrectinib", "Entrectinib"]},
    "RET":   {"tier": 1, "therapies": ["Selpercatinib", "Pralsetinib"]},
    "MET":   {"tier": 2, "therapies": ["Capmatinib", "Tepotinib"]},
    "HER2":  {"tier": 2, "therapies": ["Trastuzumab deruxtecan"]},
    "ERBB2": {"tier": 2, "therapies": ["Trastuzumab deruxtecan"]},
    "PIK3CA":{"tier": 2, "therapies": ["Alpelisib"]},
    "BRCA1": {"tier": 1, "therapies": ["Olaparib", "Rucaparib"]},
    "BRCA2": {"tier": 1, "therapies": ["Olaparib", "Rucaparib"]},
    "ESR1":  {"tier": 2, "therapies": ["Elacestrant"]},
    "FGFR2": {"tier": 2, "therapies": ["Pemigatinib", "Futibatinib"]},
    "FGFR3": {"tier": 2, "therapies": ["Erdafitinib"]},
    "IDH1":  {"tier": 2, "therapies": ["Ivosidenib"]},
    "IDH2":  {"tier": 2, "therapies": ["Enasidenib"]},
    "MYCN":  {"tier": 2, "therapies": ["Intensive multimodal therapy"]},
}

PROGNOSTIC_MARKERS = {
    "TP53":   "Genomic instability, poorer outcomes, faster resistance",
    "PTEN":   "PI3K/AKT/mTOR pathway activation, reduced TKI efficacy",
    "RB1":    "Cell cycle deregulation, treatment resistance",
    "CDKN2A": "Cell cycle checkpoint loss",
    "APC":    "Wnt pathway activation (CRC driver)",
    "SMAD4":  "TGF-β pathway loss, aggressive phenotype",
}


# ─── 4-Metric Scoring System ───────────────────────────────────────────────

def _get_field(record, *keys, default=""):
    """Try multiple field names, return first non-empty value."""
    for k in keys:
        v = record.get(k)
        if v is not None and str(v).strip() != "":
            return v
    return default


def compute_abcd_score(abcd="", consequence=""):
    """Score 0-100: SOPHiA ABCD prediction + consequence severity."""
    score = 0
    abcd_str = str(abcd).upper().strip()

    # ABCD predictor is the primary signal
    abcd_map = {"A": 65, "B": 45, "C": 20, "D": 5}
    score += abcd_map.get(abcd_str[:1] if abcd_str else "", 10)

    # Consequence severity bonus
    cons = str(consequence).lower()
    if any(kw in cons for kw in ["nonsense", "frameshift", "stop_gained", "splice"]):
        score += 30
    elif "missense" in cons:
        score += 12
    elif "inframe" in cons:
        score += 5

    return min(100, score)


def compute_qa_confidence(read_depth=None, allele_freq=None, abcd=""):
    """Score 0-100: How confident are we in this variant call?"""
    score = 50  # baseline

    # Read depth
    try:
        depth = float(read_depth) if read_depth is not None else None
        if depth is not None:
            if depth >= 200:
                score += 25
            elif depth >= 100:
                score += 20
            elif depth >= 50:
                score += 10
            elif depth < 20:
                score -= 15
    except (ValueError, TypeError):
        pass

    # Allele frequency (variant AF in sample — higher = clearer signal)
    try:
        af = float(allele_freq) if allele_freq is not None else None
        if af is not None:
            if af >= 0.3:
                score += 20
            elif af >= 0.15:
                score += 10
            elif af < 0.05:
                score -= 10
    except (ValueError, TypeError):
        pass

    # ABCD predictor as QA proxy
    abcd_str = str(abcd).upper().strip()
    if abcd_str.startswith("A"):
        score += 10
    elif abcd_str.startswith("B"):
        score += 5

    return max(0, min(100, score))


def compute_community_freq_score(community_freq):
    """Score 0-100: Rarity based on SOPHiA DDM Community Frequency (rarer = higher)."""
    try:
        val = float(community_freq) if community_freq is not None else None
        if val is None or str(community_freq).strip() in ("", "—", "-", "N/A"):
            return 80  # absent = very rare
        if val == 0:
            return 95
        if val < 0.001:
            return 90
        if val < 0.005:
            return 75
        if val < 0.01:
            return 60
        if val < 0.05:
            return 40
        if val < 0.10:
            return 25
        return 10  # common in community → likely benign/artifact
    except (ValueError, TypeError):
        return 80


def compute_clinvar_score(clinvar_sig, clinvar_review=""):
    """Score 0-100: ClinVar evidence strength."""
    sig = str(clinvar_sig).lower().strip()
    rev = str(clinvar_review).lower().strip()

    score = 0
    # Significance
    if "pathogenic" in sig and "likely" not in sig and "benign" not in sig:
        score += 55
    elif "likely_pathogenic" in sig or "likely pathogenic" in sig:
        score += 40
    elif "uncertain" in sig:
        score += 15
    elif "benign" in sig:
        score += 5
    else:
        score += 10  # no data

    # Review status bonus
    if "expert" in rev:
        score += 35
    elif "multiple" in rev:
        score += 25
    elif "criteria" in rev:
        score += 15
    elif "no assertion" in rev or rev == "":
        score += 5

    return min(100, score)


def _get_therapies(gene):
    """Look up therapies for a gene from the actionable gene database."""
    gene_upper = str(gene).upper().strip()
    if gene_upper in ACTIONABLE_GENES:
        return ACTIONABLE_GENES[gene_upper]["therapies"]
    return []


def score_variant(record):
    """Compute all 4 metrics for a single variant. Returns dict with scores."""
    gene = str(_get_field(record, "transcriptome.gene.symbol", "gene", "Gene", "GENE")).strip()
    consequence = str(_get_field(record, "short.annotated.transcriptContext.proteinVariant.consequence.sophiaNameSelect",
                                 "Coding consequence", "consequence", "Consequence", "CONSEQUENCE")).strip()
    abcd = str(_get_field(record, "short_predictor.inhouse.predictors.ABCD.result.label",
                           "SOPHiA DDM\u2122 prediction", "SOPHiA DDM prediction",
                           "abcd", "ABCD")).strip()
    clinvar_sig = str(_get_field(record, "short.annotated.catalogs.clinvar.CLNSIG",
                                  "clinvar_significance", "clinvar", "ClinVar", "CLINVAR")).strip()
    clinvar_rev = str(_get_field(record, "short.annotated.catalogs.clinvar.CLNREVSTAT",
                                  "clinvar_review_status", "clinvar_review", "ClinVarReview")).strip()
    community_freq = _get_field(record, "Community frequency",
                                 "community_frequency", "Account frequency",
                                 "Account frequency (per application)")
    read_depth = _get_field(record, "short.called.readDepth", "Read depth",
                             "read_depth", "ReadDepth", "DP")
    allele_freq = _get_field(record, "short.called.alleleFrequency", "VAF(%)",
                              "allele_frequency", "AF", "VAF")
    hgvs_c = _get_field(record, "short.annotated.transcriptContext.transcriptVariant.cnomen.base",
                         "c.DNA", "cDNA", "hgvs_c")
    hgvs_p = _get_field(record, "short.annotated.transcriptContext.proteinVariant.pnomen.hgvsRefSeq",
                         "Protein", "protein_hgvs", "hgvs_p", "hgvs", "HGVS")
    chrom = _get_field(record, "short.called.variant.location.chromosome.fullSeqName",
                        "Position", "chromosome", "CHROM", "Chr")
    in_report = _get_field(record, "userAnnotations.interpretation.inReport.flagged",
                            "in_report", default=False)

    # Compute the 4 metrics
    abcd_score = compute_abcd_score(abcd, consequence)
    clinvar_score = compute_clinvar_score(clinvar_sig, clinvar_rev)
    community_score = compute_community_freq_score(community_freq)
    qa_confidence = compute_qa_confidence(read_depth, allele_freq, abcd)
    therapies = _get_therapies(gene)

    # Composite score (weighted average — 4 metrics)
    composite = int(
        abcd_score * 0.35
        + clinvar_score * 0.25
        + community_score * 0.20
        + qa_confidence * 0.20
    )

    # Flags
    flags = []
    if abcd and abcd.upper() in ("A", "B"):
        flags.append(f"ABCD: {abcd.upper()}")
    if clinvar_score >= 50:
        flags.append(f"ClinVar: {clinvar_sig}")
    if community_score >= 80:
        flags.append("Rare in community")
    if therapies:
        tier = ACTIONABLE_GENES.get(gene.upper(), {}).get("tier", "?")
        flags.append(f"Tier {tier} therapies ({gene})")
    if gene.upper() in PROGNOSTIC_MARKERS:
        flags.append(f"Prognostic: {PROGNOSTIC_MARKERS[gene.upper()]}")

    return {
        "gene": gene or "Unknown",
        "hgvs": str(hgvs_p or hgvs_c or ""),
        "consequence": consequence,
        "chromosome": str(chrom),
        "abcd": abcd,
        "allele_frequency": str(allele_freq),
        "read_depth": str(read_depth),
        "clinvar": clinvar_sig,
        "clinvar_review": clinvar_rev,
        "community_freq": str(community_freq),
        "in_report": in_report,
        # ─── The 4 Metrics ───
        "abcd_score": abcd_score,
        "clinvar_score": clinvar_score,
        "community_score": community_score,
        "qa_confidence": qa_confidence,
        "composite_score": composite,
        # ─── Extras ───
        "therapies": therapies,
        "flags": flags,
    }


def score_case(variants_list, case_id="unknown"):
    """Score an entire case and return priority ranking."""
    if not variants_list:
        return {
            "case_id": case_id, "case_score": 0, "urgency": "low",
            "urgency_color": "#22c55e", "urgency_label": "🟢 LOW — Routine",
            "total_variants": 0, "pathogenic_count": 0,
            "top_genes": [], "top_therapies": [], "flags": [],
            "avg_abcd": 0, "avg_clinvar": 0,
            "avg_community": 0, "avg_qa": 0,
            "scored_variants": [],
        }

    scored = []
    all_flags, all_therapies = [], []
    pathogenic_count = 0
    genes_seen = set()
    sums = {"abcd": 0, "cli": 0, "com": 0, "qa": 0}

    for v in variants_list:
        sv = score_variant(v)
        scored.append(sv)
        all_flags.extend(sv["flags"])
        all_therapies.extend(sv["therapies"])
        genes_seen.add(sv["gene"])
        if "pathogenic" in sv["clinvar"].lower():
            pathogenic_count += 1
        sums["abcd"] += sv["abcd_score"]
        sums["cli"]  += sv["clinvar_score"]
        sums["com"]  += sv["community_score"]
        sums["qa"]   += sv["qa_confidence"]

    n = len(scored)
    scored.sort(key=lambda x: x["composite_score"], reverse=True)

    # Case-level composite (top variant 50% + average 30% + high-ABCD bonus 20%)
    top = scored[0]["composite_score"] if scored else 0
    avg = sum(s["composite_score"] for s in scored) / n
    high_abcd_count = sum(1 for s in scored if s["abcd_score"] >= 65)
    case_score = min(100, int(top * 0.5 + avg * 0.3 + min(high_abcd_count * 5, 20)))

    if case_score >= 70:
        urg, col, lab = "critical", "#ef4444", "🔴 CRITICAL — Immediate Review"
    elif case_score >= 50:
        urg, col, lab = "high", "#f97316", "🟠 HIGH — Priority Review"
    elif case_score >= 30:
        urg, col, lab = "moderate", "#eab308", "🟡 MODERATE — Standard Review"
    else:
        urg, col, lab = "low", "#22c55e", "🟢 LOW — Routine"

    return {
        "case_id": case_id, "case_score": case_score,
        "urgency": urg, "urgency_color": col, "urgency_label": lab,
        "total_variants": n, "pathogenic_count": pathogenic_count,
        "top_genes": list(genes_seen)[:10],
        "top_therapies": list(set(all_therapies))[:8],
        "flags": list(set(all_flags))[:15],
        "avg_abcd":       int(sums["abcd"] / n),
        "avg_clinvar":    int(sums["cli"] / n),
        "avg_community":  int(sums["com"] / n),
        "avg_qa":         int(sums["qa"] / n),
        "scored_variants": scored,
    }


def rank_cases(cases_dict):
    """Rank multiple cases by urgency. cases_dict = {case_id: [variants]}"""
    results = [score_case(v, k) for k, v in cases_dict.items()]
    results.sort(key=lambda x: x["case_score"], reverse=True)
    return results


# ─── CSV Parsing ────────────────────────────────────────────────────────────

def parse_csv_to_cases(csv_text):
    """Parse a CSV string into cases dict. Groups rows by sample/patient column."""
    reader = csv.DictReader(StringIO(csv_text))
    cases = {}
    for row in reader:
        sample = (
            row.get("sample") or row.get("Sample") or row.get("SAMPLE")
            or row.get("patient") or row.get("Patient")
            or row.get("Case") or row.get("case") or row.get("SampleID")
            or "Sample A"
        )
        sample = str(sample).strip().rstrip(";").strip()
        if not sample:
            sample = "Sample A"
        cases.setdefault(sample, []).append(row)
    return cases


# ─── LLM Summary (variant_analysis_ai.py style) ───────────────────────────

def generate_case_summary_llm(scored_case, llm_provider=None, api_key=None):
    """Generate Claude-style importance score + 2-sentence summary for a case."""

    # Format top variants like variant_analysis_ai.py
    top_variants = scored_case["scored_variants"][:10]
    variant_texts = []
    for v in top_variants:
        variant_texts.append(
            f"Gene: {v['gene']} | Prediction: {v['abcd']} | ClinVar: {v['clinvar']} "
            f"| Consequence: {v['consequence']} | HGVS: {v['hgvs']} | VAF: {v['allele_frequency']} "
            f"| CommunityFreq: {v['community_freq']} | CompositeScore: {v['composite_score']}"
        )
    variants_str = "\n".join(variant_texts)

    prompt = f"""Analyze these genetic variants from a patient sample. The file contains {scored_case['total_variants']} total variants.

Top {len(top_variants)} prioritized variants:
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

0-20:
Benign or likely benign variants with no known clinical significance.

21-40:
Variants of uncertain significance with weak disease association or low confidence.

41-60:
Potentially clinically relevant variants, moderate evidence, limited actionability.

61-80:
Pathogenic or likely pathogenic variants with strong disease association and potential therapeutic or prognostic relevance.

81-100:
Critical clinically actionable findings requiring urgent attention, such as:
- established pathogenic drivers
- FDA-recognized biomarkers
- high-confidence oncogenic mutations
- variants linked to targeted therapies
- aggressive tumor signatures
- high VAF clonal pathogenic variants

Use the FULL range of scores.
Do not default to multiples of 5.
Scores like 67, 82, 91 are preferred when appropriate.

Consider factors like:
- Pathogenicity classifications
- Actionability of variants
- Gene involvement in disease
- Prediction confidence
- VAF (variant allele frequency) values
- Whether variants are in tumor vs normal samples
"""

    # Try providers in order (Claude first)
    anthropic_key = api_key if llm_provider == "anthropic" else os.environ.get("ANTHROPIC_API_KEY")
    gemini_key = api_key if llm_provider == "gemini" else os.environ.get("GEMINI_API_KEY")
    openai_key = api_key if llm_provider == "openai" else os.environ.get("OPENAI_API_KEY")

    for provider, key, fn in [
        ("anthropic", anthropic_key, _call_anthropic),
        ("gemini", gemini_key, _call_gemini),
        ("openai", openai_key, _call_openai),
    ]:
        if key and (not llm_provider or llm_provider == provider):
            try:
                raw = fn(key, prompt, raw_text=True)
                return _parse_ai_analysis(raw)
            except Exception as e:
                print(f"{provider} error: {e}")

    return None  # No LLM available


def _parse_ai_analysis(response_text):
    """Parse Claude's JSON response into importance_score + summary."""
    try:
        json_start = response_text.find("{")
        json_end = response_text.rfind("}") + 1
        if json_start != -1 and json_end > json_start:
            result = json.loads(response_text[json_start:json_end])
            return {
                "importance_score": round(float(result.get("importance_score", 50.0)), 1),
                "summary": result.get("summary", "Analysis complete."),
            }
    except (json.JSONDecodeError, ValueError):
        pass
    return {"importance_score": 50.0, "summary": response_text[:300]}


def _call_gemini(key, prompt, raw_text=False):
    from google import genai
    from google.genai import types
    client = genai.Client(api_key=key)
    r = client.models.generate_content(
        model="gemini-2.5-flash", contents=prompt,
        config=types.GenerateContentConfig(system_instruction="You are an expert genomic pathologist. Respond with JSON only."))
    return r.text.strip()

def _call_openai(key, prompt, raw_text=False):
    import openai
    client = openai.OpenAI(api_key=key)
    r = client.chat.completions.create(model="gpt-4o", messages=[
        {"role": "system", "content": "You are an expert genomic pathologist. Respond with JSON only."},
        {"role": "user", "content": prompt}])
    return r.choices[0].message.content.strip()

def _call_anthropic(key, prompt, raw_text=False):
    import anthropic
    client = anthropic.Anthropic(api_key=key)
    r = client.messages.create(model="claude-sonnet-4-20250514", max_tokens=500,
        messages=[{"role": "user", "content": prompt}])
    return r.content[0].text.strip()


def _generate_fallback_summary(scored_case):
    """Deterministic summary when no LLM is available."""
    bullets = []
    bullets.append(f"{scored_case['total_variants']} variants — {scored_case['pathogenic_count']} ClinVar-pathogenic.")
    top_abcd = [v["gene"] for v in scored_case["scored_variants"] if v["abcd_score"] >= 65]
    bullets.append(f"High-confidence ABCD genes: {', '.join(list(set(top_abcd))[:4]) or 'None'}.")
    if scored_case["top_therapies"]:
        bullets.append(f"Consider: {', '.join(scored_case['top_therapies'][:3])}.")
    else:
        bullets.append("Standard-of-care per tumor site guidelines.")
    bullets.append("Molecular tumor board discussion recommended." if scored_case["case_score"] >= 50 else "Standard workflow. No urgent escalation.")

    # Build a 2-sentence summary like variant_analysis_ai.py
    top_abcd_str = ', '.join(list(set(top_abcd))[:4]) or 'None'
    sentence1 = (f"Analyzed {scored_case['total_variants']} variants with "
                 f"{scored_case['pathogenic_count']} ClinVar-pathogenic hits; "
                 f"high-confidence ABCD genes include {top_abcd_str}.")
    if scored_case["top_therapies"]:
        therapy_str = ', '.join(scored_case['top_therapies'][:3])
        sentence2 = (f"Consider targeted therapies ({therapy_str}); "
                     + ("molecular tumor board discussion recommended."
                        if scored_case["case_score"] >= 50
                        else "standard workflow, no urgent escalation."))
    else:
        sentence2 = ("Standard-of-care per tumor site guidelines; "
                     + ("molecular tumor board discussion recommended."
                        if scored_case["case_score"] >= 50
                        else "no urgent escalation."))

    return {
        "summary_bullets": bullets,
        "summary": f"{sentence1} {sentence2}",
        "recommended_action": scored_case.get("urgency_label", "Review case"),
        "estimated_review_time": f"{max(5, scored_case['total_variants'] * 2)} min",
    }

