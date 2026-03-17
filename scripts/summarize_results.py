from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path
from statistics import mean
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


METRICS = [
    "mean_Psi_t",
    "maximal_contamination_excursion",
    "contradiction_reserve",
    "false_core_admission_rate",
    "protected_query_accuracy",
    "protected_query_recall",
    "low_reserve_residence_time",
    "realized_fork_count",
    "contaminated_items_admitted",
    "broker_concentration",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Summarize SEC PoC CSV results.")
    parser.add_argument("--metrics-csv", default="results/metrics.csv")
    parser.add_argument("--output", default="results/summary.json")
    return parser.parse_args()


def latest_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    by_run: dict[str, dict[str, str]] = {}
    for row in rows:
        run_id = row.get("run_uid") or row["run_id"]
        if run_id not in by_run or int(row["step"]) >= int(by_run[run_id]["step"]):
            by_run[run_id] = row
    return list(by_run.values())


def main() -> None:
    args = parse_args()
    with Path(args.metrics_csv).open("r", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    grouped: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    for row in latest_rows(rows):
        for metric in METRICS:
            grouped[row["condition"]][metric].append(float(row[metric]))
    summary = {
        condition: {metric: mean(values) if values else 0.0 for metric, values in metrics.items()}
        for condition, metrics in grouped.items()
    }
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
