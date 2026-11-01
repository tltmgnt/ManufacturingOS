"""Versioned, JSON-compatible domain contracts for synthetic planning."""
from dataclasses import asdict, dataclass, field
from datetime import datetime
import hashlib
import json
import math
from typing import Any

VERSION = "1.0"


def digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, allow_nan=False).encode()).hexdigest()


def nonempty(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be a nonempty string")
    return value


@dataclass(frozen=True)
class Quantity:
    value: float
    unit: str

    @classmethod
    def parse(cls, data: Any) -> "Quantity":
        if not isinstance(data, dict) or set(data) != {"value", "unit"}:
            raise ValueError("quantity requires value and unit")
        v = data["value"]
        if type(v) not in (int, float) or not math.isfinite(v) or v <= 0:
            raise ValueError("quantity value must be finite and positive")
        return cls(v, nonempty(data["unit"], "unit"))


@dataclass(frozen=True)
class EvidenceRecord:
    evidence_id: str
    source_uri: str
    source_owner: str
    revision: str
    captured_at: str
    evidence_type: str
    claim_ids: list[str]
    content_hash: str | None = None

    @classmethod
    def parse(cls, data: dict) -> "EvidenceRecord":
        record = cls(**data)
        for name in ("evidence_id", "source_uri", "source_owner", "revision", "evidence_type"):
            nonempty(getattr(record, name), name)
        stamp = datetime.fromisoformat(nonempty(record.captured_at, "captured_at").replace("Z", "+00:00"))
        if stamp.utcoffset() is None or stamp.utcoffset().total_seconds() != 0:
            raise ValueError("evidence timestamps must use UTC")
        if not isinstance(record.claim_ids, list) or not record.claim_ids:
            raise ValueError("evidence requires claim IDs")
        for claim in record.claim_ids:
            nonempty(claim, "claim_id")
        if record.content_hash is not None:
            nonempty(record.content_hash, "content_hash")
        return record


@dataclass(frozen=True)
class ManufacturingInput:
    schema_version: str
    package_id: str
    revision: str
    product_id: str
    design_revision: str
    bom: list[dict]
    requirements: list[dict]
    demand: Quantity
    facility: dict
    constraints: list[dict]
    evidence: list[EvidenceRecord]

    @classmethod
    def from_dict(cls, data: dict) -> "ManufacturingInput":
        if not isinstance(data, dict):
            raise ValueError("input must be an object")
        required = set(cls.__dataclass_fields__)
        if set(data) != required:
            raise ValueError(f"input fields differ: missing={sorted(required-set(data))}, unknown={sorted(set(data)-required)}")
        if data["schema_version"] != VERSION:
            raise ValueError("unsupported schema_version")
        for name in ("package_id", "revision", "product_id", "design_revision"):
            nonempty(data[name], name)
        for name in ("bom", "requirements", "constraints", "evidence"):
            if not isinstance(data[name], list):
                raise ValueError(f"{name} must be a list")
        if not data["bom"] or not data["requirements"]:
            raise ValueError("BOM and requirements cannot be empty")
        for row in data["bom"]:
            if not isinstance(row, dict) or set(row) != {"item_id", "revision", "quantity"}:
                raise ValueError("BOM item requires item_id, revision, quantity")
            nonempty(row["item_id"], "item_id")
            nonempty(row["revision"], "BOM revision")
            Quantity.parse(row["quantity"])
        if len({r["item_id"] for r in data["bom"]}) != len(data["bom"]):
            raise ValueError("duplicate BOM item ID")
        claims = set()
        for row in data["requirements"]:
            if not isinstance(row, dict) or set(row) != {"requirement_id", "description"}:
                raise ValueError("requirement requires requirement_id and description")
            rid = nonempty(row["requirement_id"], "requirement_id")
            if rid in claims:
                raise ValueError("duplicate requirement ID")
            claims.add(rid)
            nonempty(row["description"], "description")
        facility = data["facility"]
        if not isinstance(facility, dict) or set(facility) != {"facility_id", "revision"}:
            raise ValueError("facility requires facility_id and revision")
        for k, v in facility.items():
            nonempty(v, k)
        ids = set()
        for row in data["constraints"]:
            if not isinstance(row, dict) or set(row) != {"constraint_id", "kind", "satisfied", "issue"}:
                raise ValueError("constraint requires constraint_id, kind, satisfied, issue")
            cid = nonempty(row["constraint_id"], "constraint_id")
            if cid in ids:
                raise ValueError("duplicate constraint ID")
            ids.add(cid)
            if row["kind"] not in ("hard", "conditional", "soft"):
                raise ValueError("invalid constraint kind")
            if row["satisfied"] is not None and type(row["satisfied"]) is not bool:
                raise ValueError("constraint satisfied must be boolean or null")
            if row["satisfied"] is not True:
                nonempty(row["issue"], "unresolved constraint issue")
            elif row["issue"] is not None:
                raise ValueError("satisfied constraint issue must be null")
        evidence = [EvidenceRecord.parse(e) for e in data["evidence"]]
        if len({e.evidence_id for e in evidence}) != len(evidence):
            raise ValueError("duplicate evidence ID")
        for e in evidence:
            if not set(e.claim_ids) <= claims:
                raise ValueError("evidence refers to unknown claim")
        return cls(**{**data, "demand": Quantity.parse(data["demand"]), "evidence": evidence})

    @property
    def fingerprint(self) -> str:
        return digest(asdict(self))


@dataclass
class AgentResult:
    agent_id: str
    agent_version: str
    schema_version: str
    status: str
    revision: str
    input_fingerprint: str
    upstream_revisions: dict[str, str]
    findings: dict
    assumptions: list[str]
    evidence_refs: list[str]
    uncertainty: str
    open_issues: list[str]


@dataclass
class Verification:
    status: str
    findings: list[str]
    conflicts: list[dict] = field(default_factory=list)


@dataclass
class ManufacturingPlan:
    schema_version: str
    package_id: str
    input_fingerprint: str
    results: dict[str, AgentResult]
    verification: Verification
    state_history: list[str]
    required_approvals: list[str]
    approval_state: str = "PENDING_HUMAN_REVIEW"
    production_authorized: bool = False
