from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sec_poc.experiments import flatten_metric_row, load_condition_config, load_yaml, make_run_uid
from sec_poc.logging_utils import dump_json, ensure_dir, write_jsonl
from sec_poc.simulator import generate_import_stream, run_episode


MAIN_WORLDS = [
    "configs/default_confirmatory.yaml",
    "configs/contamination_stress.yaml",
    "configs/fork_stress.yaml",
]
ABLATION_CONFIGS = [
    "configs/ablation_depth_discount_none.yaml",
    "configs/ablation_depth_discount_mild.yaml",
    "configs/ablation_depth_discount_strong.yaml",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run v2 scripted confirmatory and tradeoff experiments.")
    parser.add_argument("--output-dir", default="results/v2_confirmatory")
    parser.add_argument("--log-dir", default="logs/v2_confirmatory")
    parser.add_argument("--backend", default="scripted")
    return parser.parse_args()


def write_metrics_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        return
    fieldnames = sorted({field for row in rows for field in row.keys()})
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def run_main_worlds(output_dir: Path, log_dir: Path, backend: str) -> tuple[list[dict], list[dict]]:
    rows: list[dict] = []
    manifest: list[dict] = []
    for config_path in MAIN_WORLDS:
        world_base = load_yaml(config_path)
        world_name = world_base["experiment"]["world_label"]
        mode = world_base["experiment"].get("active_profile_name", "confirmatory")
        seeds = world_base["experiment"]["evaluation_seeds"]
        for seed in seeds:
            reference_config = load_condition_config(
                base_config_path=config_path,
                condition_name=world_base["experiment"]["paired_conditions"][0],
                mode=mode,
                backend_name=backend,
            )
            world_bundle = generate_import_stream(seed, reference_config)
            for condition_name in world_base["experiment"]["paired_conditions"]:
                config = load_condition_config(
                    base_config_path=config_path,
                    condition_name=condition_name,
                    mode=mode,
                    backend_name=backend,
                )
                result = run_episode(seed=seed, condition_name=condition_name, config=config, world_bundle=world_bundle)
                run_dir = ensure_dir(output_dir / "runs" / world_name / result["run_id"])
                ensure_dir(log_dir / world_name)
                write_jsonl(log_dir / world_name / f"{result['run_id']}.jsonl", result["events"])
                dump_json(run_dir / config["logging"]["config_dump_filename"], config)
                dump_json(run_dir / "metrics.json", {"rows": result["metrics"]})
                dump_json(run_dir / "final_state.json", {"items": result["final_state_items"]})
                for row in result["metrics"]:
                    payload = flatten_metric_row(
                        row,
                        run_id=result["run_id"],
                        seed=seed,
                        condition=condition_name,
                        backend=backend,
                        world=world_name,
                    )
                    payload.update(
                        {
                            "analysis_group": "confirmatory",
                            "seed_split": "evaluation",
                            "config_path": config_path,
                        }
                    )
                    rows.append(payload)
                manifest.append(
                    {
                        "run_uid": make_run_uid(world=world_name, condition=condition_name, backend=backend, seed=seed),
                        "analysis_group": "confirmatory",
                        "world": world_name,
                        "seed": seed,
                        "condition": condition_name,
                        "backend": backend,
                        "run_id": result["run_id"],
                        "event_log": f"logs/v2_confirmatory/{world_name}/{result['run_id']}.jsonl",
                        "metrics_file": f"results/v2_confirmatory/runs/{world_name}/{result['run_id']}/metrics.json",
                    }
                )
    return rows, manifest


def run_tradeoff_ablation(output_dir: Path, log_dir: Path, backend: str) -> tuple[list[dict], list[dict]]:
    rows: list[dict] = []
    manifest: list[dict] = []
    for config_path in ABLATION_CONFIGS:
        base = load_yaml(config_path)
        world_name = base["experiment"]["world_label"]
        seeds = base["experiment"]["evaluation_seeds"]
        mode = "confirmatory"
        for seed in seeds:
            config = load_yaml(config_path)
            config["experiment"]["active_profile"] = config["experiment"]["mode_profiles"][mode]
            config["experiment"]["mode"] = mode
            config["backend"]["policy_backend"] = backend
            world_bundle = generate_import_stream(seed, config)
            condition_name = Path(config_path).stem
            result = run_episode(seed=seed, condition_name=condition_name, config=config, world_bundle=world_bundle)
            run_dir = ensure_dir(output_dir / "tradeoff_runs" / world_name / result["run_id"])
            ensure_dir(log_dir / world_name)
            write_jsonl(log_dir / world_name / f"{result['run_id']}.jsonl", result["events"])
            dump_json(run_dir / config["logging"]["config_dump_filename"], config)
            dump_json(run_dir / "metrics.json", {"rows": result["metrics"]})
            dump_json(run_dir / "final_state.json", {"items": result["final_state_items"]})
            for row in result["metrics"]:
                payload = flatten_metric_row(
                    row,
                    run_id=result["run_id"],
                    seed=seed,
                    condition=condition_name,
                    backend=backend,
                    world=world_name,
                )
                payload.update(
                    {
                        "analysis_group": "tradeoff",
                        "seed_split": "evaluation",
                        "config_path": config_path,
                    }
                )
                rows.append(payload)
            manifest.append(
                {
                    "run_uid": make_run_uid(world=world_name, condition=condition_name, backend=backend, seed=seed),
                    "analysis_group": "tradeoff",
                    "world": world_name,
                    "seed": seed,
                    "condition": condition_name,
                    "backend": backend,
                    "run_id": result["run_id"],
                    "event_log": f"logs/v2_confirmatory/{world_name}/{result['run_id']}.jsonl",
                    "metrics_file": f"results/v2_confirmatory/tradeoff_runs/{world_name}/{result['run_id']}/metrics.json",
                }
            )
    return rows, manifest


def main() -> None:
    args = parse_args()
    output_dir = ensure_dir(args.output_dir)
    log_dir = ensure_dir(args.log_dir)
    confirmatory_rows, confirmatory_manifest = run_main_worlds(output_dir, log_dir, args.backend)
    tradeoff_rows, tradeoff_manifest = run_tradeoff_ablation(output_dir, log_dir, args.backend)
    rows = confirmatory_rows + tradeoff_rows
    manifest = confirmatory_manifest + tradeoff_manifest
    write_metrics_csv(output_dir / "metrics.csv", rows)
    dump_json(output_dir / "manifest.json", {"canonical_run_key": "run_uid", "runs": manifest})
    print(json.dumps({"runs": len(manifest), "metrics_csv": str(output_dir / 'metrics.csv')}, indent=2))


if __name__ == "__main__":
    main()
