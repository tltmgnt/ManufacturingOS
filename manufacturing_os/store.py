"""Append-only local JSON run records, including exact inputs and task graph."""
from dataclasses import asdict
from datetime import datetime, timezone
import json
from pathlib import Path
from uuid import uuid4

from .engine import DEPENDENCIES
from .models import ManufacturingInput, ManufacturingPlan


def save_run(directory: str | Path, package: ManufacturingInput, plan: ManufacturingPlan) -> Path:
    if package.fingerprint != plan.input_fingerprint:
        raise ValueError("plan and input fingerprints differ")
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    run_id = str(uuid4())
    record = {"schema_version": "1.0", "software_version": "0.1.0", "run_id": run_id,
              "timestamp": datetime.now(timezone.utc).isoformat(), "input": asdict(package),
              "task_graph": DEPENDENCIES, "plan": asdict(plan),
              "orchestrator_version": "A0-1.0", "verifier_version": "A10-1.0"}
    path = directory / f"{run_id}.json"
    with path.open("x", encoding="utf-8") as file:
        json.dump(record, file, indent=2, sort_keys=True, allow_nan=False)
        file.write("\n")
    return path
