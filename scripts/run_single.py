from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sec_poc.experiments import load_condition_config
from sec_poc.logging_utils import dump_json, ensure_dir, write_jsonl
from sec_poc.simulator import generate_import_stream, run_episode


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run one SEC PoC condition for one seed.")
    parser.add_argument("--config", default="configs/default.yaml")
    parser.add_argument("--condition", default="baseline")
    parser.add_argument("--backend", default="scripted")
    parser.add_argument("--mode", default="default", choices=["smoke", "default", "extended"])
    parser.add_argument("--seed", type=int, default=11)
    parser.add_argument("--output-root", default=".")
    parser.add_argument("--llm-roles", nargs="*", default=None)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config = load_condition_config(
        base_config_path=args.config,
        condition_name=args.condition,
        mode=args.mode,
        backend_name=args.backend,
        llm_roles=args.llm_roles,
    )
    world_bundle = generate_import_stream(args.seed, config)
    result = run_episode(
        seed=args.seed,
        condition_name=args.condition,
        config=config,
        world_bundle=world_bundle,
    )

    output_root = Path(args.output_root)
    result_dir = ensure_dir(output_root / "results" / result["run_id"])
    log_dir = ensure_dir(output_root / "logs")
    dump_json(result_dir / config["logging"]["config_dump_filename"], config)
    dump_json(result_dir / "metrics.json", {"rows": result["metrics"]})
    dump_json(result_dir / "final_state.json", {"items": result["final_state_items"]})
    write_jsonl(log_dir / f"{result['run_id']}.jsonl", result["events"])

    final_metrics = result["metrics"][-1] if result["metrics"] else {}
    print(json.dumps({"run_id": result["run_id"], "final_metrics": final_metrics}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
