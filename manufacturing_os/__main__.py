import argparse
import json
from pathlib import Path
import sys

from . import ManufacturingInput, Orchestrator
from .store import save_run


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run synthetic manufacturing planning mocks")
    parser.add_argument("input", type=Path)
    parser.add_argument("--output-dir", type=Path, default=Path("runs"))
    args = parser.parse_args(argv)
    try:
        package = ManufacturingInput.from_dict(json.loads(args.input.read_text(encoding="utf-8")))
        plan = Orchestrator().run(package)
        path = save_run(args.output_dir, package, plan)
    except (ValueError, TypeError, KeyError, OSError) as exc:
        print(f"Input/run error: {exc}", file=sys.stderr)
        return 2
    print(json.dumps({"verification": plan.verification.status, "state": plan.state_history[-1],
                      "production_authorized": plan.production_authorized, "record": str(path)}))
    return 1 if plan.verification.status == "FAIL" else 0


if __name__ == "__main__":
    raise SystemExit(main())
