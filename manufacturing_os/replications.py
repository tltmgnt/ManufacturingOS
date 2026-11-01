"""Bounded seeded replications of a fixed finite-batch simulation model."""
from copy import deepcopy
import json
import math
from pathlib import Path

from .jsonio import read_json
from .calculations import Scenario,fields,nonempty,quantity
from .experiments import percentile
from .models import digest
from .simulation import parse_downtime,simulate_batch,validate_simulation

REPLICATION_VERSION = "seeded-batch-replications-1.0"
MAX_WORK = 2000000


def validate_experiment(spec: dict) -> None:
    fields(spec,{"schema_version","experiment_id","revision","runs","simulation"},"replication experiment")
    if spec["schema_version"] != "1.0":
        raise ValueError("unsupported replication schema")
    for key in ("experiment_id","revision"):
        nonempty(spec[key],key)
    runs = spec["runs"]
    if type(runs) is not int or not 1 <= runs <= 1000:
        raise ValueError("replications require 1 to 1000 runs")
    template = spec["simulation"]
    if not isinstance(template,dict):
        raise ValueError("simulation template must be an object")
    validate_simulation(template)
    scenario = Scenario.from_dict(template.get("scenario"))
    size,seed = template.get("batch_size"),template.get("seed")
    if type(size) is not int or not 1 <= size <= 10000:
        raise ValueError("simulation batch_size must be an integer in [1, 10000]")
    if type(seed) is not int or not 0 <= seed < 2**32:
        raise ValueError("simulation seed must be a 32-bit nonnegative integer")
    machines = sum(op.machines for op in scenario.operations)
    if runs*(size*len(scenario.operations)+machines) > MAX_WORK:
        raise ValueError("replications exceed aggregate scheduling work limit")
    calendars,windows = parse_downtime(template.get("downtime",[]),scenario,size)
    if calendars and runs*size*(machines+len(windows)) > MAX_WORK:
        raise ValueError("replications exceed aggregate calendar work limit")


def replay_replication(spec: dict,index: int) -> dict:
    validate_experiment(spec)
    if type(index) is not int or not 0 <= index < spec["runs"]:
        raise ValueError("replication index outside configured runs")
    simulation = deepcopy(spec["simulation"])
    simulation["seed"] = (simulation["seed"]+index) % 2**32
    return simulate_batch(simulation)


def summarize(values: list[float | None],unit: str) -> dict:
    defined = [value for value in values if value is not None]
    stats = None
    if defined:
        stats = {key:quantity(value,unit) for key,value in {
            "min":min(defined),"p05":percentile(defined,.05),"p50":percentile(defined,.5),
            "p95":percentile(defined,.95),"max":max(defined),
            "mean":math.fsum(value/len(defined) for value in defined)}.items()}
    return {"defined_runs":len(defined),"undefined_runs":len(values)-len(defined),"unit":unit,"statistics":stats,
            "issue":None if defined else "No defined values in these runs; statistics are unavailable."}


def run_replications(spec: dict) -> dict:
    validate_experiment(spec)
    outcomes,units = [],{}
    for index in range(spec["runs"]):
        simulation = deepcopy(spec["simulation"])
        simulation["seed"] = (simulation["seed"]+index) % 2**32
        report = simulate_batch(simulation)
        metrics = {key:quantity(report[key],"piece") for key in
                   ("good_by_horizon","scrapped_by_horizon","wip_at_horizon","eventual_good_units","eventual_scrapped_units")}
        metrics["batch_completion_time"] = report["batch_completion_time"]
        if "cost_report" in report:
            metrics["full_batch_total_cost"] = report["cost_report"]["total_cost"]
            metrics["full_batch_unit_cost"] = report["cost_report"]["unit_cost"]
            units["full_batch_unit_cost"] = report["cost_report"]["unit_cost_unit"]
        for key,value in metrics.items():
            if value is not None:
                units[key] = value["unit"]
        outcomes.append({"run_index":index,"seed":simulation["seed"],"simulation_input_fingerprint":report["input_fingerprint"],
                         "simulation_report_hash":digest(report),"target_met":report["target_met"],"metrics":metrics})
    summaries = {key:summarize([row["metrics"][key]["value"] if row["metrics"][key] is not None else None for row in outcomes],units[key])
                 for key in sorted(units)}
    met = sum(row["target_met"] for row in outcomes)
    return {"schema_version":"1.0","replication_version":REPLICATION_VERSION,"experiment_id":spec["experiment_id"],
            "experiment_revision":spec["revision"],"experiment_fingerprint":digest(spec),"input":deepcopy(spec),
            "run_count":spec["runs"],"target_met_runs":met,"target_missed_runs":spec["runs"]-met,
            "sampled_target_met_fraction":quantity(met/spec["runs"],"fraction"),"summary":summaries,"outcomes":outcomes,
            "seed_method":"(template_seed + run_index) modulo 2**32; a separate local RNG per simulation",
            "limitations":["Repeated seeded model outcomes are not calibrated risk probabilities or observed service levels.",
                           "Parameters, route, calendars, batch size, and costs stay fixed; only the seed varies.",
                           "Quantiles use linear interpolation at (n-1)*p; statistics use defined values only, with undefined counts retained.",
                           "Cost metrics cover the entire batch, including work beyond the horizon; unit cost can be undefined with no good output.",
                           "Full timelines can be reproduced with replay_replication(input, run_index); report hashes support consistency checking.",
                           "All underlying unvalidated simulation and cost-model assumptions still apply."],
            "validation_status":"UNVALIDATED_REPLICATIONS","production_authorized":False}


def main(argv: list[str] | None = None) -> int:
    import argparse
    import sys
    parser = argparse.ArgumentParser(description="Replicate a fixed finite-batch model across recorded seeds")
    parser.add_argument("input",type=Path)
    parser.add_argument("--replay",type=int,help="Return one full simulation by zero-based run index")
    parser.add_argument("--output",type=Path,help="Create a new report without overwriting")
    args = parser.parse_args(argv)
    try:
        spec = read_json(args.input)
        report = replay_replication(spec,args.replay) if args.replay is not None else run_replications(spec)
        encoded = json.dumps(report,indent=2,sort_keys=True,allow_nan=False)+"\n"
        if args.output:
            with args.output.open("x",encoding="utf-8") as file:
                file.write(encoded)
        else:
            print(encoded,end="")
    except (ValueError,TypeError,KeyError,OSError,OverflowError,ZeroDivisionError) as exc:
        print(f"Replication error: {exc}",file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
