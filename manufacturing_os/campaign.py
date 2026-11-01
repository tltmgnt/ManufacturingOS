"""Bounded, sequential software-scenario evaluation across complete studies."""
from copy import deepcopy
import json
from pathlib import Path

from .jsonio import read_json
from .calculations import Scenario,fields,nonempty
from .models import digest
from .simulation import parse_downtime
from .study import run_study

CAMPAIGN_VERSION = "study-campaign-1.0"
MAX_CASES = 20
MAX_INPUT_BYTES = 32*1024*1024
MAX_REPORT_BYTES = 128*1024*1024
MAX_WORK = 2000000
MAX_UNCERTAINTY_SAMPLES = 10000
OBSERVATION_STATES = (None,"PASS","FAIL","REFERENCE_UNAVAILABLE","CONTEXT_MISMATCH")


def encode(value: dict) -> bytes:
    return (json.dumps(value,sort_keys=True,separators=(",",":"),allow_nan=False)+"\n").encode("utf-8")


def study_work(study: dict) -> tuple[int,int]:
    """Conservative preflight; malformed studies still become case errors later."""
    try:
        scenario = Scenario.from_dict(study["scenario"])
        config = study["simulation"]
        if not isinstance(config,dict):
            return 0,0
        size = config.get("batch_size")
        if type(size) is not int or not 1 <= size <= 10000:
            return 0,0
        machines = sum(op.machines for op in scenario.operations)
        calendars,windows = parse_downtime(config.get("downtime",[]),scenario,size)
        base = size*len(scenario.operations)+machines
        if calendars:
            base = max(base,size*(machines+len(windows)))
        replicates = study.get("replications",{})
        runs = replicates.get("runs",0) if isinstance(replicates,dict) else 0
        runs = runs if type(runs) is int and 1 <= runs <= 1000 else 0
        uncertainty = study.get("uncertainty",{})
        samples = uncertainty.get("samples",0) if isinstance(uncertainty,dict) else 0
        samples = samples if type(samples) is int and 1 <= samples <= 10000 else 0
        return (1+runs)*base+samples*len(scenario.operations),samples
    except (ValueError,TypeError,KeyError,OverflowError):
        return 0,0


