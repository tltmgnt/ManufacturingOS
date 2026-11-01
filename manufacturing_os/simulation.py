"""Finite-batch discrete-event scheduling for isolated serial process routes."""
from collections import defaultdict
from copy import deepcopy
import heapq
import math
from pathlib import Path
import random

from .jsonio import read_json
from .calculations import Scenario, fields, hours, nonempty, quantity
from .models import digest

SIMULATOR_VERSION = "serial-events-1.0"


def available_slot(start: float, duration: float, windows: list[tuple[float, float]]) -> float:
    """Find a nonpreemptive slot outside sorted half-open downtime windows."""
    if duration == 0:
        return start
    for begin, end in windows:
        if start+duration <= begin:
            break
        if start < end:
            start = end
    return start


def parse_downtime(data: object, scenario: Scenario, size: int) -> tuple[dict, list]:
    if not isinstance(data, list) or len(data) > 1000:
        raise ValueError("downtime must be a list of at most 1000 machine calendars")
    operations = {op.operation_id: op for op in scenario.operations}
    calendars, normalized = {}, []
    window_count = 0
    for row in data:
        fields(row, {"operation_id", "machine_id", "windows"}, "machine downtime")
        nonempty(row["operation_id"], "operation_id")
        if row["operation_id"] not in operations:
            raise ValueError("unknown downtime operation")
        op = operations[row["operation_id"]]
        machine = row["machine_id"]
        if type(machine) is not int or not 0 <= machine < op.machines:
            raise ValueError("downtime machine_id outside operation machine range")
        if op.availability != 1:
            raise ValueError("calendar operations require availability=1 to avoid double-counting downtime")
        key = op.operation_id, machine
        if key in calendars:
            raise ValueError("duplicate machine downtime calendar")
        if not isinstance(row["windows"], list) or not 1 <= len(row["windows"]) <= 1000:
            raise ValueError("machine downtime requires 1 to 1000 windows")
        windows = []
        for window in row["windows"]:
            fields(window, {"start", "end"}, "downtime window")
            begin, end = hours(window["start"]), hours(window["end"])
            if end <= begin:
                raise ValueError("downtime end must be after start")
            windows.append((begin, end))
        windows.sort()
        if any(windows[i][0] < windows[i-1][1] for i in range(1,len(windows))):
            raise ValueError("overlapping machine downtime windows")
        window_count += len(windows)
        if window_count > 1000:
            raise ValueError("downtime exceeds 1000 windows")
        calendars[key] = windows
    if calendars and size*(sum(op.machines for op in scenario.operations)+window_count) > 1000000:
        raise ValueError("calendar scheduling exceeds 1000000 candidate/window work units")
    for (operation_id,machine), windows in sorted(calendars.items()):
        for begin,end in windows:
            normalized.append({"operation_id":operation_id,"machine_id":machine,
                               "start":quantity(begin,"h"),"end":quantity(end,"h")})
    return calendars, normalized


def full_batch_costs(scenario: Scenario, size: int, operations: list[dict], good_units: int) -> dict:
    """Nominal active-work costs for the whole released batch, not a period P&L."""
    rows = []
    for op, result in zip(scenario.operations, operations):
        count = len(result["timeline"])
        setup = op.setup_hours*op.machines
        processing = count*op.cycle_hours
        billable = setup+processing
        machine = billable*op.machine_rate
        labor = billable*op.labor_rate
        rows.append({"operation_id":op.operation_id,"processed_input":quantity(count,"piece"),
                     "planned_setup_time":quantity(setup,"h"),"processing_time":quantity(processing,"h"),
                     "nominal_billable_time":quantity(billable,"h"),"machine_cost":quantity(machine,scenario.currency),
                     "labor_cost":quantity(labor,scenario.currency),"total_cost":quantity(machine+labor,scenario.currency)})
    material = size*scenario.material_cost_per_start
    machine = math.fsum(row["machine_cost"]["value"] for row in rows)
    labor = math.fsum(row["labor_cost"]["value"] for row in rows)
    total = math.fsum((material,machine,labor))
    return {"schema_version":"1.0","cost_model_version":"full-batch-active-cost-1.0",
            "scope":"FULL_SIMULATED_BATCH","released_input":quantity(size,"piece"),
            "eventual_good_output":quantity(good_units,"piece"),"eventual_scrap":quantity(size-good_units,"piece"),
            "material_cost":quantity(material,scenario.currency),"machine_cost":quantity(machine,scenario.currency),
            "labor_cost":quantity(labor,scenario.currency),"total_cost":quantity(total,scenario.currency),
            "unit_cost":quantity(total/good_units,f"{scenario.currency}/good_piece") if good_units else None,
            "unit_cost_unit":f"{scenario.currency}/good_piece",
            "unit_cost_issue":None if good_units else "No eventual good output; cost per good unit is undefined.",
            "operations":rows,"assumptions":[
                "All released pieces incur entry material cost; downstream processing charges only jobs reaching that operation.",
                "One planned setup per configured machine is charged, even for machines or downstream operations receiving no jobs.",
                "Machine and dedicated labor rates charge nominal setup and processing hours, not queue, idle, or downtime hours.",
                "Availability duration-stretching is not an additional billable-hours factor.",
                "Costs include the entire batch and future events beyond the reporting horizon; no horizon cost allocation is performed.",
                "No overhead, tax, inventory valuation, rework, overtime, or external quoted-price model is included."],
            "validation_status":"UNVALIDATED_ESTIMATE","production_authorized":False}


