"""Command line interface for the synthetic forecast study."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .charts import write_chart
from .forecast import forecast, read_returns, write_csv, write_json


ROOT = Path(__file__).resolve().parents[2]


def run(data_path: Path, output_dir: Path) -> dict:
    returns = read_returns(data_path)
    rows, summary = forecast(returns)
    output_dir.mkdir(parents=True, exist_ok=True)
    write_csv(output_dir / "forecast_observations.csv", rows)
    write_json(output_dir / "forecast_summary.json", summary)
    figures = ROOT / "docs" / "images"
    sample = rows[:120]
    overview = [
        ("Realized squared return", [row["realized_squared_return"] for row in sample]),
        ("Rolling 20-day variance", [row["rolling_variance_forecast"] for row in sample]),
        ("Fixed training variance", [row["reference_variance_forecast"] for row in sample]),
    ]
    workflow = [
        ("Rolling 20-day QLIKE", [row["rolling_qlike"] for row in rows]),
        ("Fixed-reference QLIKE", [row["reference_qlike"] for row in rows]),
    ]
    window = 20
    for series_index, (name, values) in enumerate(workflow):
        workflow[series_index] = (
            name,
            [None] * (window - 1) + [
                sum(values[i - window + 1:i + 1]) / window
                for i in range(window - 1, len(values))
            ],
        )
    improvement = summary["paired_loss_comparison_rolling_vs_reference"]
    qlike = improvement["mean_qlike"]["relative_reduction_fraction"]
    mse = improvement["mean_squared_return_loss"]["relative_reduction_fraction"]
    roll_win = improvement["mean_qlike"]["rolling_better_fraction_of_days"]
    overview_note = (
        f"OOS {summary['out_of_sample_observations']} QLIKE REDUCTION "
        f"{qlike:.3f} MSE REDUCTION {mse:.3f} DAILY QLIKE WINS {roll_win:.3f}"
        if qlike is not None and mse is not None
        else f"OOS {summary['out_of_sample_observations']} LOSS IMPROVEMENT UNDEFINED"
    )
    write_chart(
        figures,
        "overview",
        "Out-of-sample daily variance proxy and forecasts",
        overview,
        "Test observation",
        "Daily variance",
        overview_note,
    )
    write_chart(
        figures,
        "workflow",
        "20-observation moving average of out-of-sample QLIKE",
        workflow,
        "Test observation",
        "Mean QLIKE (lower is better)",
        "LOSS REDUCTIONS ARE DESCRIPTIVE ON THIS SYNTHETIC HOLDOUT ONLY",
    )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare synthetic one-day variance forecasts.")
    parser.add_argument("--data", type=Path, default=ROOT / "data" / "synthetic_returns.csv")
    parser.add_argument("--output", type=Path, default=ROOT / "reports")
    args = parser.parse_args()
    print(json.dumps(run(args.data, args.output), indent=2))


if __name__ == "__main__":
    main()
