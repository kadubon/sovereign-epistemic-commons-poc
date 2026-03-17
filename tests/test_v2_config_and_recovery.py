from __future__ import annotations

from sec_poc.experiments import load_condition_config, load_yaml
from sec_poc.simulator import generate_import_stream, run_episode


def test_tuned_demo_is_not_the_public_default() -> None:
    default_confirmatory = load_yaml("configs/default_confirmatory.yaml")
    tuned_demo = load_yaml("configs/tuned_demo.yaml")
    assert default_confirmatory["experiment"]["public_entrypoint"] is True
    assert tuned_demo["experiment"]["public_entrypoint"] is False


def test_no_fork_yields_na_recovery_metric() -> None:
    config = load_condition_config(
        base_config_path="configs/default_confirmatory.yaml",
        condition_name="full_sec_lite",
        mode="confirmatory",
        backend_name="scripted",
    )
    config["governance"]["mixed_exit_threshold"] = 999.0
    config["governance"]["mixed_cooldown_threshold"] = 999.0
    world_bundle = generate_import_stream(101, config)
    result = run_episode(seed=101, condition_name="full_sec_lite", config=config, world_bundle=world_bundle)
    last = result["metrics"][-1]
    assert last["realized_fork_count"] == 0
    assert last["post_fork_recovery_quality"] is None


def test_fork_stress_can_produce_recovery_metric_when_forks_occur() -> None:
    config = load_condition_config(
        base_config_path="configs/fork_stress.yaml",
        condition_name="lanes_discount",
        mode="fork_eval",
        backend_name="scripted",
    )
    world_bundle = generate_import_stream(11, config)
    result = run_episode(seed=11, condition_name="lanes_discount", config=config, world_bundle=world_bundle)
    last = result["metrics"][-1]
    assert last["realized_fork_count"] > 0
    assert last["post_fork_recovery_quality"] is not None
