import math
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

from volatility_forecasting.cli import run
from volatility_forecasting.forecast import forecast, read_returns


def fixture_returns(count=360):
    values = []
    day = date(2020, 1, 1)
    for i in range(count):
        while day.weekday() >= 5:
            day += timedelta(days=1)
        value = (0.012 if i < 180 else 0.025) * (1 if i % 2 else -1)
        values.append({"date": day.isoformat(), "return": value})
        day += timedelta(days=1)
    return values


class ForecastStudyTests(unittest.TestCase):
    def test_forecasts_are_one_step_lagged_and_metrics_finite(self):
        data = fixture_returns()
        rows, summary = forecast(data, calibration_size=100, rolling_window=20)
        self.assertEqual(len(rows), len(data) - 100)
        self.assertAlmostEqual(rows[0]["rolling_variance_forecast"], 0.012 ** 2 * (20 / 19), places=8)
        self.assertAlmostEqual(rows[0]["reference_annualized_volatility"], math.sqrt(rows[0]["reference_variance_forecast"] * 252))
        for metric in summary["metrics"].values():
            self.assertTrue(math.isfinite(metric["mean_qlike"]))
            self.assertTrue(math.isfinite(metric["mean_squared_return_loss"]))
            self.assertIn("forecast_bias_vs_squared_return", metric)
        self.assertIn("paired_loss_comparison_rolling_vs_reference", summary)

    def test_rejects_missing_out_of_sample(self):
        with self.assertRaises(ValueError):
            forecast(fixture_returns(40), calibration_size=40)

    def test_csv_validation(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "returns.csv"
            path.write_text("date,return\n2024-01-01,nan\n2024-01-02,0.1\n", encoding="utf-8")
            with self.assertRaises(ValueError):
                read_returns(path)

    def test_cli_outputs_metrics_and_figures(self):
        root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as temp:
            result = run(root / "data" / "synthetic_returns.csv", Path(temp) / "out")
            self.assertEqual(result["out_of_sample_observations"], 650)
            self.assertIn("rolling", result["metrics"])
            self.assertTrue((root / "docs" / "images" / "workflow.svg").exists())
            self.assertTrue((Path(temp) / "out" / "forecast_observations.csv").exists())


if __name__ == "__main__":
    unittest.main()
