from __future__ import annotations

import argparse
from collections import defaultdict
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sec_poc.v2_analysis import (
    group_latest_rows,
    latest_rows,
    paired_differences,
    read_csv_rows,
    safe_float,
    summarize_metric,
    write_markdown,
)


METRICS = [
    "mean_psi",
    "max_psi_observed",
    "max_positive_excursion",
    "contaminated_items_admitted",
    "contradiction_reserve",
    "false_core_admission_rate",
    "protected_query_accuracy",
    "protected_query_recall",
    "low_reserve_residence_time",
    "realized_fork_count",
    "post_fork_recovery_quality",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Summarize v2 experiment outputs.")
    parser.add_argument("--metrics-csv", required=True)
    parser.add_argument("--output-md", required=True)
    return parser.parse_args()


def render_summary(rows: list[dict[str, str]]) -> str:
    grouped = group_latest_rows(rows, ["analysis_group", "world", "condition"])
    lines = [
        "# V2 Summary",
        "",
        "This file is an auto-generated descriptive summary of existing results.",
        "Scripted runs are the primary evidence in this repository. Auxiliary Gemma runs are backend sanity checks only.",
        "Where present, `run_uid` is the canonical globally unique run identifier; `run_id` is a legacy short identifier retained for compatibility.",
        "",
    ]
    for (analysis_group, world, condition), group_rows in sorted(grouped.items()):
        lines.append(f"## {analysis_group} / {world} / {condition}")
        lines.append("")
        lines.append("| metric | mean | std | 95% bootstrap CI | n |")
        lines.append("| --- | ---: | ---: | ---: | ---: |")
        for metric in METRICS:
            values = [safe_float(row.get(metric)) for row in group_rows]
            summary = summarize_metric(values, seed=17)
            mean_value = "NA" if summary["mean"] is None else f"{summary['mean']:.3f}"
            std_value = "NA" if summary["std"] is None else f"{summary['std']:.3f}"
            ci_value = (
                "NA"
                if summary["ci_low"] is None
                else f"[{summary['ci_low']:.3f}, {summary['ci_high']:.3f}]"
            )
            lines.append(f"| `{metric}` | {mean_value} | {std_value} | {ci_value} | {summary['n']} |")
        lines.append("")

    lines.append("## Paired Effect Summaries")
    lines.append("")
    effect_specs = [
        ("contamination_stress", "lanes_only", "lanes_discount", "mean_psi", "H1 mean_psi"),
        ("contamination_stress", "lanes_only", "lanes_discount", "max_positive_excursion", "H1 max_positive_excursion"),
        ("default_confirmatory", "baseline", "lanes_only", "false_core_admission_rate", "H2 false_core"),
        ("default_confirmatory", "baseline", "lanes_only", "protected_query_accuracy", "H2 accuracy"),
        ("fork_stress", "lanes_discount", "full_sec_lite", "low_reserve_residence_time", "H3 low_reserve"),
        ("fork_stress", "lanes_discount", "full_sec_lite", "realized_fork_count", "H3 fork_count"),
        ("fork_stress", "lanes_discount", "full_sec_lite", "post_fork_recovery_quality", "H3 recovery"),
    ]
    lines.append("| label | matched seeds | mean difference (right-left) |")
    lines.append("| --- | ---: | ---: |")
    for world, left, right, metric, label in effect_specs:
        diffs = paired_differences(rows, world=world, left_condition=left, right_condition=right, metric=metric)
        mean_diff = "NA" if not diffs else f"{sum(diffs) / len(diffs):.3f}"
        lines.append(f"| {label} | {len(diffs)} | {mean_diff} |")
    lines.append("")

    latest_aux = [row for row in latest_rows(rows) if row["analysis_group"] == "aux_llm"]
    if latest_aux:
        by_backend: dict[str, list[dict[str, str]]] = defaultdict(list)
        for row in latest_aux:
            by_backend[row["backend"]].append(row)
        lines.append("## Auxiliary Backend Checks")
        lines.append("")
        lines.append("| backend | runs | mean accuracy | mean recall |")
        lines.append("| --- | ---: | ---: | ---: |")
        for backend, backend_rows in sorted(by_backend.items()):
            acc = summarize_metric([safe_float(row["protected_query_accuracy"]) for row in backend_rows])
            rec = summarize_metric([safe_float(row["protected_query_recall"]) for row in backend_rows])
            lines.append(f"| `{backend}` | {len(backend_rows)} | {acc['mean']:.3f} | {rec['mean']:.3f} |")
        lines.append("")

    return "\n".join(lines)


def main() -> None:
    args = parse_args()
    rows = read_csv_rows(args.metrics_csv)
    write_markdown(args.output_md, render_summary(rows))


if __name__ == "__main__":
    main()