def validate_simulation(spec: dict) -> tuple:
    optional = set(spec) & {"downtime", "include_costs"} if isinstance(spec, dict) else set()
    fields(spec, {"schema_version", "simulation_id", "revision", "seed", "batch_size", "scenario"} | optional, "batch simulation")
    if "include_costs" in optional and type(spec["include_costs"]) is not bool:
        raise ValueError("include_costs must be boolean")
    if spec["schema_version"] != "1.0":
        raise ValueError("unsupported simulation schema")
    for name in ("simulation_id", "revision"):
        nonempty(spec[name], name)
    if type(spec["seed"]) is not int or not 0 <= spec["seed"] < 2**32:
        raise ValueError("seed must be a 32-bit nonnegative integer")
    size = spec["batch_size"]
    if type(size) is not int or not 1 <= size <= 10000:
        raise ValueError("batch_size must be an integer in [1, 10000]")
    scenario = Scenario.from_dict(spec["scenario"])
    if size * len(scenario.operations) > 100000 or sum(op.machines for op in scenario.operations) > 10000:
        raise ValueError("simulation exceeds 100000 job-operations or 10000 machines")
    calendars, normalized_downtime = parse_downtime(spec.get("downtime", []), scenario, size)
    return optional,scenario,size,calendars,normalized_downtime


