# SEC PoC v2

This repository is a lightweight, observable-only simulator for the paper *Sovereign Epistemic Commons under No-Meta Governance* (Takahashi, K., 2026, Zenodo, DOI: `10.5281/zenodo.18997828`).
It is a small, replayable PoC for H1-H3 in synthetic worlds, not a full implementation of the paper.
The v2 update separates exploratory demo worlds from confirmatory-style held-out evaluation and tightens metric/reporting discipline.

## What Changed From v1

- v1 exploratory artifacts are preserved under `results/v1_exploratory/` and `logs/v1_exploratory/`
- v2 uses a new public default world: `configs/default_confirmatory.yaml`
- the old contrast-enhancing world is preserved as `configs/tuned_demo.yaml`
- stress worlds are split into `configs/contamination_stress.yaml` and `configs/fork_stress.yaml`
- contamination metrics now distinguish `max_psi_observed` from `max_positive_excursion`
- H3 now uses a held-out fork-stress world with actual realized forks and estimable post-fork recovery
- scripted runs are the primary evidence; Gemma/Ollama runs are auxiliary backend checks only

## Repository Status

Primary v2 outputs:

- scripted confirmatory-style runs: `results/v2_confirmatory/`
- auxiliary Ollama checks: `results/v2_aux_llm/`
- exploratory v1 history: `results/v1_exploratory/`

Canonical run identity:

- `run_id`: legacy short identifier, not globally unique across worlds
- `run_uid`: canonical unique identifier in patched metrics/manifests, formatted as `{world}__{condition}__{backend}__seed{seed}`

Public entry point:

- `configs/default_confirmatory.yaml`

Exploratory/demo world:

- `configs/tuned_demo.yaml`

## What This PoC Tests

The simulator compares four governance conditions on the same synthetic import stream and the same seed:

- `baseline`: undifferentiated memory, flat provenance weighting, deterministic threshold exit
- `lanes_only`: typed `core` / `het` / `nar` lanes, flat provenance weighting, deterministic threshold exit
- `lanes_discount`: typed lanes, provenance-depth discount, deterministic threshold exit
- `full_sec_lite`: typed lanes, provenance-depth discount, mixed exit plus cooldown

The target paper claims are represented as PoC-level hypotheses:

- `H1`: provenance-depth discount changes contamination dynamics under pressure
- `H2`: typed lanes change contradiction handling and false-core admission
- `H3`: mixed exit/fork changes low-reserve residence and fork/recovery behavior

v2 is intentionally careful about interpretation:

- H1 is treated as a purification-versus-reserve tradeoff question, not a simple win
- H2 is treated as mechanism-sensitive; typed lanes alone do not automatically dominate in this PoC
- H3 is evaluated in a dedicated held-out fork-stress world where recovery is actually measurable

`H4` percolation-stress coupling is not implemented in this repository.

## Theory-Faithful Elements

- observable-only governance with no privileged semantic judge
- hidden truth used only for evaluation, never for agent decisions
- `core`, `het`, and `nar` lane separation
- provenance-sensitive admission pressure
- deterministic replay from fixed seeds and config dumps
- paired comparisons with shared import streams across conditions
- mixed exit versus deterministic threshold exit

## PoC Proxies and Simplifications

- `Psi_t` is an explicit contamination proxy, not the full paper quantity
- contradiction reserve is a bounded-depth proxy over contradictory retained support
- broker capture is approximated through visible concentration and coalition bursts
- schema drift is reduced to a small `old` / `new` normalization mismatch
- promotion/demotion are explicit heuristics rather than theorem-level witness-family rules
- `nar` is operator summary only and is excluded from protected-query grounding

These proxies are documented in code and used consistently in the v2 report.

## World Families

- `default_confirmatory.yaml`: moderate neutral public default; not post hoc tuned to maximize visual contrasts
- `tuned_demo.yaml`: exploratory/demo world retained from v1-style contrast enhancement
- `contamination_stress.yaml`: stronger contamination and correlated-import pressure, used mainly for H1/H2
- `fork_stress.yaml`: calibrated to produce actual low-reserve episodes and realized forks, used mainly for H3

## Calibration and Evaluation Split

v2 uses a lightweight calibration protocol for stress worlds:

