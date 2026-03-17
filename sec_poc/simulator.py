from __future__ import annotations

import random
import time
from dataclasses import replace
from typing import Any

from sec_poc.agents import ExitManager, WriterAgent, apply_cooldown_filter, apply_fork
from sec_poc.commons import CommonsState, normalize_key
from sec_poc.metrics import build_metrics_snapshot
from sec_poc.policies import PolicyBackend
from sec_poc.schemas import Event, Item, Pointer, QueryResult


def truth_at_step(plan: dict[int, list[tuple[str, str]]], base_truths: dict[str, str], step: int) -> dict[str, str]:
    truths = dict(base_truths)
    for event_step in sorted(plan):
        if event_step > step:
            break
        for key, value in plan[event_step]:
            truths[key] = value
    return truths


def build_truth_plan(seed: int, config: dict[str, Any]) -> tuple[dict[str, str], dict[int, list[tuple[str, str]]]]:
    rng = random.Random(seed)
    keys = list(config["world"]["key_families"])
    base_truths = {key: f"{key.replace('.', '_')}_v0" for key in keys}
    drift_plan: dict[int, list[tuple[str, str]]] = {}
    drift_keys = rng.sample(keys, k=config["world"]["drift_keys_per_episode"])
    for offset, key in enumerate(drift_keys):
        drift_step = config["world"]["drift_steps"][offset % len(config["world"]["drift_steps"])]
        drift_plan.setdefault(drift_step, []).append((key, f"{key.replace('.', '_')}_v{offset + 1}"))
    return base_truths, drift_plan


def make_item(
    *,
    item_id: str,
    key: str,
    value: str,
    schema: str,
    parents: list[str],
    pointers: list[Pointer],
    cost: float,
    replica: str,
    broker: str,
    timestamp: int,
    source_type: str,
    provenance_depth: int,
    truth_value: str,
    coalition_flag: bool,
) -> Item:
    normalized_key, residual = normalize_key(key, schema)
    parser_valid = normalized_key is not None
    hidden_truth_match = value == truth_value
    return Item(
        item_id=item_id,
        key=key,
        value=value,
        schema=schema,
        parents=parents,
        pointers=pointers,
        cost=cost,
        replica=replica,
        broker=broker,
        lane="pending",
        provenance_depth=provenance_depth,
        timestamp=timestamp,
        source_type=source_type,
        normalized_key=normalized_key,
        parser_valid=parser_valid,
        schema_residual=residual,
        hidden_truth_match=hidden_truth_match,
        contamination_flag=not hidden_truth_match and source_type in {"contaminated", "correlated"},
        contradiction_flag=not hidden_truth_match,
        stale_flag=source_type == "stale",
        coalition_flag=coalition_flag,
    )