def simulate_batch(spec: dict) -> dict:
    optional,scenario,size,calendars,normalized_downtime = validate_simulation(spec)
    rng = random.Random(spec["seed"])
    horizon = scenario.horizon_hours
    arrivals = [(0.0, job) for job in range(size)]
    timelines = [[] for _ in range(size)]
    scrap_times: dict[int, float] = {}
    operations = []
    for op in scenario.operations:
        # Calendar setup starts at the first nonpreemptive slot from time zero.
        setup_end = op.setup_hours / op.availability
        service = op.cycle_hours / op.availability
        if not math.isfinite(setup_end) or not math.isfinite(service) or service <= 0:
            raise ValueError("unsupported time scale")
        setup_starts = [available_slot(0.0, setup_end, calendars.get((op.operation_id,machine), [])) for machine in range(op.machines)]
        ready_times = [start+setup_end for start in setup_starts]
        if any(not math.isfinite(time) for time in ready_times):
            raise ValueError("unsupported setup time scale")
        machines = [(ready_times[machine], machine) for machine in range(op.machines)]
        heapq.heapify(machines)
        busy = [max(0.0,min(horizon,finish)-min(horizon,start)) for start,finish in zip(setup_starts,ready_times)]
        calendar_operation = any(key[0]==op.operation_id for key in calendars)
        next_arrivals = []
        records = []
        for arrival, job in sorted(arrivals):
            if calendar_operation:
                start, machine = min((available_slot(max(arrival,ready_times[index]), service,
                                                    calendars.get((op.operation_id,index),[])),index)
                                     for index in range(op.machines))
            else:
                ready, machine = heapq.heappop(machines)
                start = max(arrival, ready)
            finish = start + service
            if not math.isfinite(finish) or finish <= start:
                raise ValueError("unsupported event time scale")
            # Stable draw order is operation, FIFO arrival, then job ID.
            passed = rng.random() < op.yield_fraction
            record = {"operation_id": op.operation_id, "job_id": job, "machine_id": machine,
                      "arrival_hours": arrival, "start_hours": start, "finish_hours": finish,
                      "queue_wait_hours": start-arrival, "quality_pass": passed}
            timelines[job].append(record)
            records.append(record)
            busy[machine] += max(0.0, min(finish, horizon) - min(start, horizon))
            ready_times[machine] = finish
            if not calendar_operation:
                heapq.heappush(machines, (finish, machine))
            if passed:
                next_arrivals.append((finish, job))
            else:
                scrap_times[job] = finish
        deltas = defaultdict(int)
        for row in records:
            if row["arrival_hours"] <= horizon:
                deltas[row["arrival_hours"]] += 1
            if row["start_hours"] <= horizon:
                deltas[row["start_hours"]] -= 1
        waiting = peak_waiting = 0
        for time in sorted(deltas):
            waiting += deltas[time]
            peak_waiting = max(peak_waiting, waiting)
        operations.append({"operation_id": op.operation_id,
                           "arrived_by_horizon": sum(row["arrival_hours"] <= horizon for row in records),
                           "started_by_horizon": sum(row["start_hours"] <= horizon for row in records),
                           "completed_by_horizon": sum(row["finish_hours"] <= horizon for row in records),
                           "queued_at_horizon": sum(row["arrival_hours"] <= horizon < row["start_hours"] for row in records),
                           "processing_at_horizon": sum(row["start_hours"] <= horizon < row["finish_hours"] for row in records),
                           "peak_queued_by_horizon": peak_waiting,
                           "mean_full_batch_queue_wait": quantity(math.fsum(row["queue_wait_hours"]/len(records) for row in records) if records else 0.0, "h"),
                           "occupied_fraction_by_machine": [quantity(time/horizon, "fraction") for time in busy],
                           "timeline": records})
        if "downtime" in optional:
            operations[-1]["setup_intervals"] = [{"machine_id": index, "start_hours": start, "finish_hours": start+setup_end}
                                                   for index,start in enumerate(setup_starts)]
        arrivals = next_arrivals
    final_times = {job: finish for finish, job in arrivals}
    good = sum(finish <= horizon for finish in final_times.values())
    scrapped = sum(finish <= horizon for finish in scrap_times.values())
    jobs = []
    for job in range(size):
        if job in final_times and final_times[job] <= horizon:
            state = "GOOD"
        elif job in scrap_times and scrap_times[job] <= horizon:
            state = "SCRAPPED"
        else:
            state = "WIP"
        jobs.append({"job_id": job, "state_at_horizon": state,
                     "eventual_good_completion": quantity(final_times[job], "h") if job in final_times else None,
                     "eventual_scrap_time": quantity(scrap_times[job], "h") if job in scrap_times else None})
    completion = max((row["finish_hours"] for timeline in timelines for row in timeline), default=0.0)
    result = {"schema_version": "1.0", "simulator_version": SIMULATOR_VERSION,
            "simulation_id": spec["simulation_id"], "simulation_revision": spec["revision"],
            "input_fingerprint": digest(spec), "input": deepcopy(spec),
            "horizon": quantity(horizon, "h"), "batch_size": size,
            "good_by_horizon": good, "scrapped_by_horizon": scrapped, "wip_at_horizon": size-good-scrapped,
            "target_good_units": scenario.target_good_units, "target_met": good >= scenario.target_good_units,
            "eventual_good_units": len(final_times), "eventual_scrapped_units": len(scrap_times),
            "batch_completion_time": quantity(completion, "h"),
            "operations": operations, "jobs": jobs,
            "assumptions": list(scenario.assumptions) + [
                "Finite batch released together at time zero; FIFO serial route with unlimited intermediate buffers.",
                "Parallel machines are identical, dedicated, nonpreemptive; machine ID breaks scheduling ties.",
                "One setup per machine uses the first available nonpreemptive slot from time zero." if calendars else "One setup per machine begins at time zero, even if a downstream machine has no arrivals.",
                "Calendar operations require availability=1; half-open downtime windows exclude setup and processing." if calendars else "Availability stretches setup and cycle durations by 1/availability; no downtime calendars.",
                "Independent Bernoulli quality checks occur at each operation completion; failed jobs leave the route.",
                "No transfer, rework, shared labor/equipment, recurring shifts, random breakdowns, or cost simulation." if calendars else "No transfer, rework, shared labor/equipment, shifts, maintenance, or cost simulation.",
                "Events exactly at the horizon count as completed/started; occupancy includes setup and processing.",
                "Full-batch timelines include future events beyond the reporting horizon."],
            "validation_status": "UNVALIDATED_SIMULATION", "production_authorized": False}
    if "downtime" in optional:
        result["normalized_downtime"] = normalized_downtime
    if spec.get("include_costs", False):
        result["cost_report"] = full_batch_costs(scenario,size,operations,len(final_times))
    return result


def main(argv: list[str] | None = None) -> int:
    import argparse
    import json
    import sys
    parser = argparse.ArgumentParser(description="Run a finite-batch serial-route simulation")
    parser.add_argument("input", type=Path)
    parser.add_argument("--output", type=Path, help="Create a new report without overwriting")
    args = parser.parse_args(argv)
    try:
        result = simulate_batch(read_json(args.input))
        encoded = json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n"
        if args.output:
            with args.output.open("x", encoding="utf-8") as file:
                file.write(encoded)
        else:
            print(encoded, end="")
    except (ValueError, TypeError, KeyError, OSError, OverflowError, ZeroDivisionError) as exc:
        print(f"Simulation error: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
