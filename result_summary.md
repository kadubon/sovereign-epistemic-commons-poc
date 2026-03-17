# SEC PoC v2 Result Summary

## Scope

This report replaces the earlier tuned-demo summary with a v2 reading of the repository as it now stands.

The repository now contains three distinct evidence layers:

- `results/v1_exploratory/`: historical exploratory outputs from the earlier tuned/demo phase
- `results/v2_confirmatory/`: the main scripted v2 evidence
- `results/v2_aux_llm/`: auxiliary Gemma backend checks

The main goal of v2 was not to force clean wins on every hypothesis. It was to make the PoC more scientifically defensible by separating exploratory from confirmatory-style worlds, fixing metric semantics, and ensuring H3 actually observes measurable fork recovery.

Result bookkeeping note:

- `run_id` is retained as a legacy short identifier
- `run_uid` is now the canonical globally unique identifier in patched metrics CSVs and manifests
- existing raw JSONL logs may still carry only the legacy `run_id`

## What Changed In v2

Relative to the earlier exploratory version, v2 made five substantive changes:

1. The public default world is now `configs/default_confirmatory.yaml`, while the old contrast-enhancing world is preserved explicitly as `configs/tuned_demo.yaml`.
2. The contamination metric family was corrected so `max_psi_observed` means the true maximum observed `Psi_t`, while `max_positive_excursion` records only positive excursions.
3. Stress worlds were separated from the public default and paired with a calibration/evaluation split.
4. H3 now uses a held-out `fork_stress` world where both deterministic and mixed policies realize actual forks, so post-fork recovery can be estimated rather than inferred indirectly.
5. Scripted runs remain the primary evidence. Gemma runs were executed only as auxiliary backend checks.

## Executed Experiments

### Scripted confirmatory-style runs

Executed commands:

```bash
python scripts/calibrate_stress_worlds.py --output-dir results/v2_confirmatory/calibration
python scripts/run_v2_confirmatory.py --output-dir results/v2_confirmatory --log-dir logs/v2_confirmatory --backend scripted
python scripts/summarize_v2.py --metrics-csv results/v2_confirmatory/metrics.csv --output-md results/v2_confirmatory/summary.md
python scripts/make_v2_figures.py --metrics-csv results/v2_confirmatory/metrics.csv --output-dir results/v2_confirmatory/figures
```

Design:

- calibration seeds: `11, 17, 23`
- held-out evaluation seeds: `101, 103, 107, 109, 113, 127, 131, 137, 139, 149, 151, 157`
- main worlds: `default_confirmatory`, `contamination_stress`, `fork_stress`
- main conditions: `baseline`, `lanes_only`, `lanes_discount`, `full_sec_lite`
- secondary tradeoff sweep: `ablation_depth_discount_none`, `ablation_depth_discount_mild`, `ablation_depth_discount_strong`
- total scripted runs recorded in manifest: `180`

### Auxiliary Gemma backend checks

Executed commands:

```bash
python scripts/run_v2_aux_llm.py --output-dir results/v2_aux_llm --log-dir logs/v2_aux_llm --llm-roles query --seeds 101 103 --steps 24 --imports-per-step 4
python scripts/summarize_v2.py --metrics-csv results/v2_aux_llm/metrics.csv --output-md results/v2_aux_llm/summary.md
```

What was actually run:

- world: `default_confirmatory`
- condition: `full_sec_lite`
- seeds: `101`, `103`
- backends: `ollama/gemma3:1b`, `ollama/gemma3:4b`
- episode length: `24`
- total recorded auxiliary runs: `4`

These outputs are reported only as backend sanity checks.

## Calibration Note

The calibration split was used for discipline, not for result inflation.

The main calibration target was `fork_stress`: deterministic threshold exit had to produce real forks often enough that post-fork recovery was measurable on held-out seeds. The held-out evaluation succeeded on that criterion:

- `lanes_discount` in `fork_stress`: mean realized forks `11.833`, mean post-fork recovery quality `0.268`
- `full_sec_lite` in `fork_stress`: mean realized forks `5.500`, mean post-fork recovery quality `0.368`

This is materially stronger than the earlier v1 situation, where mixed exit often eliminated forks entirely and recovery was therefore not estimable.

## Main Findings

### H1. Provenance-depth discount under contamination stress

Primary comparison: `lanes_only` vs `lanes_discount` in `contamination_stress`

| Metric | `lanes_only` | `lanes_discount` |
| --- | ---: | ---: |
| `mean_psi` | `-0.540` | `-0.643` |
| `max_positive_excursion` | `0.026` | `0.174` |
| `contaminated_items_admitted` | `7.250` | `0.000` |
| `contradiction_reserve` | `0.047` | `0.040` |
| `protected_query_accuracy` | `0.646` | `0.646` |
| `protected_query_recall` | `0.792` | `0.812` |

Interpretation:

- The depth-discount condition reduced admitted contaminated items to zero and improved `mean_psi`.
- It did not improve every contamination metric. In particular, `max_positive_excursion` worsened.
- Reserve remained low in both lane-based stress conditions and was slightly lower under `lanes_discount`.

The tradeoff sweep makes this clearer:

- `mild` discount produced the lowest `mean_psi` and zero positive excursion, but still admitted some contaminated items
- `strong` discount eliminated contaminated admissions, but produced large positive excursions and much worse `max_psi_observed`

v2 reading:

- H1 is best read as a tradeoff frontier rather than a simple monotone improvement.
- Within this PoC, the results support the mechanism claim that provenance scheduling changes purification behavior, but they also reveal reserve/accessibility costs and schedule sensitivity.

