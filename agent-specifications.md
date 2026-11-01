# Agent Specifications

All agents must use versioned input/output contracts and return evidence, assumptions, uncertainty, and open issues.

## A0 — Manufacturing Orchestrator

**Role:** Master coordinator and decision aggregator.

**Inputs:** Product package, BOM, constraints, facility context, user objective.

**Responsibilities:** Validate input completeness; decompose work; build task DAG; assign agents; track dependencies; reconcile conflicts; create plan candidate.

**Outputs:** Task graph, execution record, consolidated plan candidate, unresolved issue list.

**Restrictions:** Cannot waive hard constraints or authorize production release.

## A1 — Design for Manufacturability (DFM)

**Question:** Can the design be manufactured using the stated processes and capability?

**Inputs:** CAD metadata/geometry references, drawings, tolerances, material requirements, production volume, process capability data.

**Responsibilities:** Identify inaccessible features, tolerance concerns, geometry complexity, assembly issues, and potential redesign options.

**Outputs:** DFM findings, manufacturability assessment, redesign options, missing design information.

**Restrictions:** No geometry or tolerance change is applied without design-owner approval.

## A2 — Process Engineering

**Question:** What process route could produce the specified part?

**Inputs:** Approved design revision, material candidates, process library, facility capabilities.

**Responsibilities:** Propose process families, operation sequence, setup requirements, machine classes, inspection stages, and process dependencies.

**Outputs:** Process route, operation list, machine requirements, process assumptions.

**Restrictions:** Recommendations require qualified process-engineering review.

## A3 — Production Readiness

**Question:** Are the prerequisites for a controlled production launch present?

**Inputs:** Tooling status, approved process route, work instructions, training status, quality plan, supplier status, maintenance/calibration records.

**Responsibilities:** Check completeness and readiness evidence; identify missing prerequisites and unresolved approvals.

**Outputs:** Readiness checklist, gap list, conditional readiness recommendation.

**Restrictions:** Cannot declare regulatory or customer approval without authoritative records.

## A4 — Supplier Assessment

**Question:** Can required inputs be sourced under the stated constraints?

**Inputs:** BOM, approved supplier list, supplier performance data, lead times, logistics and geopolitical risk data.

**Responsibilities:** Compare supplier capability, quality, delivery, capacity, continuity, and sourcing risks.

**Outputs:** Supplier comparison, sourcing options, lead-time assumptions, supplier risk register.

**Restrictions:** Supplier scores must cite dated sources; no purchase order or supplier qualification action is performed autonomously.

## A5 — Materials & Tooling

**Question:** Which materials and tools are candidates for the requirements?

**Inputs:** Material specifications, design requirements, process route, tool library, lifecycle and compatibility data.

**Responsibilities:** Compare material properties and process compatibility; identify tooling needs, wear considerations, and substitutions.

**Outputs:** Material comparison, tooling specification, substitution candidates, unresolved qualification needs.

**Restrictions:** Substitutions require engineering and customer approval where applicable.

## A6 — Quality Assurance

**Question:** How will conformance be measured and controlled?

**Inputs:** Product requirements, critical-to-quality characteristics, process route, applicable standards, measurement capability.

**Responsibilities:** Propose inspection points, control plan, measurement methods, acceptance criteria, and defect categories.

**Outputs:** Inspection plan, control-plan draft, acceptance criteria, measurement-system assumptions.

**Restrictions:** Does not replace the organization's approved QMS or authorized quality function.

## A7 — Capacity Planning

**Question:** Can the facility meet demand and schedule?

**Inputs:** Operation times, machine availability, labor, shifts, setup times, maintenance windows, demand profile.

**Responsibilities:** Estimate throughput, utilization, bottlenecks, queueing, batch sizing, and schedule feasibility.

**Outputs:** Capacity model, schedule proposal, bottleneck analysis, assumptions.

**Restrictions:** Results are estimates until calibrated against facility data.

## A8 — Cost & Yield Analysis

**Question:** What are the economic and yield implications?

**Inputs:** Material and labor rates, process route, cycle times, scrap/rework assumptions, overhead rules, volume.

**Responsibilities:** Estimate unit cost, yield, scrap/rework, sensitivity, and cost drivers.

**Outputs:** Cost model, yield estimate, sensitivity analysis, assumptions.

**Restrictions:** Must not present estimates as quoted prices or guaranteed margins.

## A9 — Manufacturing Risk

**Question:** What could disrupt quality, delivery, cost, or continuity?

**Inputs:** Process route, supplier options, capacity plan, quality plan, historical failure data.

**Responsibilities:** Perform FMEA-style analysis, identify single points of failure, model disruption scenarios, propose mitigations.

**Outputs:** Risk register, severity/occurrence/detection rationale where data supports it, mitigation plan.

**Restrictions:** Risk priority scores are screening aids, not substitutes for engineering judgment.

## A10 — Verification

**Question:** Is the combined plan internally consistent, feasible under stated constraints, and adequately supported?

**Inputs:** All agent outputs, original requirements, constraints, evidence registry.

**Responsibilities:** Check completeness, units, revisions, dependencies, hard constraints, contradictions, and evidence traceability.

**Outputs:** PASS / CONDITIONAL / FAIL result, findings, conflict log, required human approvals.

**Restrictions:** A software PASS is not a production authorization, safety certification, or formal quality release.