- calibration seeds: `11, 17, 23`
- held-out evaluation seeds: `101, 103, 107, 109, 113, 127, 131, 137, 139, 149, 151, 157`

Calibration is diagnostic only. It is used to ensure that `fork_stress` generates enough deterministic-policy forks for H3 to be measurable. Main reporting uses only the held-out evaluation seeds.

## Metric Definitions

These names are the canonical v2 names used in code, CSV outputs, README, and reports.

- `mean_psi`: mean observed `Psi_t` over the run
- `max_psi_observed`: true maximum observed `Psi_t` over the run, including negative values
- `max_positive_excursion`: maximum of `max(Psi_t, 0)` over the run
- `contaminated_items_admitted`: admitted items whose hidden label is contaminated
- `contradiction_reserve`: bounded-depth contradictory support retained in `core` and `het`
- `false_core_admission_rate`: fraction of `core` items that do not match hidden truth
- `protected_query_accuracy`: fraction of protected queries answered correctly from admissible evidence
- `protected_query_recall`: fraction of protected queries for which true support remains retrievable
- `low_reserve_residence_time`: number of steps spent below the reserve floor
- `realized_fork_count`: number of forks actually taken
- `post_fork_recovery_quality`: average of `0.5 * accuracy + 0.5 * reserve` over the next `K` steps after each realized fork; reported as `NA` if no forks occur

Legacy v1-style aliases such as `maximal_contamination_excursion` are retained only for compatibility.

## What Was Actually Executed For v2

Primary scripted evidence:

- calibration diagnostics: `python scripts/calibrate_stress_worlds.py --output-dir results/v2_confirmatory/calibration`
- held-out scripted matrix: `python scripts/run_v2_confirmatory.py --output-dir results/v2_confirmatory --log-dir logs/v2_confirmatory --backend scripted`
- summarization: `python scripts/summarize_v2.py --metrics-csv results/v2_confirmatory/metrics.csv --output-md results/v2_confirmatory/summary.md`
- figures: `python scripts/make_v2_figures.py --metrics-csv results/v2_confirmatory/metrics.csv --output-dir results/v2_confirmatory/figures`

Executed scripted matrix:

- worlds: `default_confirmatory`, `contamination_stress`, `fork_stress`
- conditions: `baseline`, `lanes_only`, `lanes_discount`, `full_sec_lite`
- held-out evaluation seeds: `12`
- total scripted confirmatory/tradeoff runs recorded in manifest: `180`

Auxiliary Ollama checks actually executed:

- `python scripts/run_v2_aux_llm.py --output-dir results/v2_aux_llm --log-dir logs/v2_aux_llm --llm-roles query --seeds 101 103 --steps 24 --imports-per-step 4`
- summarized with `python scripts/summarize_v2.py --metrics-csv results/v2_aux_llm/metrics.csv --output-md results/v2_aux_llm/summary.md`

Current auxiliary artifacts contain:

- world: `default_confirmatory`
- condition: `full_sec_lite`
- models: `ollama/gemma3:1b`, `ollama/gemma3:4b`
- seed count: `2`
- episode length: `24`
- total recorded auxiliary runs: `4`

These are backend sanity checks, not core evidence for H1-H3.

## Main v2 Reading

The current v2 results are intentionally mixed rather than staged as universal wins:

- H1: depth discount reduces admitted contamination and improves `mean_psi` in `contamination_stress`, but can worsen `max_positive_excursion` and compress reserve. The depth-discount sweep reveals a real tradeoff frontier and schedule sensitivity.
- H2: typed lanes alone do not show a clean dominance result in the current confirmatory worlds. This PoC therefore does not treat H2 as established by v2 scripted evidence.
- H3: `fork_stress` now produces actual forks for both deterministic and mixed policies, making post-fork recovery estimable. This is the strongest v2 result.

See `result_summary.md` for the narrative report and `results/v2_confirmatory/summary.md` for the generated tables.

## Claim Status

| Claim | Current support level in this repo | Notes |
| --- | --- | --- |
| `H1` | partial / tradeoff-supported | Within this PoC, depth discount can reduce contamination pressure, but the reserve and excursion effects are schedule-sensitive. |
| `H2` | mixed / conditional | Typed lanes alone are not sufficient in all current synthetic worlds. |
| `H3` | strongest support | Support is concentrated in the held-out `fork_stress` world, where realized forks and recovery are measurable. |
| Gemma backend comparison | auxiliary only | `gemma3:1b` and `gemma3:4b` are lightweight backend sanity checks, not the primary scientific evidence. |

