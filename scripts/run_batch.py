from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sec_poc.experiments import load_yaml, run_condition_suite


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the paired SEC PoC comparison suite.")
    parser.add_argument("--config", default="configs/default.yaml")
    parser.add_argument("--backend", default="scripted")
    parser.add_argument("--mode", default="default", choices=["smoke", "default", "extended"])
    parser.add_argument("--output-root", default=".")
    parser.add_argument("--llm-roles", nargs="*", default=None)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    base_config = load_yaml(args.config)
    result = run_condition_suite(
        base_config_path=args.config,
        condition_names=base_config["experiment"]["paired_conditions"],
        mode=args.mode,
        backend_name=args.backend,
        output_root=args.output_root,
        llm_roles=args.llm_roles,
    )
    print(json.dumps({"runs": len(result["manifest"])}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