def generate_import_stream(seed: int, config: dict[str, Any]) -> dict[str, Any]:
    rng = random.Random(seed + config["runtime"]["seed_stride"])
    steps = config["experiment"]["active_profile"]["steps"]
    replicas = config["world"]["replicas"]
    honest_brokers = config["world"]["honest_brokers"]
    coalition_brokers = config["world"]["coalition_brokers"]
    keys = list(config["world"]["key_families"])
    base_truths, drift_plan = build_truth_plan(seed, config)
    history_values = {key: [value] for key, value in base_truths.items()}
    stream: dict[int, list[Item]] = {}

    for step in range(steps):
        current_truth = truth_at_step(drift_plan, base_truths, step)
        for key, value in current_truth.items():
            if history_values[key][-1] != value:
                history_values[key].append(value)
        step_items: list[Item] = []
        imports_per_step = config["experiment"]["active_profile"]["imports_per_step"]
        target_keys = rng.sample(keys, k=min(len(keys), imports_per_step))
        drift_keys_this_step = {drift_key for drift_key, _ in drift_plan.get(step, [])}
        for index, key in enumerate(target_keys):
            source_type = "benign"
            value = current_truth[key]
            broker = rng.choice(honest_brokers)
            replica = rng.choice(replicas)
            schema = "new"
            provenance_depth = rng.choice([0, 1, 1, 2])
            coalition_flag = False

            if key in drift_keys_this_step:
                previous_values = history_values[key][:-1]
                if previous_values:
                    value = previous_values[-1]
                    source_type = "stale"
                    schema = "old"
                    provenance_depth = 2
            elif (step + index) % config["world"]["attack_interval"] == 0:
                value = f"{key.replace('.', '_')}_poison_{step // config['world']['attack_interval']}"
                source_type = "correlated"
                broker = coalition_brokers[index % len(coalition_brokers)]
                schema = "old" if index % 2 == 0 else "new"
                provenance_depth = rng.choice([3, 4, 5])
                coalition_flag = True
            elif rng.random() < 0.22:
                value = f"{key.replace('.', '_')}_alt_{step}"
                source_type = "contradictory"
                schema = "old"
                provenance_depth = rng.choice([2, 3])

            raw_key = "legacy::" + key.replace(".", "::") if schema == "old" else key
            pointers = []
            pointer_count = rng.choice([1, 2, 3])
            for pointer_index in range(pointer_count):
                verified = source_type == "benign" or (source_type == "stale" and pointer_index == 0)
                if source_type in {"correlated", "contradictory"} and pointer_index > 0:
                    verified = False
                pointers.append(Pointer(kind="anchor" if pointer_index == 0 else "relay", verified=verified))

            step_items.append(
                make_item(
                    item_id=f"{step}_{index}_{source_type}",
                    key=raw_key,
                    value=value,
                    schema=schema,
                    parents=[],
                    pointers=pointers,
                    cost=1.0 + 0.2 * len(pointers),
                    replica=replica,
                    broker=broker,
                    timestamp=step,
                    source_type=source_type,
                    provenance_depth=provenance_depth,
                    truth_value=current_truth[key],
                    coalition_flag=coalition_flag,
                )
            )

        if step % config["world"]["attack_interval"] == 0:
            target_key = rng.choice(keys)
            for burst_index in range(config["world"]["attack_burst_size"]):
                broker = coalition_brokers[burst_index % len(coalition_brokers)]
                raw_key = target_key if burst_index % 2 else "legacy::" + target_key.replace(".", "::")
                schema = "new" if burst_index % 2 else "old"
                step_items.append(
                    make_item(
                        item_id=f"{step}_burst_{burst_index}",
                        key=raw_key,
                        value=f"{target_key.replace('.', '_')}_burst_poison_{step}",
                        schema=schema,
                        parents=[],
                        pointers=[Pointer(kind="relay", verified=False), Pointer(kind="relay", verified=False)],
                        cost=1.6,
                        replica=rng.choice(replicas),
                        broker=broker,
                        timestamp=step,
                        source_type="contaminated",
                        provenance_depth=rng.choice([4, 5]),
                        truth_value=current_truth[target_key],
                        coalition_flag=True,
                    )
                )
        stream[step] = step_items

    return {"base_truths": base_truths, "drift_plan": drift_plan, "imports": stream}


def retrieve_items(state: CommonsState, key: str, top_k: int, *, lanes: set[str]) -> list[Item]:
    items = [item for item in state.items if item.normalized_key == key and item.lane in lanes]
    ordered = sorted(
        items,
        key=lambda item: (-item.visible_score, item.provenance_depth, item.timestamp, item.item_id),
    )
    return ordered[:top_k]


def answer_queries(
    *,
    state: CommonsState,
    step: int,
    truth_values: dict[str, str],
    protected_queries: list[str],
    query_top_k: int,
    policy_backend: PolicyBackend,
    seed: int,
) -> list[QueryResult]:
    results: list[QueryResult] = []
    for offset, key in enumerate(protected_queries):
        retrieved_core = retrieve_items(state, key, query_top_k, lanes={"core"})
        retrieved_non_narrative = retrieve_items(state, key, query_top_k, lanes={"core", "het"})
        decision = policy_backend.answer_query(
            key=key,
            retrieved_core=retrieved_core,
            seed=seed + step * 31 + offset,
        )
        answer = decision["answer"]
        supporting_item_id = decision["supporting_item_id"]
        answer_correct = answer == truth_values[key]
        recall_hit = any(item.value == truth_values[key] for item in retrieved_non_narrative)
        accessibility = 0.0
        for rank, item in enumerate(retrieved_non_narrative, start=1):
            if item.value == truth_values[key]:
                accessibility = 1.0 / rank
                item.served_count += 1
                break
        for item in retrieved_core:
            item.served_count += 1
        results.append(
            QueryResult(
                key=key,
                answer=answer,
                answer_correct=answer_correct,
                recall_hit=recall_hit,
                accessibility=accessibility,
                supporting_item_id=supporting_item_id,
                retrieved_item_ids=[item.item_id for item in retrieved_non_narrative],
            )
        )
    return results


