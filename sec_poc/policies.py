from __future__ import annotations

import json
from typing import Any

from sec_poc.commons import CommonsState
from sec_poc.metrics import provenance_credit
from sec_poc.ollama_backend import OllamaBackend
from sec_poc.schemas import Item


def _pointer_quality(item: Item, pointer_budget: int) -> float:
    if not item.pointers:
        return 0.0
    checked = item.pointers[:pointer_budget]
    verified = sum(1 for pointer in checked if pointer.verified)
    return verified / max(1, len(checked))


def _visible_candidate_features(
    state: CommonsState,
    item: Item,
    config: dict[str, Any],
) -> dict[str, Any]:
    key = item.normalized_key or item.key
    same_key_items = state.items_for_key(key, lanes={"core", "het"})
    recent_same_broker = sum(1 for candidate in same_key_items if candidate.broker == item.broker)
    dominant_value = state.dominant_value(key)
    depth_schedule = config["governance"]["provenance_discount"]
    depth_weight = provenance_credit(item.provenance_depth, depth_schedule)
    pointer_quality = _pointer_quality(item, config["world"]["pointer_budget"])
    schema_score = 1.0 - item.schema_residual
    visible_score = (
        0.42 * pointer_quality
        + 0.28 * schema_score
        + 0.22 * depth_weight
        - config["governance"]["coalition_penalty"] * min(1.0, recent_same_broker / 3.0)
    )
    item.visible_score = visible_score
    return {
        "key": key,
        "value": item.value,
        "schema": item.schema,
        "pointer_quality": round(pointer_quality, 3),
        "schema_score": round(schema_score, 3),
        "depth_weight": round(depth_weight, 3),
        "visible_score": round(visible_score, 3),
        "dominant_value": dominant_value,
        "typed_lanes": config["governance"]["typed_lanes"],
        "depth_cap": config["governance"]["depth_cap"],
        "contradiction_window": config["governance"]["contradiction_window"],
    }


def scripted_review_decision(
    state: CommonsState,
    item: Item,
    config: dict[str, Any],
) -> dict[str, Any]:
    features = _visible_candidate_features(state, item, config)
    if not item.parser_valid:
        return {"accept": False, "lane": "rejected", "reason": "parser_failed", "features": features}

    core_threshold = config["governance"]["review_core_threshold"]
    het_threshold = config["governance"]["review_het_threshold"]
    typed_lanes = config["governance"]["typed_lanes"]
    dominant_value = features["dominant_value"]

    if features["visible_score"] < het_threshold:
        lane = "nar" if item.source_type == "summary" else "rejected"
        return {"accept": lane != "rejected", "lane": lane, "reason": "low_score", "features": features}

    if not typed_lanes:
        lane = "nar" if item.source_type == "summary" else "core"
        accept = lane != "rejected" and features["visible_score"] >= core_threshold - 0.08
        return {
            "accept": accept,
            "lane": lane if accept else "rejected",
            "reason": "baseline_accept" if accept else "baseline_reject",
            "features": features,
        }

    if item.source_type == "summary":
        return {"accept": True, "lane": "nar", "reason": "summary", "features": features}

    if dominant_value is None and features["visible_score"] >= core_threshold:
        return {"accept": True, "lane": "core", "reason": "bootstrapped_core", "features": features}
    if dominant_value == item.value and features["visible_score"] >= core_threshold:
        return {"accept": True, "lane": "core", "reason": "supports_dominant", "features": features}
    if item.provenance_depth <= config["governance"]["contradiction_window"]:
        return {"accept": True, "lane": "het", "reason": "held_as_heterodoxy", "features": features}
    return {"accept": False, "lane": "rejected", "reason": "outside_window", "features": features}


def scripted_query_decision(key: str, retrieved_core: list[Item]) -> dict[str, Any]:
    if not retrieved_core:
        return {"answer": None, "supporting_item_id": None}
    ordered = sorted(
        retrieved_core,
        key=lambda item: (-item.visible_score, item.provenance_depth, item.timestamp, item.item_id),
    )
    winner = ordered[0]
    return {"answer": winner.value, "supporting_item_id": winner.item_id}


class PolicyBackend:
    def __init__(self, config: dict[str, Any]):
        self.config = config
        self.backend_name = config["backend"]["policy_backend"]
        self.llm_roles = set(config["backend"].get("llm_roles", []))
        self.ollama = OllamaBackend(config) if self.backend_name.startswith("ollama/") else None
        self.fallback_count = 0

    def review_candidate(self, *, state: CommonsState, item: Item, seed: int) -> dict[str, Any]:
        fallback = scripted_review_decision(state, item, self.config)
        if self.backend_name == "scripted" or "review" not in self.llm_roles or self.ollama is None:
            return fallback
        prompt = {
            "task": "review_candidate",
            "instruction": (
                "Return strict JSON with keys accept (boolean), lane "
                "(one of core, het, nar, rejected), and reason (short string)."
            ),
            "candidate": item.to_dict(),
            "fallback_features": fallback["features"],
        }
        response = self.ollama.complete_json(
            backend_name=self.backend_name,
            system_prompt="You are a deterministic reviewer for an observable-only governance simulator.",
            user_prompt=json.dumps(prompt, sort_keys=True),
            seed=seed,
        )
        if not self._valid_review_response(response):
            self.fallback_count += 1
            return fallback
        return {
            "accept": bool(response["accept"]),
            "lane": response["lane"],
            "reason": str(response["reason"]),
            "features": fallback["features"],
        }

    def answer_query(self, *, key: str, retrieved_core: list[Item], seed: int) -> dict[str, Any]:
        fallback = scripted_query_decision(key, retrieved_core)
        if self.backend_name == "scripted" or "query" not in self.llm_roles or self.ollama is None:
            return fallback
        prompt = {
            "task": "answer_query",
            "instruction": (
                "Return strict JSON with keys answer and supporting_item_id. "
                "Use only the provided core items. If no answer exists, set answer to null."
            ),
            "query_key": key,
            "retrieved_core": [item.to_dict() for item in retrieved_core],
        }
        response = self.ollama.complete_json(
            backend_name=self.backend_name,
            system_prompt="You are a deterministic query selector for an observable-only governance simulator.",
            user_prompt=json.dumps(prompt, sort_keys=True),
            seed=seed,
        )
        if not self._valid_query_response(response):
            self.fallback_count += 1
            return fallback
        return {
            "answer": response.get("answer"),
            "supporting_item_id": response.get("supporting_item_id"),
        }

    @staticmethod
    def _valid_review_response(response: dict[str, Any] | None) -> bool:
        return bool(
            isinstance(response, dict)
            and isinstance(response.get("accept"), bool)
            and response.get("lane") in {"core", "het", "nar", "rejected"}
            and isinstance(response.get("reason"), str)
        )

    @staticmethod
    def _valid_query_response(response: dict[str, Any] | None) -> bool:
        if not isinstance(response, dict):
            return False
        if "answer" not in response:
            return False
        supporting_item_id = response.get("supporting_item_id")
        return supporting_item_id is None or isinstance(supporting_item_id, str)
