from __future__ import annotations

from sec_poc.experiments import load_condition_config
from sec_poc.simulator import generate_import_stream, run_episode


def test_scripted_replay_is_deterministic() -> None:
    config = load_condition_config(
        base_config_path="configs/default_confirmatory.yaml",
        condition_name="baseline",
        mode="confirmatory",
        backend_name="scripted",
    )
    world_bundle = generate_import_stream(11, config)
    first = run_episode(seed=11, condition_name="baseline", config=config, world_bundle=world_bundle)
    second = run_episode(seed=11, condition_name="baseline", config=config, world_bundle=world_bundle)
    first_metrics = [{k: v for k, v in row.items() if k != "runtime_seconds"} for row in first["metrics"]]
    second_metrics = [{k: v for k, v in row.items() if k != "runtime_seconds"} for row in second["metrics"]]
    assert first_metrics == second_metrics
    assert first["events"] == second["events"]
