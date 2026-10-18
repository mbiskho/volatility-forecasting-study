"""Fixed-seed generator for the included synthetic returns."""

from __future__ import annotations

import csv
import json
import random
from datetime import date, timedelta
from pathlib import Path


def generate(directory: Path, seed: int = 8831, observations: int = 900) -> None:
    rng = random.Random(seed)
    segments = [(180, 0.007), (180, 0.022), (180, 0.010), (180, 0.028), (180, 0.009)]
    values = [rng.gauss(0, volatility) for length, volatility in segments for _ in range(length)][:observations]
    directory.mkdir(parents=True, exist_ok=True)
    rows = []
    day = date(2020, 1, 1)
    for value in values:
        while day.weekday() >= 5:
            day += timedelta(days=1)
        rows.append((day.isoformat(), f"{value:.10f}"))
        day += timedelta(days=1)
    with (directory / "synthetic_returns.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        writer.writerow(["date", "return"])
        writer.writerows(rows)
    metadata = {
        "dataset": "synthetic_returns.csv",
        "observations": len(rows),
        "seed": seed,
        "return_model": "Independent zero-mean Gaussian daily simple returns within fixed-volatility blocks",
        "segments": [
            {"observations": length, "daily_standard_deviation": volatility}
            for length, volatility in segments
        ],
        "limitations": "Artificial volatility blocks; no real market observations or estimated parameters. Gaussian tails and abrupt changes are simplifications.",
    }
    (directory / "dataset_metadata.json").write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    generate(Path(__file__).resolve().parents[2] / "data")
