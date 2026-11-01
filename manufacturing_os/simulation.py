"""Finite-batch discrete-event scheduling for isolated serial process routes."""
from collections import defaultdict
from copy import deepcopy
import heapq
import math
from pathlib import Path
import random

from .calculations import Scenario, fields, nonempty, quantity
from .models import digest

SIMULATOR_VERSION = "serial-events-1.0"


def simulate_batch(spec: dict) -> dict:
    fields(spec, {"schema_version", "simulation_id", "revision", "seed", "batch_size", "scenario"}, "batch simulation")
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
    rng = random.Random(spec["seed"])
    horizon = scenario.horizon_hours
    arrivals = [(0.0, job) for job in range(size)]
    timelines = [[] for _ in range(size)]
    scrap_times: dict[int, float] = {}
    operations = []
    for op in scenario.operations:
        # Setup begins at time zero on every machine; availability stretches time,
        # rather than simulating a downtime calendar or random breakdowns.
        setup_end = op.setup_hours / op.availability
        service = op.cycle_hours / op.availability
        if not math.isfinite(setup_end) or not math.isfinite(service) or service <= 0:
            raise ValueError("unsupported time scale")
        machines = [(setup_end, machine) for machine in range(op.machines)]
        heapq.heapify(machines)
        busy = [min(horizon, setup_end)] * op.machines
        next_arrivals = []
        records = []
        for arrival, job in sorted(arrivals):
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
    return {"schema_version": "1.0", "simulator_version": SIMULATOR_VERSION,
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
                "One setup per machine begins at time zero, even if a downstream machine has no arrivals.",
                "Availability stretches setup and cycle durations by 1/availability; no downtime calendars.",
                "Independent Bernoulli quality checks occur at each operation completion; failed jobs leave the route.",
                "No transfer, rework, shared labor/equipment, shifts, maintenance, or cost simulation.",
                "Events exactly at the horizon count as completed/started; occupancy includes setup and processing.",
                "Full-batch timelines include future events beyond the reporting horizon."],
            "validation_status": "UNVALIDATED_SIMULATION", "production_authorized": False}


def main() -> int:
    import argparse
    import json
    import sys
    parser = argparse.ArgumentParser(description="Run a finite-batch serial-route simulation")
    parser.add_argument("input", type=Path)
    parser.add_argument("--output", type=Path, help="Create a new report without overwriting")
    args = parser.parse_args()
    try:
        result = simulate_batch(json.loads(args.input.read_text(encoding="utf-8")))
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