### H2. Typed lanes

Primary comparison: `baseline` vs `lanes_only`

`default_confirmatory`:

| Metric | `baseline` | `lanes_only` |
| --- | ---: | ---: |
| `false_core_admission_rate` | `0.006` | `0.017` |
| `contradiction_reserve` | `0.108` | `0.006` |
| `protected_query_accuracy` | `0.729` | `0.688` |
| `protected_query_recall` | `0.833` | `0.792` |

`contamination_stress`:

| Metric | `baseline` | `lanes_only` |
| --- | ---: | ---: |
| `false_core_admission_rate` | `0.012` | `0.027` |
| `contradiction_reserve` | `0.157` | `0.047` |
| `protected_query_accuracy` | `0.521` | `0.646` |
| `protected_query_recall` | `0.875` | `0.792` |

Interpretation:

- Typed lanes alone do not produce a clean confirmatory-style improvement in this v2 implementation.
- In both worlds, `lanes_only` increased false-core admission and reduced contradiction reserve.
- Accuracy improved under `contamination_stress`, but recall worsened and reserve remained lower.

v2 reading:

- The current scripted evidence does not justify a broad H2 success claim for typed lanes in isolation.
- The more defensible takeaway is narrower: lane structure is a mechanism-bearing substrate whose effects depend on the admission and exit rules coupled to it.

### H3. Mixed exit / fork under held-out fork stress

Primary comparison: `lanes_discount` vs `full_sec_lite` in `fork_stress`

| Metric | `lanes_discount` | `full_sec_lite` |
| --- | ---: | ---: |
| `low_reserve_residence_time` | `47.417` | `36.583` |
| `realized_fork_count` | `11.833` | `5.500` |
| `post_fork_recovery_quality` | `0.268` | `0.368` |
| `protected_query_accuracy` | `0.354` | `0.875` |
| `contradiction_reserve` | `0.063` | `0.202` |

Interpretation:

- Mixed exit reduced low-reserve residence time.
- Mixed exit also reduced fork churn rather than merely hiding it; realized forks still occurred often enough for recovery to be measured.
- When forks did occur, post-fork recovery quality was better under `full_sec_lite`.

v2 reading:

- H3 has the strongest support in the current repository.
- This does not prove the full theory, but it does demonstrate a mechanism in a held-out synthetic stress world more cleanly than v1 did.

## Auxiliary Gemma Checks

Auxiliary results are stored in `results/v2_aux_llm/`.

Observed outcome on the executed auxiliary runs:

- both `ollama/gemma3:1b` and `ollama/gemma3:4b` completed the `default_confirmatory` / `full_sec_lite` / seed `101` run
- both achieved protected-query accuracy `1.000` and recall `1.000` on that small auxiliary run
- no forks occurred in that auxiliary setting, so `post_fork_recovery_quality` is `NA`

Interpretation:

- these runs demonstrate that the Ollama backends are wired correctly and can participate in the same replayable framework
- they are not large enough to serve as substantive evidence for H1-H3 or as a meaningful model-comparison benchmark

## Stronger Claims Than v1

The following claims are now stronger than they were in the earlier exploratory version:

- exploratory versus confirmatory-style worlds are explicitly separated
- contamination metric semantics are corrected and reported transparently
- H3 now measures real fork recovery rather than only fork avoidance
- the repository now exposes a real purification-versus-reserve tradeoff instead of presenting H1 as a pure win
- the reporting language is constrained to synthetic-world mechanism claims

## Remaining Limitations

- this remains a synthetic, lightweight simulator with limited external validity
- H1 is not monotone in the current stress world; discount scheduling matters
- H2 is mixed and should not be overclaimed
- the auxiliary Gemma evidence is intentionally thin
- H3 recovery evidence is specific to the held-out `fork_stress` world and should not be generalized outside that regime
- hidden truth is still used for evaluation, which is appropriate for this PoC but not a deployment model
- H4 and several richer theory objects remain out of scope

## Security and Public-Release Audit

A lightweight public-release audit was performed before this report update.

Findings:

- no credential-like strings were found in source, configs, scripts, tests, README, report text, or citation files
- no absolute local filesystem paths were found in those public-facing source and documentation files
- results manifests use relative paths
- the only network endpoint baked into configs is the loopback Ollama URL `http://127.0.0.1:11434`

Audit note:

- this was a lightweight repository hygiene audit, not a formal application-security penetration test
- details are recorded in `SECURITY.md`

## Output Locations

- main report tables: `results/v2_confirmatory/summary.md`
- main metrics: `results/v2_confirmatory/metrics.csv`
- main figures: `results/v2_confirmatory/figures/`
- main manifest: `results/v2_confirmatory/manifest.json`
- calibration diagnostics: `results/v2_confirmatory/calibration/calibration.json`
- auxiliary summary: `results/v2_aux_llm/summary.md`
- auxiliary metrics: `results/v2_aux_llm/metrics.csv`
- auxiliary manifest: `results/v2_aux_llm/manifest.json`

## Bottom Line

v2 is scientifically cleaner than the earlier repository state even though the headline is less flattering.

- H3 is now meaningfully stronger.
- H1 is now more honest because it is reported as a tradeoff analysis.
- H2 is no longer presented as a general win that the current scripted evidence does not actually support.

That is the correct outcome for a GitHub-ready PoC: smaller claims, clearer separation of evidence types, and outputs that are easier to interpret and reproduce.
