from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sec_poc.plotting import make_all_figures


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate summary figures for SEC PoC.")
    parser.add_argument("--metrics-csv", default="results/metrics.csv")
    parser.add_argument("--output-dir", default="results/figures")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    figures = make_all_figures(args.metrics_csv, args.output_dir)
    print(json.dumps({"figures": figures}, indent=2))


if __name__ == "__main__":
    main()
