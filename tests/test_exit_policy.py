from __future__ import annotations

from sec_poc.agents import ExitManager
from sec_poc.commons import CommonsState


def test_deterministic_exit_after_streak() -> None:
    state = CommonsState(typed_lanes=True, contradiction_window=4)
    manager = ExitManager()
    config = {"governance": {"reserve_floor": 0.2, "exit_policy": "deterministic", "deterministic_exit_streak": 2}}
    metrics = {"Psi_t": 0.2, "contradiction_reserve": 0.0, "broker_concentration": 0.3, "protected_query_accuracy": 0.5}
    assert manager.choose_action(state=state, metrics=metrics, config=config) == "stay"
    assert manager.choose_action(state=state, metrics=metrics, config=config) == "fork"


def test_mixed_exit_can_cooldown_before_fork() -> None:
    state = CommonsState(typed_lanes=True, contradiction_window=4)
    manager = ExitManager()
    config = {
        "governance": {
            "reserve_floor": 0.2,
            "exit_policy": "mixed",
            "cooldown_steps": 2,
            "mixed_exit_threshold": 1.5,
            "mixed_cooldown_threshold": 0.1,
        }
    }
    metrics = {"Psi_t": 0.2, "contradiction_reserve": 0.0, "broker_concentration": 0.3, "protected_query_accuracy": 0.5}
    assert manager.choose_action(state=state, metrics=metrics, config=config) == "cooldown"
    assert state.cooldown_remaining == 2

