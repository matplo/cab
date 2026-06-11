"""Command line interface."""

from __future__ import annotations

import argparse
import json
import sys

from .config import load_config
from .pipeline import inspect_cache, run
from .plotting import plot


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="cab-eec", description="CAB EEC analysis pipeline")
    sub = parser.add_subparsers(dest="command", required=True)

    p_run = sub.add_parser("run", help="run analysis and write parquet outputs")
    p_run.add_argument("config")
    p_run.add_argument("--recompute", choices=["all", "event_index", "jet_splittings", "eec_tables"], default=None)
    p_run.add_argument("--clean", action="store_true", help="remove output_dir before running; defaults to recompute=all")
    p_run.add_argument("--plot", action="store_true", help="make plots after analysis")

    p_plot = sub.add_parser("plot", help="make plots from parquet outputs only")
    p_plot.add_argument("config")
    p_plot.add_argument("--clean", action="store_true", help="remove the configured plot output directory before plotting")

    p_cache = sub.add_parser("inspect-cache", help="show cache keys and paths")
    p_cache.add_argument("config")

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    cfg = load_config(args.config)
    if args.command == "run":
        metadata = run(cfg, recompute=args.recompute, clean=args.clean)
        print(json.dumps(metadata, indent=2, sort_keys=True))
        if args.plot:
            saved = plot(cfg, clean=args.clean)
            print(json.dumps({"plots": saved}, indent=2))
        return 0
    if args.command == "plot":
        saved = plot(cfg, clean=args.clean)
        print(json.dumps({"plots": saved}, indent=2))
        return 0
    if args.command == "inspect-cache":
        print(json.dumps(inspect_cache(cfg), indent=2, sort_keys=True))
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
