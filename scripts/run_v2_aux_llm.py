from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
import sys
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sec_poc.experiments import flatten_metric_row, load_condition_config, load_yaml, make_run_uid
from sec_poc.logging_utils import dump_json, ensure_dir, write_jsonl
from sec_poc.simulator import generate_import_stream, run_episode


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run auxiliary v2 Ollama checks.")
    parser.add_argument("--output-dir", default="results/v2_aux_llm")
    parser.add_argument("--log-dir", default="logs/v2_aux_llm")
    parser.add_argument("--llm-roles", nargs="*", default=["query"])
    parser.add_argument("--world-configs", nargs="*", default=["configs/default_confirmatory.yaml"])
    parser.add_argument("--seeds", nargs="*", type=int, default=[101, 103])
    parser.add_argument("--steps", type=int, default=24)
    parser.add_argument("--imports-per-step", type=int, default=4)
    return parser.parse_args()


def ollama_available() -> bool:
    request = urllib.request.Request("http://127.0.0.1:11434/api/tags", method="GET")
    try:
        with urllib.request.urlopen(request, timeout=3):
            return True
    except urllib.error.URLError:
        return False


def write_metrics_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        return
    fieldnames = sorted({field for row in rows for field in row.keys()})
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def run_backend(
    world_config_path: str,
    backend: str,
    seed: int,
    llm_roles: list[str],
    steps: int,
    imports_per_step: int,
    output_dir: Path,
    log_dir: Path,
) -> tuple[list[dict], list[dict]]:
    rows: list[dict] = []
    manifest: list[dict] = []
    config = load_condition_config(
        base_config_path=world_config_path,
        condition_name="full_sec_lite",
        mode="aux_llm",
        backend_name=backend,
        llm_roles=llm_roles,
    )
    config["experiment"]["active_profile"]["steps"] = steps
    config["experiment"]["active_profile"]["imports_per_step"] = imports_per_step
    config["experiment"]["active_profile"]["summary_interval"] = max(4, steps // 4)
    config["experiment"]["protected_queries"] = config["experiment"]["protected_queries"][:2]
    world_name = load_yaml(world_config_path)["experiment"]["world_label"]
    world_bundle = generate_import_stream(seed, config)
    result = run_episode(seed=seed, condition_name="full_sec_lite", config=config, world_bundle=world_bundle)
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
            condition="full_sec_lite",
            backend=backend,
            world=world_name,
        )
        payload.update(
            {
                "analysis_group": "aux_llm",
                "seed_split": "auxiliary",
                "config_path": world_config_path,
            }
        )
        rows.append(payload)
    manifest.append(
        {
            "run_uid": make_run_uid(world=world_name, condition="full_sec_lite", backend=backend, seed=seed),
            "world": world_name,
            "seed": seed,
            "backend": backend,
            "run_id": result["run_id"],
            "event_log": f"logs/v2_aux_llm/{world_name}/{result['run_id']}.jsonl",
            "metrics_file": f"results/v2_aux_llm/runs/{world_name}/{result['run_id']}/metrics.json",
        }
    )
    return rows, manifest


def main() -> None:
    args = parse_args()
    output_dir = ensure_dir(args.output_dir)
    log_dir = ensure_dir(args.log_dir)
    if not ollama_available():
        payload = {"executed": False, "reason": "Ollama server was not reachable."}
        dump_json(output_dir / "manifest.json", payload)
        print(json.dumps(payload, indent=2))
        return

    rows: list[dict] = []
    manifest: list[dict] = []
    for backend in ["ollama/gemma3:1b", "ollama/gemma3:4b"]:
        for config_path in args.world_configs:
            for seed in args.seeds:
                backend_rows, backend_manifest = run_backend(
                    config_path,
                    backend,
                    seed,
                    args.llm_roles,
                    args.steps,
                    args.imports_per_step,
                    output_dir,
                    log_dir,
                )
                rows.extend(backend_rows)
                manifest.extend(backend_manifest)

    write_metrics_csv(output_dir / "metrics.csv", rows)
    dump_json(output_dir / "manifest.json", {"executed": True, "canonical_run_key": "run_uid", "runs": manifest})
    print(json.dumps({"executed": True, "runs": len(manifest)}, indent=2))


if __name__ == "__main__":
    main()
