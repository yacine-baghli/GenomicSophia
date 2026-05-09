"""
AI Engine — Scores and ranks genomic cases by 5 clinical metrics.
Metrics: Actionability, Disease Urgency, QA Confidence, gnomAD Rarity, ClinVar Evidence.
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


# ─── 5-Metric Scoring System ───────────────────────────────────────────────

def _get_field(record, *keys, default=""):
    """Try multiple field names, return first non-empty value."""
    for k in keys:
        v = record.get(k)
        if v is not None and str(v).strip() != "":
            return v
    return default


def compute_actionability(gene, consequence=""):
    """Score 0-100: Is there a targeted therapy for this gene/variant?"""
    gene_upper = str(gene).upper().strip()
    cons = str(consequence).lower()
    if gene_upper in ACTIONABLE_GENES:
        info = ACTIONABLE_GENES[gene_upper]
        base = 90 if info["tier"] == 1 else 65
        # Loss-of-function in tumor suppressor = higher actionability
        if any(kw in cons for kw in ["frameshift", "nonsense", "stop_gained", "splice"]):
            base = min(100, base + 10)
        return base, info["therapies"]
    if gene_upper in PROGNOSTIC_MARKERS:
        return 30, []
    return 10, []


def compute_disease_urgency(acmg="", abcd="", consequence=""):
    """Score 0-100: How urgent is this variant based on classification + consequence?"""
    score = 0
    acmg_str = str(acmg).lower().strip()
    abcd_str = str(abcd).upper().strip()
    cons = str(consequence).lower()

    # ACMG
    if "pathogenic" in acmg_str and "likely" not in acmg_str:
        score += 45
    elif "likely pathogenic" in acmg_str:
        score += 30
    elif "uncertain" in acmg_str:
        score += 10

    # ABCD predictor
    abcd_map = {"A": 35, "B": 22, "C": 8, "D": 0}
    score += abcd_map.get(abcd_str[:1] if abcd_str else "", 0)

    # Consequence severity
    if any(kw in cons for kw in ["nonsense", "frameshift", "stop_gained", "splice"]):
        score += 20
    elif "missense" in cons:
        score += 8

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


def compute_gnomad_score(gnomad_value):
    """Score 0-100: Rarity in population (rarer = higher score = more likely pathogenic)."""
    try:
        val = float(gnomad_value) if gnomad_value is not None else None
        if val is None or str(gnomad_value).strip() in ("", "—", "-", "N/A"):
            return 80  # absent from gnomAD = very rare = likely pathogenic
        if val == 0:
            return 95
        if val < 0.00001:
            return 90
        if val < 0.0001:
            return 75
        if val < 0.001:
            return 55
        if val < 0.01:
            return 30
        return 10  # common variant — likely benign
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


def score_variant(record):
    """Compute all 5 metrics for a single variant. Returns dict with scores."""
    gene = str(_get_field(record, "transcriptome.gene.symbol", "gene", "Gene", "GENE")).strip()
    consequence = str(_get_field(record, "short.annotated.transcriptContext.proteinVariant.consequence.sophiaNameSelect", "consequence", "Consequence", "CONSEQUENCE")).strip()
    acmg = str(_get_field(record, "userAnnotations.interpretation.acmg.result.classificationFinal", "clinical_significance", "acmg", "ACMG", "Classification")).strip()
    abcd = str(_get_field(record, "short_predictor.inhouse.predictors.ABCD.result.label", "abcd", "ABCD")).strip()
    clinvar_sig = str(_get_field(record, "short.annotated.catalogs.clinvar.CLNSIG", "clinvar", "ClinVar", "CLINVAR")).strip()
    clinvar_rev = str(_get_field(record, "short.annotated.catalogs.clinvar.CLNREVSTAT", "clinvar_review", "ClinVarReview")).strip()
    gnomad = _get_field(record, "short.annotated.catalogs.gnomadGenomes.global.global.value", "short.annotated.catalogs.gnomadExomes.global.global.value", "gnomad", "gnomAD", "GNOMAD")
    read_depth = _get_field(record, "short.called.readDepth", "read_depth", "ReadDepth", "DP")
    allele_freq = _get_field(record, "short.called.alleleFrequency", "allele_frequency", "AF", "VAF")
    hgvs_c = _get_field(record, "short.annotated.transcriptContext.transcriptVariant.cnomen.base", "hgvs_c")
    hgvs_p = _get_field(record, "short.annotated.transcriptContext.proteinVariant.pnomen.hgvsRefSeq", "hgvs_p", "hgvs", "HGVS")
    chrom = _get_field(record, "short.called.variant.location.chromosome.fullSeqName", "chromosome", "CHROM", "Chr")
    in_report = _get_field(record, "userAnnotations.interpretation.inReport.flagged", "in_report", default=False)

    actionability, therapies = compute_actionability(gene, consequence)
    disease_urgency = compute_disease_urgency(acmg, abcd, consequence)
    qa_confidence = compute_qa_confidence(read_depth, allele_freq, abcd)
    gnomad_score = compute_gnomad_score(gnomad)
    clinvar_score = compute_clinvar_score(clinvar_sig, clinvar_rev)

    # Composite score (weighted average)
    composite = int(
        actionability * 0.30
        + disease_urgency * 0.30
        + clinvar_score * 0.20
        + gnomad_score * 0.10
        + qa_confidence * 0.10
    )

    # Flags
    flags = []
    if actionability >= 65:
        tier = ACTIONABLE_GENES.get(gene.upper(), {}).get("tier", "?")
        flags.append(f"Tier {tier} actionable ({gene})")
    if disease_urgency >= 50:
        flags.append(f"ACMG: {acmg}")
    if abcd and abcd.upper() in ("A", "B"):
        flags.append(f"ABCD: {abcd.upper()}")
    if clinvar_score >= 50:
        flags.append(f"ClinVar: {clinvar_sig}")
    if gnomad_score >= 80:
        flags.append("Rare variant")
    if gene.upper() in PROGNOSTIC_MARKERS:
        flags.append(f"Prognostic: {PROGNOSTIC_MARKERS[gene.upper()]}")

    return {
        "gene": gene or "Unknown",
        "hgvs": str(hgvs_p or hgvs_c or ""),
        "consequence": consequence,
        "chromosome": str(chrom),
        "acmg": acmg,
        "abcd": abcd,
        "allele_frequency": str(allele_freq),
        "read_depth": str(read_depth),
        "clinvar": clinvar_sig,
        "clinvar_review": clinvar_rev,
        "gnomad": str(gnomad),
        "in_report": in_report,
        # ─── The 5 Metrics ───
        "actionability": actionability,
        "disease_urgency": disease_urgency,
        "qa_confidence": qa_confidence,
        "gnomad_score": gnomad_score,
        "clinvar_score": clinvar_score,
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
            "total_variants": 0, "actionable_count": 0, "pathogenic_count": 0,
            "top_genes": [], "top_therapies": [], "flags": [],
            "avg_actionability": 0, "avg_disease_urgency": 0,
            "avg_qa_confidence": 0, "avg_gnomad": 0, "avg_clinvar": 0,
            "scored_variants": [],
        }

    scored = []
    all_flags, all_therapies = [], []
    pathogenic_count = actionable_count = 0
    genes_seen = set()
    sums = {"act": 0, "urg": 0, "qa": 0, "gno": 0, "cli": 0}

    for v in variants_list:
        sv = score_variant(v)
        scored.append(sv)
        all_flags.extend(sv["flags"])
        all_therapies.extend(sv["therapies"])
        genes_seen.add(sv["gene"])
        if "pathogenic" in sv["acmg"].lower():
            pathogenic_count += 1
        if sv["actionability"] >= 50:
            actionable_count += 1
        sums["act"] += sv["actionability"]
        sums["urg"] += sv["disease_urgency"]
        sums["qa"]  += sv["qa_confidence"]
        sums["gno"] += sv["gnomad_score"]
        sums["cli"] += sv["clinvar_score"]

    n = len(scored)
    scored.sort(key=lambda x: x["composite_score"], reverse=True)

    # Case-level composite (top variant 50% + average 30% + actionable bonus 20%)
    top = scored[0]["composite_score"] if scored else 0
    avg = sum(s["composite_score"] for s in scored) / n
    case_score = min(100, int(top * 0.5 + avg * 0.3 + min(actionable_count * 5, 20)))

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
        "total_variants": n, "actionable_count": actionable_count,
        "pathogenic_count": pathogenic_count,
        "top_genes": list(genes_seen)[:10],
        "top_therapies": list(set(all_therapies))[:8],
        "flags": list(set(all_flags))[:15],
        "avg_actionability":  int(sums["act"] / n),
        "avg_disease_urgency": int(sums["urg"] / n),
        "avg_qa_confidence":  int(sums["qa"] / n),
        "avg_gnomad":         int(sums["gno"] / n),
        "avg_clinvar":        int(sums["cli"] / n),
        "scored_variants": scored,
    }


def rank_cases(cases_dict):
    """Rank multiple cases by urgency. cases_dict = {case_id: [variants]}"""
    results = [score_case(v, k) for k, v in cases_dict.items()]
    results.sort(key=lambda x: x["case_score"], reverse=True)
    return results


# ─── CSV Parsing ────────────────────────────────────────────────────────────

def parse_csv_to_cases(csv_text):
    """
    Parse a CSV string into cases dict. Expects columns like:
    Sample, Gene, HGVS, Consequence, ACMG, ABCD, ClinVar, gnomAD, ReadDepth, AF ...
    Groups rows by 'Sample' column (or treats all as one case).
    """
    reader = csv.DictReader(StringIO(csv_text))
    cases = {}
    for row in reader:
        # Determine sample/case id
        sample = (
            row.get("Sample") or row.get("sample") or row.get("SAMPLE")
            or row.get("Case") or row.get("case") or row.get("SampleID")
            or "Sample A"
        )
        cases.setdefault(sample, []).append(row)
    return cases


# ─── LLM Summary ───────────────────────────────────────────────────────────

def get_copilot_system_prompt():
    return """You are an expert Genomic Pathologist AI Co-Pilot integrated into the SOPHiA DDM™ platform.