def run_episode(
    *,
    seed: int,
    condition_name: str,
    config: dict[str, Any],
    world_bundle: dict[str, Any],
) -> dict[str, Any]:
    runtime_started = time.perf_counter()
    state = CommonsState(
        typed_lanes=config["governance"]["typed_lanes"],
        contradiction_window=config["governance"]["contradiction_window"],
    )
    writer = WriterAgent()
    exit_manager = ExitManager()
    policy_backend = PolicyBackend(config)
    safe_backend_name = (
        config["backend"]["policy_backend"].replace("/", "_").replace(":", "_")
    )
    run_id = f"{condition_name}_{safe_backend_name}_{seed}"
    events: list[dict[str, Any]] = []
    metric_rows: list[dict[str, Any]] = []
    psi_history: list[float] = []
    contaminated_items_admitted = 0
    recovery_window = config["experiment"].get("recovery_window", 3)
    pending_recovery_windows: list[dict[str, Any]] = []
    completed_recovery_scores: list[float] = []

    protected_queries = config["experiment"]["protected_queries"]
    steps = config["experiment"]["active_profile"]["steps"]

    for step in range(steps):
        truth_values = truth_at_step(world_bundle["drift_plan"], world_bundle["base_truths"], step)
        incoming = [replace(item) for item in world_bundle["imports"][step]]
        incoming = apply_cooldown_filter(incoming, state.cooldown_remaining > 0)

        summary_item = writer.maybe_create_summary(
            state=state,
            step=step,
            summary_interval=config["experiment"]["active_profile"]["summary_interval"],
            summary_min_items=config["governance"]["summary_min_items"],
        )
        if summary_item is not None:
            incoming.append(summary_item)

        for candidate in incoming:
            lane_before = candidate.lane
            decision = policy_backend.review_candidate(state=state, item=candidate, seed=seed + step * 97)
            candidate.lane = decision["lane"]
            accepted = decision["accept"] and candidate.lane != "rejected"
            if accepted:
                state.add_item(candidate)
                if candidate.contamination_flag:
                    contaminated_items_admitted += 1
            events.append(
                Event(
                    run_id=run_id,
                    seed=seed,
                    step=step,
                    condition=condition_name,
                    model_backend=config["backend"]["policy_backend"],
                    agent_role="reviewer",
                    action_type="review",
                    key=candidate.normalized_key,
                    candidate_value=candidate.value,
                    accepted=accepted,
                    lane_before=lane_before,
                    lane_after=candidate.lane,
                    provenance_depth=candidate.provenance_depth,
                    broker_id=candidate.broker,
                    replica_id=candidate.replica,
                    contamination_flag=candidate.contamination_flag,
                    contradiction_flag=candidate.contradiction_flag,
                    Psi_t=None,
                    contradiction_reserve=None,
                    reserve_state=None,
                    exit_action=None,
                    fork_id=state.current_fork_id,
                    extra={
                        "item_id": candidate.item_id,
                        "source_type": candidate.source_type,
                        "review_reason": decision["reason"],
                        "visible_score": candidate.visible_score,
                    },
                ).to_dict()
            )

        lane_updates = state.recalculate_lanes(
            depth_cap=config["governance"]["depth_cap"],
            promotion_min_support=config["governance"]["promotion_min_support"],
        )
        for item_id, before, after in lane_updates:
            if before == after:
                continue
            item = next(item for item in state.items if item.item_id == item_id)
            events.append(
                Event(
                    run_id=run_id,
                    seed=seed,
                    step=step,
                    condition=condition_name,
                    model_backend=config["backend"]["policy_backend"],
                    agent_role="governance",
                    action_type="lane_update",
                    key=item.normalized_key,
                    candidate_value=item.value,
                    accepted=True,
                    lane_before=before,
                    lane_after=after,
                    provenance_depth=item.provenance_depth,
                    broker_id=item.broker,
                    replica_id=item.replica,
                    contamination_flag=item.contamination_flag,
                    contradiction_flag=item.contradiction_flag,
                    Psi_t=None,
                    contradiction_reserve=None,
                    reserve_state=None,
                    exit_action=None,
                    fork_id=state.current_fork_id,
                ).to_dict()
            )

        query_results = answer_queries(
            state=state,
            step=step,
            truth_values=truth_values,
            protected_queries=protected_queries,
            query_top_k=config["experiment"]["query_top_k"],
            policy_backend=policy_backend,
            seed=seed,
        )
        for result in query_results:
            events.append(
                Event(
                    run_id=run_id,
                    seed=seed,
                    step=step,
                    condition=condition_name,
                    model_backend=config["backend"]["policy_backend"],
                    agent_role="querier",
                    action_type="query",
                    key=result.key,
                    candidate_value=result.answer,
                    accepted=result.answer_correct,
                    lane_before=None,
                    lane_after=None,
                    provenance_depth=None,
                    broker_id=None,
                    replica_id=None,
                    contamination_flag=None,
                    contradiction_flag=None,
                    Psi_t=None,
                    contradiction_reserve=None,
                    reserve_state=None,
                    exit_action=None,
                    fork_id=state.current_fork_id,
                    extra={
                        "answer_correct": result.answer_correct,
                        "recall_hit": result.recall_hit,
                        "accessibility": result.accessibility,
                        "supporting_item_id": result.supporting_item_id,
                    },
                ).to_dict()
            )

        provisional_metrics = build_metrics_snapshot(
            step=step,
            items=state.items,
            protected_keys=protected_queries,
            schedule=config["governance"]["provenance_discount"],
            contradiction_window=config["governance"]["contradiction_window"],
            epsilon_floor=config["runtime"]["epsilon_floor"],
            service_coeff=config["runtime"]["weight_service_coeff"],
            psi_history=[],
            low_reserve_residence_time=exit_manager.low_reserve_residence_time,
            realized_fork_count=state.fork_count,
            contaminated_items_admitted=contaminated_items_admitted,
            runtime_seconds=time.perf_counter() - runtime_started,
            model_call_counts={
                "total": policy_backend.ollama.usage.calls if policy_backend.ollama else 0,
                "fallback": policy_backend.fallback_count,
            },
            token_usage={
                "prompt_tokens": policy_backend.ollama.usage.prompt_tokens if policy_backend.ollama else 0,
                "completion_tokens": policy_backend.ollama.usage.completion_tokens if policy_backend.ollama else 0,
            },
            post_fork_recovery_quality=None,
            query_results=query_results,
        )
        psi_history.append(provisional_metrics.Psi_t)
        runtime_seconds = time.perf_counter() - runtime_started
        current_recovery_score = (
            0.5 * provisional_metrics.protected_query_accuracy
            + 0.5 * provisional_metrics.contradiction_reserve
        )
        next_pending_windows: list[dict[str, Any]] = []
        for window in pending_recovery_windows:
            window["scores"].append(current_recovery_score)
            window["remaining"] -= 1
            if window["remaining"] > 0:
                next_pending_windows.append(window)
            elif window["scores"]:
                completed_recovery_scores.append(sum(window["scores"]) / len(window["scores"]))
        pending_recovery_windows = next_pending_windows
        observed_recovery_scores = completed_recovery_scores + [
            sum(window["scores"]) / len(window["scores"])
            for window in pending_recovery_windows
            if window["scores"]
        ]

        metric_payload = {
            "Psi_t": provisional_metrics.Psi_t,
            "contradiction_reserve": provisional_metrics.contradiction_reserve,
            "broker_concentration": provisional_metrics.broker_concentration,
            "protected_query_accuracy": provisional_metrics.protected_query_accuracy,
        }
        action = exit_manager.choose_action(state=state, metrics=metric_payload, config=config)
        if action == "fork":
            apply_fork(state, config)
            pending_recovery_windows.append({"remaining": recovery_window, "scores": []})
        snapshot = build_metrics_snapshot(
            step=step,
            items=state.items,
            protected_keys=protected_queries,
            schedule=config["governance"]["provenance_discount"],
            contradiction_window=config["governance"]["contradiction_window"],
            epsilon_floor=config["runtime"]["epsilon_floor"],
            service_coeff=config["runtime"]["weight_service_coeff"],
            psi_history=psi_history,
            low_reserve_residence_time=exit_manager.low_reserve_residence_time,
            realized_fork_count=state.fork_count,
            contaminated_items_admitted=contaminated_items_admitted,
            runtime_seconds=runtime_seconds,
            model_call_counts={
                "total": policy_backend.ollama.usage.calls if policy_backend.ollama else 0,
                "fallback": policy_backend.fallback_count,
            },
            token_usage={
                "prompt_tokens": policy_backend.ollama.usage.prompt_tokens if policy_backend.ollama else 0,
                "completion_tokens": policy_backend.ollama.usage.completion_tokens if policy_backend.ollama else 0,
            },
            post_fork_recovery_quality=(
                sum(observed_recovery_scores) / len(observed_recovery_scores)
                if observed_recovery_scores
                else None
            ),
            query_results=query_results,
        )
        metric_rows.append(snapshot.to_dict())
        reserve_state = "low" if snapshot.contradiction_reserve < config["governance"]["reserve_floor"] else "ok"
        events.append(
            Event(
                run_id=run_id,
                seed=seed,
                step=step,
                condition=condition_name,
                model_backend=config["backend"]["policy_backend"],
                agent_role="exit_manager",
                action_type="exit",
                key=None,
                candidate_value=None,
                accepted=None,
                lane_before=None,
                lane_after=None,
                provenance_depth=None,
                broker_id=None,
                replica_id=None,
                contamination_flag=None,
                contradiction_flag=None,
                Psi_t=snapshot.Psi_t,
                contradiction_reserve=snapshot.contradiction_reserve,
                reserve_state=reserve_state,
                exit_action=action,
                fork_id=state.current_fork_id,
                extra={
                    "realized_fork_count": state.fork_count,
                    "low_reserve_residence_time": exit_manager.low_reserve_residence_time,
                },
            ).to_dict()
        )

    return {
        "run_id": run_id,
        "events": events,
        "metrics": metric_rows,
        "final_state_items": [item.to_dict() for item in state.items],
    }
