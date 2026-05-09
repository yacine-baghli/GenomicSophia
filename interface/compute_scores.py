import argparse
from pathlib import Path

import pandas as pd


def normalize_to_100(series: pd.Series) -> pd.Series:
    min_val = series.min()
    max_val = series.max()
    if pd.isna(min_val) or pd.isna(max_val) or min_val == max_val:
        return pd.Series([0] * len(series), index=series.index)
    return ((series - min_val) / (max_val - min_val) * 100).round(1)


def score_one_csv(input_csv: Path) -> dict:
    df = pd.read_csv(input_csv)

    # Disease urgency from the 2nd column values (A highest -> D lowest),
    # then aggregated as one score for the whole CSV.
    urgency_map = {"A": 100, "B": 20, "C": 20, "D": 0}
    second_col = df.columns[1]
    urgency_per_row = df[second_col].astype(str).str.strip().str.upper().map(urgency_map).fillna(0)
    disease_urgency_score = round(float(urgency_per_row.sum()), 1)

    # Placeholder requested by user (numeric so it can be combined).
    actionability_score = 50.0

    # QA confidence from read depth, aggregated as one dataset score.
    read_depth = pd.to_numeric(df.get("Read depth"), errors="coerce").fillna(0)
    qa_per_row = normalize_to_100(read_depth)
    qa_confidence_score = round(float(qa_per_row.mean()), 1)

    overall_score = round((disease_urgency_score + actionability_score + qa_confidence_score) / 3, 1)

    return {
        "file": input_csv.name,
        "Rows analyzed": len(df),
        "Disease urgency score": disease_urgency_score,
        "Actionability score (placeholder)": actionability_score,
        "QA confidence score": qa_confidence_score,
        "Overall CSV score": overall_score,
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
