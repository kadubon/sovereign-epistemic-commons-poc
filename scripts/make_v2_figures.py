from __future__ import annotations

import argparse
from collections import defaultdict
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import matplotlib.pyplot as plt

from sec_poc.v2_analysis import latest_rows, read_csv_rows, safe_float


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate v2 figures.")
    parser.add_argument("--metrics-csv", required=True)
    parser.add_argument("--output-dir", required=True)
    return parser.parse_args()


def grouped_means(rows: list[dict[str, str]], *, world: str, conditions: list[str], metric: str) -> tuple[list[str], list[float]]:
    latest = [
        row for row in latest_rows(rows)
        if row["world"] == world and row["condition"] in conditions and row["analysis_group"] == "confirmatory"
    ]
    grouped: dict[str, list[float]] = defaultdict(list)
    for row in latest:
        value = safe_float(row.get(metric))
        if value is not None:
            grouped[row["condition"]].append(value)
    labels = conditions
    values = [
        sum(grouped.get(label, [])) / len(grouped.get(label, [])) if grouped.get(label) else 0.0
        for label in labels
    ]
    return labels, values


def tradeoff_means(rows: list[dict[str, str]], metric: str) -> tuple[list[str], list[float]]:
    latest = [row for row in latest_rows(rows) if row["analysis_group"] == "tradeoff"]
    grouped: dict[str, list[float]] = defaultdict(list)
    for row in latest:
        label = row["condition"].replace("ablation_depth_discount_", "")
        value = safe_float(row.get(metric))
        if value is not None:
            grouped[label].append(value)
    labels = ["none", "mild", "strong"]
    values = [sum(grouped.get(label, [])) / len(grouped.get(label, [])) if grouped.get(label) else 0.0 for label in labels]
    return labels, values


def save_bar(path: Path, title: str, ylabel: str, labels: list[str], values: list[float]) -> None:
    plt.figure(figsize=(8, 4.5))
    plt.bar(labels, values, color=["#30475e", "#5c7c8a", "#8eaebd", "#d2d2d2"][: len(labels)])
    plt.title(title)
    plt.ylabel(ylabel)
    plt.tight_layout()
    plt.savefig(path, dpi=160)
    plt.close()


def save_tradeoff_scatter(path: Path, rows: list[dict[str, str]]) -> None:
    latest = [row for row in latest_rows(rows) if row["analysis_group"] == "tradeoff"]
    x = []
    y = []
    labels = []
    for label in ["none", "mild", "strong"]:
        subset = [row for row in latest if row["condition"].endswith(label)]
        if not subset:
            continue
        mean_excursion = sum(safe_float(row["max_positive_excursion"]) for row in subset) / len(subset)
        mean_reserve = sum(safe_float(row["contradiction_reserve"]) for row in subset) / len(subset)
        x.append(mean_excursion)
        y.append(mean_reserve)
        labels.append(label)
    plt.figure(figsize=(6, 5))
    plt.scatter(x, y, color="#30475e")
    for xi, yi, label in zip(x, y, labels, strict=True):
        plt.annotate(label, (xi, yi))
    plt.xlabel("max_positive_excursion")
    plt.ylabel("contradiction_reserve")
    plt.title("Contamination vs Reserve Tradeoff")
    plt.tight_layout()
    plt.savefig(path, dpi=160)
    plt.close()


def main() -> None:
    args = parse_args()
    rows = read_csv_rows(args.metrics_csv)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    save_bar(
        output_dir / "h2_false_core_default_confirmatory.png",
        "H2 False Core Admission",
        "false_core_admission_rate",
        *grouped_means(rows, world="default_confirmatory", conditions=["baseline", "lanes_only"], metric="false_core_admission_rate"),
    )
    save_bar(
        output_dir / "h2_accuracy_default_confirmatory.png",
        "H2 Accuracy",
        "protected_query_accuracy",
        *grouped_means(rows, world="default_confirmatory", conditions=["baseline", "lanes_only"], metric="protected_query_accuracy"),
    )
    save_bar(
        output_dir / "h2_recall_default_confirmatory.png",
        "H2 Recall",
        "protected_query_recall",
        *grouped_means(rows, world="default_confirmatory", conditions=["baseline", "lanes_only"], metric="protected_query_recall"),
    )
    save_bar(
        output_dir / "h2_contradiction_reserve_default_confirmatory.png",
        "H2 Contradiction Reserve",
        "contradiction_reserve",
        *grouped_means(rows, world="default_confirmatory", conditions=["baseline", "lanes_only"], metric="contradiction_reserve"),
    )
    save_bar(
        output_dir / "h1_mean_psi_tradeoff.png",
        "H1 Tradeoff: mean_psi",
        "mean_psi",
        *tradeoff_means(rows, metric="mean_psi"),
    )
    save_bar(
        output_dir / "h1_max_positive_excursion_tradeoff.png",
        "H1 Tradeoff: max_positive_excursion",
        "max_positive_excursion",
        *tradeoff_means(rows, metric="max_positive_excursion"),
    )
    save_bar(
        output_dir / "h1_contradiction_reserve_tradeoff.png",
        "H1 Tradeoff: contradiction_reserve",
        "contradiction_reserve",
        *tradeoff_means(rows, metric="contradiction_reserve"),
    )
    save_bar(
        output_dir / "h1_accuracy_tradeoff.png",
        "H1 Tradeoff: accuracy",
        "protected_query_accuracy",
        *tradeoff_means(rows, metric="protected_query_accuracy"),
    )
    save_bar(
        output_dir / "h1_recall_tradeoff.png",
        "H1 Tradeoff: recall",
        "protected_query_recall",
        *tradeoff_means(rows, metric="protected_query_recall"),
    )
    save_tradeoff_scatter(output_dir / "h1_tradeoff_contamination_vs_reserve.png", rows)
    save_bar(
        output_dir / "h3_low_reserve_fork_stress.png",
        "H3 Low-Reserve Residence",
        "low_reserve_residence_time",
        *grouped_means(rows, world="fork_stress", conditions=["lanes_discount", "full_sec_lite"], metric="low_reserve_residence_time"),
    )
    save_bar(
        output_dir / "h3_fork_count_fork_stress.png",
        "H3 Realized Fork Count",
        "realized_fork_count",
        *grouped_means(rows, world="fork_stress", conditions=["lanes_discount", "full_sec_lite"], metric="realized_fork_count"),
    )
    save_bar(
        output_dir / "h3_recovery_fork_stress.png",
        "H3 Post-Fork Recovery Quality",
        "post_fork_recovery_quality",
        *grouped_means(rows, world="fork_stress", conditions=["lanes_discount", "full_sec_lite"], metric="post_fork_recovery_quality"),
    )
    save_bar(
        output_dir / "structure_lane_occupancy_core_default_confirmatory.png",
        "Lane Occupancy: Core",
        "lane_occupancy_ratios.core",
        *grouped_means(rows, world="default_confirmatory", conditions=["baseline", "lanes_only", "lanes_discount", "full_sec_lite"], metric="lane_occupancy_ratios.core"),
    )


if __name__ == "__main__":
    main()

