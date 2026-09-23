"""Command-line entry points for inspection, caching, training, and replay."""

from __future__ import annotations

import argparse
import json

from . import api
from .backtest import replay, train_for_mode
from .data import inspect_scada
from .weather import fetch_archive


def main() -> None:
    parser = argparse.ArgumentParser(prog="samal-ml")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("inspect")
    sub.add_parser("fetch")
    train = sub.add_parser("train")
    train.add_argument("--mode", default="test", choices=("test", "val_feb2025", "val_winter"))
    validate = sub.add_parser("validate")
    validate.add_argument("--mode", default="val_feb2025", choices=("val_feb2025", "val_winter"))
    sub.add_parser("test-run")
    sub.add_parser("evaluate")
    live = sub.add_parser("live")
    live.add_argument("--issue-date", required=True)
    args = parser.parse_args()
    if args.command == "inspect":
        output = inspect_scada()
    elif args.command == "fetch":
        output = fetch_archive()
    elif args.command == "train":
        output = {"model": str(train_for_mode(args.mode))}
    elif args.command == "validate":
        output = replay(args.mode)
    elif args.command == "test-run":
        output = replay("test")
    elif args.command == "evaluate":
        output = api.get_metrics("val_feb2025")
    else:
        output = api.run_forecast(args.issue_date, mode="test")
    print(json.dumps(output, indent=2, default=str))


if __name__ == "__main__":
    main()
