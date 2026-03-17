from __future__ import annotations

from sec_poc.metrics import contamination_potential, contradiction_reserve, summarize_psi_series
from sec_poc.schemas import Item, Pointer


def make_item(name: str, value: str, lane: str, depth: int, truth_match: bool) -> Item:
    return Item(
        item_id=name,
        key="claim.alpha",
        value=value,
        schema="new",
        parents=[],
        pointers=[Pointer(kind="anchor", verified=True)],
        cost=1.0,
        replica="r1",
        broker=f"b_{name}",
        lane=lane,
        provenance_depth=depth,
        timestamp=0,
        source_type="benign",
        normalized_key="claim.alpha",
        hidden_truth_match=truth_match,
    )


def test_contamination_potential_increases_with_depth_discounted_mass() -> None:
    items = [
        make_item("a", "truth", "core", 0, True),
        make_item("b", "wrong", "core", 5, False),
    ]
    psi_depth, _, _ = contamination_potential(items, schedule="depth", epsilon_floor=0.02, service_coeff=0.25)
    psi_flat, _, _ = contamination_potential(items, schedule="flat", epsilon_floor=0.02, service_coeff=0.25)
    assert psi_depth > psi_flat


def test_contradiction_reserve_positive_when_het_keeps_conflict() -> None:
    items = [
        make_item("a", "truth", "core", 0, True),
        make_item("b", "other", "het", 2, False),
    ]
    reserve = contradiction_reserve(items, ["claim.alpha"], contradiction_window=4)
    assert reserve > 0


def test_all_negative_psi_series_keeps_negative_max_observed_and_zero_positive_excursion() -> None:
    mean_psi, max_psi_observed, max_positive_excursion = summarize_psi_series([-0.5, -0.2, -0.1])
    assert mean_psi < 0
    assert max_psi_observed == -0.1
    assert max_positive_excursion == 0.0
