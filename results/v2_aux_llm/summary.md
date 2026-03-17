# V2 Summary

This file is an auto-generated descriptive summary of existing results.
Scripted runs are the primary evidence in this repository. Auxiliary Gemma runs are backend sanity checks only.
Where present, `run_uid` is the canonical globally unique run identifier; `run_id` is a legacy short identifier retained for compatibility.

## aux_llm / default_confirmatory / full_sec_lite

| metric | mean | std | 95% bootstrap CI | n |
| --- | ---: | ---: | ---: | ---: |
| `mean_psi` | -0.602 | 0.295 | [-0.896, -0.307] | 4 |
| `max_psi_observed` | -0.033 | 0.700 | [-0.733, 0.666] | 4 |
| `max_positive_excursion` | 0.333 | 0.333 | [0.000, 0.666] | 4 |
| `contaminated_items_admitted` | 0.000 | 0.000 | [0.000, 0.000] | 4 |
| `contradiction_reserve` | 0.000 | 0.000 | [0.000, 0.000] | 4 |
| `false_core_admission_rate` | 0.000 | 0.000 | [0.000, 0.000] | 4 |
| `protected_query_accuracy` | 1.000 | 0.000 | [1.000, 1.000] | 4 |
| `protected_query_recall` | 1.000 | 0.000 | [1.000, 1.000] | 4 |
| `low_reserve_residence_time` | 24.000 | 0.000 | [24.000, 24.000] | 4 |
| `realized_fork_count` | 0.000 | 0.000 | [0.000, 0.000] | 4 |
| `post_fork_recovery_quality` | NA | NA | NA | 0 |

## Paired Effect Summaries

| label | matched seeds | mean difference (right-left) |
| --- | ---: | ---: |
| H1 mean_psi | 0 | NA |
| H1 max_positive_excursion | 0 | NA |
| H2 false_core | 0 | NA |
| H2 accuracy | 0 | NA |
| H3 low_reserve | 0 | NA |
| H3 fork_count | 0 | NA |
| H3 recovery | 0 | NA |

## Auxiliary Backend Checks

| backend | runs | mean accuracy | mean recall |
| --- | ---: | ---: | ---: |
| `ollama/gemma3:1b` | 2 | 1.000 | 1.000 |
| `ollama/gemma3:4b` | 2 | 1.000 | 1.000 |
