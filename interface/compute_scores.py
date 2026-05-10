import argparse
from pathlib import Path

import pandas as pd


def normalize_to_100(series: pd.Series) -> pd.Series:
    min_val = series.min()
    max_val = series.max()
    if pd.isna(min_val) or pd.isna(max_val) or min_val == max_val:
        return pd.Series([0] * len(series), index=series.index)
    return ((series - min_val) / (max_val - min_val) * 100).round(1)


def rarity_from_frequency(freq: pd.Series) -> pd.Series:
    """Lower community frequency => higher rarity (0–100). Same as normalize_to_100 but inverted."""
    min_val = freq.min()
    max_val = freq.max()
    if pd.isna(min_val) or pd.isna(max_val) or min_val == max_val:
        return pd.Series([50.0] * len(freq), index=freq.index)
    scaled = (max_val - freq) / (max_val - min_val) * 100
    return scaled.round(1)


def soft_clip_disease_urgency(raw_score: float) -> float:
    """Soft clipping so only very extreme cases reach 100."""
    k = 125.0  # Tuned so that at ~500, score is ~80
    return round(100 * (raw_score / (raw_score + k)), 1)


def score_one_csv(input_csv: Path) -> dict:
    df = pd.read_csv(input_csv)

    # Disease urgency from the 2nd column values (A highest -> D lowest),
    # then aggregated as one score for the whole CSV.
    urgency_map = {"A": 10, "B": 3, "C": 2, "D": 0}
    second_col = df.columns[1]
    urgency_per_row = df[second_col].astype(str).str.strip().str.upper().map(urgency_map).fillna(0)
    raw_disease_sum = float(urgency_per_row.sum())
    disease_urgency_score = soft_clip_disease_urgency(raw_disease_sum)

    # Rarity: Community frequency inverted, only variants with prediction A or B.
    second_vals = df[second_col].astype(str).str.strip().str.upper()
    ab_mask = second_vals.isin({"A", "B"})
    comm_col = "Community frequency"
    freq_raw = pd.to_numeric(df.loc[ab_mask, comm_col], errors="coerce")
    freq_valid = freq_raw.dropna()
    if freq_valid.empty:
        rarity_score = 0.0
    else:
        rarity_row = rarity_from_frequency(freq_valid)
        rarity_score = round(float(rarity_row.mean()), 1)

    # QA confidence from read depth, aggregated as one dataset score.
    read_depth = pd.to_numeric(df.get("Read depth"), errors="coerce").fillna(0)
    qa_per_row = normalize_to_100(read_depth)
    qa_confidence_score = round(float(qa_per_row.mean()), 1)

    overall_score = round((disease_urgency_score + rarity_score + qa_confidence_score) / 3, 1)

    return {
        "file": input_csv.name,
        "Rows analyzed": len(df),
        "Disease urgency score": disease_urgency_score,
        "Rarity score (A/B community freq)": rarity_score,
        "QA confidence score": qa_confidence_score,
        "Overall patient score": overall_score,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Compute one global score per CSV (up to 10 files).")
    parser.add_argument(
        "csv_files",
        nargs="*",
        help="CSV paths to score. If omitted, uses extracted_table.csv.",
    )
    parser.add_argument(
        "--output",
        default="dataset_scores.csv",
        help="Output summary CSV path (default: dataset_scores.csv).",
    )
    args = parser.parse_args()

    input_csvs = [Path(path) for path in args.csv_files] if args.csv_files else [Path("extracted_table.csv")]

    if len(input_csvs) > 10:
        raise ValueError("A maximum of 10 CSV files is supported per run.")

    results = [score_one_csv(path) for path in input_csvs]
    summary = pd.DataFrame(results)
    output_csv = Path(args.output)
    summary.to_csv(output_csv, index=False)

    print(f"Saved: {output_csv.resolve()}")
    print("\nGlobal scores:")
    print(summary.to_string(index=False))


if __name__ == "__main__":
    main()
