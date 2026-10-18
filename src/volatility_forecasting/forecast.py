"""One-step variance forecasts and strictly out-of-sample loss evaluation."""

from __future__ import annotations

import csv
import json
import math
from pathlib import Path
from statistics import mean, variance
from typing import Any


ROLLING_WINDOW = 20
CALIBRATION_SIZE = 250
ANNUALIZATION_DAYS = 252
VARIANCE_FLOOR = 1e-12


def read_returns(path: str | Path) -> list[dict[str, Any]]:
    with Path(path).open(newline="", encoding="utf-8") as stream:
        rows = [
            {"date": row["date"], "return": float(row["return"])}
            for row in csv.DictReader(stream)
        ]
    if any(not math.isfinite(row["return"]) for row in rows):
        raise ValueError("Returns must be finite numbers")
    if any(a["date"] >= b["date"] for a, b in zip(rows, rows[1:])):
        raise ValueError("Dates must be strictly increasing")
    return rows


def _correlation(left: list[float], right: list[float]) -> float | None:
    if len(left) < 2:
        return None
    mean_left, mean_right = mean(left), mean(right)
    centered_left = [value - mean_left for value in left]
    centered_right = [value - mean_right for value in right]
    denominator = math.sqrt(
        sum(value * value for value in centered_left)
        * sum(value * value for value in centered_right)
    )
    return (
        sum(a * b for a, b in zip(centered_left, centered_right)) / denominator
        if denominator
        else None
    )


def forecast(returns: list[dict[str, Any]], calibration_size: int = CALIBRATION_SIZE,
             rolling_window: int = ROLLING_WINDOW) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Compare lagged rolling variance with a fixed training-sample variance."""
    if calibration_size < 2 or rolling_window < 2:
        raise ValueError("Calibration size and rolling window must both be at least 2")
    if len(returns) <= calibration_size:
        raise ValueError("Need at least one observation beyond the calibration period")
    if len(returns) < rolling_window:
        raise ValueError("Not enough returns for the rolling window")
    values = [row["return"] for row in returns]
    reference_variance = max(variance(values[:calibration_size]), VARIANCE_FLOOR)
    rows: list[dict[str, Any]] = []
    for index in range(calibration_size, len(returns)):
        rolling_variance = max(variance(values[index - rolling_window:index]), VARIANCE_FLOOR)
        realized_squared_return = values[index] ** 2
        rows.append({
            "date": returns[index]["date"],
            "return": values[index],
            "realized_squared_return": realized_squared_return,
            "rolling_variance_forecast": rolling_variance,
            "reference_variance_forecast": reference_variance,
            "rolling_annualized_volatility": math.sqrt(rolling_variance * ANNUALIZATION_DAYS),
            "reference_annualized_volatility": math.sqrt(reference_variance * ANNUALIZATION_DAYS),
            "rolling_squared_error": (realized_squared_return - rolling_variance) ** 2,
            "reference_squared_error": (realized_squared_return - reference_variance) ** 2,
            "rolling_qlike": math.log(rolling_variance) + realized_squared_return / rolling_variance,
            "reference_qlike": math.log(reference_variance) + realized_squared_return / reference_variance,
        })
    metrics = {}
    for method in ("rolling", "reference"):
        forecasts = [row[f"{method}_variance_forecast"] for row in rows]
        losses = [row[f"{method}_squared_error"] for row in rows]
        metrics[method] = {
            "mean_squared_return_loss": mean(losses),
            "mean_qlike": mean(row[f"{method}_qlike"] for row in rows),
            "mean_annualized_volatility": mean(row[f"{method}_annualized_volatility"] for row in rows),
            "forecast_bias_vs_squared_return": mean(
                forecast_value - row["realized_squared_return"]
                for forecast_value, row in zip(forecasts, rows)
            ),
            "correlation_with_squared_return": _correlation(
                forecasts, [row["realized_squared_return"] for row in rows]
            ),
            "fraction_of_days_squared_return_below_forecast": mean(
                float(row["realized_squared_return"] <= forecast_value)
                for forecast_value, row in zip(forecasts, rows)
            ),
        }
    loss_improvement = {}
    for key in ("mean_squared_return_loss", "mean_qlike"):
        rolling_loss = metrics["rolling"][key]
        reference_loss = metrics["reference"][key]
        loss_improvement[key] = {
            "absolute_reduction": reference_loss - rolling_loss,
            "relative_reduction_fraction": (
                (reference_loss - rolling_loss) / abs(reference_loss)
                if reference_loss
                else None
            ),
            "rolling_better_fraction_of_days": mean(
                float(row[f"rolling_{'squared_error' if key == 'mean_squared_return_loss' else 'qlike'}"]
                      < row[f"reference_{'squared_error' if key == 'mean_squared_return_loss' else 'qlike'}"])
                for row in rows
            ),
        }
    summary = {
        "calibration_observations": calibration_size,
        "out_of_sample_observations": len(rows),
        "rolling_window_observations": rolling_window,
        "forecast_horizon": "one trading day",
        "loss_target": "squared daily return as a noisy proxy for latent daily variance",
        "losses": {
            "squared_return_loss": "mean((r_t^2 - h_t)^2)",
            "qlike": "mean(log(h_t) + r_t^2 / h_t); lower is better",
        },
        "annualization": f"Annualized volatility = sqrt(daily variance * {ANNUALIZATION_DAYS}); loss values use daily units.",
        "variance_floor": VARIANCE_FLOOR,
        "metrics": metrics,
        "paired_loss_comparison_rolling_vs_reference": loss_improvement,
        "interpretation": (
            "Synthetic out-of-sample benchmark comparison only. Squared returns are noisy "
            "variance proxies; no claim of forecasting skill on real markets."
        ),
    }
    return rows, summary


def write_csv(path: str | Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        raise ValueError("Cannot write an empty forecast result")
    with Path(path).open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def write_json(path: str | Path, data: dict[str, Any]) -> None:
    Path(path).write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
