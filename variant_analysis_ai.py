import argparse
import json
import os
from pathlib import Path

import anthropic
import pandas as pd


def format_variant_for_analysis(row: dict) -> str:
    """Format a single variant row for Claude analysis."""
    gene = row.get("gene", "Unknown")
    prediction = row.get("SOPHiA DDM™ prediction", "")
    clingen = row.get("clingen", "")
    clinvar_sig = row.get("clinvar_significance", "")
    consequence = row.get("Coding consequence", "")
    hgvs = row.get("DNA HGVS", "")
    vaf = row.get("VAF(%)", "")
    
    return f"Gene: {gene} | Prediction: {prediction} | ClinGen: {clingen} | ClinVar: {clinvar_sig} | Consequence: {consequence} | HGVS: {hgvs} | VAF: {vaf}"


def get_ai_variant_analysis(csv_path: Path) -> dict:
    """Use Claude API to analyze variants and provide importance score and summary."""
    
    df = pd.read_csv(csv_path)
    
    if len(df) == 0:
        return {
            "file": csv_path.name,
            "Rows analyzed": 0,
            "AI Importance Score": 0.0,
            "Variant Summary": "No variants found",
        }
    
    # Select top variants: prioritize high-confidence predictions (A, B) and pathogenic variants
    second_col = df.columns[1]  # SOPHiA DDM™ prediction column
    df_sorted = df.copy()
    df_sorted["pred"] = df_sorted[second_col].astype(str).str.strip().str.upper()
    df_sorted["is_ab"] = df_sorted["pred"].isin({"A", "B"})
    df_sorted["is_pathogenic"] = df_sorted.get("clinvar_significance", "").astype(str).str.contains("Pathogenic|Likely", case=False, na=False)
    
    # Score variants for selection: A/B predictions get priority, then pathogenic variants
    df_sorted["selection_score"] = (
        df_sorted["is_ab"].astype(int) * 2 +
        df_sorted["is_pathogenic"].astype(int) * 1
    )
    
    df_sorted = df_sorted.sort_values("selection_score", ascending=False)
    
    # Take top 5-10 variants for analysis
    top_count = min(10, len(df_sorted))
    top_variants = df_sorted.head(top_count)
    
    # Format variants for Claude
    variant_texts = [format_variant_for_analysis(row) for _, row in top_variants.iterrows()]
    variants_str = "\n".join(variant_texts)
    
    # Build prompt for Claude
    prompt = f"""Analyze these genetic variants from a patient sample. The file contains {len(df)} total variants.

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
    
    # Call Claude API
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError(
            "ANTHROPIC_API_KEY environment variable not set. "
            "Please set it before running this script: export ANTHROPIC_API_KEY=your_key"
        )
    
    client = anthropic.Anthropic(api_key=api_key)
    
    message = client.messages.create(
        model="claude-opus-4-1-20250805",
        max_tokens=500,
        messages=[
            {"role": "user", "content": prompt}
        ]
    )
    
    response_text = message.content[0].text
    
    # Parse JSON response
    try:
        # Extract JSON from response (in case Claude adds extra text)
        json_start = response_text.find("{")
        json_end = response_text.rfind("}") + 1
        if json_start != -1 and json_end > json_start:
            json_str = response_text[json_start:json_end]
            result = json.loads(json_str)
            importance_score = float(result.get("importance_score", 50.0))
            summary = result.get("summary", "Analysis complete")
        else:
            importance_score = 50.0
            summary = response_text[:200]
    except (json.JSONDecodeError, ValueError):
        importance_score = 50.0
        summary = response_text[:200]
    
    return {
        "file": csv_path.name,
        "Rows analyzed": len(df),
        "AI Importance Score": round(importance_score, 1),
        "Variant Summary": summary,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Use Claude API to analyze variants and provide importance scores."
    )
    parser.add_argument(
        "csv_files",
        nargs="+",
        help="CSV paths to analyze.",
    )
    parser.add_argument(
        "--output",
        default="ai_analysis.csv",
        help="Output summary CSV path (default: ai_analysis.csv).",
    )
    args = parser.parse_args()

    input_csvs = [Path(path) for path in args.csv_files]
    
    if len(input_csvs) > 10:
        raise ValueError("A maximum of 10 CSV files is supported per run.")

    print("Analyzing variants with Claude API...")
    results = []
    for i, csv_path in enumerate(input_csvs, 1):
        print(f"  [{i}/{len(input_csvs)}] {csv_path.name}...", end=" ", flush=True)
        result = get_ai_variant_analysis(csv_path)
        results.append(result)
        print("Done")

    summary = pd.DataFrame(results)
    output_csv = Path(args.output)
    summary.to_csv(output_csv, index=False)

    print(f"\nSaved: {output_csv.resolve()}")
    print("\nAI Analysis Results:")
    print(summary.to_string(index=False))


if __name__ == "__main__":
    main()
