"""Capture or compare a sanitized disposable-VM runtime contract."""

import argparse
import json
from pathlib import Path

from jbpa.config import ROOT
from jbpa.regression import capture, compare, load_contract
from jbpa.results import write_result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("capture", "compare"))
    parser.add_argument("--result")
    parser.add_argument("--observation")
    parser.add_argument(
        "--contract",
        default=str(ROOT / "evidence/pa-12.9.2.2/ubuntu-24.04/runtime-contract.yaml"),
    )
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    if args.mode == "capture":
        if not args.result:
            parser.error("--result is required")
        data = capture(args.result)
    else:
        if not args.observation:
            parser.error("--observation is required")
        data = compare(json.loads(Path(args.observation).read_text()), load_contract(args.contract))
    write_result(args.output, json.dumps(data, indent=2, sort_keys=True) + "\n")
    return 0 if data.get("status") != "CONTRACT_CHANGED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
