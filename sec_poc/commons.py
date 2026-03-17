from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import replace
from typing import Iterable

from sec_poc.schemas import Item


def normalize_key(raw_key: str, schema: str) -> tuple[str | None, float]:
    key = raw_key.strip().lower()
    if schema == "new":
        return key, 0.0
    if schema == "old":
        key = key.replace("legacy::", "")
        key = key.replace("claim/", "claim.")
        key = key.replace("::", ".")
        key = key.replace("_", ".")
        return key, 0.18
    return None, 1.0


class CommonsState:
    def __init__(self, *, typed_lanes: bool, contradiction_window: int):
        self.typed_lanes = typed_lanes
        self.contradiction_window = contradiction_window
        self.items: list[Item] = []
        self.current_fork_id = "root"
        self.cooldown_remaining = 0
        self.fork_count = 0

    def clone_items(self) -> list[Item]:
        return [replace(item) for item in self.items]

    def add_item(self, item: Item) -> None:
        self.items.append(item)

    def non_narrative_items(self) -> list[Item]:
        return [item for item in self.items if item.lane in {"core", "het"}]

    def items_for_key(self, key: str, *, lanes: Iterable[str] | None = None) -> list[Item]:
        lane_filter = set(lanes) if lanes is not None else None
        return [
            item
            for item in self.items
            if item.normalized_key == key and (lane_filter is None or item.lane in lane_filter)
        ]

    def dominant_value(self, key: str) -> str | None:
        core_items = self.items_for_key(key, lanes={"core"})
        if not core_items:
            return None
        counts = Counter(item.value for item in core_items)
        return counts.most_common(1)[0][0]

    def support_count(self, key: str, value: str) -> int:
        brokers = {
            item.broker
            for item in self.non_narrative_items()
            if item.normalized_key == key and item.value == value
        }
        return len(brokers)

    def recalculate_lanes(self, *, depth_cap: int, promotion_min_support: int) -> list[tuple[str, str, str]]:
        if not self.typed_lanes:
            updates: list[tuple[str, str, str]] = []
            for item in self.items:
                before = item.lane
                if item.source_type == "summary":
                    item.lane = "nar"
                elif item.lane != "rejected":
                    item.lane = "core"
                updates.append((item.item_id, before, item.lane))
            return updates

        updates: list[tuple[str, str, str]] = []
        grouped: dict[str, list[Item]] = defaultdict(list)
        for item in self.items:
            grouped[item.normalized_key or item.key].append(item)

        for key_items in grouped.values():
            evidence_items = [item for item in key_items if item.source_type != "summary"]
            support_scores: Counter[str] = Counter()
            for item in evidence_items:
                weight = 1.0 if item.provenance_depth <= depth_cap else 0.5
                support_scores[item.value] += weight
            dominant_value = support_scores.most_common(1)[0][0] if support_scores else None
            for item in key_items:
                before = item.lane
                if item.source_type == "summary":
                    item.lane = "nar"
                elif dominant_value is None:
                    item.lane = "nar"
                elif item.value == dominant_value and (
                    item.provenance_depth <= depth_cap
                    or self.support_count(item.normalized_key or item.key, item.value) >= promotion_min_support
                ):
                    item.lane = "core"
                elif item.provenance_depth <= self.contradiction_window:
                    item.lane = "het"
                else:
                    item.lane = "nar"
                updates.append((item.item_id, before, item.lane))
        return updates

    def fork(self, *, max_depth_to_keep: int) -> None:
        kept_items: list[Item] = []
        for item in self.items:
            if item.source_type == "summary":
                continue
            if item.provenance_depth <= max_depth_to_keep and item.lane == "core":
                item.fork_id = f"fork_{self.fork_count + 1}"
                kept_items.append(item)
        self.fork_count += 1
        self.current_fork_id = f"fork_{self.fork_count}"
        self.items = kept_items