Given scored variant data, generate a concise clinical triage summary.
Output EXACTLY this JSON (no markdown, no backticks):
{"summary_bullets":["bullet1","bullet2","bullet3","bullet4"],"recommended_action":"1-line action","estimated_review_time":"X min"}
Be extremely concise and clinical. Reference specific gene and drug names."""


def generate_case_summary_llm(scored_case, llm_provider=None, api_key=None):
    """Generate LLM-powered case summary."""
    prompt = f"""Case Score: {scored_case['case_score']}/100 ({scored_case['urgency_label']})
Variants: {scored_case['total_variants']} | Actionable: {scored_case['actionable_count']} | Pathogenic: {scored_case['pathogenic_count']}
Avg Metrics — Actionability:{scored_case['avg_actionability']} Urgency:{scored_case['avg_disease_urgency']} QA:{scored_case['avg_qa_confidence']} gnomAD:{scored_case['avg_gnomad']} ClinVar:{scored_case['avg_clinvar']}
Genes: {', '.join(scored_case['top_genes'][:5])}
Therapies: {', '.join(scored_case['top_therapies'][:5]) or 'None'}
Top 5 variants:
"""
    for v in scored_case["scored_variants"][:5]:
        prompt += f"  - {v['gene']} {v['hgvs']} | Composite:{v['composite_score']} Act:{v['actionability']} Urg:{v['disease_urgency']} QA:{v['qa_confidence']} ClinVar:{v['clinvar']}\n"

    gemini_key = api_key if llm_provider == "gemini" else os.environ.get("GEMINI_API_KEY")
    openai_key = api_key if llm_provider == "openai" else os.environ.get("OPENAI_API_KEY")
    anthropic_key = api_key if llm_provider == "anthropic" else os.environ.get("ANTHROPIC_API_KEY")

    for provider, key, fn in [
        ("gemini", gemini_key, _call_gemini),
        ("openai", openai_key, _call_openai),
        ("anthropic", anthropic_key, _call_anthropic),
    ]:
        if key and (not llm_provider or llm_provider == provider):
            try:
                return fn(key, prompt)
            except Exception as e:
                print(f"{provider} error: {e}")

    return _generate_fallback_summary(scored_case)


def _call_gemini(key, prompt):
    from google import genai
    from google.genai import types
    client = genai.Client(api_key=key)
    r = client.models.generate_content(
        model="gemini-2.5-flash", contents=prompt,
        config=types.GenerateContentConfig(system_instruction=get_copilot_system_prompt()))
    return _parse_json(r.text)

def _call_openai(key, prompt):
    import openai
    client = openai.OpenAI(api_key=key)
    r = client.chat.completions.create(model="gpt-4o", messages=[
        {"role": "system", "content": get_copilot_system_prompt()},
        {"role": "user", "content": prompt}])
    return _parse_json(r.choices[0].message.content)

def _call_anthropic(key, prompt):
    import anthropic
    client = anthropic.Anthropic(api_key=key)
    r = client.messages.create(model="claude-3-opus-20240229", max_tokens=500,
        system=get_copilot_system_prompt(), messages=[{"role": "user", "content": prompt}])
    return _parse_json(r.content[0].text)

def _parse_json(text):
    clean = text.strip()
    for prefix in ("```json", "```"):
        if clean.startswith(prefix):
            clean = clean[len(prefix):]
    if clean.endswith("```"):
        clean = clean[:-3]
    return json.loads(clean.strip())

def _generate_fallback_summary(scored_case):
    bullets = []
    bullets.append(f"{scored_case['total_variants']} variants — {scored_case['pathogenic_count']} pathogenic, {scored_case['actionable_count']} actionable.")
    ag = [v["gene"] for v in scored_case["scored_variants"] if v["actionability"] >= 50]
    bullets.append(f"Actionable genes: {', '.join(set(ag)[:4]) or 'None'}.")
    if scored_case["top_therapies"]:
        bullets.append(f"Consider: {', '.join(scored_case['top_therapies'][:3])}.")
    else:
        bullets.append("Standard-of-care per tumor site guidelines.")
    bullets.append("Molecular tumor board discussion recommended." if scored_case["case_score"] >= 50 else "Standard workflow. No urgent escalation.")
    return {
        "summary_bullets": bullets,
        "recommended_action": scored_case.get("urgency_label", "Review case"),
        "estimated_review_time": f"{max(5, scored_case['total_variants'] * 2)} min",
    }
