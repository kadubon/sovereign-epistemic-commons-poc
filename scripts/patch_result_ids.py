from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sec_poc.experiments import make_run_uid


TARGETS = [
    {
        "metrics_csv": "results/v1_exploratory/metrics.csv",
        "manifest_json": "results/v1_exploratory/manifest.json",
        "default_world": "v1_exploratory",
        "analysis_group": "exploratory",
        "results_prefix": "results/v1_exploratory",
        "logs_prefix": "logs/v1_exploratory",
    },
    {
        "metrics_csv": "results/v2_confirmatory/metrics.csv",
        "manifest_json": "results/v2_confirmatory/manifest.json",
        "default_world": None,
        "analysis_group": None,
        "results_prefix": "results/v2_confirmatory",
        "logs_prefix": "logs/v2_confirmatory",
    },
    {
        "metrics_csv": "results/v2_aux_llm/metrics.csv",
        "manifest_json": "results/v2_aux_llm/manifest.json",
        "default_world": None,
        "analysis_group": None,
        "results_prefix": "results/v2_aux_llm",
        "logs_prefix": "logs/v2_aux_llm",
    },
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Patch existing result tables and manifests with canonical run_uid fields.")
    parser.add_argument("--root", default=".")
    return parser.parse_args()


def normalize_legacy_path(path: str, *, prefix: str) -> str:
    path = path.replace("\\", "/")
    if path.startswith(f"{prefix}/"):
        suffix = path[len(prefix) + 1 :]
        repeated_leaf = prefix.split("/")[-1]
        while suffix.startswith(f"{repeated_leaf}/"):
            suffix = suffix[len(repeated_leaf) + 1 :]
        return f"{prefix}/{suffix}"
    if path.startswith("results/") or path.startswith("logs/"):
        tail = path.split("/", 1)[1]
        repeated_leaf = prefix.split("/")[-1]
        while tail.startswith(f"{repeated_leaf}/"):
            tail = tail[len(repeated_leaf) + 1 :]
        return f"{prefix}/{tail}"
    return path


def infer_condition(run: dict) -> str:
    if run.get("condition"):
        return str(run["condition"])
    run_id = str(run.get("run_id", ""))
    if "full_sec_lite" in run_id:
        return "full_sec_lite"
    if "lanes_discount" in run_id:
        return "lanes_discount"
    if "lanes_only" in run_id:
        return "lanes_only"
    if "baseline" in run_id:
        return "baseline"
    return run_id


def patch_metrics_csv(path: Path, *, default_world: str | None, analysis_group: str | None) -> int:
    if not path.exists():
        return 0
    with path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
        fieldnames = list(rows[0].keys()) if rows else []
    changed = 0
    if "run_uid" not in fieldnames:
        fieldnames.append("run_uid")
    if default_world is not None and "world" not in fieldnames:
        fieldnames.append("world")
    if analysis_group is not None and "analysis_group" not in fieldnames:
        fieldnames.append("analysis_group")
    for row in rows:
        world = row.get("world") or default_world
        if world is not None and not row.get("world"):
            row["world"] = world
            changed += 1
        if analysis_group is not None and not row.get("analysis_group"):
            row["analysis_group"] = analysis_group
            changed += 1
        world_for_uid = row.get("world") or default_world or "legacy"
        run_uid = make_run_uid(
            world=world_for_uid,
            condition=row["condition"],
            backend=row["backend"],
            seed=int(row["seed"]),
        )
        if row.get("run_uid") != run_uid:
            row["run_uid"] = run_uid
            changed += 1
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    return changed


def patch_manifest(path: Path, *, default_world: str | None, analysis_group: str | None, results_prefix: str, logs_prefix: str) -> int:
    if not path.exists():
        return 0
    payload = json.loads(path.read_text(encoding="utf-8"))
    runs = payload.get("runs", [])
    changed = 0
    if payload.get("canonical_run_key") != "run_uid":
        payload["canonical_run_key"] = "run_uid"
        changed += 1
    for run in runs:
        world = run.get("world") or default_world
        if world is not None and not run.get("world"):
            run["world"] = world
            changed += 1
        if analysis_group is not None and not run.get("analysis_group"):
            run["analysis_group"] = analysis_group
            changed += 1
        run_uid = make_run_uid(
            world=run.get("world") or default_world or "legacy",
            condition=infer_condition(run),
            backend=run["backend"],
            seed=int(run["seed"]),
        )
        if run.get("run_uid") != run_uid:
            run["run_uid"] = run_uid
            changed += 1
        if "condition" not in run and infer_condition(run):
            run["condition"] = infer_condition(run)
            changed += 1
        if default_world == "v1_exploratory":
            new_metrics_file = normalize_legacy_path(run["metrics_file"], prefix=results_prefix)
            new_event_log = normalize_legacy_path(run["event_log"], prefix=logs_prefix)
            if run["metrics_file"] != new_metrics_file:
                run["metrics_file"] = new_metrics_file
                changed += 1
            if run["event_log"] != new_event_log:
                run["event_log"] = new_event_log
                changed += 1
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return changed


def main() -> None:
    args = parse_args()
    root = Path(args.root)
    summary: dict[str, dict[str, int]] = {}
    for target in TARGETS:
        metrics_path = root / target["metrics_csv"]
        manifest_path = root / target["manifest_json"]
        metrics_changed = patch_metrics_csv(
            metrics_path,
            default_world=target["default_world"],
            analysis_group=target["analysis_group"],
        )
        manifest_changed = patch_manifest(
            manifest_path,
            default_world=target["default_world"],
            analysis_group=target["analysis_group"],
            results_prefix=target["results_prefix"],
            logs_prefix=target["logs_prefix"],
        )
        summary[target["metrics_csv"]] = {
            "metrics_rows_or_fields_changed": metrics_changed,
            "manifest_entries_or_fields_changed": manifest_changed,
        }
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
