"""Context-bound comparison with observations from a captured JSON reference."""
import base64
from copy import deepcopy
import json
from pathlib import Path

from .jsonio import loads, read_json, MAX_REPORT_BYTES
from .calculations import fields,hours,measure,nonempty,quantity
from .models import digest

OBSERVATION_VERSION = "captured-reference-checks-1.0"
METRICS = {"good_by_horizon","scrapped_by_horizon","wip_at_horizon","eventual_good_units",
           "eventual_scrapped_units","batch_completion_time","full_batch_total_cost","full_batch_unit_cost"}


def evaluate_observations(spec: dict,replications: dict | None,metadata: dict,sources: dict) -> dict:
    config = spec["observation_checks"]
    fields(config,{"evidence_id","tolerances"},"observation checks")
    nonempty(config["evidence_id"],"reference evidence ID")
    evidence_id = config["evidence_id"]
    if not isinstance(config["tolerances"],dict) or not config["tolerances"] or not set(config["tolerances"])<=METRICS:
        raise ValueError("tolerances must be a nonempty supported metric mapping")
    tolerance_units={key:"piece" for key in METRICS}
    tolerance_units.update(batch_completion_time="h",full_batch_total_cost=spec["scenario"]["currency"],
                           full_batch_unit_cost=spec["scenario"]["currency"]+"/good_piece")
    for metric,tolerance in config["tolerances"].items():
        measure(tolerance,tolerance_units[metric])
    evidence = next((row for row in spec["manufacturing_input"]["evidence"] if row["evidence_id"]==evidence_id),None)
    if evidence is None:
        raise ValueError("unknown observation reference evidence ID")
    result = {"schema_version":"1.0","observation_version":OBSERVATION_VERSION,"evidence_id":evidence_id,
              "source_uri":evidence["source_uri"],"source_revision":evidence["revision"],
              "status":"REFERENCE_UNAVAILABLE","reference_kind":None,"observation_count":None,
              "checks":[],"issues":[],"config_fingerprint":digest(config),
              "limitations":["Checks compare replication means with declared observations and analyst-supplied absolute tolerances.",
                             "Metadata and hash checks establish supplied-source consistency, not authentic origin or observational truth.",
                             "Agreement does not calibrate model parameters, prove generalization, or grant manufacturing approval."],
              "production_authorized":False}
    eligible = next(row for row in metadata["records"] if row["evidence_id"]==evidence_id)["metadata_eligible"]
    matched = next(row for row in sources["records"] if row["evidence_id"]==evidence_id)["status"]=="HASH_MATCHED"
    if not eligible or not matched:
        result["issues"] = ["Selected reference must have both eligible metadata and hash-matched captured content."]
        return result
    captured = next(row for row in spec["evidence_snapshot"]["files"] if row["evidence_id"]==evidence_id)
    reference = loads(base64.b64decode(captured["content_base64"],validate=True))
    fields(reference,{"schema_version","reference_kind","observation_count","context","metrics"},"captured observation reference")
    if reference["schema_version"] != "1.0" or reference["reference_kind"] not in ("synthetic","declared_observations"):
        raise ValueError("unsupported observation reference schema/kind")
    count = reference["observation_count"]
    if type(count) is not int or count <= 0:
        raise ValueError("observation_count must be a positive integer")
    result.update(reference_kind=reference["reference_kind"],observation_count=count,
                  reference_fingerprint=digest(reference),reference_context=deepcopy(reference["context"]))
    package = spec["manufacturing_input"]
    expected = {"product_id":package["product_id"],"design_revision":package["design_revision"],
                "facility_id":package["facility"]["facility_id"],"facility_revision":package["facility"]["revision"],
                "scenario_fingerprint":spec["binding"]["scenario_fingerprint"],
                "simulation_config_fingerprint":digest(spec["simulation"]),"batch_size":spec["simulation"]["batch_size"],
                "horizon":spec["scenario"]["horizon"]}
    fields(reference["context"],set(expected),"observation reference context")
    for key,value in reference["context"].items():
        if key=="horizon":
            equal = hours(value,positive=True)==hours(expected[key],positive=True)
        elif key=="batch_size":
            if type(value) is not int or value <= 0:
                raise ValueError("reference batch_size must be a positive integer")
            equal = value==expected[key]
        else:
            nonempty(value,key)
            equal = value==expected[key]
        if not equal:
            result["issues"].append("Reference context mismatch: "+key)
    if result["issues"]:
        result["status"] = "CONTEXT_MISMATCH"
        return result
    observations,tolerances = reference["metrics"],config["tolerances"]
    if not isinstance(observations,dict) or not observations or not set(observations)<=METRICS:
        raise ValueError("reference metrics must be a nonempty supported metric mapping")
    if not isinstance(tolerances,dict) or set(tolerances)!=set(observations):
        raise ValueError("tolerances must cover exactly the captured reference metrics")
    units = {key:"piece" for key in METRICS}
    units.update(batch_completion_time="h",full_batch_total_cost=spec["scenario"]["currency"],
                 full_batch_unit_cost=spec["scenario"]["currency"]+"/good_piece")
    for metric,observed in sorted(observations.items()):
        unit = units[metric]
        observed_value = measure(observed,unit)
        tolerance = measure(tolerances[metric],unit)
        summary = replications["summary"].get(metric) if replications is not None else None
        check = {"metric":metric,"observed":deepcopy(observed),"absolute_tolerance":deepcopy(tolerances[metric]),
                 "model_mean":None,"residual":None,"status":"FAIL","issue":None}
        if replications is None:
            check.update(status="NOT_EVALUATED",issue="Input preflight only; model comparisons were not run.")
        elif summary is None:
            check["issue"] = "Metric is unavailable in the configured model outputs."
        elif summary["undefined_runs"] or summary["statistics"] is None:
            check["issue"] = "Model metric is undefined in one or more runs; no conditional-mean comparison performed."
        else:
            model = summary["statistics"]["mean"]
            if model["unit"] != unit:
                raise ValueError("model/reference units differ")
            residual = model["value"]-observed_value
            check.update(model_mean=deepcopy(model),residual=quantity(residual,unit),
                         status="PASS" if abs(residual)<=tolerance else "FAIL")
        result["checks"].append(check)
    result["status"] = "REFERENCE_CONTRACT_VALID" if replications is None else "PASS" if all(check["status"]=="PASS" for check in result["checks"]) else "FAIL"
    return result


def main(argv: list[str] | None = None) -> int:
    import argparse
    import sys
    from .study import reconstruct_report
    parser = argparse.ArgumentParser(description="Inspect captured-reference checks in a reconstructable study report")
    parser.add_argument("report",type=Path)
    parser.add_argument("--output",type=Path,help="Create a new check report without overwriting")
    args = parser.parse_args(argv)
    try:
        report = reconstruct_report(read_json(args.report, max_bytes=MAX_REPORT_BYTES))
        if "observation_report" not in report:
            raise ValueError("study report does not include observation_checks")
        result = report["observation_report"]
        encoded = json.dumps(result,indent=2,sort_keys=True,allow_nan=False)+"\n"
        if args.output:
            with args.output.open("x",encoding="utf-8") as file:
                file.write(encoded)
        else:
            print(encoded,end="")
        return 0 if result["status"]=="PASS" else 1
    except (ValueError,TypeError,KeyError,OSError,OverflowError,ZeroDivisionError) as exc:
        print(f"Observation check error: {exc}",file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