def run_campaign(spec: dict) -> dict:
    fields(spec,{"schema_version","campaign_id","revision","cases"},"study campaign")
    if spec["schema_version"] != "1.0":
        raise ValueError("unsupported campaign schema")
    for key in ("campaign_id","revision"):
        nonempty(spec[key],key)
    if not isinstance(spec["cases"],list) or not 1 <= len(spec["cases"]) <= MAX_CASES:
        raise ValueError("campaign requires 1 to 20 cases")
    input_size = len(encode(spec))
    if input_size > MAX_INPUT_BYTES:
        raise ValueError("campaign input exceeds 32 MiB")
    seen,work,samples = set(),0,0
    for case in spec["cases"]:
        fields(case,{"case_id","study","expected_review_state","expected_blocking_codes","expected_observation_status"},"campaign case")
        nonempty(case["case_id"],"case_id")
        if case["case_id"] in seen:
            raise ValueError("duplicate campaign case ID")
        seen.add(case["case_id"])
        if not isinstance(case["study"],dict):
            raise ValueError("campaign study must be an object")
        if case["expected_review_state"] not in ("HUMAN_REVIEW","REVISION_REQUIRED"):
            raise ValueError("unsupported expected study review state")
        codes = case["expected_blocking_codes"]
        if not isinstance(codes,list):
            raise ValueError("expected_blocking_codes must be a list")
        for code in codes:
            nonempty(code,"expected blocking code")
        if len(set(codes))!=len(codes):
            raise ValueError("duplicate expected blocking code")
        if case["expected_observation_status"] not in OBSERVATION_STATES:
            raise ValueError("unsupported expected observation status")
        case_work,case_samples = study_work(case["study"])
        work += case_work
        samples += case_samples
    if work > MAX_WORK or samples > MAX_UNCERTAINTY_SAMPLES:
        raise ValueError("campaign exceeds aggregate scheduling/uncertainty work limits")
    cases,total_size = [],input_size
    for case in spec["cases"]:
        expected = {"review_state":case["expected_review_state"],"blocking_codes":sorted(case["expected_blocking_codes"]),
                    "observation_status":case["expected_observation_status"]}
        report,error = None,None
        try:
            report = run_study(case["study"])
        except Exception as exc:
            # Record child execution errors explicitly; never treat them as
            # expected failure cases or silently skip subsequent studies.
            error = {"type":type(exc).__name__,"message":str(exc)}
        actual,mismatches = None,[]
        if report is None:
            mismatches.append({"field":"execution","expected":"completed study","actual":"ERROR"})
        else:
            actual = {"review_state":report["review_state"],
                      "blocking_codes":sorted(f["code"] for f in report["findings"] if f["severity"]=="BLOCKING"),
                      "observation_status":report.get("observation_report",{}).get("status")}
            for key,value in expected.items():
                if actual[key]!=value:
                    mismatches.append({"field":key,"expected":value,"actual":actual[key]})
            total_size += len(encode(report))
            if total_size > MAX_REPORT_BYTES:
                raise ValueError("campaign report exceeds 128 MiB")
        cases.append({"case_id":case["case_id"],"status":"FAIL" if mismatches else "PASS",
                      "execution_status":"ERROR" if error else "COMPLETED","error":error,
                      "expected":expected,"actual":actual,"mismatches":mismatches,
                      "study_report_hash":digest(report) if report is not None else None,"study_report":report})
    passed = sum(case["status"]=="PASS" for case in cases)
    result = {"schema_version":"1.0","campaign_version":CAMPAIGN_VERSION,"campaign_id":spec["campaign_id"],
              "campaign_revision":spec["revision"],"campaign_fingerprint":digest(spec),"input":deepcopy(spec),
              "scope":"SOFTWARE_EXPECTATION_CHECKS","status":"PASS" if passed==len(cases) else "FAIL",
              "case_count":len(cases),"passed_cases":passed,"failed_cases":len(cases)-passed,
              "execution_errors":sum(case["execution_status"]=="ERROR" for case in cases),
              "revision_required_studies":sum(case["actual"] is not None and case["actual"]["review_state"]=="REVISION_REQUIRED" for case in cases),
              "estimated_work_units":work,"uncertainty_sample_count":samples,"cases":cases,
              "limitations":["Campaign PASS means configured software outcomes matched, including intentionally blocked studies.",
                             "It does not mean studies are production-ready, calibrated, authenticated, or approved.",
                             "Cases run sequentially and independently; execution errors always fail their case.",
                             "Full inputs and successful child reports are retained for reproducibility; no external source paths are followed."],
              "approval_state":"PENDING_HUMAN_REVIEW","production_authorized":False}
    if len(encode(result)) > MAX_REPORT_BYTES:
        raise ValueError("campaign report exceeds 128 MiB")
    return result


def reconstruct_campaign(report: dict) -> dict:
    if not isinstance(report,dict) or "input" not in report:
        raise ValueError("expected a complete campaign report")
    reconstructed = run_campaign(report["input"])
    if digest(report)!=digest(reconstructed):
        raise ValueError("campaign report differs from reconstruction")
    return reconstructed


def main(argv: list[str] | None = None) -> int:
    import argparse
    import sys
    parser = argparse.ArgumentParser(description="Evaluate a bounded campaign of study software expectations")
    parser.add_argument("input",type=Path)
    parser.add_argument("--output",type=Path,help="Create a complete campaign report without overwriting")
    args = parser.parse_args(argv)
    try:
        if args.input.stat().st_size > MAX_INPUT_BYTES:
            raise ValueError("campaign input exceeds 32 MiB")
        result = run_campaign(read_json(args.input))
        if args.output:
            with args.output.open("xb") as file:
                file.write(encode(result))
            print(json.dumps({key:result[key] for key in ("campaign_id","scope","status","case_count","passed_cases","failed_cases","execution_errors","revision_required_studies","production_authorized")},sort_keys=True))
        else:
            print(encode(result).decode("utf-8"),end="")
        return 0 if result["status"]=="PASS" else 1
    except (ValueError,TypeError,KeyError,OSError,OverflowError,ZeroDivisionError) as exc:
        print(f"Campaign error: {exc}",file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
