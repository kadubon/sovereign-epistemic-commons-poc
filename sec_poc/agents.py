from __future__ import annotations

from collections import Counter
from dataclasses import replace
from typing import Any

from sec_poc.commons import CommonsState
from sec_poc.schemas import Item


class WriterAgent:
    def maybe_create_summary(
        self,
        *,
        state: CommonsState,
        step: int,
        summary_interval: int,
        summary_min_items: int,
    ) -> Item | None:
        if step == 0 or step % summary_interval != 0:
            return None
        key_counts = Counter(item.normalized_key for item in state.items if item.source_type != "summary")
        if not key_counts:
            return None
        key, count = key_counts.most_common(1)[0]
        if count < summary_min_items:
            return None
        evidence_values = sorted({item.value for item in state.items if item.normalized_key == key})
        if not evidence_values:
            return None
        value = "summary:" + "|".join(evidence_values[:4])
        return Item(
            item_id=f"summary_{step}_{key.replace('.', '_')}",
            key=key,
            value=value,
            schema="new",
            parents=[item.item_id for item in state.items if item.normalized_key == key][-3:],
            pointers=[],
            cost=0.1,
            replica="replica_a",
            broker="writer_summary",
            lane="nar",
            provenance_depth=0,
            timestamp=step,
            source_type="summary",
            normalized_key=key,
            parser_valid=True,
            schema_residual=0.0,
        )


class ExitManager:
    def __init__(self) -> None:
        self.low_reserve_streak = 0
        self.low_reserve_residence_time = 0
        self.last_fork_step: int | None = None
        self.post_fork_quality_samples: list[float] = []

    def choose_action(
        self,
        *,
        state: CommonsState,
        metrics: dict[str, Any],
        config: dict[str, Any],
    ) -> str:
        reserve_floor = config["governance"]["reserve_floor"]
        low_reserve = metrics["contradiction_reserve"] < reserve_floor
        if low_reserve:
            self.low_reserve_streak += 1
            self.low_reserve_residence_time += 1
        else:
            self.low_reserve_streak = 0

        if state.cooldown_remaining > 0:
            state.cooldown_remaining -= 1
            return "stay"

        exit_policy = config["governance"]["exit_policy"]
        if exit_policy == "deterministic":
            threshold = config["governance"]["deterministic_exit_streak"]
            return "fork" if self.low_reserve_streak >= threshold else "stay"

        hazard = (
            0.42 * max(0.0, metrics["Psi_t"])
            + 0.38 * max(0.0, reserve_floor - metrics["contradiction_reserve"])
            + 0.20 * metrics["broker_concentration"]
        )
        if low_reserve and hazard >= config["governance"]["mixed_exit_threshold"]:
            return "fork"
        if low_reserve and hazard >= config["governance"]["mixed_cooldown_threshold"]:
            state.cooldown_remaining = config["governance"]["cooldown_steps"]
            return "cooldown"
        return "stay"

    def note_fork(self, *, step: int, metrics: dict[str, Any]) -> None:
        self.last_fork_step = step
        self.low_reserve_streak = 0
        self.post_fork_quality_samples.append(metrics["protected_query_accuracy"])

    def note_post_step(self, *, step: int, metrics: dict[str, Any]) -> float:
        if self.last_fork_step is None:
            return 0.0
        if 0 < step - self.last_fork_step <= 3:
            self.post_fork_quality_samples.append(metrics["protected_query_accuracy"])
        if not self.post_fork_quality_samples:
            return 0.0
        return sum(self.post_fork_quality_samples) / len(self.post_fork_quality_samples)


def apply_fork(state: CommonsState, config: dict[str, Any]) -> None:
    state.fork(max_depth_to_keep=config["governance"]["depth_cap"])
    state.cooldown_remaining = config["governance"]["cooldown_steps"]


def apply_cooldown_filter(candidates: list[Item], cooldown_active: bool) -> list[Item]:
    if not cooldown_active:
        return candidates
    filtered: list[Item] = []
    for candidate in candidates:
        if candidate.coalition_flag and candidate.provenance_depth > 1:
            continue
        filtered.append(replace(candidate))
    return filtered

