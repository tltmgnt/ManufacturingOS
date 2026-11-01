# Risk, Safety, and Security Boundaries

## 1. Intended use

Initial MADMS use is limited to manufacturing planning and decision support using synthetic or specifically authorized data. It is not a machine controller, safety instrumented system, or substitute for engineering, quality, regulatory, or customer approval.

## 2. Prohibited initial capabilities

The initial system must not:
- issue commands to CNC machines, robots, PLCs, or production equipment;
- bypass interlocks, safety procedures, or quality gates;
- autonomously approve engineering changes or material substitutions;
- autonomously qualify suppliers or issue purchase orders;
- certify regulatory compliance or product safety;
- release product to production or shipment.

## 3. Principal risks

| Risk | Control |
|---|---|
| Hallucinated process or material recommendation | Require evidence, source references, and qualified review |
| Incorrect units or tolerance interpretation | Typed units, schema validation, range checks |
| Stale CAD/BOM revision | Revision pinning and dependency invalidation |
| Supplier data outdated | Timestamp, source, confidence, refresh policy |
| Objective function hides hard constraint | Separate hard constraints from soft optimization |
| Agent disagreement | Explicit conflict record and accountable human owner |
| Prompt/tool injection in documents | Treat imported content as untrusted data; isolate tool permissions |
| Unauthorized data exposure | Least privilege, access controls, encryption, audit logging |
| Unsafe operational integration | Excluded from initial scope; separate hazard and security assessment required |

## 4. Human authorization gates

Qualified personnel must review and authorize, as applicable:
- design changes;
- process selection and process qualification;
- material substitutions;
- supplier qualification;
- quality-control plans and acceptance criteria;
- production readiness and release.

## 5. Security development requirements

Before any real enterprise or factory integration:
- threat model the system and connectors;
- establish identity and role-based access;
- secure secrets and credentials;
- log and monitor agent/tool actions;
- validate uploaded files and external content;
- conduct dependency and vulnerability scanning;
- define backup, recovery, and incident response;
- complete the organization's applicable cybersecurity review.
