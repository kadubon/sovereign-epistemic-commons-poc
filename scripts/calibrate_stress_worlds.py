from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sec_poc.experiments import load_condition_config, load_yaml
from sec_poc.logging_utils import dump_json
from sec_poc.simulator import generate_import_stream, run_episode


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run v2 calibration diagnostics for stress worlds.")
    parser.add_argument("--output-dir", default="results/v2_confirmatory/calibration")
    return parser.parse_args()


def summarize_world(base_config_path: str, mode: str, conditions: list[str]) -> dict:
    base = load_yaml(base_config_path)
    seeds = base["experiment"]["calibration_seeds"]
    summary = {condition: {"forks": [], "low_reserve": [], "recovery": []} for condition in conditions}
    for seed in seeds:
        reference = load_condition_config(
            base_config_path=base_config_path,
            condition_name=conditions[0],
            mode=mode,
            backend_name="scripted",
        )
        world_bundle = generate_import_stream(seed, reference)
        for condition in conditions:
            config = load_condition_config(
                base_config_path=base_config_path,
                condition_name=condition,
                mode=mode,
                backend_name="scripted",
            )
            result = run_episode(seed=seed, condition_name=condition, config=config, world_bundle=world_bundle)
            last = result["metrics"][-1]
            summary[condition]["forks"].append(last["realized_fork_count"])
            summary[condition]["low_reserve"].append(last["low_reserve_residence_time"])
            summary[condition]["recovery"].append(last["post_fork_recovery_quality"])
    return {
        condition: {
            "mean_forks": sum(values["forks"]) / len(values["forks"]),
            "mean_low_reserve_residence_time": sum(values["low_reserve"]) / len(values["low_reserve"]),
            "mean_post_fork_recovery_quality": (
                sum(value for value in values["recovery"] if value is not None)
                / len([value for value in values["recovery"] if value is not None])
                if any(value is not None for value in values["recovery"])
                else None
            ),
        }
        for condition, values in summary.items()
    }


def main() -> None:
    args = parse_args()
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    fork_stress = summarize_world("configs/fork_stress.yaml", "fork_eval", ["lanes_discount", "full_sec_lite"])
    contamination_stress = summarize_world("configs/contamination_stress.yaml", "confirmatory", ["baseline", "lanes_only", "lanes_discount"])
    payload = {
        "fork_stress_calibration": fork_stress,
        "contamination_stress_calibration": contamination_stress,
        "note": (
            "Calibration is diagnostic only. World parameters are frozen before held-out evaluation."
        ),
    }
    dump_json(output_dir / "calibration.json", payload)
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

