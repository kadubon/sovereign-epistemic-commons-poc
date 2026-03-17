from __future__ import annotations

import csv
from collections import defaultdict
from pathlib import Path
from statistics import mean
from typing import Any

import matplotlib.pyplot as plt


FIGURE_SPECS = [
    ("maximal_contamination_excursion", "Contamination Excursion Comparison", "contamination_excursion.png"),
    ("contradiction_reserve", "Contradiction Reserve Comparison", "contradiction_reserve.png"),
    ("false_core_admission_rate", "False Core Admission Comparison", "false_core_admission.png"),
    ("low_reserve_residence_time", "Low-Reserve Residence Time", "low_reserve_residence.png"),
    ("realized_fork_count", "Fork Count Comparison", "fork_count.png"),
    ("protected_query_accuracy", "Protected Query Accuracy", "accuracy.png"),
    ("protected_query_recall", "Protected Query Recall", "recall.png"),
]


def read_metrics_csv(path: str | Path) -> list[dict[str, Any]]:
    with Path(path).open("r", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def latest_rows_per_run(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_run: dict[str, dict[str, Any]] = {}
    for row in rows:
        run_id = row.get("run_uid") or row["run_id"]
        current_step = int(row["step"])
        if run_id not in by_run or current_step >= int(by_run[run_id]["step"]):
            by_run[run_id] = row
    return list(by_run.values())


def aggregate_by_condition(rows: list[dict[str, Any]], metric_name: str) -> tuple[list[str], list[float]]:
    grouped: dict[str, list[float]] = defaultdict(list)
    for row in latest_rows_per_run(rows):
        grouped[row["condition"]].append(float(row[metric_name]))
    labels = sorted(grouped)
    values = [mean(grouped[label]) if grouped[label] else 0.0 for label in labels]
    return labels, values


def make_all_figures(metrics_csv: str | Path, output_dir: str | Path) -> list[str]:
    rows = read_metrics_csv(metrics_csv)
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    saved_paths: list[str] = []
    for metric_name, title, filename in FIGURE_SPECS:
        labels, values = aggregate_by_condition(rows, metric_name)
        plt.figure(figsize=(8, 4.5))
        plt.bar(labels, values, color=["#2f5d62", "#5e8b7e", "#a7c4bc", "#dfd8ca"][: len(labels)])
        plt.title(title)
        plt.ylabel(metric_name)
        plt.tight_layout()
        file_path = output_path / filename
        plt.savefig(file_path, dpi=160)
        plt.close()
        saved_paths.append(str(file_path))
    return saved_paths
