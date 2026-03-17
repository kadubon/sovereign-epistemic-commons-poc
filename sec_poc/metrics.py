from __future__ import annotations

import math
from collections import Counter

from sec_poc.schemas import Item, MetricsSnapshot, QueryResult


def provenance_credit(depth: int, schedule: str) -> float:
    if depth < 0:
        raise ValueError("provenance depth must be non-negative")
    if schedule == "flat":
        return 0.65 if depth < 99 else 0.0
    if schedule == "mild":
        return math.exp(-0.25 * depth)
    if schedule == "depth":
        return math.exp(-0.55 * depth)
    if schedule == "strong":
        return math.exp(-0.9 * depth)
    raise ValueError(f"unknown provenance discount schedule: {schedule}")


def item_weight(item: Item, service_coeff: float) -> float:
    return 1.0 + service_coeff * item.served_count


def observable_exogeneity_credit(item: Item, schedule: str) -> float:
    if not item.pointers:
        pointer_credit = 0.0
    else:
        pointer_credit = sum(1 for pointer in item.pointers if pointer.verified) / len(item.pointers)
    schema_credit = max(0.0, 1.0 - item.schema_residual)
    provenance = provenance_credit(item.provenance_depth, schedule)
    return provenance * (0.6 * pointer_credit + 0.4 * schema_credit)


def contamination_potential(
    items: list[Item],
    *,
    schedule: str,
    epsilon_floor: float,
    service_coeff: float,
) -> tuple[float, float, float]:
    if not items:
        return 0.0, 0.0, 1.0
    raw_weights = [item_weight(item, service_coeff) for item in items]
    total_weight = sum(raw_weights)
    normalized_weights = [weight / total_weight for weight in raw_weights]
    x_exo = sum(
        observable_exogeneity_credit(item, schedule) * normalized_weight
        for item, normalized_weight in zip(items, normalized_weights, strict=True)
    )
    endogenous = 1.0 - x_exo
    psi_t = math.log((endogenous + epsilon_floor) / (x_exo + epsilon_floor))
    return psi_t, x_exo, endogenous


def contradiction_reserve(items: list[Item], protected_keys: list[str], contradiction_window: int) -> float:
    by_key: dict[str, list[Item]] = {key: [] for key in protected_keys}
    for item in items:
        if item.normalized_key in by_key and item.lane in {"core", "het"}:
            by_key[item.normalized_key].append(item)
    if not by_key:
        return 0.0
    per_key_scores: list[float] = []
    for key_items in by_key.values():
        value_counter = Counter(item.value for item in key_items)
        if len(value_counter) <= 1:
            per_key_scores.append(0.0)
            continue
        dominant_value, _ = value_counter.most_common(1)[0]
        contradictory_mass = 0.0
        total_mass = 0.0
        seen_brokers: set[str] = set()
        for item in key_items:
            mass = 1.0 / (1.0 + item.provenance_depth)
            total_mass += mass
            if item.value != dominant_value and item.provenance_depth <= contradiction_window:
                contradictory_mass += mass
                seen_brokers.add(item.broker)
        if total_mass == 0:
            per_key_scores.append(0.0)
            continue
        diversity_multiplier = min(1.0, 0.5 + 0.25 * len(seen_brokers))
        per_key_scores.append(min(1.0, (contradictory_mass / total_mass) * diversity_multiplier))
    return sum(per_key_scores) / len(per_key_scores)


def lane_occupancy(items: list[Item]) -> dict[str, float]:
    counts = Counter(item.lane for item in items)
    total = max(1, sum(counts.values()))
    return {
        "core": counts.get("core", 0) / total,
        "het": counts.get("het", 0) / total,
        "nar": counts.get("nar", 0) / total,
    }


def false_core_admission_rate(items: list[Item]) -> float:
    core_items = [item for item in items if item.lane == "core"]
    if not core_items:
        return 0.0
    false_items = [item for item in core_items if not item.hidden_truth_match]
    return len(false_items) / len(core_items)


def broker_concentration(items: list[Item]) -> float:
    visible_items = [item for item in items if item.lane in {"core", "het"}]
    if not visible_items:
        return 0.0
    counts = Counter(item.broker for item in visible_items)
    total = sum(counts.values())
    return sum((count / total) ** 2 for count in counts.values())


def summarize_queries(query_results: list[QueryResult]) -> tuple[float, float, float]:
    if not query_results:
        return 0.0, 0.0, 0.0
    accuracy = sum(1 for result in query_results if result.answer_correct) / len(query_results)
    recall = sum(1 for result in query_results if result.recall_hit) / len(query_results)
    accessibility = sum(result.accessibility for result in query_results) / len(query_results)
    return accuracy, recall, accessibility


def summarize_psi_series(psi_history: list[float]) -> tuple[float, float, float]:
    if not psi_history:
        return 0.0, 0.0, 0.0
    mean_psi = sum(psi_history) / len(psi_history)
    max_psi_observed = max(psi_history)
    max_positive_excursion = max(max(psi, 0.0) for psi in psi_history)
    return mean_psi, max_psi_observed, max_positive_excursion


def build_metrics_snapshot(
    *,
    step: int,
    items: list[Item],
    protected_keys: list[str],
    schedule: str,
    contradiction_window: int,
    epsilon_floor: float,
    service_coeff: float,
    psi_history: list[float],
    low_reserve_residence_time: int,
    realized_fork_count: int,
    contaminated_items_admitted: int,
    runtime_seconds: float,
    model_call_counts: dict[str, int],
    token_usage: dict[str, int],
    post_fork_recovery_quality: float,
    query_results: list[QueryResult],
) -> MetricsSnapshot:
    psi_t, _, _ = contamination_potential(
        items,
        schedule=schedule,
        epsilon_floor=epsilon_floor,
        service_coeff=service_coeff,
    )
    accuracy, recall, accessibility = summarize_queries(query_results)
    mean_psi, max_psi_observed, max_positive_excursion = summarize_psi_series(psi_history)
    return MetricsSnapshot(
        step=step,
        Psi_t=psi_t,
        mean_psi=mean_psi,
        max_psi_observed=max_psi_observed,
        max_positive_excursion=max_positive_excursion,
        contradiction_reserve=contradiction_reserve(items, protected_keys, contradiction_window),
        false_core_admission_rate=false_core_admission_rate(items),
        protected_query_accuracy=accuracy,
        protected_query_recall=recall,
        accessibility_proxy=accessibility,
        low_reserve_residence_time=low_reserve_residence_time,
        realized_fork_count=realized_fork_count,
        contaminated_items_admitted=contaminated_items_admitted,
        lane_occupancy_ratios=lane_occupancy(items),
        runtime_seconds=runtime_seconds,
        model_call_counts=model_call_counts,
        token_usage=token_usage,
        broker_concentration=broker_concentration(items),
        post_fork_recovery_quality=post_fork_recovery_quality,
        mean_Psi_t=mean_psi,
        maximal_contamination_excursion=max_positive_excursion,
    )