## How to Interpret This PoC

This repository is a small synthetic, observable-only mechanism PoC.
It is not a claim of external validity, not a benchmark of frontier-model intelligence, and not a confirmation of the full paper-level framework.
The results are best read as evidence about governance mechanisms, failure modes, and tradeoffs within this PoC.

## Figures

The v2 figure script generates at least:

- H2: false-core admission, accuracy/recall, contradiction reserve
- H1 tradeoff: `mean_psi`, `max_positive_excursion`, contradiction reserve, accuracy/recall, contamination-versus-reserve
- H3: low-reserve residence, realized fork count, post-fork recovery quality
- structure: lane occupancy ratios

Outputs are written to `results/v2_confirmatory/figures/`.

## Installation

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

## Typical Commands

Single scripted run:

```bash
python scripts/run_single.py --config configs/default_confirmatory.yaml --condition baseline --backend scripted --seed 101
```

Confirmatory batch:

```bash
python scripts/run_v2_confirmatory.py --output-dir results/v2_confirmatory --log-dir logs/v2_confirmatory --backend scripted
```

Calibration diagnostics:

```bash
python scripts/calibrate_stress_worlds.py --output-dir results/v2_confirmatory/calibration
```

Summarize confirmatory runs:

```bash
python scripts/summarize_v2.py --metrics-csv results/v2_confirmatory/metrics.csv --output-md results/v2_confirmatory/summary.md
```

Make v2 figures:

```bash
python scripts/make_v2_figures.py --metrics-csv results/v2_confirmatory/metrics.csv --output-dir results/v2_confirmatory/figures
```

Auxiliary Gemma backend check:

```bash
python scripts/run_v2_aux_llm.py --output-dir results/v2_aux_llm --log-dir logs/v2_aux_llm --llm-roles query --seeds 101 103 --steps 24 --imports-per-step 4
```

Run tests:

```bash
pytest -q
```

## Expected Outputs

- `logs/v2_confirmatory/**/*.jsonl`: event-level replay logs
- `results/v2_confirmatory/metrics.csv`: flattened scripted metrics
- `results/v2_confirmatory/summary.md`: generated metric tables and paired effects
- `results/v2_confirmatory/manifest.json`: run manifest
- `results/v2_confirmatory/figures/*.png`: v2 figures
- `results/v2_aux_llm/metrics.csv`: auxiliary LLM metrics
- `results/v2_aux_llm/summary.md`: auxiliary summary
- `results/v2_aux_llm/manifest.json`: auxiliary manifest

Patched result tables and manifests expose `run_uid` as the canonical globally unique identifier. Existing raw JSONL logs may still contain only the legacy `run_id`.

## Reproducibility Notes

- scripted runs are deterministic for fixed seed, config, and backend
- paired comparisons reuse the same generated import stream across conditions
- config dumps are stored per run for replay
- Ollama runs are deterministic-first and fail closed to scripted fallback on invalid outputs, but local model-serving variability may still remain

## Public Release Hygiene

- no external API keys are required
- results and manifests use relative paths
- loopback Ollama URL is documented as `http://127.0.0.1:11434`
- v1 exploratory outputs are clearly separated from v2 confirmatory-style outputs
- a lightweight release audit is recorded in `SECURITY.md`

## Limitations

- this is still a synthetic mechanism PoC with limited external validity
- H1 behavior is schedule-sensitive and should be read as a tradeoff analysis, not a monotone theorem replica
- H2 remains mixed in the current heuristic realization
- auxiliary Gemma runs are too small to support substantive causal claims or serious model-comparison statements
- H3 recovery evidence is specific to the held-out `fork_stress` regime in this repository
- no privileged oracle judge is used, so evaluation is intentionally constrained
- H4 and several paper-level structures remain out of scope

## Possible v2.1 / v3 Extensions

- percolation-stress coupling
- replica bridge diversity
- richer capture-cost metrics
- stronger contradiction reconstruction windows
