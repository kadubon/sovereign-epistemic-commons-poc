from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class Pointer:
    kind: str
    verified: bool


@dataclass
class Item:
    item_id: str
    key: str
    value: str
    schema: str
    parents: list[str]
    pointers: list[Pointer]
    cost: float
    replica: str
    broker: str
    lane: str
    provenance_depth: int
    timestamp: int
    source_type: str
    fork_id: str = "root"
    normalized_key: str | None = None
    parser_valid: bool = True
    schema_residual: float = 0.0
    visible_score: float = 0.0
    served_count: int = 0
    hidden_truth_match: bool = False
    contamination_flag: bool = False
    contradiction_flag: bool = False
    stale_flag: bool = False
    coalition_flag: bool = False

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["pointers"] = [asdict(pointer) for pointer in self.pointers]
        return payload


@dataclass
class QueryResult:
    key: str
    answer: str | None
    answer_correct: bool
    recall_hit: bool
    accessibility: float
    supporting_item_id: str | None
    retrieved_item_ids: list[str]


@dataclass
class Event:
    run_id: str
    seed: int
    step: int
    condition: str
    model_backend: str
    agent_role: str
    action_type: str
    key: str | None
    candidate_value: str | None
    accepted: bool | None
    lane_before: str | None
    lane_after: str | None
    provenance_depth: int | None
    broker_id: str | None
    replica_id: str | None
    contamination_flag: bool | None
    contradiction_flag: bool | None
    Psi_t: float | None
    contradiction_reserve: float | None
    reserve_state: str | None
    exit_action: str | None
    fork_id: str | None
    extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload.update(payload.pop("extra"))
        return payload


@dataclass
class MetricsSnapshot:
    step: int
    Psi_t: float
    mean_psi: float
    max_psi_observed: float
    max_positive_excursion: float
    contradiction_reserve: float
    false_core_admission_rate: float
    protected_query_accuracy: float
    protected_query_recall: float
    accessibility_proxy: float
    low_reserve_residence_time: int
    realized_fork_count: int
    contaminated_items_admitted: int
    lane_occupancy_ratios: dict[str, float]
    runtime_seconds: float
    model_call_counts: dict[str, int]
    token_usage: dict[str, int]
    broker_concentration: float
    post_fork_recovery_quality: float | None
    mean_Psi_t: float | None = None
    maximal_contamination_excursion: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
