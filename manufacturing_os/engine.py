"""Deterministic DAG execution. All specialist outputs are explicitly mocks."""
from dataclasses import asdict
from typing import Protocol

from .models import AgentResult, ManufacturingInput, ManufacturingPlan, Verification, VERSION, digest

# A0 coordinates; A10 verifies after all specialists have completed.
DEPENDENCIES = {
    "A1": (), "A2": ("A1",), "A5": ("A2",), "A4": ("A5",),
    "A7": ("A2", "A4"), "A8": ("A5", "A7"), "A6": ("A2", "A5"),
    "A9": ("A4", "A6", "A7", "A8"), "A3": ("A6", "A9"),
}
FIELDS = {"A1": "dfm", "A2": "route", "A5": "materials_and_tooling", "A4": "suppliers",
          "A7": "capacity", "A8": "cost_and_yield", "A6": "quality", "A9": "risk", "A3": "readiness"}
APPROVALS = ["design owner", "process engineering", "materials engineering", "supplier qualification",
             "quality", "production readiness"]


class Agent(Protocol):
    agent_id: str
    version: str

    def run(self, package: ManufacturingInput, upstream: dict[str, AgentResult]) -> AgentResult: ...


def task_order(graph: dict[str, tuple[str, ...]]) -> list[str]:
    if any(dep not in graph for deps in graph.values() for dep in deps):
        raise ValueError("unknown task dependency")
    order: list[str] = []
    remaining = set(graph)
    while remaining:
        ready = sorted(n for n in remaining if set(graph[n]) <= set(order))
        if not ready:
            raise ValueError("cyclic task dependencies")
        order.extend(ready)
        remaining.difference_update(ready)
    return order


class MockAgent:
    version = "mock-1.0"

    def __init__(self, agent_id: str):
        self.agent_id = agent_id

    def run(self, package: ManufacturingInput, upstream: dict[str, AgentResult]) -> AgentResult:
        result = AgentResult(
            agent_id=self.agent_id, agent_version=self.version, schema_version=VERSION,
            status="CONDITIONAL", revision="", input_fingerprint=package.fingerprint,
            upstream_revisions={k: v.revision for k, v in sorted(upstream.items())},
            findings={FIELDS[self.agent_id]: None},
            assumptions=["Synthetic orchestration demonstration; no manufacturing analysis performed."],
            evidence_refs=[], uncertainty="unknown",
            open_issues=[f"{FIELDS[self.agent_id]} is unknown; qualified analysis and evidence required."],
        )
        result.revision = result_revision(result)
        return result


def result_revision(result: AgentResult) -> str:
    return digest({k: v for k, v in asdict(result).items() if k != "revision"})


def invalidate(package: ManufacturingInput, results: dict[str, AgentResult]) -> set[str]:
    """Mark stale input/results and propagate to every dependent task in place."""
    stale = set()
    for aid in task_order(DEPENDENCIES):
        if aid not in results:
            stale.add(aid)
            continue
        result = results[aid]
        expected = {d: results[d].revision for d in DEPENDENCIES[aid] if d in results}
        if (result.input_fingerprint != package.fingerprint or result.status == "STALE"
                or result.revision != result_revision(result)
                or result.upstream_revisions != expected or set(DEPENDENCIES[aid]) & stale):
            stale.add(aid)
            result.status = "STALE"
    return stale


