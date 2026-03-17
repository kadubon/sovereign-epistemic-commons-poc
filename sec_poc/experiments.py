from __future__ import annotations

import csv
from copy import deepcopy
from pathlib import Path
from typing import Any

import yaml

from sec_poc.logging_utils import dump_json, ensure_dir, write_jsonl
from sec_poc.simulator import generate_import_stream, run_episode


def make_run_uid(*, world: str, condition: str, backend: str, seed: int) -> str:
    return f"{world}__{condition}__{backend}__seed{seed}"


def deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = deep_merge(merged[key], value)
        else:
            merged[key] = deepcopy(value)
    return merged


def load_yaml(path: str | Path) -> dict[str, Any]:
    path = Path(path)
    with path.open("r", encoding="utf-8") as handle:
        payload = yaml.safe_load(handle)
    if isinstance(payload, dict) and "extends" in payload:
        base_path = (path.parent / payload.pop("extends")).resolve()
        base_payload = load_yaml(base_path)
        return deep_merge(base_payload, payload)
    return payload


def load_condition_config(
    *,
    base_config_path: str | Path,
    condition_name: str,
    mode: str,
    backend_name: str | None = None,
    llm_roles: list[str] | None = None,
) -> dict[str, Any]:
    base_config = load_yaml(base_config_path)
    condition_path = Path(base_config_path).with_name(f"{condition_name}.yaml")
    condition_override = load_yaml(condition_path)
    config = deep_merge(base_config, condition_override)
    config["experiment"]["active_profile"] = config["experiment"]["mode_profiles"][mode]
    config["experiment"]["mode"] = mode
    if backend_name is not None:
        config["backend"]["policy_backend"] = backend_name
    if llm_roles is not None:
        config["backend"]["llm_roles"] = llm_roles
    return config


def flatten_metric_row(
    row: dict[str, Any],
    *,
    run_id: str,
    seed: int,
    condition: str,
    backend: str,
    world: str | None = None,
) -> dict[str, Any]:
    flattened = {"run_id": run_id, "seed": seed, "condition": condition, "backend": backend}
    if world is not None:
        flattened["world"] = world
        flattened["run_uid"] = make_run_uid(world=world, condition=condition, backend=backend, seed=seed)
    for key, value in row.items():
        if isinstance(value, dict):
            for nested_key, nested_value in value.items():
                flattened[f"{key}.{nested_key}"] = nested_value
        else:
            flattened[key] = value
    return flattened


def write_metrics_csv(path: str | Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    output_path = Path(path)
    ensure_dir(output_path.parent)
    fieldnames = sorted({field for row in rows for field in row.keys()})
    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def run_condition_suite(
    *,
    base_config_path: str | Path,
    condition_names: list[str],
    mode: str,
    backend_name: str,
    output_root: str | Path,
    llm_roles: list[str] | None = None,
) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    output_root = Path(output_root)
    results_dir = ensure_dir(output_root / "results")
    logs_dir = ensure_dir(output_root / "logs")
    manifests: list[dict[str, Any]] = []

    shared_base_config = load_yaml(base_config_path)
    world_name = shared_base_config.get("experiment", {}).get("world_label", Path(base_config_path).stem)
    seeds = shared_base_config["experiment"]["mode_profiles"][mode]["seeds"]
    for seed in seeds:
        reference_config = load_condition_config(
            base_config_path=base_config_path,
            condition_name=condition_names[0],
            mode=mode,
            backend_name=backend_name,
            llm_roles=llm_roles,
        )
        world_bundle = generate_import_stream(seed, reference_config)
        for condition_name in condition_names:
            config = load_condition_config(
                base_config_path=base_config_path,
                condition_name=condition_name,
                mode=mode,
                backend_name=backend_name,
                llm_roles=llm_roles,
            )
            result = run_episode(seed=seed, condition_name=condition_name, config=config, world_bundle=world_bundle)
            run_dir = results_dir / result["run_id"]
            ensure_dir(run_dir)
            write_jsonl(logs_dir / f"{result['run_id']}.jsonl", result["events"])
            dump_json(run_dir / config["logging"]["config_dump_filename"], config)
            dump_json(run_dir / "final_state.json", {"items": result["final_state_items"]})
            dump_json(run_dir / "metrics.json", {"rows": result["metrics"]})
            for row in result["metrics"]:
                rows.append(
                    flatten_metric_row(
                        row,
                        run_id=result["run_id"],
                        seed=seed,
                        condition=condition_name,
                        backend=backend_name,
                        world=world_name,
                    )
                )
            manifests.append(
                {
                    "run_uid": make_run_uid(world=world_name, condition=condition_name, backend=backend_name, seed=seed),
                    "run_id": result["run_id"],
                    "world": world_name,
                    "seed": seed,
                    "condition": condition_name,
                    "backend": backend_name,
                    "event_log": f"logs/{result['run_id']}.jsonl",
                    "metrics_file": f"results/{result['run_id']}/metrics.json",
                }
            )

    write_metrics_csv(results_dir / "metrics.csv", rows)
    dump_json(results_dir / "manifest.json", {"canonical_run_key": "run_uid", "runs": manifests})
    return {"rows": rows, "manifest": manifests}
