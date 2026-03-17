from __future__ import annotations

from sec_poc.commons import CommonsState
from sec_poc.schemas import Item, Pointer
from sec_poc.simulator import retrieve_items


def test_het_lane_not_used_for_direct_core_answers() -> None:
    state = CommonsState(typed_lanes=True, contradiction_window=4)
    state.add_item(
        Item(
            item_id="core1",
            key="claim.alpha",
            value="truth",
            schema="new",
            parents=[],
            pointers=[Pointer(kind="anchor", verified=True)],
            cost=1.0,
            replica="r1",
            broker="b1",
            lane="core",
            provenance_depth=0,
            timestamp=0,
            source_type="benign",
            normalized_key="claim.alpha",
        )
    )
    state.add_item(
        Item(
            item_id="het1",
            key="claim.alpha",
            value="other",
            schema="new",
            parents=[],
            pointers=[Pointer(kind="anchor", verified=True)],
            cost=1.0,
            replica="r1",
            broker="b2",
            lane="het",
            provenance_depth=1,
            timestamp=0,
            source_type="contradictory",
            normalized_key="claim.alpha",
        )
    )
    retrieved = retrieve_items(state, "claim.alpha", 5, lanes={"core"})
    assert [item.item_id for item in retrieved] == ["core1"]