def verify(package: ManufacturingInput, results: dict[str, AgentResult]) -> Verification:
    failures, outstanding, conflicts = [], [], []
    evidence_ids = {e.evidence_id for e in package.evidence}
    missing = set(DEPENDENCIES) - set(results)
    if missing:
        failures.append(f"Missing specialist results: {', '.join(sorted(missing))}")
    if set(results) - set(DEPENDENCIES):
        failures.append("Unexpected specialist results")
    stale = invalidate(package, results)
    if stale - missing:
        failures.append(f"Stale results: {', '.join(sorted(stale-missing))}")
    for aid, result in sorted(results.items()):
        if result.agent_id != aid or result.schema_version != VERSION or not result.agent_version:
            failures.append(f"{aid}: invalid result identity or version")
        if result.status not in ("PASS", "CONDITIONAL", "FAIL", "STALE"):
            failures.append(f"{aid}: invalid status")
        if result.status == "FAIL":
            failures.append(f"{aid}: failed")
        if not set(result.evidence_refs) <= evidence_ids:
            failures.append(f"{aid}: unknown evidence references")
        # Phase 1 cannot validate real manufacturing conclusions.
        if not result.agent_version.startswith("mock-"):
            failures.append(f"{aid}: non-mock results unsupported in Phase 1")
        if result.status == "CONDITIONAL" or result.open_issues or not result.evidence_refs:
            outstanding.append(f"{aid}: analysis/evidence outstanding")
        if any(v is None for v in result.findings.values()) and not result.open_issues:
            failures.append(f"{aid}: unknown findings lack explanatory issues")
        if result.agent_version.startswith("mock-"):
            outstanding.append(f"{aid}: mock output requires qualified analysis")
    for c in package.constraints:
        if c["kind"] == "hard" and c["satisfied"] is not True:
            if c["satisfied"] is False:
                failures.append(f"Hard constraint violated: {c['constraint_id']}")
                conflicts.append({"conflict_id": c["constraint_id"], "classification": "hard",
                                  "claim": "required satisfied", "observed": False,
                                  "source": package.package_id, "revision": package.revision,
                                  "severity": "blocking", "issue": c["issue"],
                                  "decision_owner": "qualified human reviewer", "resolution": None})
            else:
                outstanding.append(f"Hard constraint unknown: {c['constraint_id']}")
        elif c["satisfied"] is not True:
            outstanding.append(f"Unresolved {c['kind']} constraint: {c['constraint_id']}")
    covered = {claim for e in package.evidence for claim in e.claim_ids}
    for req in package.requirements:
        if req["requirement_id"] not in covered:
            outstanding.append(f"No evidence for requirement {req['requirement_id']}")
    return Verification("FAIL" if failures else "CONDITIONAL" if outstanding else "PASS",
                        failures + outstanding, conflicts)


class Orchestrator:
    def __init__(self, agents: dict[str, Agent] | None = None):
        self.agents = agents if agents is not None else {aid: MockAgent(aid) for aid in DEPENDENCIES}
        if set(self.agents) != set(DEPENDENCIES):
            raise ValueError("exactly A1-A9 specialist agents are required")

    def run(self, package: ManufacturingInput) -> ManufacturingPlan:
        # Revalidate even callers who construct or mutate dataclasses directly.
        package = ManufacturingInput.from_dict(asdict(package))
        history = ["RECEIVED", "INPUT_VALIDATION", "ANALYSIS"]
        results: dict[str, AgentResult] = {}
        for aid in task_order(DEPENDENCIES):
            upstream = {d: results[d] for d in DEPENDENCIES[aid]}
            try:
                result = self.agents[aid].run(package, upstream)
                if not isinstance(result, AgentResult):
                    raise TypeError("agent must return AgentResult")
                results[aid] = result
            except Exception as exc:
                # Failed runs remain inspectable and cannot produce PASS.
                result = MockAgent(aid).run(package, upstream)
                result.status = "FAIL"
                result.open_issues = [f"Agent exception: {type(exc).__name__}: {exc}"]
                result.revision = result_revision(result)
                results[aid] = result
        history.extend(["INTEGRATION", "VERIFICATION"])
        verification = verify(package, results)
        history.extend(["REVISION_REQUIRED"] if verification.status == "FAIL"
                       else ["CONDITIONAL" if verification.status == "CONDITIONAL" else "VERIFIED_CANDIDATE", "HUMAN_REVIEW"])
        return ManufacturingPlan(VERSION, package.package_id, package.fingerprint, results, verification,
                                 history, list(APPROVALS))
