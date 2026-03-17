from __future__ import annotations

import csv
import math
import random
from collections import defaultdict
from pathlib import Path
from statistics import mean, pstdev
from typing import Any


def read_csv_rows(path: str | Path) -> list[dict[str, str]]:
    with Path(path).open("r", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def canonical_run_key(row: dict[str, str]) -> str:
    return row.get("run_uid") or f"{row.get('world', 'legacy')}__{row['run_id']}"


def latest_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    by_key: dict[str, dict[str, str]] = {}
    for row in rows:
        key = canonical_run_key(row)
        step = int(row["step"])
        if key not in by_key or step >= int(by_key[key]["step"]):
            by_key[key] = row
    return list(by_key.values())


def safe_float(value: str | float | int | None) -> float | None:
    if value is None:
        return None
    if isinstance(value, (float, int)):
        if isinstance(value, float) and math.isnan(value):
            return None
        return float(value)
    stripped = str(value).strip()
    if stripped == "" or stripped.lower() in {"na", "none", "null"}:
        return None
    try:
        return float(stripped)
    except ValueError:
        return None


def bootstrap_mean_ci(values: list[float], *, seed: int = 0, draws: int = 500) -> tuple[float, float]:
    if not values:
        return (0.0, 0.0)
    rng = random.Random(seed)
    samples = []
    for _ in range(draws):
        bootstrap_sample = [values[rng.randrange(len(values))] for _ in range(len(values))]
        samples.append(mean(bootstrap_sample))
    samples.sort()
    lo_index = int(0.025 * (len(samples) - 1))
    hi_index = int(0.975 * (len(samples) - 1))
    return samples[lo_index], samples[hi_index]


def summarize_metric(values: list[float | None], *, seed: int = 0) -> dict[str, Any]:
    clean = [value for value in values if value is not None]
    if not clean:
        return {"n": 0, "mean": None, "std": None, "ci_low": None, "ci_high": None}
    ci_low, ci_high = bootstrap_mean_ci(clean, seed=seed)
    std = 0.0 if len(clean) == 1 else pstdev(clean)
    return {"n": len(clean), "mean": mean(clean), "std": std, "ci_low": ci_low, "ci_high": ci_high}


def group_latest_rows(rows: list[dict[str, str]], group_fields: list[str]) -> dict[tuple[str, ...], list[dict[str, str]]]:
    grouped: dict[tuple[str, ...], list[dict[str, str]]] = defaultdict(list)
    for row in latest_rows(rows):
        grouped[tuple(row[field] for field in group_fields)].append(row)
    return grouped


def paired_differences(
    rows: list[dict[str, str]],
    *,
    world: str,
    left_condition: str,
    right_condition: str,
    metric: str,
    seed_split: str = "evaluation",
) -> list[float]:
    left_by_seed: dict[str, float] = {}
    right_by_seed: dict[str, float] = {}
    for row in latest_rows(rows):
        if row["world"] != world or row.get("seed_split", "evaluation") != seed_split:
            continue
        value = safe_float(row.get(metric))
        if value is None:
            continue
        if row["condition"] == left_condition:
            left_by_seed[row["seed"]] = value
        elif row["condition"] == right_condition:
            right_by_seed[row["seed"]] = value
    paired = []
    for seed in sorted(set(left_by_seed) & set(right_by_seed)):
        paired.append(right_by_seed[seed] - left_by_seed[seed])
    return paired


def write_markdown(path: str | Path, text: str) -> None:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(text, encoding="utf-8")
